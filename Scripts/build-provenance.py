#!/usr/bin/env python3
"""Build the existing translator locally and retain unsigned provenance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink material: " + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {
                "sha256": sha(path), "sizeBytes": path.stat().st_size}
    if not result:
        raise ValueError("Empty stage")
    return result


def verify(archive, stage, manifest):
    expected = {stage.name + "/" + name: row for name, row in inventory(stage).items()}
    expected[manifest.name] = {"sha256": sha(manifest), "sizeBytes": manifest.stat().st_size}
    with zipfile.ZipFile(archive) as package:
        files = [row for row in package.infolist() if not row.is_dir()]
        if len(files) != len(expected) or {row.filename for row in files} != set(expected):
            raise ValueError("Unexpected or duplicate archive files")
        for row in files:
            h = hashlib.sha256()
            with package.open(row) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if (row.file_size != expected[row.filename]["sizeBytes"]
                    or h.hexdigest() != expected[row.filename]["sha256"]):
                raise ValueError("Archive bytes differ: " + row.filename)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.release.resolve()
    if not out.is_relative_to(root / "dist") or out.exists():
        raise ValueError("Use a fresh release directory under canonical dist")
    if git(root, "branch", "--show-current") != "main" or git(root, "status", "--porcelain"):
        raise ValueError("Commit all reviewed source on canonical main")
    commit = git(root, "rev-parse", "HEAD")
    if git(root, "rev-parse", "origin/main") != commit:
        raise ValueError("Push source before building")
    repository = git(root, "remote", "get-url", "origin").removesuffix(".git")
    if repository != "https://github.com/Master1C8/the-murder-of-sonic-the-hedgehog-localization":
        raise ValueError("Unexpected repository")
    resources = {
        "macos": root / "Sources/MurderOfSonicLocalizationInstaller/Resources",
        "windows": root / "Windows/Resources",
    }
    materials = {platform: inventory(folder) for platform, folder in resources.items()}
    origin = root / "dist/retained-public-inputs/windows-payload-origin.json"
    origin_record = json.loads(origin.read_text())
    origin_hash = sha(origin)
    if inventory(resources["windows"] / "LocalizationPayload") != origin_record["files"]:
        raise ValueError("Retained Windows payload differs from verified public input")
    tools = {}
    for name in ["swift", "clang", "lipo", "codesign", "ditto", "x86_64-w64-mingw32-gcc",
                 "x86_64-w64-mingw32-windres", "magick", "python3"]:
        executable = shutil.which(name)
        if not executable:
            raise ValueError("Missing tool: " + name)
        if name in {"swift", "clang"} and executable == "/usr/bin/" + name:
            executable = subprocess.check_output(["xcrun", "--find", name], text=True).strip()
        tools[name] = {"path": str(Path(executable).resolve()), "sha256": sha(executable)}
    tools["swiftVersion"] = subprocess.check_output(["swift", "--version"], text=True).strip()
    tools["sdkVersion"] = subprocess.check_output(["xcrun", "--show-sdk-version"], text=True).strip()
    started = datetime.now(timezone.utc).isoformat()
    out.mkdir(parents=True)
    win = out / "Murder of Sonic - VN Revival Windows"
    win.mkdir()
    env = {**os.environ, "VNREVIVAL_RELEASE_DIR": str(out), "VNREVIVAL_WINDOWS_BUILD_DIR": str(win)}
    with (out / "build.log").open("x") as log:
        for command in [
            ["zsh", "Scripts/release-audit.sh"],
            ["zsh", "Scripts/build-windows-installer.sh"],
            ["python3", "Scripts/test-windows-runtime-payload.py", "--resources", str(resources["windows"])],
        ]:
            subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    shutil.copytree(resources["windows"], win / "Resources")
    shutil.copyfile(root / "Windows/install.ps1", win / "install.ps1")
    config = json.loads((resources["windows"] / "PackageConfig.json").read_text())
    locales = [row["siteLocale"] for row in config["languages"]]
    if len(set(locales)) != 30:
        raise ValueError("Expected 30 locales")
    manifest = {"schemaVersion": 1, "gameSlug": "the-murder-of-sonic-the-hedgehog",
                "platform": "windows", "locales": {locale: {"requiredPaths": [
                    "Resources/LocalizationPayload/F/shared/StreamingAssets/VNRevival/Locales/" + locale + ".story.json.gz"
                ]} for locale in locales}}
    for row in manifest["locales"].values():
        for name in row["requiredPaths"]:
            if not (win / name).is_file():
                raise ValueError("Missing locale input: " + name)
    (win / "vnrevival-locales.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if sha(origin) != origin_hash or materials != {platform: inventory(folder) for platform, folder in resources.items()}:
        raise ValueError("Payload changed during build")
    if git(root, "rev-parse", "HEAD") != commit or git(root, "status", "--porcelain"):
        raise ValueError("Source changed during build")
    records = []
    for platform, label, stage in [
        ("windows", "Windows", win), ("macos", "macOS", out / "Murder of Sonic — VN Revival.app")
    ]:
        archive = out / ("Sonic-Installer-" + label + "-0.2.1.zip")
        release = out / "vnrevival-release.json"
        release.write_text(json.dumps({"schemaVersion": 1, "gameSlug": manifest["gameSlug"],
            "platform": platform, "version": "0.2.1", "sourceCommit": commit,
            "sourceTreeClean": True, "repositoryUrl": repository,
            "recipe": "Scripts/build-provenance.py"}, indent=2) + "\n")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
            for name in inventory(stage):
                package.write(stage / name, stage.name + "/" + name)
            package.write(release, release.name)
        entries = verify(archive, stage, release)
        release.rename(out / (platform + "-vnrevival-release.json"))
        if archive.stat().st_size > 100_000_000:
            raise ValueError("Archive exceeds 100 MB")
        records.append({"platform": platform, "filename": archive.name, "sha256": sha(archive),
                        "sizeBytes": archive.stat().st_size, "verifiedEntries": entries})
    (out / "payload-materials.json").write_text(json.dumps(materials, indent=2) + "\n")
    shutil.copyfile(origin, out / "windows-payload-origin.json")
    (out / "source-tree.txt").write_text(git(root, "ls-tree", "-r", "--full-tree", commit) + "\n")
    (out / "SHA256SUMS").write_text("".join(r["sha256"] + "  " + r["filename"] + "\n" for r in records))
    (out / "provenance.json").write_text(json.dumps({
        "schemaVersion": 1, "version": "0.2.1",
        "source": {"repository": repository, "commit": commit, "tree": git(root, "rev-parse", "HEAD^{tree}")},
        "build": {"method": "local macOS compilation and Windows cross-compilation",
                  "recipe": "Scripts/build-provenance.py", "startedAt": started,
                  "completedAt": datetime.now(timezone.utc).isoformat(), "tools": tools,
                  "logSha256": sha(out / "build.log")},
        "materials": {"inventory": "payload-materials.json", "sha256": sha(out / "payload-materials.json"),
                      "retainedWindowsOrigin": "windows-payload-origin.json"},
        "artifacts": records,
        "assurance": {"statement": "unsigned local build record", "publisherSignature": None,
                      "notarization": None, "runtimeBoundary": "Native fixture tests and full payload checks; no new real-game run"}
    }, indent=2) + "\n")
    print(json.dumps({"sourceCommit": commit, "artifacts": records}))


if __name__ == "__main__":
    main()
