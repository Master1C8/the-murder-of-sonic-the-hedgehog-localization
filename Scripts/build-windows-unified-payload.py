#!/usr/bin/env python3
"""Build the compact, verified 30-locale Windows installer payload."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


PROJECT = Path(__file__).resolve().parent.parent
LOCALIZATION = PROJECT / "Documentation/Localization"
FONTS = PROJECT / "LocalizationAssets/Fonts"
SOURCE_CONFIG = PROJECT / "Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"
WINDOWS_RESOURCES = PROJECT / "Windows/Resources"
PATCH_BUILDER = PROJECT / "Scripts/build-windows-locale-patch.py"
BASE_LOCALE = "ru"
COMPLEX = {"ar", "fa", "he", "hi", "th"}
FONT_BY_LOCALE = {
    **{locale: "NotoSans-Regular.ttf" for locale in (
        "bg", "cs", "de", "el", "es", "es-419", "fil", "fr", "hu", "id",
        "it", "nl", "pl", "pt-BR", "ro", "ru", "sr", "sw", "tr", "uk", "vi",
    )},
    "ar": "Complex/NotoSansArabicLatin-ar-Shaped.ttf",
    "fa": "Complex/NotoSansArabicLatin-fa-Shaped.ttf",
    "he": "Complex/NotoSansHebrewLatin-he-Shaped.ttf",
    "hi": "Complex/NotoSansDevanagariLatin-hi-Shaped.ttf",
    "th": "Complex/NotoSansThaiLatin-th-Shaped.ttf",
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


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{details}")


def windows_path(value: str) -> str:
    return value.replace("StreamingAssets/aa/StandaloneOSX/", "StreamingAssets/aa/StandaloneWindows64/")


def payload_key(relative: str) -> str:
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:24]


def delta_path(payload_root: Path, locale: str, relative: str) -> Path:
    layer = "base" if locale == BASE_LOCALE else locale
    return payload_root / "D" / layer / f"{payload_key(relative)}.xdelta"


def payload_file_path(payload_root: Path, locale: str, relative: str) -> Path:
    source_name = Path(relative).name
    return payload_root / "F" / locale / f"{payload_key(relative)}-{source_name}"


def build_locale(locale: str, data_root: Path, inventory: Path, output: Path, unitypy_root: Path) -> None:
    command = [
        "python3", str(PATCH_BUILDER),
        "--data-root", str(data_root),
        "--inventory", str(inventory),
        "--overlay", str(LOCALIZATION / f"{locale}.overlay.json"),
        "--font", str(FONTS / FONT_BY_LOCALE[locale]),
        "--output", str(output),
        "--target-locale", locale,
    ]
    if locale in COMPLEX:
        command.extend(["--shaping-map", str(FONTS / "Complex" / f"{locale}.shaping.json")])
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(unitypy_root)
    run(command, env=environment)


def make_delta(tool: Path, source: Path, target: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run([str(tool), "-a", "-S", "djw", "-1", "-e", "-f", "-s", str(source), str(target), str(output)])


def verify_delta(tool: Path, source: Path, delta: Path, expected_hash: str, scratch: Path) -> None:
    scratch.parent.mkdir(parents=True, exist_ok=True)
    run([str(tool), "-d", "-f", "-s", str(source), str(delta), str(scratch)])
    try:
        if sha256(scratch) != expected_hash:
            raise RuntimeError(f"Delta verification failed: {delta}")
    finally:
        scratch.unlink(missing_ok=True)


def artifact(path: Path, payload_root: Path) -> dict[str, str]:
    return {"path": path.relative_to(payload_root).as_posix(), "sha256": sha256(path)}


def validate_manifest(locale: str, path: Path) -> dict:
    manifest = json.loads((path / "development-patch-manifest.json").read_text(encoding="utf-8"))
    if manifest["targetLocale"] != locale or manifest["missingTranslationIds"]:
        raise RuntimeError(f"Incomplete Windows runtime patch: {locale}")
    if manifest.get("imagesModified") is not False:
        raise RuntimeError(f"Unexpected image state in Windows runtime patch: {locale}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--unitypy-root", type=Path, required=True)
    parser.add_argument("--xdelta", type=Path, required=True)
    parser.add_argument("--windows-xdelta", type=Path, required=True)
    parser.add_argument("--xdelta-license", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--work-root", type=Path)
    args = parser.parse_args()

    source_config = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    locales = [row["runtimeCode"] for row in source_config["languages"]]
    if len(locales) != 30 or set(locales) != set(FONT_BY_LOCALE):
        raise RuntimeError("PackageConfig and the pinned 30-locale font map differ")
    for required in (
        args.data_root, args.inventory, args.unitypy_root, args.xdelta,
        args.windows_xdelta, args.xdelta_license,
    ):
        if not required.exists():
            raise RuntimeError(f"Required input is missing: {required}")
    file_report = subprocess.run(["file", str(args.windows_xdelta)], check=True, text=True, capture_output=True).stdout
    if "PE32+ executable" not in file_report or "x86-64" not in file_report:
        raise RuntimeError("The bundled xdelta3 decoder is not Windows x64: " + file_report.strip())

    persistent_work = args.work_root is not None
    work = (
        args.work_root.resolve()
        if persistent_work
        else Path(tempfile.mkdtemp(prefix="sonic-windows-payload.", dir="/private/tmp"))
    )
    builds = work / "builds"
    cached_manifests = work / "manifests"
    staged_payload = work / "LocalizationPayload"
    scratch = work / "verify"
    previous_payload = WINDOWS_RESOURCES / "LocalizationPayload"
    try:
        builds.mkdir(parents=True, exist_ok=True)
        cached_manifests.mkdir(parents=True, exist_ok=True)
        base_build = builds / BASE_LOCALE
        base_manifest_path = cached_manifests / f"{BASE_LOCALE}.json"
        base_manifest = None
        if base_manifest_path.is_file() and base_build.is_dir():
            candidate = json.loads(base_manifest_path.read_text(encoding="utf-8"))
            if all(
                (base_build / row["path"]).is_file()
                and sha256(base_build / row["path"]) == row["patchedSha256"]
                for row in candidate["files"]
            ):
                base_manifest = candidate
                print(f"reused {BASE_LOCALE}", flush=True)
        if base_manifest is None:
            if base_build.exists():
                shutil.rmtree(base_build)
            build_locale(BASE_LOCALE, args.data_root.resolve(), args.inventory.resolve(), base_build, args.unitypy_root.resolve())
            base_manifest = validate_manifest(BASE_LOCALE, base_build)
            base_manifest_path.write_text(
                json.dumps(base_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"built {BASE_LOCALE}", flush=True)

        tool_output = staged_payload / "Tools/xdelta3.exe"
        tool_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.windows_xdelta, tool_output)
        shutil.copy2(args.xdelta_license, staged_payload / "Tools/XDELTA-LICENSE")
        (staged_payload / "README.md").write_text(
            "# Windows localization payload\n\n"
            "`D/base` stores pristine-Windows-to-Russian xdelta layers. "
            "`D/<code>` stores Russian-to-locale layers, and `F/<code>` stores complex-script helper DLLs. "
            "Artifact names are flattened to stay below legacy Windows path limits. "
            "The installer verifies every source, artifact, and reconstructed SHA-256 before replacement.\n",
            encoding="utf-8",
        )

        originals: dict[str, Path] = {}
        base_targets: dict[str, Path] = {}
        base_deltas: dict[str, Path] = {}
        for row in base_manifest["files"]:
            if not row.get("originalSha256"):
                continue
            manifest_path = row["path"]
            relative = windows_path(manifest_path)
            source = args.data_root / manifest_path
            target = base_build / manifest_path
            delta = delta_path(staged_payload, BASE_LOCALE, relative)
            legacy_delta = previous_payload / "Base" / BASE_LOCALE / f"{relative}.xdelta"
            if not delta.is_file() and legacy_delta.is_file():
                delta.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_delta, delta)
            if not delta.is_file():
                make_delta(args.xdelta, source, target, delta)
            verify_delta(args.xdelta, source, delta, row["patchedSha256"], scratch / f"base-{len(base_deltas)}.out")
            originals[relative] = source
            base_targets[relative] = target
            base_deltas[relative] = delta
            print(f"packed and verified Base/{BASE_LOCALE}/{relative}", flush=True)

        manifests: dict[str, dict] = {BASE_LOCALE: base_manifest}
        for locale in locales:
            if locale == BASE_LOCALE:
                continue
            locale_manifest_path = cached_manifests / f"{locale}.json"
            if locale_manifest_path.is_file():
                cached = json.loads(locale_manifest_path.read_text(encoding="utf-8"))
                cache_valid = True
                for index, row in enumerate(cached["files"]):
                    manifest_path = row["path"]
                    relative = windows_path(manifest_path)
                    if row.get("originalSha256"):
                        delta = delta_path(staged_payload, locale, relative)
                        legacy_delta = previous_payload / "Locales" / locale / f"{relative}.xdelta"
                        if not delta.is_file() and legacy_delta.is_file():
                            delta.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(legacy_delta, delta)
                        if not delta.is_file():
                            cache_valid = False
                            break
                        try:
                            verify_delta(
                                args.xdelta.resolve(), base_targets[relative], delta,
                                row["patchedSha256"], scratch / f"cached-{locale}-{index}.out",
                            )
                        except RuntimeError:
                            cache_valid = False
                            break
                    else:
                        payload_file = payload_file_path(staged_payload, locale, relative)
                        legacy_file = previous_payload / "Locales" / locale / relative
                        if not payload_file.is_file() and legacy_file.is_file():
                            payload_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(legacy_file, payload_file)
                        if not payload_file.is_file() or sha256(payload_file) != row["patchedSha256"]:
                            cache_valid = False
                            break
                if cache_valid:
                    manifests[locale] = cached
                    print(f"reused {locale}", flush=True)
                    continue
            locale_build = builds / locale
            if locale_build.exists():
                shutil.rmtree(locale_build)
            build_locale(locale, args.data_root.resolve(), args.inventory.resolve(), locale_build, args.unitypy_root.resolve())
            manifest = validate_manifest(locale, locale_build)
            manifests[locale] = manifest
            print(f"built {locale}", flush=True)
            jobs = []
            for index, row in enumerate(manifest["files"]):
                if not row.get("originalSha256"):
                    continue
                manifest_path = row["path"]
                relative = windows_path(manifest_path)
                delta = delta_path(staged_payload, locale, relative)
                jobs.append((index, relative, locale_build / manifest_path, delta, row["patchedSha256"]))
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {
                    pool.submit(make_delta, args.xdelta.resolve(), base_targets[relative], target, delta):
                    (index, relative, target, delta, expected)
                    for index, relative, target, delta, expected in jobs
                }
                for future in concurrent.futures.as_completed(futures):
                    index, relative, target, delta, expected = futures[future]
                    future.result()
                    verify_delta(
                        args.xdelta.resolve(), base_targets[relative], delta, expected,
                        scratch / f"{locale}-{index}.out",
                    )
            for row in manifest["files"]:
                if row.get("originalSha256"):
                    continue
                manifest_path = row["path"]
                relative = windows_path(manifest_path)
                destination = payload_file_path(staged_payload, locale, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(locale_build / manifest_path, destination)
                if sha256(destination) != row["patchedSha256"]:
                    raise RuntimeError(f"Copied payload verification failed: {locale}/{relative}")
            locale_manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            shutil.rmtree(locale_build)
            print(f"packed and verified {locale}", flush=True)

        language_rows = {
            row["runtimeCode"]: {
                "siteLocale": row["siteLocale"],
                "runtimeCode": row["runtimeCode"],
                "nativeLanguageName": row["nativeLanguageName"],
                "ready": True,
            }
            for row in source_config["languages"]
        }
        for locale in locales:
            files: list[dict[str, object]] = []
            for row in manifests[locale]["files"]:
                manifest_path = row["path"]
                relative = windows_path(manifest_path)
                item: dict[str, object] = {
                    "path": relative,
                    "originalSHA256": row.get("originalSha256"),
                    "payloadSHA256": row["patchedSha256"],
                }
                if row.get("originalSha256"):
                    chain = [artifact(base_deltas[relative], staged_payload)]
                    if locale != BASE_LOCALE:
                        chain.append(artifact(delta_path(staged_payload, locale, relative), staged_payload))
                    item["artifacts"] = chain
                else:
                    destination = payload_file_path(staged_payload, locale, relative)
                    if locale == BASE_LOCALE:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(base_build / manifest_path, destination)
                    item["payloadPath"] = destination.relative_to(staged_payload).as_posix()
                    item["artifactSHA256"] = sha256(destination)
                files.append(item)
            language_rows[locale]["files"] = files

        config = {
            key: value for key, value in source_config.items()
            if key not in {"languages", "files"}
        }
        config["payloadReady"] = True
        config["languages"] = [language_rows[locale] for locale in locales]
        config["files"] = []
        (work / "PackageConfig.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        build_manifest = {
            "schemaVersion": 1,
            "kind": "vn-revival-unified-windows-text-payload",
            "baseLocale": BASE_LOCALE,
            "locales": locales,
            "localeCount": len(locales),
            "imagesModified": False,
            "deltaTool": {
                "name": "xdelta3.exe",
                "sha256": sha256(tool_output),
                "license": "XDELTA-LICENSE",
            },
        }
        (staged_payload / "BuildManifest.json").write_text(
            json.dumps(build_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        WINDOWS_RESOURCES.mkdir(parents=True, exist_ok=True)
        payload = WINDOWS_RESOURCES / "LocalizationPayload"
        previous = WINDOWS_RESOURCES / "LocalizationPayload.previous"
        if previous.exists():
            shutil.rmtree(previous)
        if payload.exists():
            payload.rename(previous)
        staged_payload.rename(payload)
        if previous.exists():
            shutil.rmtree(previous)
        shutil.copy2(work / "PackageConfig.json", WINDOWS_RESOURCES / "PackageConfig.json")
        print(json.dumps({
            "locales": len(locales),
            "payloadBytes": sum(path.stat().st_size for path in payload.rglob("*") if path.is_file()),
            "imagesModified": False,
        }, indent=2))
        return 0
    finally:
        if not persistent_work:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
