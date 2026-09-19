#!/usr/bin/env python3
"""Extract a deterministic, source-only localization inventory from Unity assets.

This tool deliberately does not translate text.  It reads the read-only Steam
installation selected by the caller, writes source inventory JSON, and can
validate a hand-authored locale overlay without changing the installed game.

UnityPy is intentionally an external extraction dependency.  Keep it outside
the repository (for example in /private/tmp) and pass it through PYTHONPATH.
"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence


SCHEMA_VERSION = 1
GAME_ID = "the-murder-of-sonic-the-hedgehog"
STEAM_APP_ID = "2324650"
STEAM_BUILD_ID = "20535215"
GAME_VERSION = "1.01"
UNITY_VERSION = "2021.3.9f1"

TEXT_BEARING_IMAGE_HINTS = (
    "closeup",
    "blueprint",
    "book",
    "card",
    "cake",
    "concert",
    "egg",
    "lore",
    "map",
    "manual",
    "menu",
    "note",
    "paper",
    "printout",
    "safecode",
    "sign",
    "ticket",
    "whiteboard",
)

TECHNICAL_INK_PREFIXES = (
    ">>>>",
    "VAR?",
    "LIST?",
    "CHOICE?",
    "READ_COUNT",
    "TURNS_SINCE",
    "RANDOM",
    "SEQUENCE",
    "CYCLE",
    "ONCE",
    "STOPPED",
    "END",
)

ESTABLISHING_SHOT_PATTERN = re.compile(
    r"(?P<prefix>\s*>>>>EstablishingShot\()(?P<body>[^()\r\n]+)(?P<suffix>\)\s*)"
)
RUNTIME_SPEAKER_LABELS_ASSET = "runtime/speaker-display-labels"
NON_DISPLAY_SPEAKER_KEYS = {"Barry", "NamelessMC"}

# SaveFileView derives the visible location from GameState.environment and
# then calls SplitCamelCase. Keep those runtime keys untouched and translate
# only the final display string through already-authored UI units. Three
# dining-car environments are special-cased by the game to the same label.
# Reusing existing units avoids changing the canonical 3,547-unit corpus while
# the same runtime mapping remains available to every locale.
SAVE_LOCATION_ENVIRONMENT_UNITS = {
    "Prologue": "managed:1649d41bf047661f",
    "MessyDiningCar": "managed:1649d41bf047661f",
    "LockdownDiningCar": "managed:1649d41bf047661f",
    "Lounge": "unity:level0:1483:m_text",
    "Credits": "unity:level0:1484:m_text",
    "SafeRoom": "unity:level0:1486:m_text",
    "Library": "unity:level0:1489:m_text",
    "DiningCloset": "unity:level0:1492:m_text",
    "Conductor_Car": "unity:level0:1499:m_text",
    "Saloon": "unity:level0:1496:m_text",
    "TestCar": "unity:level0:1497:m_text",
    "Casino": "unity:level0:1498:m_text",
    "Final_Push": "unity:level0:1500:m_text",
}
DINING_CAR_ENVIRONMENTS = {"Prologue", "MessyDiningCar", "LockdownDiningCar"}

INTERNAL_INK_VALUES = {"menu", "vectorticket"}
PLACEHOLDER_TEXT = {"Text", "New Text", "Text goes here", "Text goes here!", "Item description goes here!"}
DISPLAY_TOKENS = {"L", "×", "0", "0/0", "100%", "​"}

CONFIRMED_MANAGED_UI = {
    "AssistModeActiveToggle::UpdateDisplay@IL_000f",
    "AssistModeActiveToggle::UpdateDisplay@IL_001b",
    "SaveFileView::UpdateInfoText@IL_0170",
    "SaveDataManager::OnOpenSaveMenu@IL_0013",
    "SaveDataManager::OnOpenSaveMenu@IL_0023",
    "SaveDataManager::OnOpenLoadMenu@IL_0013",
    "SaveDataManager::OnOpenLoadMenu@IL_0023",
}

PROTECTED_MANAGED_CONTROL_STRINGS = {
    "DialogView::OnDialogReadyToUpdate@IL_0035",
    "DialogView::OnDialogReadyToUpdate@IL_006b",
    "DialogView::OnDialogReadyToUpdate@IL_0098",
}

DEFAULTGROUP_BUNDLE = "defaultgroup_assets_all_4d829fc9da7ab64c374ae5aebaeeafd8.bundle"
INVENTORY_BUNDLE = "inventoryitems_assets_all_99d768e0da67f575e33404b5acc31e43.bundle"
DYNAMIC_FALLBACK_FONT_ASSET = 1226172976683833684
DYNAMIC_FALLBACK_SOURCE_FONT = 2716190411336593533
SHARED_FALLBACK_FONT_ASSET = 573
SHARED_FALLBACK_SOURCE_FONT = 161
SHARED_SCENE_FONT_ASSETS = (561, 569, 570, 571, 574)

LAYOUT_OVERRIDE_FIELDS = {
    "m_fontSize",
    "m_fontSizeBase",
}

# The level0 TMP components use the same serialized layout for these two
# fields, but UnityPy cannot reconstruct their legacy MonoBehaviour type tree.
# Offsets are relative to the padded end of m_text, so changing the localized
# string length does not change which bytes are patched.
LEVEL0_LAYOUT_FIELD_OFFSETS = {
    "m_fontSize": 192,
    "m_fontSizeBase": 196,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_path(parts: Sequence[object]) -> str:
    result = ""
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}" if result else str(part)
    return result


def walk_json(
    value: Any,
    path: tuple[object, ...] = (),
    ancestors: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[object, ...], tuple[str, ...], str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, path + (key,), ancestors + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, path + (index,), ancestors)
    elif isinstance(value, str):
        yield path, ancestors, value


def runtime_string_controls(
    value: Any,
    path: tuple[object, ...] = (),
) -> Iterator[tuple[tuple[object, ...], str, str]]:
    """Find compiled Ink string operands whose bytes affect runtime control flow."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from runtime_string_controls(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if (
                child == "str"
                and index + 3 < len(value)
                and isinstance(value[index + 1], str)
                and value[index + 1].startswith("^")
                and value[index + 2] == "/str"
            ):
                operand = value[index + 1][1:]
                next_value = value[index + 3]
                operation: str | None = None
                if next_value == "==":
                    operation = "comparison"
                elif isinstance(next_value, dict) and ({"VAR=", "temp="} & next_value.keys()):
                    operation = "assignment"
                elif (
                    next_value == "/ev"
                    and index + 4 < len(value)
                    and isinstance(value[index + 4], dict)
                    and ({"VAR=", "temp="} & value[index + 4].keys())
                ):
                    operation = "assignment"
                if operation is not None and operand:
                    yield path + (index + 1,), operand, operation
            yield from runtime_string_controls(child, path + (index,))


def build_runtime_exact_manifest(
    inventory: dict[str, Any],
    story: dict[str, Any],
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in inventory["units"]}
    controls: list[dict[str, Any]] = []
    for path, operand, operation in runtime_string_controls(story):
        source_path = json_path(path)
        identifier = f"ink:{source_path}"
        row = by_id.get(identifier)
        if row is None or row.get("body") != operand:
            raise ValueError(f"Runtime operand does not match inventory: {identifier}")
        controls.append(
            {
                "id": identifier,
                "sourcePath": source_path,
                "value": operand,
                "operation": operation,
                "overlayRequired": bool(row.get("translatable")),
            }
        )

    prefixes: list[dict[str, str]] = []
    for row in inventory["units"]:
        if row.get("sourceAsset") != "sharedassets0.assets::story":
            continue
        original = row.get("original")
        body = row.get("body")
        if (
            not isinstance(original, str)
            or not isinstance(body, str)
            or original != "^" + body
            or "::" not in body
        ):
            continue
        prefix = body.split("::", 1)[0] + "::"
        following = body[len(prefix) :]
        if following.startswith(" "):
            prefix += " "
        prefixes.append(
            {
                "id": row["id"],
                "sourcePath": row["sourcePath"],
                "prefix": prefix,
            }
        )

    return {
        "schemaVersion": 1,
        "kind": "runtime-preserve-exactly",
        "game": GAME_ID,
        "sourceFingerprint": inventory["source"]["fingerprint"],
        "sourceStorySha256": inventory["story"]["storySha256"],
        "controls": controls,
        "inlinePrefixes": prefixes,
        "notes": (
            "Compatibility manifest for runtime-sensitive strings that remain in the "
            "stable translation corpus. Values and prefixes are byte-exact requirements."
        ),
    }


def runtime_exact_errors(
    inventory: dict[str, Any],
    artifact: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if manifest.get("sourceFingerprint") != inventory["source"]["fingerprint"]:
        errors.append({"id": "manifest", "error": "source fingerprint mismatch"})
    if manifest.get("sourceStorySha256") != inventory["story"]["storySha256"]:
        errors.append({"id": "manifest", "error": "source story hash mismatch"})
    units = artifact.get("units", {})
    if not isinstance(units, dict):
        return errors + [{"id": "artifact", "error": "units must be an object"}]
    for row in manifest.get("controls", []):
        if not row.get("overlayRequired"):
            continue
        identifier = row["id"]
        actual = units.get(identifier)
        if actual != row["value"]:
            errors.append(
                {
                    "id": identifier,
                    "error": "runtime control value changed",
                    "expected": row["value"],
                    "actual": actual if isinstance(actual, str) else repr(actual),
                }
            )
    for row in manifest.get("inlinePrefixes", []):
        identifier = row["id"]
        actual = units.get(identifier)
        if not isinstance(actual, str) or not actual.startswith(row["prefix"]):
            errors.append(
                {
                    "id": identifier,
                    "error": "runtime inline prefix changed",
                    "expected": row["prefix"],
                    "actual": actual if isinstance(actual, str) else repr(actual),
                }
            )
    return errors


def load_runtime_exact_manifest(inventory_path: Path) -> dict[str, Any]:
    path = inventory_path.with_name("runtime-exact-values.json")
    if not path.is_file():
        raise SystemExit(f"Runtime exact manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_unity_text_asset(raw: bytes) -> tuple[str, bytes] | None:
    """Read the byte layout used by Unity TextAsset without a type tree."""
    if len(raw) < 8:
        return None
    name_length = struct.unpack_from("<I", raw, 0)[0]
    name_end = 4 + name_length
    if name_end > len(raw):
        return None
    position = (name_end + 3) & ~3
    if position + 4 > len(raw):
        return None
    text_length = struct.unpack_from("<I", raw, position)[0]
    text_start = position + 4
    text_end = text_start + text_length
    if text_end > len(raw):
        return None
    try:
        name = raw[4:name_end].decode("utf-8")
    except UnicodeDecodeError:
        name = raw[4:name_end].decode("utf-8", errors="replace")
    return name, raw[text_start:text_end]


def encode_unity_text_asset(name: str, payload: bytes) -> bytes:
    name_bytes = name.encode("utf-8")
    prefix = struct.pack("<I", len(name_bytes)) + name_bytes
    prefix += b"\0" * ((-len(prefix)) % 4)
    suffix = struct.pack("<I", len(payload)) + payload
    suffix += b"\0" * ((-len(suffix)) % 4)
    return prefix + suffix


def load_unitypy() -> Any:
    try:
        import UnityPy  # type: ignore
    except ImportError as error:
        raise SystemExit(
            "UnityPy is required for extraction. Install it outside the repository "
            "and rerun with PYTHONPATH pointing at that environment."
        ) from error
    return UnityPy


def object_type_name(obj: Any) -> str:
    return getattr(getattr(obj, "type", None), "name", "Unknown")


def object_location(obj: Any) -> str:
    assets_file = getattr(obj, "assets_file", None)
    assets_name = getattr(assets_file, "name", None) or "serialized-file"
    return f"{assets_name}#{getattr(obj, 'path_id', 'unknown')}"


def ink_scene(ancestors: Sequence[str]) -> str:
    return ancestors[1] if len(ancestors) > 1 else "ungrouped"


def is_internal_ink_value(value: str, ancestors: Sequence[str]) -> bool:
    return value.strip() in INTERNAL_INK_VALUES and "Give_Vector_Item" in ancestors


def text_status(value: str) -> tuple[bool, str, str]:
    stripped = value.strip()
    if not stripped or stripped in DISPLAY_TOKENS:
        return False, "display-token", "not-applicable"
    if stripped in PLACEHOLDER_TEXT:
        return True, "placeholder-needs-runtime-confirmation", "needs-review"
    return True, "typed-field", "untranslated"


def read_story(data_root: Path, UnityPy: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    source = data_root / "sharedassets0.assets"
    environment = UnityPy.load(str(source))
    story_bytes: bytes | None = None
    story_name = "story"
    story_object_path = ""
    for obj in environment.objects:
        if object_type_name(obj) != "TextAsset":
            continue
        parsed = parse_unity_text_asset(obj.get_raw_data())
        if parsed is None:
            continue
        name, payload = parsed
        if name == "story":
            story_name = name
            story_bytes = payload
            story_object_path = object_location(obj)
            break
    if story_bytes is None:
        raise RuntimeError(f"TextAsset 'story' was not found in {source}")

    story_text = story_bytes.decode("utf-8-sig")
    story = json.loads(story_text)
    units: list[dict[str, Any]] = []
    technical = 0
    visible = 0
    for path, ancestors, value in walk_json(story):
        if not value.startswith("^") or len(value) == 1:
            continue
        raw_body = value[1:]
        trimmed = raw_body.strip()
        speaker: str | None = None
        body = raw_body
        text_prefix: str | None = None
        text_suffix: str | None = None
        establishing_shot = ESTABLISHING_SHOT_PATTERN.fullmatch(raw_body)
        if establishing_shot is not None:
            body = establishing_shot.group("body")
            text_prefix = "^" + establishing_shot.group("prefix")
            text_suffix = establishing_shot.group("suffix")
        if "::" in raw_body:
            possible_speaker, possible_body = raw_body.split("::", 1)
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9' _-]*", possible_speaker.strip()):
                speaker = possible_speaker.strip()
                body = possible_body
        is_technical = (
            not trimmed
            or (
                establishing_shot is None
                and any(trimmed.startswith(prefix) for prefix in TECHNICAL_INK_PREFIXES)
            )
            or is_internal_ink_value(trimmed, ancestors)
            or "global decl" in ancestors
            or (speaker is not None and not body.strip())
        )
        is_choice = any("choice" in ancestor.lower() for ancestor in ancestors) or raw_body.startswith("!")
        if not is_technical:
            visible += 1
        else:
            technical += 1
        unit = {
            "id": f"ink:{json_path(path)}",
            "sourceAsset": "sharedassets0.assets::story",
            "sourcePath": json_path(path),
            "ancestors": list(ancestors),
            "scene": ink_scene(ancestors),
            "kind": (
                "location-display-label"
                if establishing_shot is not None
                else ("choice" if is_choice else ("dialogue" if speaker else "narration"))
            ),
            "speaker": speaker,
            "original": value,
            "body": body,
            "translatable": not is_technical,
            "translation": None,
            "technicalStatus": (
                "protected-command-shell"
                if establishing_shot is not None
                else "preserve-exactly"
            ),
            "editorialStatus": "untranslated" if not is_technical else "not-applicable",
        }
        if text_prefix is not None and text_suffix is not None:
            unit["textPrefix"] = text_prefix
            unit["textSuffix"] = text_suffix
        units.append(unit)

    metadata = {
        "asset": "sharedassets0.assets",
        "textAsset": story_name,
        "object": story_object_path,
        "utf8Bytes": len(story_bytes),
        "textCharacters": len(story_text),
        "sourceSha256": sha256_bytes(story_bytes),
        "storySha256": sha256_bytes(story_text.encode("utf-8")),
        "inkVersion": story.get("inkVersion"),
        "listDefinitions": sorted(story.get("listDefs", {}).keys()),
        "unitCount": len(units),
        "visibleUnitCount": visible,
        "technicalUnitCount": technical,
    }
    return metadata, {"schemaVersion": SCHEMA_VERSION, "metadata": metadata, "units": units, "story": story}


def speaker_display_label_units(story_units: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    speaker_keys = sorted(
        {
            row["speaker"]
            for row in story_units
            if isinstance(row.get("speaker"), str)
            and row["speaker"] not in NON_DISPLAY_SPEAKER_KEYS
        }
    )
    return [
        {
            "id": f"runtime:speaker:{speaker}",
            "sourceAsset": RUNTIME_SPEAKER_LABELS_ASSET,
            "sourcePath": f"DialogView::nameTagText[{speaker}]",
            "kind": "speaker-display-label",
            "speaker": None,
            "runtimeKey": speaker,
            "original": speaker,
            "body": speaker,
            "translatable": True,
            "translation": None,
            "technicalStatus": "display-only-key-preserved",
            "editorialStatus": "untranslated",
        }
        for speaker in speaker_keys
    ]


def walk_tree(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from walk_tree(child, child_prefix)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_tree(child, f"{prefix}[{index}]")
    else:
        yield prefix, value


def game_object_hierarchy(game_object: Any) -> str | None:
    names: list[str] = []
    current = game_object
    seen: set[int] = set()
    while current is not None:
        path_id = getattr(getattr(current, "object_reader", None), "path_id", None)
        if isinstance(path_id, int):
            if path_id in seen:
                break
            seen.add(path_id)
        name = getattr(current, "m_Name", None)
        if isinstance(name, str) and name:
            names.append(name)
        parent = None
        for component in getattr(current, "m_Component", []):
            pointer = getattr(component, "component", None)
            try:
                candidate = pointer.read()
            except Exception:
                continue
            father = getattr(candidate, "m_Father", None)
            if father is None or not getattr(father, "m_PathID", 0):
                continue
            try:
                parent_transform = father.read()
                parent = parent_transform.m_GameObject.read()
            except Exception:
                parent = None
            break
        current = parent
    return "/".join(reversed(names)) if names else None


def object_hierarchy(obj: Any) -> str | None:
    try:
        value = obj.read()
        pointer = getattr(value, "m_GameObject", None)
        if pointer is None or not getattr(pointer, "m_PathID", 0):
            return None
        return game_object_hierarchy(pointer.read())
    except Exception:
        return None


def raw_game_object_hierarchy(obj: Any, objects_by_path_id: dict[int, Any]) -> str | None:
    raw = obj.get_raw_data()
    if len(raw) < 12:
        return None
    file_id = struct.unpack_from("<i", raw, 0)[0]
    path_id = struct.unpack_from("<q", raw, 4)[0]
    if file_id != 0 or path_id not in objects_by_path_id:
        return None
    try:
        return game_object_hierarchy(objects_by_path_id[path_id].read())
    except Exception:
        return None


def extract_inventory_items(data_root: Path, UnityPy: Any) -> list[dict[str, Any]]:
    bundles = sorted((data_root / "StreamingAssets" / "aa" / "StandaloneOSX").glob("inventoryitems_assets_all_*.bundle"))
    if not bundles:
        return []
    environment = UnityPy.load(str(bundles[0]))
    rows: list[dict[str, Any]] = []
    for obj in sorted(environment.objects, key=lambda item: getattr(item, "path_id", 0)):
        if object_type_name(obj) != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or tree.get("m_Script") is None:
            continue
        name = tree.get("Name")
        description = tree.get("Description")
        if not isinstance(name, str) or not isinstance(description, str):
            continue
        item_key = str(tree.get("m_Name") or name).strip().lower().replace(" ", "-")
        for field, value in (("Name", name), ("Description", description)):
            rows.append(
                {
                    "id": f"inventory:{item_key}:{field}",
                    "sourceAsset": bundles[0].name,
                    "sourcePath": object_location(obj),
                    "kind": "inventory-name" if field == "Name" else "inventory-description",
                    "field": field,
                    "context": str(tree.get("m_Name") or item_key),
                    "original": value,
                    "translation": None,
                    "translatable": True,
                    "technicalStatus": "typed-field",
                    "editorialStatus": "untranslated",
                }
            )
    return rows


def extract_defaultgroup_text(data_root: Path, UnityPy: Any) -> list[dict[str, Any]]:
    bundles = sorted((data_root / "StreamingAssets" / "aa" / "StandaloneOSX").glob("defaultgroup_assets_all_*.bundle"))
    if not bundles:
        return []
    environment = UnityPy.load(str(bundles[0]))
    rows: list[dict[str, Any]] = []
    seen: Counter[str] = Counter()
    for obj in sorted(environment.objects, key=lambda item: getattr(item, "path_id", 0)):
        if object_type_name(obj) != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict):
            continue
        for field_path, value in walk_tree(tree):
            if field_path != "m_text" and not field_path.endswith(".m_text"):
                continue
            if not isinstance(value, str):
                continue
            text = value
            translatable, technical_status, editorial_status = text_status(text)
            seen[text] += 1
            rows.append(
                {
                    "id": f"unity:defaultgroup:{getattr(obj, 'path_id', 'unknown')}:{field_path}",
                    "sourceAsset": bundles[0].name,
                    "sourcePath": object_location(obj),
                    "kind": "unity-ui-text",
                    "field": field_path,
                    "context": object_hierarchy(obj),
                    "original": text,
                    "translation": None,
                    "translatable": translatable,
                    "occurrences": 0,
                    "technicalStatus": technical_status,
                    "editorialStatus": editorial_status,
                }
            )
    for row in rows:
        row["occurrences"] = seen[row["original"]]
    return rows


def extract_level0_text(data_root: Path, UnityPy: Any) -> list[dict[str, Any]]:
    source = data_root / "level0"
    environment = UnityPy.load(str(source))
    objects_by_path_id = {getattr(obj, "path_id", 0): obj for obj in environment.objects}
    rows: list[dict[str, Any]] = []
    seen: Counter[str] = Counter()
    for obj in sorted(environment.objects, key=lambda item: getattr(item, "path_id", 0)):
        if object_type_name(obj) != "MonoBehaviour":
            continue
        serialized_type = getattr(obj, "serialized_type", None)
        if getattr(serialized_type, "script_type_index", None) != 60:
            continue
        raw = obj.get_raw_data()
        # The script's serialized string begins with a fixed 88-byte prefix,
        # followed by Unity's little-endian string length and UTF-8 bytes.
        # UnityPy cannot reconstruct this older scene type tree, so keep this
        # narrow raw-field reader instead of guessing from arbitrary strings.
        if len(raw) < 92:
            continue
        length = struct.unpack_from("<I", raw, 88)[0]
        start = 92
        end = start + length
        if end > len(raw):
            continue
        try:
            text = raw[start:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
        translatable, technical_status, editorial_status = text_status(text)
        seen[text] += 1
        rows.append(
            {
                "id": f"unity:level0:{getattr(obj, 'path_id', 'unknown')}:m_text",
                "sourceAsset": "level0",
                "sourcePath": object_location(obj),
                "kind": "scene-ui-text",
                "field": "m_text",
                "context": raw_game_object_hierarchy(obj, objects_by_path_id),
                "original": text,
                "translation": None,
                "translatable": translatable,
                "occurrences": 0,
                "technicalStatus": "raw-" + technical_status,
                "editorialStatus": editorial_status,
            }
        )
    for row in rows:
        row["occurrences"] = seen[row["original"]]
    return rows


def extracted_image_path(bundle: Path, source_path: str) -> Path:
    relative = PurePosixPath(source_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe image path: {source_path}")
    return Path(bundle.stem).joinpath(*relative.parts)


def extract_image_candidates(
    data_root: Path,
    UnityPy: Any,
    export_root: Path | None = None,
) -> list[dict[str, Any]]:
    bundle_dir = data_root / "StreamingAssets" / "aa" / "StandaloneOSX"
    rows: list[dict[str, Any]] = []
    for bundle in sorted(bundle_dir.glob("*.bundle")):
        try:
            environment = UnityPy.load(str(bundle))
            entries = list(environment.container.items())
            paths = sorted(
                {
                    str(path)
                    for path, obj in entries
                    if object_type_name(obj) in {"Texture2D", "Sprite"}
                    if any(hint in str(path).lower() for hint in TEXT_BEARING_IMAGE_HINTS)
                }
            )
        except Exception as error:
            rows.append(
                {
                    "id": f"bundle:{bundle.name}",
                    "sourceAsset": bundle.name,
                    "kind": "bundle",
                    "original": None,
                    "translation": None,
                    "translatable": False,
                    "technicalStatus": "container-read-failed",
                    "editorialStatus": "not-applicable",
                    "error": str(error),
                }
            )
            continue
        for path in paths:
            matches = [obj for entry_path, obj in entries if str(entry_path) == path]
            chosen = next((obj for obj in matches if object_type_name(obj) == "Texture2D"), None)
            if chosen is None:
                chosen = next((obj for obj in matches if object_type_name(obj) == "Sprite"), None)
            row: dict[str, Any] = {
                "id": f"image:{bundle.name}:{path}",
                "sourceAsset": bundle.name,
                "sourcePath": path,
                "sourceObject": object_location(chosen) if chosen is not None else None,
                "sourceObjectType": object_type_name(chosen) if chosen is not None else None,
                "kind": "text-bearing-image-candidate",
                "original": path.rsplit("/", 1)[-1],
                "translation": None,
                "translatable": False,
                "technicalStatus": "needs-visual-review",
                "editorialStatus": "needs-review",
            }
            if export_root is not None and chosen is not None:
                try:
                    image = chosen.read().image
                    relative_output = extracted_image_path(bundle, path)
                    output_path = export_root / relative_output
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path, format="PNG")
                    row.update(
                        {
                            "extractedPath": relative_output.as_posix(),
                            "width": image.width,
                            "height": image.height,
                            "mode": image.mode,
                            "pngSha256": sha256_file(output_path),
                        }
                    )
                except Exception as error:
                    row["technicalStatus"] = "image-export-failed"
                    row["error"] = str(error)
            rows.append(row)
    return rows


def extract_font_inventory(data_root: Path, UnityPy: Any) -> list[dict[str, Any]]:
    candidates = [data_root / "sharedassets0.assets", data_root / "resources.assets"]
    candidates.extend(sorted((data_root / "StreamingAssets" / "aa" / "StandaloneOSX").glob("*.bundle")))
    rows: list[dict[str, Any]] = []
    for source in candidates:
        if not source.exists():
            continue
        try:
            environment = UnityPy.load(str(source))
        except Exception:
            continue
        for obj in sorted(environment.objects, key=lambda item: getattr(item, "path_id", 0)):
            if object_type_name(obj) not in {"Font", "MonoBehaviour"}:
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if not isinstance(tree, dict):
                continue
            flattened = list(walk_tree(tree))
            sequence = next(
                (value for field, value in flattened if "charactersequence" in field.lower() and isinstance(value, str)),
                None,
            )
            names = {str(value) for _, value in flattened if isinstance(value, str)}
            has_font_signal = object_type_name(obj) == "Font" or sequence is not None or any(
                isinstance(value, str)
                and (" SDF" in value or value.endswith(" Font") or value.endswith("Font"))
                for _, value in flattened
            )
            if not has_font_signal:
                continue
            rows.append(
                {
                    "id": f"font:{source.name}:{getattr(obj, 'path_id', 'unknown')}",
                    "sourceAsset": source.name,
                    "sourcePath": object_location(obj),
                    "kind": "font-or-font-asset",
                    "nameHints": sorted(names)[:20],
                    "characterSequence": sequence,
                    "translation": None,
                    "translatable": False,
                    "technicalStatus": "coverage-needs-check",
                    "editorialStatus": "not-applicable",
                }
            )
    return rows


def asset_manifest(data_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in data_root.rglob("*") if item.is_file()):
        relative = path.relative_to(data_root).as_posix()
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decode_monodis_string(value: str) -> str:
    try:
        decoded = ast.literal_eval('"' + value + '"')
        return decoded if isinstance(decoded, str) else value
    except (SyntaxError, ValueError):
        return value.replace(r'\"', '"').replace(r"\\", "\\")


def extract_managed_string_candidates(data_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    assembly = data_root / "Managed" / "Assembly-CSharp.dll"
    executable = shutil.which("monodis")
    if executable is None:
        return [], {"name": "monodis", "status": "not-found"}
    completed = subprocess.run(
        [executable, str(assembly)],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if completed.returncode != 0:
        return [], {
            "name": "monodis",
            "status": "failed",
            "exitCode": completed.returncode,
            "error": completed.stderr.strip()[:500],
        }
    rows: list[dict[str, Any]] = []
    pending: list[tuple[str, str]] = []
    ldstr_pattern = re.compile(r'^\s*(IL_[0-9A-Fa-f]+):\s+ldstr "(.*)"\s*$')
    method_end_pattern = re.compile(r"^\s*}\s+// end of method (.+)::(.+)$")
    for line in completed.stdout.splitlines():
        match = ldstr_pattern.match(line)
        if match:
            pending.append((match.group(1), decode_monodis_string(match.group(2))))
            continue
        match = method_end_pattern.match(line)
        if not match:
            continue
        owner = f"{match.group(1)}::{match.group(2)}"
        for il_offset, value in pending:
            if not value or len(value) > 1024:
                continue
            source_path = f"{owner}@{il_offset}"
            confirmed_ui = source_path in CONFIRMED_MANAGED_UI
            protected_control = source_path in PROTECTED_MANAGED_CONTROL_STRINGS
            identifier_hash = sha256_bytes(f"{owner}\0{il_offset}\0{value}".encode("utf-8"))[:16]
            rows.append(
                {
                    "id": f"managed:{identifier_hash}",
                    "sourceAsset": "Managed/Assembly-CSharp.dll",
                    "sourcePath": source_path,
                    "method": owner,
                    "ilOffset": il_offset,
                    "kind": (
                        "managed-ui-text"
                        if confirmed_ui
                        else ("managed-runtime-control" if protected_control else "managed-string-candidate")
                    ),
                    "original": value,
                    "translation": None,
                    "translatable": confirmed_ui,
                    "technicalStatus": (
                        "confirmed-runtime-ui"
                        if confirmed_ui
                        else ("runtime-control-identifier" if protected_control else "needs-code-usage-review")
                    ),
                    "editorialStatus": (
                        "untranslated"
                        if confirmed_ui
                        else ("not-applicable" if protected_control else "needs-review")
                    ),
                }
            )
        pending = []
    version = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    version_line = next((line for line in (version.stdout + version.stderr).splitlines() if line.strip()), "unknown")
    return rows, {"name": "monodis", "status": "passed", "version": version_line}


def source_group(row: dict[str, Any]) -> str:
    if row.get("sourceAsset") == "sharedassets0.assets::story":
        return f"story/{row.get('scene') or 'ungrouped'}"
    if row.get("kind", "").startswith("inventory-"):
        return "inventory"
    if row.get("kind") == "scene-ui-text":
        return "ui/scene"
    if row.get("kind") == "unity-ui-text":
        return "ui/addressables"
    if row.get("kind") == "managed-ui-text":
        return "ui/managed"
    if row.get("kind") == "speaker-display-label":
        return "ui/speaker-names"
    return "misc"


def group_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "ungrouped"


def translation_source_row(row: dict[str, Any]) -> dict[str, Any]:
    source_text = row.get("body", row["original"]).strip()
    note = None
    if row.get("speaker"):
        note = "Translate dialogue body only; the speaker key is runtime control data."
    elif row.get("kind") == "speaker-display-label":
        note = "Translate the displayed name only; runtimeKey remains unchanged."
    elif row.get("kind") == "location-display-label":
        note = "Translate the displayed location only; the EstablishingShot command shell remains unchanged."
    elif row.get("kind") == "unity-ui-text" and "CreditsPositionName" in source_text:
        note = "Translate credit role labels; preserve personal names and rich-text tags."
    elif row.get("kind") == "managed-ui-text":
        note = "Confirmed runtime UI string in Assembly-CSharp.dll; reinsertion requires the managed-code patch stage."
    return {
        "id": row["id"],
        "group": source_group(row),
        "kind": row["kind"],
        "speaker": row.get("speaker"),
        "context": row.get("context") or row.get("method") or " > ".join(row.get("ancestors", [])),
        "sourceAsset": row["sourceAsset"],
        "sourcePath": row["sourcePath"],
        "sourceText": source_text,
        "protectedTokens": protected_tokens(source_text),
        "note": note,
        "translation": None,
    }


def write_translation_source(output: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    source_root = output / "Source" / "en"
    batches_root = source_root / "batches"
    if batches_root.exists():
        shutil.rmtree(batches_root)
    rows = [translation_source_row(row) for row in inventory["units"] if row.get("translatable")]
    source_units_sha256 = sha256_bytes(compact_json(rows).encode("utf-8"))
    package = {
        "schemaVersion": SCHEMA_VERSION,
        "game": inventory["game"],
        "sourceLocale": "en",
        "sourceFingerprint": inventory["source"]["fingerprint"],
        "sourceUnitsSha256": source_units_sha256,
        "unitCount": len(rows),
        "units": rows,
    }
    write_json(source_root / "source.en.json", package)

    source_root.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "id", "group", "kind", "speaker", "context", "sourceAsset",
        "sourcePath", "sourceText", "protectedTokens", "note", "translation",
    ]
    with (source_root / "source.en.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["protectedTokens"] = json.dumps(row["protectedTokens"], ensure_ascii=False)
            writer.writerow(csv_row)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["group"], []).append(row)
    for group, group_rows in sorted(grouped.items()):
        write_json(
            batches_root / f"{group_slug(group)}.json",
            {
                "schemaVersion": SCHEMA_VERSION,
                "game": GAME_ID,
                "sourceLocale": "en",
                "sourceFingerprint": inventory["source"]["fingerprint"],
                "sourceUnitsSha256": source_units_sha256,
                "group": group,
                "unitCount": len(group_rows),
                "units": group_rows,
            },
        )

    write_json(
        source_root / "translation-template.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "game": GAME_ID,
            "sourceLocale": "en",
            "targetLocale": None,
            "translationFormat": "story-body-or-static-field",
            "sourceFingerprint": inventory["source"]["fingerprint"],
            "sourceUnitsSha256": source_units_sha256,
            "units": {row["id"]: None for row in rows},
            "notes": "Set targetLocale and hand-author translations directly from source.en.json or the scene batches.",
        },
    )
    return {
        "sourceUnitsSha256": source_units_sha256,
        "unitCount": len(rows),
        "batchCount": len(grouped),
    }


def extract(args: argparse.Namespace) -> int:
    data_root = args.data_root.expanduser().resolve()
    output = args.output.resolve()
    required = [data_root / "level0", data_root / "sharedassets0.assets"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required game data: " + ", ".join(missing))

    UnityPy = load_unitypy()
    story_metadata, story_inventory = read_story(data_root, UnityPy)
    inventory_items = extract_inventory_items(data_root, UnityPy)
    defaultgroup_text = extract_defaultgroup_text(data_root, UnityPy)
    level0_text = extract_level0_text(data_root, UnityPy)
    image_staging = output / ".images.en.tmp"
    if image_staging.exists():
        shutil.rmtree(image_staging)
    image_candidates = extract_image_candidates(data_root, UnityPy, image_staging)
    final_images = output / "Source" / "en" / "images"
    if final_images.exists():
        shutil.rmtree(final_images)
    final_images.parent.mkdir(parents=True, exist_ok=True)
    image_staging.replace(final_images)
    fonts = extract_font_inventory(data_root, UnityPy)
    managed_strings, managed_tool = extract_managed_string_candidates(data_root)
    confirmed_managed_strings = [row for row in managed_strings if row.get("translatable")]
    speaker_labels = speaker_display_label_units(story_inventory["units"])

    source_manifest = asset_manifest(data_root)
    source_fingerprint = sha256_bytes(compact_json(source_manifest).encode("utf-8"))
    translatable = [
        *story_inventory["units"],
        *inventory_items,
        *defaultgroup_text,
        *level0_text,
        *confirmed_managed_strings,
        *speaker_labels,
    ]
    inventory = {
        "schemaVersion": SCHEMA_VERSION,
        "game": {
            "id": GAME_ID,
            "steamAppID": STEAM_APP_ID,
            "steamBuildID": STEAM_BUILD_ID,
            "version": GAME_VERSION,
            "unityVersion": UNITY_VERSION,
        },
        "source": {
            "dataRoot": str(data_root),
            "fingerprint": source_fingerprint,
            "assets": source_manifest,
        },
        "story": story_metadata,
        "counts": {
            "translatableUnits": sum(1 for row in translatable if row["translatable"]),
            "inkUnits": len(story_inventory["units"]),
            "inkVisibleUnits": story_metadata["visibleUnitCount"],
            "inventoryUnits": len(inventory_items),
            "defaultgroupUnits": len(defaultgroup_text),
            "level0Units": len(level0_text),
            "imageCandidates": len(image_candidates),
            "fontAssets": len(fonts),
            "managedStringCandidates": len(managed_strings),
            "managedConfirmedUnits": len(confirmed_managed_strings),
            "speakerDisplayLabels": len(speaker_labels),
        },
        "units": translatable,
        "images": image_candidates,
        "fonts": fonts,
        "managedStrings": managed_strings,
    }
    write_json(output / "inventory.json", inventory)
    write_json(output / "story.en.json", story_inventory["story"])
    write_json(
        output / "runtime-exact-values.json",
        build_runtime_exact_manifest(inventory, story_inventory["story"]),
    )
    translation_source = write_translation_source(output, inventory)
    write_json(
        output / "extraction-report.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "game": inventory["game"],
            "sourceFingerprint": source_fingerprint,
            "sourceManifestSha256": sha256_bytes(compact_json(source_manifest).encode("utf-8")),
            "counts": inventory["counts"],
            "story": story_metadata,
            "translationSource": translation_source,
            "tool": {
                "name": "Scripts/extract-localization-assets.py",
                "python": sys.version.split()[0],
                "unitypy": getattr(UnityPy, "__version__", "unknown"),
                "managedStrings": managed_tool,
            },
        },
    )
    print(json.dumps({"output": str(output), "counts": inventory["counts"]}, ensure_ascii=False, indent=2))
    return 0


def html_tags(value: str) -> list[str]:
    return re.findall(
        r"</?(?:style|size|color|align|font|link|mark|sprite|br)(?:=[^>]+)?>",
        value,
        flags=re.IGNORECASE,
    )


def protected_tokens(value: str) -> list[str]:
    tokens = html_tags(value)
    tokens.extend(re.findall(r"\\[nrt\\]|%\d*\$?[sdif]|\{[^{}]+\}|\b\d+(?:\.\d+)?\b", value))
    return sorted(tokens)


def validate_layout_overrides(
    inventory: dict[str, Any],
    overlay: dict[str, Any],
) -> list[str]:
    units = {row["id"]: row for row in inventory["units"]}
    overrides = overlay.get("layoutOverrides", {})
    if not isinstance(overrides, dict):
        return ["layoutOverrides must be an object"]
    errors: list[str] = []
    for identifier, fields in overrides.items():
        row = units.get(identifier)
        if row is None:
            errors.append(f"unknown layout override ID: {identifier}")
            continue
        if row.get("sourceAsset") not in {DEFAULTGROUP_BUNDLE, "level0"}:
            errors.append(f"layout override is not a supported TMP label: {identifier}")
        if not isinstance(fields, dict) or not fields:
            errors.append(f"layout override must contain fields: {identifier}")
            continue
        unknown_fields = sorted(set(fields) - LAYOUT_OVERRIDE_FIELDS)
        if unknown_fields:
            errors.append(
                f"unsupported layout fields for {identifier}: " + ", ".join(unknown_fields)
            )
        for field, value in fields.items():
            if field not in LAYOUT_OVERRIDE_FIELDS:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= 200:
                errors.append(f"invalid {field} for {identifier}: {value!r}")
    return errors


def validate(args: argparse.Namespace) -> int:
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    overlay = json.loads(args.overlay.read_text(encoding="utf-8"))
    runtime_exact = load_runtime_exact_manifest(args.inventory)
    inventory_units = {row["id"]: row for row in inventory["units"] if row.get("translatable")}
    translations = overlay.get("units", {})
    missing = sorted(identifier for identifier in inventory_units if not isinstance(translations.get(identifier), str) or not translations[identifier].strip())
    extra = sorted(identifier for identifier in translations if identifier not in inventory_units)
    token_errors: list[dict[str, Any]] = []
    for identifier, translation in translations.items():
        source = inventory_units.get(identifier)
        if source is None or not isinstance(translation, str):
            continue
        expected = protected_tokens(source.get("body", source["original"]))
        actual = protected_tokens(translation)
        if expected != actual:
            token_errors.append({"id": identifier, "expected": expected, "actual": actual})
    layout_errors = validate_layout_overrides(inventory, overlay)
    runtime_exact_failures = runtime_exact_errors(inventory, overlay, runtime_exact)
    needs_review = [
        row["id"]
        for row in inventory["units"]
        if row.get("translatable") and row.get("editorialStatus") == "needs-review"
    ]
    result = {
        "inventoryUnits": len(inventory_units),
        "translatedUnits": sum(1 for identifier in inventory_units if isinstance(translations.get(identifier), str) and translations[identifier].strip()),
        "missing": missing,
        "extra": extra,
        "tokenErrors": token_errors,
        "layoutErrors": layout_errors,
        "runtimeExactErrors": runtime_exact_failures,
        "needsReview": needs_review,
        "ok": (
            (not missing or args.allow_incomplete)
            and not extra
            and not token_errors
            and not layout_errors
            and not runtime_exact_failures
            and (not needs_review or args.allow_incomplete)
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def parse_json_path(value: str) -> list[str | int]:
    parts: list[str | int] = []
    for match in re.finditer(r"([^\.\[\]]+)|\[(\d+)\]", value):
        if match.group(2) is not None:
            parts.append(int(match.group(2)))
        else:
            parts.append(match.group(1))
    if not parts:
        raise ValueError(f"Invalid JSON path: {value}")
    return parts


def preserve_edge_whitespace(source: str, replacement: str) -> str:
    leading = source[: len(source) - len(source.lstrip())]
    trailing = source[len(source.rstrip()) :]
    return leading + replacement.strip() + trailing


def localized_story_value(row: dict[str, Any], translation: str) -> str:
    body_source = row.get("body", row["original"])
    body = preserve_edge_whitespace(body_source, translation)
    if "textPrefix" in row or "textSuffix" in row:
        prefix = row.get("textPrefix", "")
        suffix = row.get("textSuffix", "")
        if row["original"] != prefix + body_source + suffix:
            raise SystemExit(f"Protected runtime shell mismatch for {row['id']}")
        return prefix + body + suffix
    prefix_length = len(row["original"]) - len(body_source)
    return row["original"][:prefix_length] + body


def apply_story(args: argparse.Namespace) -> int:
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    overlay = json.loads(args.overlay.read_text(encoding="utf-8"))
    runtime_exact_failures = runtime_exact_errors(
        inventory,
        overlay,
        load_runtime_exact_manifest(args.inventory),
    )
    if runtime_exact_failures:
        raise SystemExit(
            "Runtime exact validation failed: "
            + "; ".join(f"{row['id']}: {row['error']}" for row in runtime_exact_failures[:10])
        )
    story = json.loads(args.story.read_text(encoding="utf-8"))
    source_units = {
        row["id"]: row
        for row in inventory["units"]
        if row.get("translatable") and row.get("sourceAsset") == "sharedassets0.assets::story"
    }
    translations = overlay.get("units", {})
    changed = 0
    missing_paths: list[str] = []
    for identifier, translation in translations.items():
        row = source_units.get(identifier)
        if row is None or not isinstance(translation, str) or not translation.strip():
            continue
        parts = parse_json_path(row["sourcePath"])
        cursor: Any = story
        try:
            for part in parts[:-1]:
                cursor = cursor[part]
            current = cursor[parts[-1]]
        except (KeyError, IndexError, TypeError):
            missing_paths.append(identifier)
            continue
        if current != row["original"]:
            raise SystemExit(f"Source mismatch for {identifier}: story JSON was not extracted from this inventory")
        cursor[parts[-1]] = localized_story_value(row, translation)
        changed += 1
    if missing_paths:
        raise SystemExit("Missing story paths: " + ", ".join(missing_paths[:10]))
    write_json(args.output, story)
    print(json.dumps({"output": str(args.output), "changed": changed}, ensure_ascii=False, indent=2))
    return 0


def compile_overlay(args: argparse.Namespace) -> int:
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    manual = json.loads(args.manual.read_text(encoding="utf-8"))
    target_locale = manual.get("targetLocale")
    if not isinstance(target_locale, str) or not target_locale.strip() or target_locale == "en":
        raise SystemExit("Manual translation must declare a non-English targetLocale")
    expected_fingerprint = inventory["source"]["fingerprint"]
    if manual.get("sourceFingerprint") != expected_fingerprint:
        raise SystemExit(
            "Manual translation fingerprint does not match inventory: "
            f"{manual.get('sourceFingerprint')} != {expected_fingerprint}"
        )
    all_units = {row["id"]: row for row in inventory["units"]}
    source_units = [row for row in inventory["units"] if row.get("translatable")]
    authored = manual.get("units", {})
    unknown = sorted(identifier for identifier in authored if identifier not in all_units)
    if unknown:
        raise SystemExit("Manual translation contains unknown IDs: " + ", ".join(unknown[:10]))
    invalid_preserved = []
    for identifier, value in authored.items():
        row = all_units[identifier]
        if row.get("translatable") or not isinstance(value, str) or not value.strip():
            continue
        original = row.get("body", row["original"])
        if value.strip() != original.strip():
            invalid_preserved.append(identifier)
    if invalid_preserved:
        raise SystemExit(
            "Manual translation changes non-translatable display tokens: "
            + ", ".join(invalid_preserved[:10])
        )
    layout_errors = validate_layout_overrides(inventory, manual)
    if layout_errors:
        raise SystemExit("Invalid layout overrides: " + "; ".join(layout_errors[:10]))
    runtime_exact_failures = runtime_exact_errors(
        inventory,
        manual,
        load_runtime_exact_manifest(args.inventory),
    )
    if runtime_exact_failures:
        raise SystemExit(
            "Runtime exact validation failed: "
            + "; ".join(f"{row['id']}: {row['error']}" for row in runtime_exact_failures[:10])
        )
    values = {row["id"]: authored.get(row["id"]) for row in source_units}
    overlay = {
        "schemaVersion": manual.get("schemaVersion", SCHEMA_VERSION),
        "game": GAME_ID,
        "sourceLocale": "en",
        "targetLocale": target_locale,
        "translationFormat": manual.get("translationFormat", "story-body-or-static-field"),
        "sourceFingerprint": expected_fingerprint,
        "sourceStorySha256": inventory["story"]["storySha256"],
        "units": values,
        "layoutOverrides": manual.get("layoutOverrides", {}),
        "notes": "Generated from a hand-authored locale file; wording is never generated by this script.",
    }
    write_json(args.output, overlay)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "inventoryUnits": len(values),
                "translatedUnits": sum(1 for value in values.values() if isinstance(value, str) and value.strip()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_sharedassets(args: argparse.Namespace) -> int:
    UnityPy = load_unitypy()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    overlay = json.loads(args.overlay.read_text(encoding="utf-8"))
    if overlay.get("sourceFingerprint") != inventory["source"]["fingerprint"]:
        raise SystemExit("Overlay and inventory fingerprints do not match")
    runtime_exact_failures = runtime_exact_errors(
        inventory,
        overlay,
        load_runtime_exact_manifest(args.inventory),
    )
    if runtime_exact_failures:
        raise SystemExit(
            "Runtime exact validation failed: "
            + "; ".join(f"{row['id']}: {row['error']}" for row in runtime_exact_failures[:10])
        )
    source_path = args.source.resolve()
    environment = UnityPy.load(str(source_path))
    source_units = {
        row["id"]: row
        for row in inventory["units"]
        if row.get("translatable") and row.get("sourceAsset") == "sharedassets0.assets::story"
    }
    translations = overlay.get("units", {})
    changed = 0
    for obj in environment.objects:
        if object_type_name(obj) != "TextAsset":
            continue
        parsed = parse_unity_text_asset(obj.get_raw_data())
        if parsed is None or parsed[0] != "story":
            continue
        _, payload = parsed
        story = json.loads(payload.decode("utf-8-sig"))
        for identifier, translation in translations.items():
            row = source_units.get(identifier)
            if row is None or not isinstance(translation, str) or not translation.strip():
                continue
            parts = parse_json_path(row["sourcePath"])
            cursor: Any = story
            for part in parts[:-1]:
                cursor = cursor[part]
            current = cursor[parts[-1]]
            if current != row["original"]:
                raise SystemExit(f"Source mismatch for {identifier}")
            cursor[parts[-1]] = localized_story_value(row, translation)
            changed += 1
        localized_payload = json.dumps(story, ensure_ascii=False, separators=(",", ":")).encode("utf-8-sig")
        obj.set_raw_data(encode_unity_text_asset("story", localized_payload))
        break
    else:
        raise SystemExit("TextAsset 'story' was not found")
    args.output.mkdir(parents=True, exist_ok=True)
    environment.save(out_path=str(args.output))
    print(json.dumps({"output": str(args.output), "changedStoryUnits": changed}, ensure_ascii=False, indent=2))
    return 0


def expected_source_hashes(inventory: dict[str, Any]) -> dict[str, str]:
    return {row["path"]: row["sha256"] for row in inventory["source"]["assets"]}


def verify_original_file(data_root: Path, relative_path: str, hashes: dict[str, str]) -> Path:
    source = data_root / PurePosixPath(relative_path)
    expected = hashes.get(relative_path)
    if expected is None:
        raise SystemExit(f"Inventory has no source hash for {relative_path}")
    if not source.is_file():
        raise SystemExit(f"Original file is missing: {source}")
    actual = sha256_file(source)
    if actual != expected:
        raise SystemExit(f"Original hash mismatch for {relative_path}: {actual} != {expected}")
    return source


def save_unity_environment(environment: Any, output_file: Path, pack: str = "none") -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    environment.save(pack=pack, out_path=str(output_file.parent))
    if not output_file.is_file():
        raise SystemExit(f"UnityPy did not produce {output_file}")


def translated_rows(
    inventory: dict[str, Any],
    overlay: dict[str, Any],
    source_asset: str,
) -> list[tuple[dict[str, Any], str]]:
    translations = overlay.get("units", {})
    rows: list[tuple[dict[str, Any], str]] = []
    for row in inventory["units"]:
        if not row.get("translatable") or row.get("sourceAsset") != source_asset:
            continue
        value = translations.get(row["id"])
        if isinstance(value, str) and value.strip():
            rows.append((row, preserve_edge_whitespace(row.get("body", row["original"]), value)))
    return rows


def save_location_display_labels(
    inventory: dict[str, Any],
    overlay: dict[str, Any],
) -> list[tuple[str, str]]:
    inventory_by_id = {row["id"]: row for row in inventory["units"]}
    translations = overlay.get("units", {})
    labels: dict[str, str] = {}
    for environment, identifier in SAVE_LOCATION_ENVIRONMENT_UNITS.items():
        row = inventory_by_id.get(identifier)
        if row is None or not row.get("translatable"):
            raise SystemExit(f"Save-location display unit is missing or protected: {identifier}")
        translation = translations.get(identifier)
        if not isinstance(translation, str) or not translation.strip():
            raise SystemExit(f"Save-location display translation is missing: {identifier}")
        if environment in DINING_CAR_ENVIRONMENTS:
            runtime_display = "Dining Car"
        else:
            runtime_display = re.sub(r"([A-Z])", r" \1", environment).strip()
            runtime_display = runtime_display.replace("_", " ").strip()
        localized = translation.strip()
        previous = labels.get(runtime_display)
        if previous is not None and previous != localized:
            raise SystemExit(f"Conflicting save-location translations for {runtime_display!r}")
        labels[runtime_display] = localized
    return list(labels.items())


def patch_story_asset(
    UnityPy: Any,
    source: Path,
    output: Path,
    rows: list[tuple[dict[str, Any], str]],
    font_template_source: Path,
) -> tuple[int, int]:
    environment = UnityPy.load(str(source))
    template_environment = UnityPy.load(str(font_template_source))
    template_object = next(
        (obj for obj in template_environment.objects if getattr(obj, "path_id", 0) == -3204990983181140799),
        None,
    )
    if template_object is None:
        raise SystemExit("TMP font type template was not found in the default group bundle")
    font_nodes = template_object.serialized_type.node
    shared_objects = {getattr(obj, "path_id", 0): obj for obj in environment.objects}
    fallback_pointer = {"m_FileID": 0, "m_PathID": SHARED_FALLBACK_FONT_ASSET}
    patched_fonts = 0
    for path_id in (SHARED_FALLBACK_FONT_ASSET, *SHARED_SCENE_FONT_ASSETS):
        font_object = shared_objects.get(path_id)
        if font_object is None:
            raise SystemExit(f"Shared TMP font asset was not found: {path_id}")
        tree = font_object.read_typetree(nodes=font_nodes)
        if path_id == SHARED_FALLBACK_FONT_ASSET:
            tree["m_AtlasPopulationMode"] = 1
            tree["m_SourceFontFile"] = {"m_FileID": 0, "m_PathID": SHARED_FALLBACK_SOURCE_FONT}
            if "m_IsMultiAtlasTexturesEnabled" in tree:
                tree["m_IsMultiAtlasTexturesEnabled"] = 1
        else:
            fallbacks = tree.get("m_FallbackFontAssetTable")
            if not isinstance(fallbacks, list):
                fallbacks = []
                tree["m_FallbackFontAssetTable"] = fallbacks
            if not any(item.get("m_PathID") == SHARED_FALLBACK_FONT_ASSET for item in fallbacks):
                fallbacks.append(dict(fallback_pointer))
        font_object.save_typetree(tree, nodes=font_nodes)
        patched_fonts += 1

    changed = 0
    for obj in environment.objects:
        if object_type_name(obj) != "TextAsset":
            continue
        parsed = parse_unity_text_asset(obj.get_raw_data())
        if parsed is None or parsed[0] != "story":
            continue
        _, payload = parsed
        story = json.loads(payload.decode("utf-8-sig"))
        for row, translation in rows:
            parts = parse_json_path(row["sourcePath"])
            cursor: Any = story
            for part in parts[:-1]:
                cursor = cursor[part]
            current = cursor[parts[-1]]
            if current != row["original"]:
                raise SystemExit(f"Source mismatch for {row['id']}")
            cursor[parts[-1]] = localized_story_value(row, translation)
            changed += 1
        localized = json.dumps(story, ensure_ascii=False, separators=(",", ":")).encode("utf-8-sig")
        obj.set_raw_data(encode_unity_text_asset("story", localized))
        save_unity_environment(environment, output)
        return changed, patched_fonts
    raise SystemExit("TextAsset 'story' was not found")


def replace_level0_text(raw: bytes, source: str, translation: str, identifier: str) -> bytes:
    if len(raw) < 92:
        raise SystemExit(f"Serialized component is too short for {identifier}")
    old_length = struct.unpack_from("<I", raw, 88)[0]
    old_start = 92
    old_end = old_start + old_length
    old_padded_end = (old_end + 3) & ~3
    if old_padded_end > len(raw):
        raise SystemExit(f"Serialized text is truncated for {identifier}")
    try:
        current = raw[old_start:old_end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise SystemExit(f"Serialized text is not UTF-8 for {identifier}: {error}")
    if current != source:
        raise SystemExit(f"Source mismatch for {identifier}: {current!r} != {source!r}")
    encoded = translation.encode("utf-8")
    padding = b"\0" * ((4 - (len(encoded) % 4)) % 4)
    return raw[:88] + struct.pack("<I", len(encoded)) + encoded + padding + raw[old_padded_end:]


def replace_level0_layout(
    raw: bytes,
    fields: dict[str, float],
    identifier: str,
) -> bytes:
    if not fields:
        return raw
    if len(raw) < 92:
        raise SystemExit(f"Serialized component is too short for {identifier}")
    text_length = struct.unpack_from("<I", raw, 88)[0]
    text_padded_end = (92 + text_length + 3) & ~3
    patched = bytearray(raw)
    for field, value in fields.items():
        relative_offset = LEVEL0_LAYOUT_FIELD_OFFSETS.get(field)
        if relative_offset is None:
            raise SystemExit(f"Unsupported level0 layout field {field} for {identifier}")
        offset = text_padded_end + relative_offset
        if offset + 4 > len(patched):
            raise SystemExit(f"Serialized layout field {field} is truncated for {identifier}")
        current = struct.unpack_from("<f", patched, offset)[0]
        if not 1 <= current <= 200:
            raise SystemExit(
                f"Unexpected serialized {field} value for {identifier}: {current!r}"
            )
        struct.pack_into("<f", patched, offset, float(value))
    return bytes(patched)


def patch_level0(
    UnityPy: Any,
    source: Path,
    output: Path,
    rows: list[tuple[dict[str, Any], str]],
    layout_overrides: dict[str, dict[str, float]],
) -> int:
    environment = UnityPy.load(str(source))
    objects = {getattr(obj, "path_id", 0): obj for obj in environment.objects}
    for row, translation in rows:
        path_id = int(row["id"].split(":", 3)[2])
        obj = objects.get(path_id)
        if obj is None:
            raise SystemExit(f"Object was not found for {row['id']}")
        localized = preserve_edge_whitespace(row["original"], translation)
        raw = replace_level0_text(obj.get_raw_data(), row["original"], localized, row["id"])
        raw = replace_level0_layout(raw, layout_overrides.get(row["id"], {}), row["id"])
        obj.set_raw_data(raw)
    translated_ids = {row["id"] for row, _ in rows}
    missing = sorted(set(layout_overrides) - translated_ids)
    if missing:
        raise SystemExit("level0 layout override has no translated row: " + ", ".join(missing))
    save_unity_environment(environment, output)
    return len(rows)


def patch_defaultgroup_bundle(
    UnityPy: Any,
    source: Path,
    output: Path,
    rows: list[tuple[dict[str, Any], str]],
    layout_overrides: dict[str, dict[str, float]],
) -> tuple[int, int]:
    environment = UnityPy.load(str(source))
    objects = {getattr(obj, "path_id", 0): obj for obj in environment.objects}
    translated_by_id = {row["id"]: (row, translation) for row, translation in rows}
    identifiers = list(translated_by_id)
    identifiers.extend(identifier for identifier in layout_overrides if identifier not in translated_by_id)
    for identifier in identifiers:
        row_and_translation = translated_by_id.get(identifier)
        path_id = int(identifier.split(":", 3)[2])
        obj = objects.get(path_id)
        if obj is None:
            raise SystemExit(f"Addressables text object was not found for {identifier}")
        tree = obj.read_typetree()
        if row_and_translation is not None:
            row, translation = row_and_translation
            if tree.get("m_text") != row["original"]:
                raise SystemExit(f"Source mismatch for {row['id']}")
            tree["m_text"] = preserve_edge_whitespace(row["original"], translation)
        for field, value in layout_overrides.get(identifier, {}).items():
            if field not in tree:
                raise SystemExit(f"Layout field {field} was not found for {identifier}")
            tree[field] = float(value)
        obj.save_typetree(tree)

    fallback_pointer = {"m_FileID": 0, "m_PathID": DYNAMIC_FALLBACK_FONT_ASSET}
    font_assets = 0
    for obj in environment.objects:
        if object_type_name(obj) != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or "m_CharacterTable" not in tree or "m_AtlasPopulationMode" not in tree:
            continue
        font_assets += 1
        if getattr(obj, "path_id", 0) == DYNAMIC_FALLBACK_FONT_ASSET:
            tree["m_AtlasPopulationMode"] = 1
            tree["m_SourceFontFile"] = {"m_FileID": 0, "m_PathID": DYNAMIC_FALLBACK_SOURCE_FONT}
            if "m_IsMultiAtlasTexturesEnabled" in tree:
                tree["m_IsMultiAtlasTexturesEnabled"] = 1
        else:
            fallbacks = tree.get("m_FallbackFontAssetTable")
            if not isinstance(fallbacks, list):
                fallbacks = []
                tree["m_FallbackFontAssetTable"] = fallbacks
            if not any(item.get("m_PathID") == DYNAMIC_FALLBACK_FONT_ASSET for item in fallbacks):
                fallbacks.append(dict(fallback_pointer))
        obj.save_typetree(tree)
    if font_assets == 0:
        raise SystemExit("No TMP font assets were found in the default group bundle")
    save_unity_environment(environment, output, pack="lz4")
    return len(rows), font_assets


def patch_inventory_bundle(
    UnityPy: Any,
    source: Path,
    output: Path,
    rows: list[tuple[dict[str, Any], str]],
) -> int:
    environment = UnityPy.load(str(source))
    objects = {getattr(obj, "path_id", 0): obj for obj in environment.objects}
    grouped: dict[int, list[tuple[dict[str, Any], str]]] = {}
    for row, translation in rows:
        path_id = int(row["sourcePath"].rsplit("#", 1)[1])
        grouped.setdefault(path_id, []).append((row, translation))
    for path_id, patches in grouped.items():
        obj = objects.get(path_id)
        if obj is None:
            raise SystemExit(f"Inventory object was not found: {path_id}")
        tree = obj.read_typetree()
        for row, translation in patches:
            field = row["field"]
            if tree.get(field) != row["original"]:
                raise SystemExit(f"Source mismatch for {row['id']}")
            tree[field] = preserve_edge_whitespace(row["original"], translation)
        obj.save_typetree(tree)
    save_unity_environment(environment, output, pack="lz4")
    return len(rows)


def locate_cecil() -> Path:
    candidates = sorted(Path("/opt/homebrew/Cellar/mono").glob("*/lib/mono/gac/Mono.Cecil/0.11.*/Mono.Cecil.dll"))
    if not candidates:
        raise SystemExit("Mono.Cecil 0.11 was not found")
    return candidates[-1]


def patch_managed_assembly(
    source: Path,
    output: Path,
    rows: list[tuple[dict[str, Any], str]],
    speaker_labels: list[tuple[dict[str, Any], str]],
    save_location_labels: list[tuple[str, str]],
) -> tuple[int, int, int]:
    compiler = shutil.which("mcs")
    runtime = shutil.which("mono")
    if compiler is None or runtime is None:
        raise SystemExit("Mono mcs/mono is required to patch managed UI strings")
    output.parent.mkdir(parents=True, exist_ok=True)
    helper_source = Path(__file__).with_name("PatchManagedStrings.cs")
    helper = output.parent / "PatchManagedStrings.exe"
    patch_file = output.parent / "managed-string-patches.tsv"
    labels_file = output.parent / "speaker-display-labels.tsv"
    save_locations_file = output.parent / "save-location-display-labels.tsv"
    lines = []
    source_pattern = re.compile(r"^(?P<type>.+)::(?P<method>.+)@IL_(?P<offset>[0-9A-Fa-f]+)$")
    for row, translation in rows:
        match = source_pattern.match(row["sourcePath"])
        if match is None:
            raise SystemExit(f"Malformed managed source path: {row['sourcePath']}")
        localized = preserve_edge_whitespace(row["original"], translation)
        encoded_source = base64.b64encode(row["original"].encode("utf-8")).decode("ascii")
        encoded_translation = base64.b64encode(localized.encode("utf-8")).decode("ascii")
        lines.append(
            "\t".join(
                (match.group("type"), match.group("method"), match.group("offset"), encoded_source, encoded_translation)
            )
        )
    patch_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    label_lines = []
    for row, translation in speaker_labels:
        runtime_key = row.get("runtimeKey")
        if not isinstance(runtime_key, str) or not runtime_key:
            raise SystemExit(f"Speaker display label has no runtimeKey: {row['id']}")
        label_lines.append(
            "\t".join(
                (
                    base64.b64encode(runtime_key.encode("utf-8")).decode("ascii"),
                    base64.b64encode(translation.strip().encode("utf-8")).decode("ascii"),
                )
            )
        )
    labels_file.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
    save_location_lines = [
        "\t".join(
            (
                base64.b64encode(runtime_display.encode("utf-8")).decode("ascii"),
                base64.b64encode(translation.encode("utf-8")).decode("ascii"),
            )
        )
        for runtime_display, translation in save_location_labels
    ]
    save_locations_file.write_text("\n".join(save_location_lines) + "\n", encoding="utf-8")
    compile_result = subprocess.run(
        [compiler, "-nologo", f"-r:{locate_cecil()}", f"-out:{helper}", str(helper_source)],
        check=False,
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        raise SystemExit("Managed patch helper compilation failed: " + compile_result.stderr.strip())
    patch_result = subprocess.run(
        [
            runtime,
            str(helper),
            str(source),
            str(output),
            str(patch_file),
            str(labels_file),
            str(save_locations_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if patch_result.returncode != 0:
        raise SystemExit("Managed string patch failed: " + patch_result.stderr.strip())
    helper.unlink(missing_ok=True)
    patch_file.unlink(missing_ok=True)
    labels_file.unlink(missing_ok=True)
    save_locations_file.unlink(missing_ok=True)
    return len(rows), len(speaker_labels), len(save_location_labels)


def decode_7bit_integer(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if position >= len(data) or shift >= 35:
            raise SystemExit("Malformed Addressables catalog string length")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            return value, position
        shift += 7


def skip_catalog_string(data: bytes, position: int) -> int:
    length, position = decode_7bit_integer(data, position)
    end = position + length
    if end > len(data):
        raise SystemExit("Malformed Addressables catalog string")
    return end


def patch_addressables_catalog(source: Path, output: Path, bundle_sizes: dict[str, int]) -> int:
    catalog = json.loads(source.read_text(encoding="utf-8"))
    raw = base64.b64decode(catalog["m_ExtraDataString"])
    position = 0
    records: list[bytes] = []
    changed = 0
    while position < len(raw):
        record_start = position
        position += 1  # Serialized object type tag.
        position = skip_catalog_string(raw, position)
        position = skip_catalog_string(raw, position)
        prefix = raw[record_start:position]
        if position + 4 > len(raw):
            raise SystemExit("Malformed Addressables extra-data record")
        payload_length = struct.unpack_from("<I", raw, position)[0]
        position += 4
        payload_end = position + payload_length
        if payload_end > len(raw):
            raise SystemExit("Truncated Addressables extra-data record")
        payload_text = raw[position:payload_end].decode("utf-16le")
        position = payload_end
        options = json.loads(payload_text)
        content_hash = options.get("m_Hash")
        for bundle_name, size in bundle_sizes.items():
            name_hash = bundle_name.rsplit("_", 1)[-1].removesuffix(".bundle")
            if content_hash != name_hash:
                continue
            options["m_Crc"] = 0
            options["m_BundleSize"] = size
            changed += 1
        encoded = json.dumps(options, ensure_ascii=False, separators=(",", ":")).encode("utf-16le")
        if len(encoded) > payload_length or (payload_length - len(encoded)) % 2:
            raise SystemExit("Addressables record cannot preserve its original byte length")
        encoded += " ".encode("utf-16le") * ((payload_length - len(encoded)) // 2)
        records.append(prefix + struct.pack("<I", payload_length) + encoded)
    if changed != len(bundle_sizes):
        raise SystemExit(f"Addressables catalog updated {changed} bundle records; expected {len(bundle_sizes)}")
    catalog["m_ExtraDataString"] = base64.b64encode(b"".join(records)).decode("ascii")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return changed


def build_development_patch(args: argparse.Namespace) -> int:
    UnityPy = load_unitypy()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    overlay = json.loads(args.overlay.read_text(encoding="utf-8"))
    if overlay.get("sourceFingerprint") != inventory["source"]["fingerprint"]:
        raise SystemExit("Overlay and inventory fingerprints do not match")
    runtime_exact_failures = runtime_exact_errors(
        inventory,
        overlay,
        load_runtime_exact_manifest(args.inventory),
    )
    if runtime_exact_failures:
        raise SystemExit(
            "Runtime exact validation failed: "
            + "; ".join(f"{row['id']}: {row['error']}" for row in runtime_exact_failures[:10])
        )
    if overlay.get("targetLocale") != "ru":
        raise SystemExit("This development patch command is restricted to the reviewed Russian overlay")
    output_root = args.output.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"Development patch output must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    data_root = args.data_root.resolve()
    hashes = expected_source_hashes(inventory)
    relative_paths = {
        "story": "sharedassets0.assets",
        "level0": "level0",
        "defaultgroup": f"StreamingAssets/aa/StandaloneOSX/{DEFAULTGROUP_BUNDLE}",
        "inventory": f"StreamingAssets/aa/StandaloneOSX/{INVENTORY_BUNDLE}",
        "managed": "Managed/Assembly-CSharp.dll",
        "catalog": "StreamingAssets/aa/catalog.json",
    }
    sources = {key: verify_original_file(data_root, value, hashes) for key, value in relative_paths.items()}
    outputs = {key: output_root / PurePosixPath(value) for key, value in relative_paths.items()}

    counts: dict[str, int] = {}
    counts["story"], counts["sharedFontAssets"] = patch_story_asset(
        UnityPy,
        sources["story"],
        outputs["story"],
        translated_rows(inventory, overlay, "sharedassets0.assets::story"),
        sources["defaultgroup"],
    )
    counts["level0"] = patch_level0(
        UnityPy,
        sources["level0"],
        outputs["level0"],
        translated_rows(inventory, overlay, "level0"),
        {
            identifier: fields
            for identifier, fields in overlay.get("layoutOverrides", {}).items()
            if identifier.startswith("unity:level0:")
        },
    )
    counts["defaultgroup"], counts["fontAssets"] = patch_defaultgroup_bundle(
        UnityPy,
        sources["defaultgroup"],
        outputs["defaultgroup"],
        translated_rows(inventory, overlay, DEFAULTGROUP_BUNDLE),
        {
            identifier: fields
            for identifier, fields in overlay.get("layoutOverrides", {}).items()
            if identifier.startswith("unity:defaultgroup:")
        },
    )
    counts["layoutOverrides"] = len(overlay.get("layoutOverrides", {}))
    counts["inventory"] = patch_inventory_bundle(
        UnityPy,
        sources["inventory"],
        outputs["inventory"],
        translated_rows(inventory, overlay, INVENTORY_BUNDLE),
    )
    (
        counts["managed"],
        counts["speakerDisplayLabels"],
        counts["saveLocationDisplayLabels"],
    ) = patch_managed_assembly(
        sources["managed"],
        outputs["managed"],
        translated_rows(inventory, overlay, "Managed/Assembly-CSharp.dll"),
        translated_rows(inventory, overlay, RUNTIME_SPEAKER_LABELS_ASSET),
        save_location_display_labels(inventory, overlay),
    )
    counts["catalogRecords"] = patch_addressables_catalog(
        sources["catalog"],
        outputs["catalog"],
        {
            DEFAULTGROUP_BUNDLE: outputs["defaultgroup"].stat().st_size,
            INVENTORY_BUNDLE: outputs["inventory"].stat().st_size,
        },
    )

    source_units = [row for row in inventory["units"] if row.get("translatable")]
    missing = [
        row["id"]
        for row in source_units
        if not isinstance(overlay.get("units", {}).get(row["id"]), str)
        or not overlay["units"][row["id"]].strip()
    ]
    files = []
    for key, relative_path in relative_paths.items():
        files.append(
            {
                "path": relative_path,
                "originalSha256": sha256_file(sources[key]),
                "patchedSha256": sha256_file(outputs[key]),
                "patchedBytes": outputs[key].stat().st_size,
            }
        )
    manifest = {
        "schemaVersion": 1,
        "kind": "russian-development-runtime-patch",
        "game": GAME_ID,
        "steamAppId": STEAM_APP_ID,
        "steamBuildId": STEAM_BUILD_ID,
        "gameVersion": GAME_VERSION,
        "sourceFingerprint": inventory["source"]["fingerprint"],
        "targetLocale": "ru",
        "developmentOnly": True,
        "imagesModified": False,
        "counts": counts,
        "missingTranslationIds": missing,
        "files": files,
        "fontStrategy": {
            "kind": "dynamic-tmp-fallback",
            "font": "Liberation Sans",
            "sceneSourceFontPathId": SHARED_FALLBACK_SOURCE_FONT,
            "sceneFallbackFontAssetPathId": SHARED_FALLBACK_FONT_ASSET,
            "addressablesSourceFontPathId": DYNAMIC_FALLBACK_SOURCE_FONT,
            "addressablesFallbackFontAssetPathId": DYNAMIC_FALLBACK_FONT_ASSET,
        },
    }
    write_json(output_root / "development-patch-manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def validate_source(args: argparse.Namespace) -> int:
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    runtime_exact = load_runtime_exact_manifest(args.inventory)
    story_path = args.inventory.with_name("story.en.json")
    source_root = args.source_root.resolve()
    source = json.loads((source_root / "source.en.json").read_text(encoding="utf-8"))
    expected_rows = [translation_source_row(row) for row in inventory["units"] if row.get("translatable")]
    expected_ids = [row["id"] for row in expected_rows]
    expected_sha256 = sha256_bytes(compact_json(expected_rows).encode("utf-8"))
    errors: list[str] = []
    if not story_path.is_file():
        errors.append(f"source story is missing: {story_path}")
    else:
        story = json.loads(story_path.read_text(encoding="utf-8"))
        if runtime_exact != build_runtime_exact_manifest(inventory, story):
            errors.append("runtime exact manifest does not match source story and inventory")
    if source.get("sourceFingerprint") != inventory["source"]["fingerprint"]:
        errors.append("source fingerprint does not match inventory")
    if source.get("sourceUnitsSha256") != expected_sha256:
        errors.append("source unit fingerprint does not match inventory")
    if source.get("units") != expected_rows:
        errors.append("source.en.json units do not match inventory")

    batch_ids: list[str] = []
    batch_files = sorted((source_root / "batches").glob("*.json"))
    for path in batch_files:
        batch = json.loads(path.read_text(encoding="utf-8"))
        if batch.get("sourceUnitsSha256") != expected_sha256:
            errors.append(f"batch fingerprint mismatch: {path.name}")
        batch_ids.extend(row.get("id") for row in batch.get("units", []))
    if sorted(batch_ids) != sorted(expected_ids) or len(batch_ids) != len(set(batch_ids)):
        errors.append("batch IDs are incomplete or duplicated")

    with (source_root / "source.en.csv").open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    if [row.get("id") for row in csv_rows] != expected_ids:
        errors.append("CSV IDs do not match source JSON")
    for csv_row, expected in zip(csv_rows, expected_rows):
        if csv_row.get("sourceText") != expected["sourceText"]:
            errors.append(f"CSV source text mismatch: {expected['id']}")
            break

    image_errors: list[str] = []
    extracted_images = 0
    for row in inventory.get("images", []):
        relative = row.get("extractedPath")
        if not relative:
            image_errors.append(f"image was not exported: {row['id']}")
            continue
        path = source_root / "images" / relative
        if not path.is_file():
            image_errors.append(f"missing image: {relative}")
            continue
        extracted_images += 1
        if sha256_file(path) != row.get("pngSha256"):
            image_errors.append(f"image checksum mismatch: {relative}")
    errors.extend(image_errors)
    image_review_summary: dict[str, Any] | None = None
    if args.image_review is not None:
        review = json.loads(args.image_review.read_text(encoding="utf-8"))
        candidate_ids = [row["id"] for row in inventory.get("images", [])]
        candidate_paths = {row["sourcePath"] for row in inventory.get("images", [])}
        expected_candidate_sha256 = sha256_bytes(compact_json(candidate_ids).encode("utf-8"))
        text_paths = [row.get("sourcePath") for row in review.get("textBearing", [])]
        preserve_paths = review.get("preserveExactSymbols", [])
        reviewed_count = review.get("reviewedCandidates")
        counts = review.get("classificationCounts", {})
        classified_count = sum(
            counts.get(key, 0)
            for key in ("textBearing", "preserveExactSymbols", "noLanguageText")
            if isinstance(counts.get(key, 0), int)
        )
        if review.get("sourceFingerprint") != inventory["source"]["fingerprint"]:
            errors.append("image review source fingerprint does not match inventory")
        if review.get("candidateSetSha256") != expected_candidate_sha256:
            errors.append("image review candidate fingerprint does not match inventory")
        if review.get("reviewStatus") != "complete":
            errors.append("image review is not marked complete")
        if reviewed_count != len(candidate_ids) or classified_count != len(candidate_ids):
            errors.append("image review classification count does not cover every candidate")
        if counts.get("textBearing") != len(text_paths):
            errors.append("image review text-bearing count does not match its list")
        if counts.get("preserveExactSymbols") != len(preserve_paths):
            errors.append("image review preserve-exact count does not match its list")
        unknown_paths = sorted((set(text_paths) | set(preserve_paths)) - candidate_paths)
        if unknown_paths:
            errors.append("image review contains unknown source paths: " + ", ".join(unknown_paths[:5]))
        duplicate_paths = sorted(set(text_paths) & set(preserve_paths))
        if duplicate_paths:
            errors.append("image review classifications overlap: " + ", ".join(duplicate_paths[:5]))
        image_review_summary = {
            "reviewedCandidates": reviewed_count,
            "textBearing": len(text_paths),
            "preserveExactSymbols": len(preserve_paths),
        }
    result = {
        "sourceUnits": len(expected_rows),
        "batchFiles": len(batch_files),
        "csvRows": len(csv_rows),
        "imageCandidates": len(inventory.get("images", [])),
        "extractedImages": extracted_images,
        "imageReview": image_review_summary,
        "sourceUnitsSha256": expected_sha256,
        "errors": errors,
        "ok": not errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def write_runtime_exact_manifest(args: argparse.Namespace) -> int:
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    story = json.loads(args.story.read_text(encoding="utf-8"))
    manifest = build_runtime_exact_manifest(inventory, story)
    write_json(args.output, manifest)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "controls": len(manifest["controls"]),
                "overlayRequiredControls": sum(
                    1 for row in manifest["controls"] if row["overlayRequired"]
                ),
                "inlinePrefixes": len(manifest["inlinePrefixes"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract_parser = subparsers.add_parser("extract", help="extract source inventory")
    extract_parser.add_argument("--data-root", type=Path, required=True)
    extract_parser.add_argument("--output", type=Path, required=True)
    extract_parser.set_defaults(handler=extract)
    validate_parser = subparsers.add_parser("validate", help="validate a hand-authored locale overlay")
    validate_parser.add_argument("--inventory", type=Path, required=True)
    validate_parser.add_argument("--overlay", type=Path, required=True)
    validate_parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="report missing units without treating incompleteness as a failure",
    )
    validate_parser.set_defaults(handler=validate)
    apply_parser = subparsers.add_parser("apply-story", help="apply authored story translations to a JSON copy")
    apply_parser.add_argument("--inventory", type=Path, required=True)
    apply_parser.add_argument("--overlay", type=Path, required=True)
    apply_parser.add_argument("--story", type=Path, required=True)
    apply_parser.add_argument("--output", type=Path, required=True)
    apply_parser.set_defaults(handler=apply_story)
    compile_parser = subparsers.add_parser("compile-overlay", help="compile the manual overlay without generating wording")
    compile_parser.add_argument("--inventory", type=Path, required=True)
    compile_parser.add_argument("--manual", type=Path, required=True)
    compile_parser.add_argument("--output", type=Path, required=True)
    compile_parser.set_defaults(handler=compile_overlay)
    shared_parser = subparsers.add_parser("build-sharedassets", help="build a derived sharedassets0.assets story payload")
    shared_parser.add_argument("--source", type=Path, required=True)
    shared_parser.add_argument("--inventory", type=Path, required=True)
    shared_parser.add_argument("--overlay", type=Path, required=True)
    shared_parser.add_argument("--output", type=Path, required=True, help="directory for the derived asset")
    shared_parser.set_defaults(handler=build_sharedassets)
    development_parser = subparsers.add_parser(
        "build-development-patch",
        help="build a complete Russian runtime patch without changing the installed game",
    )
    development_parser.add_argument("--data-root", type=Path, required=True)
    development_parser.add_argument("--inventory", type=Path, required=True)
    development_parser.add_argument("--overlay", type=Path, required=True)
    development_parser.add_argument("--output", type=Path, required=True)
    development_parser.set_defaults(handler=build_development_patch)
    source_parser = subparsers.add_parser("validate-source", help="validate the prepared English source package")
    source_parser.add_argument("--inventory", type=Path, required=True)
    source_parser.add_argument("--source-root", type=Path, required=True)
    source_parser.add_argument(
        "--image-review",
        type=Path,
        help="validate a completed human image review against the extracted candidate set",
    )
    source_parser.set_defaults(handler=validate_source)
    exact_parser = subparsers.add_parser(
        "build-runtime-exact-manifest",
        help="derive byte-exact Ink runtime operands and inline prefixes",
    )
    exact_parser.add_argument("--inventory", type=Path, required=True)
    exact_parser.add_argument("--story", type=Path, required=True)
    exact_parser.add_argument("--output", type=Path, required=True)
    exact_parser.set_defaults(handler=write_runtime_exact_manifest)
    return parser


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.handler(arguments))
