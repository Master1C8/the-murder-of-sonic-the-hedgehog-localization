#!/usr/bin/env python3
"""Verify the compact Windows runtime payload against all canonical overlays."""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parent.parent
LOCALIZATION = PROJECT / "Documentation/Localization"
PAYLOAD = PROJECT / "Windows/Resources/LocalizationPayload"
CONFIG = PROJECT / "Windows/Resources/PackageConfig.json"
EXTRACTION_SCRIPT = PROJECT / "Scripts/extract-localization-assets.py"
COMPLEX = {"ar": (1, True), "fa": (1, True), "he": (2, True), "hi": (3, False), "th": (4, False)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode(value: str) -> str:
    return base64.b64decode(value).decode("utf-8")


def load_extraction_module() -> Any:
    spec = importlib.util.spec_from_file_location("extract_localization_assets", EXTRACTION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the localization extraction module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> int:
    module = load_extraction_module()
    inventory = json.loads((LOCALIZATION / "inventory.json").read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads((PAYLOAD / "BuildManifest.json").read_text(encoding="utf-8"))
    languages = config.get("languages", [])
    if not config.get("payloadReady") or len(languages) != 30:
        fail("PackageConfig is not a ready 30-locale package")
    if manifest.get("architecture") != "shared-runtime-external-locale-data":
        fail("BuildManifest does not select the compact shared runtime")
    if manifest.get("imagesModified") is not False:
        fail("The compact payload unexpectedly modifies images")
    if manifest.get("runtime", {}).get("managedPatchReport") != (
        "1 initializer; 1 story loader; 28 text redirects; 1 animation guard"
    ):
        fail("The managed runtime hook report is incomplete")

    runtime_payload = PAYLOAD / "F/shared/Managed/VNRevival.Runtime.dll"
    if sha256(runtime_payload) != manifest["runtime"]["sha256"]:
        fail("The runtime DLL checksum does not match BuildManifest")
    if sha256(PAYLOAD / "Tools/xdelta3.exe") != manifest["deltaTool"]["sha256"]:
        fail("The Windows xdelta checksum does not match BuildManifest")

    locales = [row["runtimeCode"] for row in languages]
    if locales != manifest.get("locales") or len(set(locales)) != 30:
        fail("Locale order or uniqueness differs between config and manifest")
    shared_files = config.get("files", [])
    if len(shared_files) < 60:
        fail("PackageConfig does not declare the shared payload once at top level")
    expected_shared_paths = {row["path"] for row in shared_files}
    if len(expected_shared_paths) != len(shared_files):
        fail("The shared payload contains duplicate destination paths")
    originals = [row for row in shared_files if row.get("originalSHA256")]
    if len(originals) != 1 or originals[0]["path"] != "Managed/Assembly-CSharp.dll":
        fail("The shared payload patches more than the one managed assembly")
    for row in shared_files:
        artifacts = row.get("artifacts") or []
        if artifacts:
            for artifact in artifacts:
                path = PAYLOAD / artifact["path"]
                if not path.is_file() or sha256(path) != artifact["sha256"]:
                    fail(f"Payload artifact mismatch: {artifact['path']}")
        else:
            path = PAYLOAD / row["payloadPath"]
            if not path.is_file() or sha256(path) != row["artifactSHA256"]:
                fail(f"Payload file mismatch: {row['payloadPath']}")
            if row["payloadSHA256"] != row["artifactSHA256"]:
                fail(f"Direct payload hash mismatch: {row['path']}")
    for language in languages:
        files = language.get("files", [])
        active = [row for row in files if row["path"] == "StreamingAssets/VNRevival/active-locale.txt"]
        if len(active) != 1 or len(files) != 1:
            fail(f"Active-locale file is missing or duplicated: {language['runtimeCode']}")
        for row in files:
            path = PAYLOAD / row["payloadPath"]
            if not path.is_file() or sha256(path) != row["artifactSHA256"]:
                fail(f"Active-locale payload mismatch: {language['runtimeCode']}")
    if sum(path.startswith("StreamingAssets/VNRevival/Locales/") for path in expected_shared_paths) != 60:
        fail("The shared payload does not contain two packs for each of 30 locales")
    forbidden = ("sharedassets0.assets", "level0", "defaultgroup_assets", "inventoryitems_assets", "catalog.json")
    if any(any(token in path for token in forbidden) for path in expected_shared_paths):
        fail("A rebuilt Unity asset unexpectedly remains in the compact payload")

    rows_by_id = {row["id"]: row for row in inventory["units"]}
    story_rows = [
        row for row in inventory["units"]
        if row.get("translatable") and row.get("sourceAsset") == "sharedassets0.assets::story"
    ]
    runtime_rows = [
        row for row in inventory["units"]
        if row.get("translatable") and row.get("sourceAsset") != "sharedassets0.assets::story"
    ]
    if len(story_rows) != 3335 or len(runtime_rows) != 212:
        fail("Canonical inventory counts changed")

    for locale in locales:
        overlay = json.loads((LOCALIZATION / f"{locale}.overlay.json").read_text(encoding="utf-8"))
        story_path = PAYLOAD / f"F/shared/StreamingAssets/VNRevival/Locales/{locale}.story.json.gz"
        runtime_path = PAYLOAD / f"F/shared/StreamingAssets/VNRevival/Locales/{locale}.runtime.tsv.gz"
        with gzip.open(story_path, "rt", encoding="utf-8") as stream:
            story = json.load(stream)
        for row in story_rows:
            cursor: Any = story
            parts = module.parse_json_path(row["sourcePath"])
            for part in parts:
                cursor = cursor[part]
            expected = module.localized_story_value(row, overlay["units"][row["id"]])
            if cursor != expected:
                fail(f"Localized story mismatch: {locale}/{row['id']}")

        translations: dict[str, list[str]] = {}
        exact_shapes = 0
        span_shapes = 0
        with gzip.open(runtime_path, "rt", encoding="utf-8") as stream:
            header = stream.readline().rstrip("\n").split("\t")
            expected_mode, expected_rtl = COMPLEX.get(locale, (0, False))
            if len(header) != 6 or header[:4] != [
                "VNREVIVAL2", locale, str(expected_mode), "1" if expected_rtl else "0"
            ]:
                fail(f"Runtime-data header mismatch: {locale}")
            if not decode(header[4]) or not decode(header[5]):
                fail(f"Runtime-data font metadata is empty: {locale}")
            for line in stream:
                fields = line.rstrip("\n").split("\t")
                if fields[0] == "T" and len(fields) == 5:
                    translations.setdefault(decode(fields[1]), []).append(decode(fields[3]))
                elif fields[0] == "E" and len(fields) == 3:
                    exact_shapes += 1
                elif fields[0] == "S" and len(fields) == 3:
                    span_shapes += 1
                else:
                    fail(f"Malformed runtime-data row: {locale}")
        for row in runtime_rows:
            expected = module.preserve_edge_whitespace(row["original"], overlay["units"][row["id"]])
            if expected not in translations.get(row["original"], []):
                fail(f"Runtime translation mismatch: {locale}/{row['id']}")
        if locale in COMPLEX and (exact_shapes == 0 or span_shapes == 0):
            fail(f"Complex-script shaping data is empty: {locale}")
        if locale not in COMPLEX and (exact_shapes != 0 or span_shapes != 0):
            fail(f"Unexpected shaping data for simple-script locale: {locale}")

    payload_bytes = sum(path.stat().st_size for path in PAYLOAD.rglob("*") if path.is_file())
    if payload_bytes >= 100 * 1024 * 1024:
        fail(f"Compact payload exceeds 100 MiB: {payload_bytes}")
    print(
        json.dumps(
            {
                "status": "WINDOWS_RUNTIME_PAYLOAD_TEST_PASS",
                "locales": len(locales),
                "storyUnitsPerLocale": len(story_rows),
                "runtimeUnitsPerLocale": len(runtime_rows),
                "payloadBytes": payload_bytes,
                "payloadMiB": round(payload_bytes / 1024 / 1024, 2),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exception:
        print(str(exception), file=sys.stderr)
        raise SystemExit(1)
