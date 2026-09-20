#!/usr/bin/env python3
"""Build and verify the compact 30-locale installer payload.

The runtime patch builder emits complete files. This packer stores one verified
Russian base delta from the pristine Steam files and a second delta from that
base to every other locale. The installer applies the chain transactionally.
Localized PNGs are intentionally out of scope for this payload revision.
"""

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
CONFIG = PROJECT / "Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"
PAYLOAD = PROJECT / "Sources/MurderOfSonicLocalizationInstaller/Resources/LocalizationPayload"
PATCH_BUILDER = PROJECT / "Scripts/extract-localization-assets.py"
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


def build_locale(locale: str, data_root: Path, output: Path, unitypy_root: Path) -> None:
    command = [
        "python3", str(PATCH_BUILDER), "build-locale-patch",
        "--data-root", str(data_root),
        "--inventory", str(LOCALIZATION / "inventory.json"),
        "--overlay", str(LOCALIZATION / f"{locale}.overlay.json"),
        "--font", str(FONTS / FONT_BY_LOCALE[locale]),
        "--output", str(output),
    ]
    if locale in COMPLEX:
        command.extend(["--shaping-map", str(FONTS / "Complex" / f"{locale}.shaping.json")])
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(unitypy_root)
    run(command, env=environment)


def make_delta(tool: Path, source: Path, target: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        str(tool), "-a", "-S", "djw", "-1", "-e", "-f",
        "-s", str(source), str(target), str(output),
    ])


def verify_delta(tool: Path, source: Path, delta: Path, expected: Path, scratch: Path) -> None:
    scratch.parent.mkdir(parents=True, exist_ok=True)
    run([str(tool), "-d", "-f", "-s", str(source), str(delta), str(scratch)])
    try:
        if sha256(scratch) != sha256(expected):
            raise RuntimeError(f"Delta verification failed: {delta}")
    finally:
        scratch.unlink(missing_ok=True)


def artifact(path: Path, payload_root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(payload_root).as_posix(),
        "sha256": sha256(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--unitypy-root", type=Path, required=True)
    parser.add_argument("--xdelta", type=Path, required=True)
    parser.add_argument("--xdelta-license", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    locales = [row["runtimeCode"] for row in config["languages"]]
    if set(locales) != set(FONT_BY_LOCALE) or len(locales) != 30:
        raise RuntimeError("PackageConfig and the pinned 30-locale font map differ")
    for required in (args.data_root, args.unitypy_root, args.xdelta, args.xdelta_license):
        if not required.exists():
            raise RuntimeError(f"Required input is missing: {required}")

    work = Path(tempfile.mkdtemp(prefix="sonic-unified-payload.", dir="/private/tmp"))
    builds = work / "builds"
    staged_payload = work / "LocalizationPayload"
    scratch = work / "verify"
    try:
        builds.mkdir()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(build_locale, locale, args.data_root.resolve(), builds / locale, args.unitypy_root.resolve()): locale
                for locale in locales
            }
            for future in concurrent.futures.as_completed(futures):
                locale = futures[future]
                future.result()
                print(f"built {locale}", flush=True)

        manifests = {
            locale: json.loads((builds / locale / "development-patch-manifest.json").read_text(encoding="utf-8"))
            for locale in locales
        }
        for locale, manifest in manifests.items():
            if manifest["targetLocale"] != locale or manifest["missingTranslationIds"]:
                raise RuntimeError(f"Incomplete runtime patch: {locale}")
            if manifest.get("imagesModified") is not False:
                raise RuntimeError(f"Unexpected image state in runtime patch: {locale}")

        tool_output = staged_payload / "Tools/xdelta3"
        tool_output.parent.mkdir(parents=True)
        shutil.copy2(args.xdelta, tool_output)
        tool_output.chmod(0o755)
        shutil.copy2(args.xdelta_license, staged_payload / "Tools/XDELTA-LICENSE")

        base_manifest = manifests[BASE_LOCALE]
        original_by_path = {
            row["path"]: args.data_root / row["path"]
            for row in base_manifest["files"] if row.get("originalSha256")
        }
        base_delta_by_path: dict[str, Path] = {}
        delta_jobs: list[tuple[Path, Path, Path]] = []
        for relative, original in original_by_path.items():
            base_target = builds / BASE_LOCALE / relative
            delta = staged_payload / "Base" / BASE_LOCALE / f"{relative}.xdelta"
            base_delta_by_path[relative] = delta
            delta_jobs.append((original, base_target, delta))
        for locale in locales:
            if locale == BASE_LOCALE:
                continue
            for relative in original_by_path:
                delta_jobs.append((
                    builds / BASE_LOCALE / relative,
                    builds / locale / relative,
                    staged_payload / "Locales" / locale / f"{relative}.xdelta",
                ))

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(make_delta, args.xdelta.resolve(), source, target, delta): delta
                for source, target, delta in delta_jobs
            }
            for future in concurrent.futures.as_completed(futures):
                delta = futures[future]
                future.result()
                print(f"packed {delta.relative_to(staged_payload)}", flush=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    verify_delta,
                    args.xdelta.resolve(), source, delta, target,
                    scratch / f"{index}.out",
                ): delta
                for index, (source, target, delta) in enumerate(delta_jobs)
            }
            for future in concurrent.futures.as_completed(futures):
                delta = futures[future]
                future.result()
                print(f"verified {delta.relative_to(staged_payload)}", flush=True)

        language_rows = {row["runtimeCode"]: row for row in config["languages"]}
        for locale in locales:
            files: list[dict[str, object]] = []
            for row in manifests[locale]["files"]:
                relative = row["path"]
                item: dict[str, object] = {
                    "path": relative,
                    "originalSHA256": row.get("originalSha256"),
                    "payloadSHA256": row["patchedSha256"],
                }
                if row.get("originalSha256"):
                    chain = [artifact(base_delta_by_path[relative], staged_payload)]
                    if locale != BASE_LOCALE:
                        chain.append(artifact(
                            staged_payload / "Locales" / locale / f"{relative}.xdelta",
                            staged_payload,
                        ))
                    item["artifacts"] = chain
                else:
                    source = builds / locale / relative
                    destination = staged_payload / "Locales" / locale / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    item["payloadPath"] = destination.relative_to(staged_payload).as_posix()
                    item["artifactSHA256"] = sha256(destination)
                files.append(item)
            language_rows[locale]["ready"] = True
            language_rows[locale]["files"] = files

        config["payloadReady"] = True
        config["files"] = []
        config["copy"]["installingTitle"] = "Установка локализации"
        config["copy"]["selectLanguageMessage"] = (
            "В сборку входят 30 локализаций. Выберите язык, который нужно применить к игре."
        )
        config["copy"]["installingMessage"] = "Проверка и установка выбранной локализации VN Revival…"
        config["copy"]["installedMessage"] = "Локализация установлена"

        build_manifest = {
            "schemaVersion": 1,
            "kind": "vn-revival-unified-text-payload",
            "baseLocale": BASE_LOCALE,
            "locales": locales,
            "localeCount": len(locales),
            "imagesModified": False,
            "deltaTool": {
                "name": "xdelta3",
                "sha256": sha256(tool_output),
                "license": "XDELTA-LICENSE",
            },
        }
        (staged_payload / "BuildManifest.json").write_text(
            json.dumps(build_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        old_payload = PAYLOAD.with_name("LocalizationPayload.previous")
        if old_payload.exists():
            shutil.rmtree(old_payload)
        if PAYLOAD.exists():
            PAYLOAD.rename(old_payload)
        staged_payload.rename(PAYLOAD)
        if old_payload.exists():
            shutil.rmtree(old_payload)
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "locales": len(locales),
            "payloadBytes": sum(path.stat().st_size for path in PAYLOAD.rglob("*") if path.is_file()),
            "imagesModified": False,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
