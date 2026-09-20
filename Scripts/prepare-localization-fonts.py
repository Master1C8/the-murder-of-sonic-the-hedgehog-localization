#!/usr/bin/env python3
"""Prepare the pinned VN Revival font set from verified upstream Noto files.

The script never downloads files.  Supply the exact upstream files in
``--source-dir``; their SHA-256 values are verified before any output is made.
FontTools 4.60.2 is pinned because merged binary output is version-sensitive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import fontTools
from fontTools.merge import Merger


FONTTOOLS_VERSION = "4.60.2"
LICENSE_FILE = "OFL-Noto.txt"
LICENSE_SHA256 = "0dab92d0544f7b233403f14b84a663bdbfa746982eda629e7f4f9ffe1b036feb"

SOURCES = {
    "NotoSans-Regular.ttf": {
        "sha256": "b85c38ecea8a7cfb39c24e395a4007474fa5a4fc864f6ee33309eb4948d232d5",
        "url": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
    },
    "NotoSansArabic-Regular.ttf": {
        "sha256": "ceea25b464a656dc3b26849bab9356740401af62aedf1bfa8b7f0d9b75925b1b",
        "url": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf",
    },
    "NotoSansHebrew-Regular.ttf": {
        "sha256": "a7fa16fffb27bedb060a0866267c29e9859aeb9c21cc33f5b3aaf6eb062eca85",
        "url": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf",
    },
    "NotoSansDevanagari-Regular.ttf": {
        "sha256": "385e78e6359a9d88a0f243d53b1209d7548361ba2194e2b9ec779bcaa7e8949d",
        "url": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf",
    },
    "NotoSansThai-Regular.ttf": {
        "sha256": "404ddfb5ed0aaa6b6ec8a85700d682978992062d67da93903967b56cbd9a4acc",
        "url": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansThai/NotoSansThai-Regular.ttf",
    },
    "NotoSansCJKsc-Regular.otf": {
        "sha256": "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b",
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    },
    "NotoSansCJKtc-Regular.otf": {
        "sha256": "661161a320cfecc88b013bcda4868f462c92e19dbecc77438ca5ae13846a8533",
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf",
    },
    "NotoSansCJKjp-Regular.otf": {
        "sha256": "68a3fc98800b2a27b371f2fb79991daf3633bd89309d4ffaa6946fd587f375b5",
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf",
    },
    "NotoSansCJKkr-Regular.otf": {
        "sha256": "6bcb2a0703aa137e874fc2dffa85f6c21ba9a67fa329e81b8c801663af7e992a",
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Regular.otf",
    },
}

MERGES = {
    "NotoSansArabicLatin-Regular.ttf": ("NotoSans-Regular.ttf", "NotoSansArabic-Regular.ttf"),
    "NotoSansHebrewLatin-Regular.ttf": ("NotoSans-Regular.ttf", "NotoSansHebrew-Regular.ttf"),
    "NotoSansDevanagariLatin-Regular.ttf": (
        "NotoSans-Regular.ttf",
        "NotoSansDevanagari-Regular.ttf",
    ),
    "NotoSansThaiLatin-Regular.ttf": ("NotoSans-Regular.ttf", "NotoSansThai-Regular.ttf"),
}

COPIES = (
    "NotoSans-Regular.ttf",
    "NotoSansCJKsc-Regular.otf",
    "NotoSansCJKtc-Regular.otf",
    "NotoSansCJKjp-Regular.otf",
    "NotoSansCJKkr-Regular.otf",
)

EXPECTED_OUTPUTS = {
    "NotoSans-Regular.ttf": SOURCES["NotoSans-Regular.ttf"]["sha256"],
    "NotoSansArabicLatin-Regular.ttf": "f93d0f17bcbc02ec3c73aad54d8291aba84924069545c99a31f9bf2edc95d2ba",
    "NotoSansHebrewLatin-Regular.ttf": "5d47c2310ef31393df8029d9a85db065133ab7132505248710482cf2d243e694",
    "NotoSansDevanagariLatin-Regular.ttf": "0170c95346aa3984f3b9d96260333e7f58d8b15608c17810aa527b898fbec794",
    "NotoSansThaiLatin-Regular.ttf": "587d24571c0509bf756c9062ad58556fdfbd00163660167557ce1515ebbbb631",
    "NotoSansCJKsc-Regular.otf": SOURCES["NotoSansCJKsc-Regular.otf"]["sha256"],
    "NotoSansCJKtc-Regular.otf": SOURCES["NotoSansCJKtc-Regular.otf"]["sha256"],
    "NotoSansCJKjp-Regular.otf": SOURCES["NotoSansCJKjp-Regular.otf"]["sha256"],
    "NotoSansCJKkr-Regular.otf": SOURCES["NotoSansCJKkr-Regular.otf"]["sha256"],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"Required file is missing: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"SHA-256 mismatch for {path.name}: {actual} != {expected}")


def prepare(args: argparse.Namespace) -> int:
    if fontTools.__version__ != FONTTOOLS_VERSION:
        raise SystemExit(
            f"FontTools {FONTTOOLS_VERSION} is required for reproducible output; "
            f"found {fontTools.__version__}"
        )
    source_dir = args.source_dir.resolve()
    output_dir = args.output.resolve()
    for filename, metadata in SOURCES.items():
        verify(source_dir / filename, metadata["sha256"])
    verify(source_dir / LICENSE_FILE, LICENSE_SHA256)

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in COPIES:
        shutil.copyfile(source_dir / filename, output_dir / filename)
    for output_name, input_names in MERGES.items():
        font = Merger().merge([str(source_dir / name) for name in input_names])
        # FontTools otherwise stamps the current time into ``head.modified``,
        # making an equivalent build produce a different binary and SHA-256.
        font.recalcTimestamp = False
        font["head"].created = 2082844800
        font["head"].modified = 2082844800
        font.save(output_dir / output_name)
    shutil.copyfile(source_dir / LICENSE_FILE, output_dir / "OFL-1.1.txt")

    for filename, expected in EXPECTED_OUTPUTS.items():
        verify(output_dir / filename, expected)
    verify(output_dir / "OFL-1.1.txt", LICENSE_SHA256)

    manifest = {
        "schemaVersion": 1,
        "license": {
            "identifier": "OFL-1.1",
            "file": "OFL-1.1.txt",
            "sha256": LICENSE_SHA256,
        },
        "toolchain": {"fontTools": FONTTOOLS_VERSION},
        "sources": {
            name: {**metadata, "bytes": (source_dir / name).stat().st_size}
            for name, metadata in sorted(SOURCES.items())
        },
        "outputs": {
            name: {
                "sha256": expected,
                "bytes": (output_dir / name).stat().st_size,
                "recipe": (
                    {"kind": "merge", "inputs": list(MERGES[name])}
                    if name in MERGES
                    else {"kind": "verified-copy", "input": name}
                ),
            }
            for name, expected in sorted(EXPECTED_OUTPUTS.items())
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_dir),
                "fonts": len(EXPECTED_OUTPUTS),
                "fontTools": fontTools.__version__,
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source-dir", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(prepare(parser().parse_args()))
