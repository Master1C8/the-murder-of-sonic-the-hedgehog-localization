#!/usr/bin/env python3
"""Static integrity gate for the packaged 30-locale installer payload."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"
PAYLOAD = ROOT / "Sources/MurderOfSonicLocalizationInstaller/Resources/LocalizationPayload"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise RuntimeError(f"Unsafe payload path: {value}")
    return PAYLOAD.joinpath(*relative.parts)


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    languages = config.get("languages", [])
    if config.get("payloadReady") is not True or len(languages) != 30:
        raise RuntimeError("Unified payload is not marked ready for all 30 locales")
    artifacts: dict[str, str] = {}
    for language in languages:
        files = language.get("files") or []
        if language.get("ready") is not True or not files:
            raise RuntimeError(f"Locale payload is incomplete: {language.get('runtimeCode')}")
        for item in files:
            if not item.get("payloadSHA256") or len(item["payloadSHA256"]) != 64:
                raise RuntimeError(f"Missing output SHA-256: {item.get('path')}")
            chain = item.get("artifacts")
            if chain:
                rows = chain
            else:
                rows = [{
                    "path": item.get("payloadPath", item["path"]),
                    "sha256": item.get("artifactSHA256", item["payloadSHA256"]),
                }]
            for row in rows:
                prior = artifacts.setdefault(row["path"], row["sha256"])
                if prior != row["sha256"]:
                    raise RuntimeError(f"Conflicting artifact hash: {row['path']}")
    for relative, expected in artifacts.items():
        path = safe_path(relative)
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Payload artifact failed integrity check: {relative}")

    manifest = json.loads((PAYLOAD / "BuildManifest.json").read_text(encoding="utf-8"))
    if manifest.get("localeCount") != 30 or manifest.get("imagesModified") is not False:
        raise RuntimeError("Payload build manifest is inconsistent")
    tool = PAYLOAD / "Tools/xdelta3"
    if not tool.is_file() or not tool.stat().st_mode & 0o111 or sha256(tool) != manifest["deltaTool"]["sha256"]:
        raise RuntimeError("Bundled xdelta3 helper failed integrity check")
    file_report = subprocess.run(["file", str(tool)], text=True, capture_output=True, check=True).stdout
    if "universal binary" not in file_report or "x86_64" not in file_report or "arm64" not in file_report:
        raise RuntimeError("Bundled xdelta3 helper is not universal arm64/x86_64")
    print(json.dumps({
        "locales": len(languages),
        "artifacts": len(artifacts),
        "payloadBytes": sum(path.stat().st_size for path in PAYLOAD.rglob("*") if path.is_file()),
        "imagesModified": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
