#!/usr/bin/env python3
"""Build one reviewed locale against the verified Windows Steam assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
PATCH_BUILDER = PROJECT / "Scripts/extract-localization-assets.py"
WINDOWS_DEFAULTGROUP = "defaultgroup_assets_all_3a3b6c1fd8dd35a5213740db9e4c849e.bundle"
WINDOWS_INVENTORY = "inventoryitems_assets_all_98593d5b25d5883f9039e62e508fb742.bundle"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--shaping-map", type=Path)
    parser.add_argument("--font-name")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-locale", required=True)
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("extract_localization_assets", PATCH_BUILDER)
    if spec is None or spec.loader is None:
        raise SystemExit("Could not load the runtime patch builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DEFAULTGROUP_BUNDLE = WINDOWS_DEFAULTGROUP
    module.INVENTORY_BUNDLE = WINDOWS_INVENTORY
    overlay = json.loads(args.overlay.read_text(encoding="utf-8"))
    if overlay.get("targetLocale") != args.target_locale:
        raise SystemExit("The requested target locale does not match the overlay")
    return module.build_runtime_patch(args, None, "windows-locale-runtime-patch")


if __name__ == "__main__":
    raise SystemExit(main())
