#!/usr/bin/env python3
"""Capture guarded localized Sonic UI screens through Oculix."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG = PROJECT_ROOT / "Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"
PAYLOAD = PROJECT_ROOT / "Sources/MurderOfSonicLocalizationInstaller/Resources/LocalizationPayload"
INSTALLER_CORE = PROJECT_ROOT / "Sources/MurderOfSonicLocalizationInstaller/InstallerCore.swift"
PACKAGE_TYPES = PROJECT_ROOT / "Sources/MurderOfSonicLocalizationInstaller/PackageConfig.swift"
OCULIX_SCRIPT = SCRIPT_DIR / "qa_capture.sikuli"
TEMPLATE = SCRIPT_DIR / "templates/2x/main-menu.png"
OCULIX_JAR = Path("/Users/antonkrutov/Applications/Oculix/oculixide-4.0.0-macos.jar")
JAVA = Path("/opt/homebrew/opt/openjdk@17/bin/java")
MAGICK = Path("/opt/homebrew/bin/magick")
GAME_NAME = "The Murder of Sonic The Hedgehog"
GAME_BUNDLE_ID = "com.Sonic-Social.The-Murder-of-Sonic-The-Hedgehog"
GAME_PATTERN = "/The Murder of Sonic The Hedgehog.app/Contents/MacOS/The Murder of Sonic The Hedgehog"
GAME_ROOT = Path("/Users/antonkrutov/Library/Application Support/Steam/steamapps/common/Themurderofsonicthehedgehog")
RECEIPT = GAME_ROOT / ".vn-revival/fun.vnrevival.murder-of-sonic.languages/receipt.json"
SAVE = Path("/Users/antonkrutov/Library/Application Support/com.Sonic-Social.The-Murder-of-Sonic-The-Hedgehog/SaveData.data")
UPLOAD = PROJECT_ROOT / "Screenshots/upload"
REVIEW = PROJECT_ROOT / "Screenshots/evidence"

SCREENS = {
    "main-menu": {"order": "01", "slug": "main-menu"},
    "load-game": {"order": "02", "slug": "load-game"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def game_pids() -> list[int]:
    result = subprocess.run(["/usr/bin/pgrep", "-f", GAME_PATTERN], text=True, capture_output=True)
    return [int(value) for value in result.stdout.split() if value.isdigit()]


def stop_game() -> None:
    pids = game_pids()
    for sig, delay in ((signal.SIGINT, 4), (signal.SIGTERM, 3), (signal.SIGKILL, 1)):
        if not pids:
            return
        for pid in pids:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, sig)
        deadline = time.time() + delay
        while time.time() < deadline and game_pids():
            time.sleep(0.2)
        pids = game_pids()
    if pids:
        raise RuntimeError(f"game processes did not stop: {pids}")


def active_locale() -> str:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    return receipt["activeLanguage"]["runtimeCode"]


def compile_installer(runtime: Path) -> Path:
    output = runtime / "install-locale"
    run([
        "/usr/bin/xcrun", "swiftc", "-module-cache-path", str(runtime / "module-cache"),
        str(PACKAGE_TYPES), str(INSTALLER_CORE), str(SCRIPT_DIR / "install_locale.swift"),
        "-o", str(output),
    ])
    return output


def install_locale(installer: Path, locale: str) -> None:
    result = run([str(installer), locale, str(CONFIG), str(PAYLOAD)], capture_output=True)
    if f"installed-and-verified {locale}" not in result.stdout or active_locale() != locale:
        raise RuntimeError(f"locale verification failed for {locale}")


def launch_game() -> None:
    run(["/usr/bin/open", "steam://rungameid/2324650"])
    deadline = time.time() + 60
    while time.time() < deadline:
        if game_pids():
            time.sleep(3)
            run(["/usr/bin/open", "-b", GAME_BUNDLE_ID])
            time.sleep(2)
            return
        time.sleep(0.5)
    raise RuntimeError("the Steam game process did not start")


def run_oculix(runtime: Path, locale: str, screen: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([
        str(JAVA), "-jar", str(OCULIX_JAR), "-c", "-r", str(OCULIX_SCRIPT),
        "--", "capture", str(runtime), locale, screen,
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def image_size(path: Path) -> tuple[int, int]:
    result = run([str(MAGICK), "identify", "-format", "%w %h", str(path)], capture_output=True)
    width, height = result.stdout.split()
    return int(width), int(height)


def load_locales() -> list[dict[str, str]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    return [
        {"runtimeCode": item["runtimeCode"], "siteLocale": item["siteLocale"]}
        for item in config["languages"]
    ]


def prepare_runtime(runtime: Path) -> None:
    (runtime / "raw").mkdir()
    target = runtime / "templates/2x"
    target.mkdir(parents=True)
    shutil.copy2(TEMPLATE, target / "main-menu.png")
    load_game_template = SCRIPT_DIR / "templates/2x/load-game.png"
    if load_game_template.is_file():
        shutil.copy2(load_game_template, target / "load-game.png")
    for source, output in (
        (SCRIPT_DIR / "activate_app.swift", runtime / "activate-app"),
        (SCRIPT_DIR / "cg_input.swift", runtime / "cg-input"),
    ):
        run(["/usr/bin/xcrun", "swiftc", str(source), "-o", str(output)])


def write_evidence(
    locale: dict[str, str], screenshot: Path, prior: str, save_hash: str, screen: str
) -> None:
    width, height = image_size(screenshot)
    capture_method = (
        "Oculix 4.0.0 guarded main-menu recognition with native macOS screencapture"
        if screen == "main-menu"
        else "Oculix 4.0.0 guarded main-menu-to-load-game recognition with native macOS screencapture"
    )
    evidence = {
        "schemaVersion": 1,
        "date": dt.date.today().isoformat(),
        "runtimeLocale": locale["runtimeCode"],
        "publishingLocale": locale["siteLocale"],
        "screen": screen,
        "gameVersion": "1.01",
        "steamBuildID": "20535215",
        "captureMethod": capture_method,
        "resolution": {"width": width, "height": height},
        "automatedResult": "pass",
        "visualReview": {"status": "pending", "findings": []},
        "result": "capture-pass-review-pending",
        "activeLocaleVerified": active_locale() == prior,
        "restoration": {
            "priorLocale": prior,
            "localeRestored": active_locale() == prior,
            "saveWritten": sha256(SAVE) != save_hash,
        },
        "screenshot": {"file": os.path.relpath(screenshot, REVIEW), "sha256": sha256(screenshot)},
    }
    REVIEW.mkdir(parents=True, exist_ok=True)
    metadata = SCREENS[screen]
    path = REVIEW / (
        f"{locale['siteLocale']}-{metadata['order']}-{metadata['slug']}-evidence.json"
    )
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def capture(locale: dict[str, str], screen: str, replace: bool) -> None:
    if game_pids():
        raise RuntimeError("the game is already running")
    metadata = SCREENS[screen]
    output_name = f"{locale['siteLocale']}-{metadata['order']}-{metadata['slug']}"
    destination = UPLOAD / f"{output_name}.png"
    if destination.exists() and not replace:
        raise RuntimeError(f"output exists: {destination}")
    save_hash = sha256(SAVE)
    prior = active_locale()
    with tempfile.TemporaryDirectory(prefix="sonic-visual-qa-") as temporary:
        runtime = Path(temporary)
        prepare_runtime(runtime)
        installer = compile_installer(runtime)
        try:
            install_locale(installer, locale["runtimeCode"])
            launch_game()
            result = run_oculix(runtime, locale["runtimeCode"], screen)
            print(result.stdout, end="")
            if result.returncode:
                for name in ("failure.png", "oculix-failure.png"):
                    source = runtime / name
                    if source.is_file():
                        REVIEW.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, REVIEW / f"{output_name}-{name}")
                raise RuntimeError(f"Oculix failed for {locale['runtimeCode']}")
            source = runtime / "raw" / (
                f"{locale['runtimeCode']}-{metadata['order']}-{metadata['slug']}-raw.png"
            )
            if not source.is_file():
                raise RuntimeError(f"missing capture: {source}")
            UPLOAD.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        finally:
            stop_game()
            if active_locale() != prior:
                install_locale(installer, prior)
        if sha256(SAVE) != save_hash:
            raise RuntimeError("SaveData.data changed during capture")
        write_evidence(locale, destination, prior, save_hash, screen)
        print(f"visual-qa-complete {locale['runtimeCode']} {destination}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locale", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--screen", choices=sorted(SCREENS), default="main-menu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required_paths = [
        CONFIG, PAYLOAD, INSTALLER_CORE, PACKAGE_TYPES,
        SCRIPT_DIR / "activate_app.swift", SCRIPT_DIR / "cg_input.swift",
        OCULIX_JAR, JAVA, MAGICK, TEMPLATE, RECEIPT, SAVE,
    ]
    if args.screen == "load-game":
        required_paths.append(SCRIPT_DIR / "templates/2x/load-game.png")
    for required in required_paths:
        if not required.exists():
            raise RuntimeError(f"required dependency is missing: {required}")
    locales = load_locales()
    if args.list:
        for locale in locales:
            print(f"{locale['runtimeCode']} -> {locale['siteLocale']}")
        return 0
    if args.all:
        if args.locale:
            raise RuntimeError("locale cannot be combined with --all")
        for locale in locales:
            metadata = SCREENS[args.screen]
            stem = f"{locale['siteLocale']}-{metadata['order']}-{metadata['slug']}"
            destination = UPLOAD / f"{stem}.png"
            evidence_path = REVIEW / f"{stem}-evidence.json"
            if not args.replace and destination.is_file() and evidence_path.is_file():
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                result = evidence.get("result")
                if result in {"pass", "visual-review-failed", "capture-pass-review-pending"}:
                    print(f"skip-existing {locale['runtimeCode']} {result}")
                    continue
            capture(locale, args.screen, args.replace)
        return 0
    selected = next((item for item in locales if item["runtimeCode"] == args.locale), None)
    if selected is None:
        raise RuntimeError("choose a locale or use --all")
    capture(selected, args.screen, args.replace)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
