#!/usr/bin/env python3
"""Build the compact shared-runtime payload for all 30 locales."""

from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


PROJECT = Path(__file__).resolve().parent.parent
LOCALIZATION = PROJECT / "Documentation/Localization"
FONTS = PROJECT / "LocalizationAssets/Fonts"
FONT_AUDIT = LOCALIZATION / "Fonts/font-audit.json"
SOURCE_CONFIG = PROJECT / "Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"
WINDOWS_RESOURCES = PROJECT / "Windows/Resources"
MACOS_RESOURCES = PROJECT / "Sources/MurderOfSonicLocalizationInstaller/Resources"
EXTRACTION_SCRIPT = PROJECT / "Scripts/extract-localization-assets.py"
RUNTIME_SOURCE = PROJECT / "Scripts/VNRevivalRuntime.cs"
PATCHER_SOURCE = PROJECT / "Scripts/PatchRuntimeLoader.cs"

COMPLEX = {"ar", "fa", "he", "hi", "th"}
FONT_BY_LOCALE = {
    **{
        locale: "NotoSans-Regular.ttf"
        for locale in (
            "bg", "cs", "de", "el", "es", "es-419", "fil", "fr", "hu", "id",
            "it", "nl", "pl", "pt-BR", "ro", "ru", "sr", "sw", "tr", "uk", "vi",
        )
    },
    "ar": "NotoSansArabicLatin-ar-Shaped.ttf",
    "fa": "NotoSansArabicLatin-fa-Shaped.ttf",
    "he": "NotoSansHebrewLatin-he-Shaped.ttf",
    "hi": "NotoSansDevanagariLatin-hi-Shaped.ttf",
    "th": "NotoSansThaiLatin-th-Shaped.ttf",
    "ja": "NotoSansCJKjp-Regular.otf",
    "ko": "NotoSansCJKkr-Regular.otf",
    "zh": "NotoSansCJKsc-Regular.otf",
    "zh-TW": "NotoSansCJKtc-Regular.otf",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout.strip()


def locate_cecil() -> Path:
    candidates = sorted(Path("/opt/homebrew/Cellar/mono").glob("*/lib/mono/gac/Mono.Cecil/0.11.*/Mono.Cecil.dll"))
    if not candidates:
        raise RuntimeError("Mono.Cecil 0.11 was not found")
    return candidates[-1]


def load_extraction_module() -> Any:
    spec = importlib.util.spec_from_file_location("extract_localization_assets", EXTRACTION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the localization extraction module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def normalized_context(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r" \(TMP\)$", "", value)


def deterministic_gzip(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as stream:
            stream.write(content)


def font_source(filename: str) -> Path:
    path = FONTS / "Complex" / filename if filename.endswith("-Shaped.ttf") else FONTS / filename
    if not path.is_file():
        raise RuntimeError(f"Prepared font is missing: {path}")
    return path


def build_story(
    module: Any,
    source_story: dict[str, Any],
    story_rows: list[dict[str, Any]],
    overlay: dict[str, Any],
) -> bytes:
    story = copy.deepcopy(source_story)
    translations = overlay["units"]
    changed = 0
    for row in story_rows:
        translation = translations.get(row["id"])
        if not isinstance(translation, str) or not translation.strip():
            raise RuntimeError(f"Story translation is missing: {row['id']}")
        parts = module.parse_json_path(row["sourcePath"])
        cursor: Any = story
        for part in parts[:-1]:
            cursor = cursor[part]
        if cursor[parts[-1]] != row["original"]:
            raise RuntimeError(f"Story source mismatch: {row['id']}")
        cursor[parts[-1]] = module.localized_story_value(row, translation)
        changed += 1
    if changed != 3335:
        raise RuntimeError(f"Expected 3,335 localized story values; found {changed}")
    return (json.dumps(story, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def build_runtime_data(
    module: Any,
    locale: str,
    inventory: dict[str, Any],
    overlay: dict[str, Any],
    font_filename: str,
    font_family: str,
) -> bytes:
    if len(overlay.get("units", {})) != 3547:
        raise RuntimeError(f"Locale {locale} does not contain 3,547 translations")
    layout = module.effective_level0_layout_overrides(overlay)
    layout.update(module.effective_defaultgroup_layout_overrides(overlay))
    mode = int(module.COMPLEX_SCRIPT_MODES.get(locale, 0))
    rtl = locale in {"ar", "fa", "he"}
    lines = [
        "\t".join(("VNREVIVAL2", locale, str(mode), "1" if rtl else "0", encode(font_filename), encode(font_family)))
    ]
    for row in inventory["units"]:
        if not row.get("translatable") or row.get("sourceAsset") == "sharedassets0.assets::story":
            continue
        translation = overlay["units"].get(row["id"])
        if not isinstance(translation, str) or not translation.strip():
            raise RuntimeError(f"Runtime translation is missing: {locale}/{row['id']}")
        source = row["original"]
        localized = module.preserve_edge_whitespace(source, translation)
        override = layout.get(row["id"], {})
        font_size = override.get("m_fontSize", override.get("m_fontSizeBase", ""))
        lines.append(
            "\t".join(
                (
                    "T",
                    encode(source),
                    encode(normalized_context(row.get("context"))),
                    encode(localized),
                    "" if font_size == "" else format(float(font_size), ".9g"),
                )
            )
        )

    # Save slots derive these English labels from internal environment keys.
    # They are display aliases, not additional translation units.
    for runtime_display, localized in sorted(module.save_location_display_labels(inventory, overlay)):
        lines.append("\t".join(("T", encode(runtime_display), "", encode(localized), "")))

    if locale in COMPLEX:
        shaping_path = FONTS / "Complex" / f"{locale}.shaping.json"
        shaping = json.loads(shaping_path.read_text(encoding="utf-8"))
        if shaping.get("locale") != locale or bool(shaping.get("rightToLeft")) != rtl:
            raise RuntimeError(f"Complex-script shaping metadata mismatch: {locale}")
        exact: dict[str, str] = {}
        for key in ("runtimeEntries", "imageEntries"):
            for item in shaping.get(key, []):
                logical = item.get("logical")
                shaped = item.get("shaped")
                if not isinstance(logical, str) or not isinstance(shaped, str):
                    raise RuntimeError(f"Malformed shaping entry: {locale}/{key}")
                previous = exact.get(logical)
                if previous is not None and previous != shaped:
                    raise RuntimeError(f"Conflicting exact shaping entry: {locale}/{logical!r}")
                exact[logical] = shaped
        for logical, shaped in sorted(exact.items()):
            lines.append("\t".join(("E", encode(logical), encode(shaped))))
        spans: dict[str, str] = {}
        for item in shaping.get("spanEntries", []):
            logical = item.get("logical")
            shaped = item.get("shaped")
            if not isinstance(logical, str) or not logical or not isinstance(shaped, str):
                raise RuntimeError(f"Malformed span shaping entry: {locale}")
            previous = spans.get(logical)
            if previous is not None and previous != shaped:
                raise RuntimeError(f"Conflicting span shaping entry: {locale}/{logical!r}")
            spans[logical] = shaped
        for logical, shaped in sorted(spans.items()):
            lines.append("\t".join(("S", encode(logical), encode(shaped))))
    return ("\n".join(lines) + "\n").encode("utf-8")


def payload_item(path: str, payload_path: Path, payload_root: Path) -> dict[str, Any]:
    digest = sha256(payload_path)
    return {
        "path": path,
        "originalSHA256": None,
        "payloadSHA256": digest,
        "payloadPath": payload_path.relative_to(payload_root).as_posix(),
        "artifactSHA256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--managed-root", type=Path, required=True)
    parser.add_argument("--xdelta", type=Path, required=True)
    parser.add_argument("--target", choices=("windows", "macos"), default="windows")
    parser.add_argument("--target-xdelta", type=Path)
    parser.add_argument("--windows-xdelta", type=Path)
    parser.add_argument("--output-resources", type=Path)
    parser.add_argument("--xdelta-license", type=Path, required=True)
    args = parser.parse_args()

    managed_root = args.managed_root.resolve()
    target_xdelta = (args.target_xdelta or args.windows_xdelta)
    if target_xdelta is None:
        parser.error("one of --target-xdelta or --windows-xdelta is required")
    target_xdelta = target_xdelta.resolve()
    output_resources = (
        args.output_resources.resolve()
        if args.output_resources
        else (WINDOWS_RESOURCES if args.target == "windows" else MACOS_RESOURCES)
    )
    tool_name = "xdelta3.exe" if args.target == "windows" else "xdelta3"
    source_assembly = managed_root / "Assembly-CSharp.dll"
    dependencies = (
        source_assembly,
        managed_root / "Unity.TextMeshPro.dll",
        managed_root / "UnityEngine.CoreModule.dll",
        managed_root / "UnityEngine.TextRenderingModule.dll",
        managed_root / "UnityEngine.UIModule.dll",
        managed_root / "UnityEngine.UI.dll",
        managed_root / "netstandard.dll",
        args.xdelta.resolve(),
        target_xdelta,
        args.xdelta_license.resolve(),
    )
    for required in dependencies:
        if not required.is_file():
            raise RuntimeError(f"Required input is missing: {required}")
    file_report = run(["file", str(target_xdelta)])
    if args.target == "windows":
        if "PE32+ executable" not in file_report or "x86-64" not in file_report:
            raise RuntimeError("The bundled xdelta decoder is not Windows x64: " + file_report)
    elif "universal binary" not in file_report or "x86_64" not in file_report or "arm64" not in file_report:
        raise RuntimeError("The bundled xdelta decoder is not universal macOS arm64/x86_64: " + file_report)

    config_source = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    language_sources = config_source["languages"]
    locales = [row["runtimeCode"] for row in language_sources]
    if len(locales) != 30 or set(locales) != set(FONT_BY_LOCALE):
        raise RuntimeError("PackageConfig and the pinned 30-locale font map differ")
    inventory = json.loads((LOCALIZATION / "inventory.json").read_text(encoding="utf-8"))
    source_story = json.loads((LOCALIZATION / "story.en.json").read_text(encoding="utf-8"))
    story_rows = [
        row for row in inventory["units"]
        if row.get("translatable") and row.get("sourceAsset") == "sharedassets0.assets::story"
    ]
    module = load_extraction_module()
    font_audit = json.loads(FONT_AUDIT.read_text(encoding="utf-8"))
    if not font_audit.get("ok"):
        raise RuntimeError("The pinned font audit is not passing")

    work = Path(tempfile.mkdtemp(prefix="sonic-runtime-payload.", dir="/private/tmp"))
    staged = work / "LocalizationPayload"
    try:
        tools = staged / "Tools"
        tools.mkdir(parents=True)
        shutil.copy2(target_xdelta, tools / tool_name)
        (tools / tool_name).chmod(0o755)
        shutil.copy2(args.xdelta_license.resolve(), tools / "XDELTA-LICENSE")

        runtime_dir = work / "runtime"
        runtime_dir.mkdir()
        runtime_dll = runtime_dir / "VNRevival.Runtime.dll"
        compile_runtime = [
            "mcs", "-nologo", "-target:library", f"-out:{runtime_dll}", f"-lib:{managed_root}",
            "-r:Unity.TextMeshPro.dll", "-r:UnityEngine.CoreModule.dll",
            "-r:UnityEngine.TextRenderingModule.dll", "-r:UnityEngine.UIModule.dll",
            "-r:UnityEngine.UI.dll", "-r:netstandard.dll", "-r:System.IO.Compression.dll",
            str(RUNTIME_SOURCE),
        ]
        run(compile_runtime)
        patcher = runtime_dir / "PatchRuntimeLoader.exe"
        run(["mcs", "-nologo", f"-r:{locate_cecil()}", f"-out:{patcher}", str(PATCHER_SOURCE)])
        patched_assembly = runtime_dir / "Assembly-CSharp.dll"
        patch_report = run(["mono", str(patcher), str(source_assembly), str(patched_assembly), str(runtime_dll)])
        expected_report = "1 initializer; 1 story loader; 28 text redirects; 1 animation guard"
        if patch_report != expected_report:
            raise RuntimeError("Unexpected managed patch report: " + patch_report)

        assembly_delta = staged / "D/shared/Assembly-CSharp.dll.xdelta"
        assembly_delta.parent.mkdir(parents=True)
        run([
            str(args.xdelta.resolve()), "-a", "-S", "djw", "-1", "-e", "-f",
            "-s", str(source_assembly), str(patched_assembly), str(assembly_delta),
        ])
        verification = runtime_dir / "Assembly-CSharp.verified.dll"
        run([
            str(args.xdelta.resolve()), "-d", "-f", "-s", str(source_assembly),
            str(assembly_delta), str(verification),
        ])
        if sha256(verification) != sha256(patched_assembly):
            raise RuntimeError("The shared Assembly-CSharp delta failed verification")

        shared_files: list[dict[str, Any]] = [
            {
                "path": "Managed/Assembly-CSharp.dll",
                "originalSHA256": sha256(source_assembly),
                "payloadSHA256": sha256(patched_assembly),
                "artifacts": [
                    {
                        "path": assembly_delta.relative_to(staged).as_posix(),
                        "sha256": sha256(assembly_delta),
                    }
                ],
            }
        ]
        runtime_payload = staged / "F/shared/Managed/VNRevival.Runtime.dll"
        runtime_payload.parent.mkdir(parents=True)
        shutil.copy2(runtime_dll, runtime_payload)
        shared_files.append(payload_item("Managed/VNRevival.Runtime.dll", runtime_payload, staged))

        fonts_output = staged / "F/shared/StreamingAssets/VNRevival/Fonts"
        for filename in sorted(set(FONT_BY_LOCALE.values())):
            destination = fonts_output / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(font_source(filename), destination)
            shared_files.append(payload_item(f"StreamingAssets/VNRevival/Fonts/{filename}", destination, staged))
        license_source = FONTS / "OFL-1.1.txt"
        license_output = fonts_output / "OFL-1.1.txt"
        shutil.copy2(license_source, license_output)
        shared_files.append(payload_item("StreamingAssets/VNRevival/Fonts/OFL-1.1.txt", license_output, staged))

        locale_output = staged / "F/shared/StreamingAssets/VNRevival/Locales"
        for locale in locales:
            overlay = json.loads((LOCALIZATION / f"{locale}.overlay.json").read_text(encoding="utf-8"))
            if overlay.get("targetLocale") != locale:
                raise RuntimeError(f"Overlay target mismatch: {locale}")
            font_filename = FONT_BY_LOCALE[locale]
            font_family = font_audit["fonts"][font_filename]["family"]
            runtime_path = locale_output / f"{locale}.runtime.tsv.gz"
            story_path = locale_output / f"{locale}.story.json.gz"
            deterministic_gzip(
                runtime_path,
                build_runtime_data(module, locale, inventory, overlay, font_filename, font_family),
            )
            deterministic_gzip(story_path, build_story(module, source_story, story_rows, overlay))
            shared_files.append(
                payload_item(f"StreamingAssets/VNRevival/Locales/{runtime_path.name}", runtime_path, staged)
            )
            shared_files.append(
                payload_item(f"StreamingAssets/VNRevival/Locales/{story_path.name}", story_path, staged)
            )
            print(f"packed {locale}", flush=True)

        language_rows = []
        active_root = staged / "F/active"
        for source in language_sources:
            locale = source["runtimeCode"]
            active_payload = active_root / f"{locale}.txt"
            active_payload.parent.mkdir(parents=True, exist_ok=True)
            active_payload.write_text(locale + "\n", encoding="utf-8")
            active_item = payload_item(
                "StreamingAssets/VNRevival/active-locale.txt",
                active_payload,
                staged,
            )
            language_rows.append(
                {
                    "siteLocale": source["siteLocale"],
                    "runtimeCode": locale,
                    "nativeLanguageName": source["nativeLanguageName"],
                    "ready": True,
                    "files": [active_item],
                }
            )

        config = {key: value for key, value in config_source.items() if key not in {"languages", "files"}}
        config["payloadReady"] = True
        config["languages"] = language_rows
        config["files"] = shared_files
        config_path = work / "PackageConfig.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        build_manifest = {
            "schemaVersion": 2,
            "kind": f"vn-revival-shared-runtime-{args.target}-text-payload",
            "locales": locales,
            "localeCount": len(locales),
            "imagesModified": False,
            "architecture": "shared-runtime-external-locale-data",
            "runtime": {
                "assembly": "Managed/VNRevival.Runtime.dll",
                "sha256": sha256(runtime_dll),
                "managedPatchReport": patch_report,
            },
            "deltaTool": {
                "name": tool_name,
                "sha256": sha256(tools / tool_name),
                "license": "XDELTA-LICENSE",
            },
        }
        (staged / "BuildManifest.json").write_text(
            json.dumps(build_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (staged / "README.md").write_text(
            f"# {args.target.capitalize()} localization payload\n\n"
            "One shared managed runtime loads all 30 compressed locale packs and fonts from bundled files. "
            "Only Assembly-CSharp.dll is patched; original Unity asset bundles remain untouched.\n",
            encoding="utf-8",
        )

        output_resources.mkdir(parents=True, exist_ok=True)
        payload = output_resources / "LocalizationPayload"
        previous = output_resources / "LocalizationPayload.previous"
        if previous.exists():
            shutil.rmtree(previous)
        if payload.exists():
            payload.rename(previous)
        staged.rename(payload)
        shutil.copy2(config_path, output_resources / "PackageConfig.json")
        if previous.exists():
            shutil.rmtree(previous)
        payload_bytes = sum(path.stat().st_size for path in payload.rglob("*") if path.is_file())
        print(
            json.dumps(
                {
                    "locales": len(locales),
                    "payloadBytes": payload_bytes,
                    "payloadMiB": round(payload_bytes / 1024 / 1024, 2),
                    "imagesModified": False,
                    "architecture": build_manifest["architecture"],
                    "target": args.target,
                },
                indent=2,
            )
        )
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
