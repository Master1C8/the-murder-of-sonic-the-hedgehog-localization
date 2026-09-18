#!/usr/bin/env python3
"""Install or restore a hash-locked development runtime patch.

This helper is intentionally separate from the unified 30-language release
installer.  It accepts only the development manifest produced by
extract-localization-assets.py and keeps verified originals beside the game.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any


APP_ID = "2324650"
BUILD_ID = "20535215"
STATE_DIRECTORY = Path(".vn-revival/dev-russian-runtime")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_value(text: str, key: str) -> str | None:
    match = re.search(rf'^\s*"{re.escape(key)}"\s+"([^"]*)"\s*$', text, flags=re.MULTILINE)
    return match.group(1) if match else None


def safe_relative(root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        raise SystemExit(f"Unsafe manifest path: {value}")
    result = (root / Path(*relative.parts)).resolve()
    if result != root and root not in result.parents:
        raise SystemExit(f"Manifest path escapes its root: {value}")
    return result


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], Path, Path]:
    manifest = json.loads(args.patch_manifest.read_text(encoding="utf-8"))
    if manifest.get("kind") != "russian-development-runtime-patch" or not manifest.get("developmentOnly"):
        raise SystemExit("Refusing a non-development patch manifest")
    if manifest.get("steamAppId") != APP_ID or manifest.get("steamBuildId") != BUILD_ID:
        raise SystemExit("Development patch targets a different Steam build")
    if manifest.get("imagesModified") is not False:
        raise SystemExit("Development patch must not modify images")

    steam_text = args.steam_manifest.read_text(encoding="utf-8")
    if manifest_value(steam_text, "appid") != APP_ID:
        raise SystemExit("Steam manifest has the wrong App ID")
    if manifest_value(steam_text, "buildid") != BUILD_ID:
        raise SystemExit("Installed Steam build is unsupported")
    install_dir = manifest_value(steam_text, "installdir")
    if not install_dir:
        raise SystemExit("Steam manifest has no install directory")
    expected_root = (args.steam_manifest.parent / "common" / install_dir).resolve()
    data_root = args.data_root.resolve()
    app_bundle = data_root.parent.parent.parent
    game_root = app_bundle.parent
    if game_root != expected_root:
        raise SystemExit("Data directory is not tied to the supplied Steam manifest")
    return manifest, game_root, data_root


def install(args: argparse.Namespace) -> int:
    manifest, game_root, data_root = validate_inputs(args)
    payload_root = args.patch_manifest.parent.resolve()
    state_root = game_root / STATE_DIRECTORY
    backup_root = state_root / "original-backup"
    transaction = state_root / "transaction"
    staged_root = transaction / "staged"
    rollback_root = transaction / "rollback"
    receipt = state_root / "receipt.json"
    if transaction.exists():
        raise SystemExit(f"Interrupted transaction requires manual review: {transaction}")
    staged_root.mkdir(parents=True)
    rollback_root.mkdir(parents=True)

    files: list[dict[str, Any]] = manifest["files"]
    destinations: list[tuple[dict[str, Any], Path, Path, Path]] = []
    try:
        for item in files:
            relative = item["path"]
            payload = safe_relative(payload_root, relative)
            destination = safe_relative(data_root, relative)
            backup = safe_relative(backup_root, relative)
            staged = safe_relative(staged_root, relative)
            if not payload.is_file() or sha256_file(payload) != item["patchedSha256"]:
                raise RuntimeError(f"Payload hash mismatch: {relative}")
            if not destination.is_file():
                raise RuntimeError(f"Installed file is missing: {relative}")
            current = sha256_file(destination)
            if current not in (item["originalSha256"], item["patchedSha256"]):
                raise RuntimeError(f"Foreign modification detected: {relative}")
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                if sha256_file(backup) != item["originalSha256"]:
                    raise RuntimeError(f"Damaged original backup: {relative}")
            else:
                if current != item["originalSha256"]:
                    raise RuntimeError(f"Original backup is unavailable: {relative}")
                shutil.copy2(destination, backup)
                if sha256_file(backup) != item["originalSha256"]:
                    raise RuntimeError(f"Could not verify original backup: {relative}")
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(payload, staged)
            if sha256_file(staged) != item["patchedSha256"]:
                raise RuntimeError(f"Could not verify staged payload: {relative}")
            destinations.append((item, destination, staged, safe_relative(rollback_root, relative)))

        installed: list[tuple[dict[str, Any], Path, Path]] = []
        try:
            for item, destination, staged, rollback in destinations:
                rollback.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, rollback)
                os.replace(staged, destination)
                if sha256_file(destination) != item["patchedSha256"]:
                    raise RuntimeError(f"Installed hash mismatch: {item['path']}")
                installed.append((item, destination, rollback))
        except Exception:
            for _, destination, rollback in reversed(installed):
                if rollback.exists():
                    os.replace(rollback, destination)
            raise

        receipt_data = {
            "kind": manifest["kind"],
            "steamAppId": APP_ID,
            "steamBuildId": BUILD_ID,
            "sourceFingerprint": manifest["sourceFingerprint"],
            "targetLocale": manifest["targetLocale"],
            "files": files,
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt_tmp = transaction / "receipt.json"
        receipt_tmp.write_text(json.dumps(receipt_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(receipt_tmp, receipt)
    finally:
        if transaction.exists():
            shutil.rmtree(transaction)

    print(json.dumps({"installed": len(files), "receipt": str(receipt)}, ensure_ascii=False))
    return 0


def restore(args: argparse.Namespace) -> int:
    manifest, game_root, data_root = validate_inputs(args)
    state_root = game_root / STATE_DIRECTORY
    backup_root = state_root / "original-backup"
    files: list[dict[str, Any]] = manifest["files"]
    for item in files:
        destination = safe_relative(data_root, item["path"])
        backup = safe_relative(backup_root, item["path"])
        if not destination.is_file() or sha256_file(destination) != item["patchedSha256"]:
            raise SystemExit(f"Refusing to overwrite an unexpected current file: {item['path']}")
        if not backup.is_file() or sha256_file(backup) != item["originalSha256"]:
            raise SystemExit(f"Original backup is unavailable or damaged: {item['path']}")
    for item in files:
        destination = safe_relative(data_root, item["path"])
        backup = safe_relative(backup_root, item["path"])
        temporary = destination.with_name(destination.name + ".vn-revival-restore")
        shutil.copy2(backup, temporary)
        if sha256_file(temporary) != item["originalSha256"]:
            raise SystemExit(f"Restore staging hash mismatch: {item['path']}")
        os.replace(temporary, destination)
    print(json.dumps({"restored": len(files), "backupPreserved": str(backup_root)}, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name, handler in (("install", install), ("restore", restore)):
        command = subparsers.add_parser(name)
        command.add_argument("--patch-manifest", type=Path, required=True)
        command.add_argument("--steam-manifest", type=Path, required=True)
        command.add_argument("--data-root", type=Path, required=True)
        command.set_defaults(handler=handler)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.handler(arguments))
