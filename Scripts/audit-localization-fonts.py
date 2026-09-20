#!/usr/bin/env python3
"""Audit exact localized corpora against the pinned prepared font set."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from fontTools.ttLib import TTFont


LOCALES = (
    "ar", "bg", "cs", "de", "el", "es", "es-419", "fa", "fil", "fr",
    "he", "hi", "hu", "id", "it", "ja", "ko", "nl", "pl", "pt-BR",
    "ro", "ru", "sr", "sw", "th", "tr", "uk", "vi", "zh", "zh-TW",
)

LOCALE_FONTS = {locale: "NotoSans-Regular.ttf" for locale in LOCALES}
LOCALE_FONTS.update(
    {
        "ar": "NotoSansArabicLatin-Regular.ttf",
        "fa": "NotoSansArabicLatin-Regular.ttf",
        "he": "NotoSansHebrewLatin-Regular.ttf",
        "hi": "NotoSansDevanagariLatin-Regular.ttf",
        "th": "NotoSansThaiLatin-Regular.ttf",
        "ja": "NotoSansCJKjp-Regular.otf",
        "ko": "NotoSansCJKkr-Regular.otf",
        "zh": "NotoSansCJKsc-Regular.otf",
        "zh-TW": "NotoSansCJKtc-Regular.otf",
    }
)

SHAPING_REQUIRED = {"ar", "fa", "hi", "th"}
BIDI_REQUIRED = {"ar", "fa", "he"}
TMP_TAG = re.compile(r"<[^<>]*>")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def name_value(font: TTFont, name_id: int) -> str | None:
    for record in font["name"].names:
        if record.nameID == name_id:
            try:
                return record.toUnicode()
            except UnicodeDecodeError:
                continue
    return None


def layout_tags(font: TTFont, table_name: str, field: str) -> list[str]:
    if table_name not in font:
        return []
    table = font[table_name].table
    records = getattr(getattr(table, field, None), field.replace("List", "Record"), None)
    if records is None:
        records = getattr(getattr(table, field, None), "ScriptRecord" if field == "ScriptList" else "FeatureRecord", [])
    attribute = "ScriptTag" if field == "ScriptList" else "FeatureTag"
    return sorted({getattr(record, attribute) for record in records})


def image_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    images = document.get("images")
    if isinstance(images, list):
        return images
    if isinstance(images, dict):
        return list(images.values())
    raise ValueError("images must be an array or object")


def iter_visible_characters(values: Iterable[str]) -> Iterable[str]:
    for value in values:
        for character in TMP_TAG.sub("", value):
            if character in "\n\r\t":
                continue
            yield character


def codepoint_row(codepoint: int) -> dict[str, Any]:
    character = chr(codepoint)
    return {
        "codepoint": f"U+{codepoint:04X}",
        "character": character,
        "name": unicodedata.name(character, "UNNAMED"),
        "category": unicodedata.category(character),
        "bidiClass": unicodedata.bidirectional(character),
    }


def inspect_font(path: Path) -> tuple[dict[str, Any], set[int]]:
    font = TTFont(path, lazy=True)
    cmap = set((font.getBestCmap() or {}).keys())
    space_name = (font.getBestCmap() or {}).get(0x20)
    space_advance = font["hmtx"].metrics.get(space_name, (0, 0))[0] if space_name else 0
    result = {
        "file": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "family": name_value(font, 1),
        "style": name_value(font, 2),
        "version": name_value(font, 5),
        "postScriptName": name_value(font, 6),
        "license": name_value(font, 13),
        "licenseUrl": name_value(font, 14),
        "glyphCodepoints": len(cmap),
        "space": {"present": 0x20 in cmap, "advance": space_advance},
        "metrics": {
            "unitsPerEm": font["head"].unitsPerEm,
            "hheaAscent": font["hhea"].ascent,
            "hheaDescent": font["hhea"].descent,
            "hheaLineGap": font["hhea"].lineGap,
            "typoAscent": font["OS/2"].sTypoAscender,
            "typoDescent": font["OS/2"].sTypoDescender,
            "typoLineGap": font["OS/2"].sTypoLineGap,
        },
        "openType": {
            "gsubScripts": layout_tags(font, "GSUB", "ScriptList"),
            "gsubFeatures": layout_tags(font, "GSUB", "FeatureList"),
            "gposScripts": layout_tags(font, "GPOS", "ScriptList"),
            "gposFeatures": layout_tags(font, "GPOS", "FeatureList"),
        },
    }
    return result, cmap


def audit(args: argparse.Namespace) -> int:
    localization_root = args.localization_root.resolve()
    project_root = localization_root.parents[1]
    font_root = args.font_root.resolve()
    output = args.output.resolve()
    manifest_path = font_root / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Prepared-font manifest is missing: {manifest_path}")
    font_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    fonts: dict[str, dict[str, Any]] = {}
    cmaps: dict[str, set[int]] = {}
    errors: list[str] = []
    for filename in sorted(set(LOCALE_FONTS.values())):
        path = font_root / filename
        if not path.is_file():
            errors.append(f"font is missing: {filename}")
            continue
        details, cmap = inspect_font(path)
        expected = font_manifest.get("outputs", {}).get(filename, {}).get("sha256")
        if details["sha256"] != expected:
            errors.append(f"font hash does not match manifest: {filename}")
        if not details["space"]["present"] or details["space"]["advance"] <= 0:
            errors.append(f"font has no usable U+0020 advance: {filename}")
        if "SIL Open Font License" not in (details["license"] or ""):
            errors.append(f"font does not declare SIL Open Font License: {filename}")
        fonts[filename] = details
        cmaps[filename] = cmap

    locale_results: dict[str, Any] = {}
    for locale in LOCALES:
        overlay_path = localization_root / f"{locale}.overlay.json"
        images_path = localization_root / f"{locale}.images.manual.json"
        if not overlay_path.is_file() or not images_path.is_file():
            errors.append(f"locale inputs are missing: {locale}")
            continue
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        images = json.loads(images_path.read_text(encoding="utf-8"))
        rows = image_rows(images)
        if overlay.get("targetLocale") != locale or images.get("targetLocale") != locale:
            errors.append(f"target locale mismatch: {locale}")
        if len(overlay.get("units", {})) != 3547:
            errors.append(f"overlay does not contain 3,547 units: {locale}")
        if len(rows) != 10:
            errors.append(f"image plan does not contain 10 rows: {locale}")

        values = list(overlay.get("units", {}).values())
        values.extend(row.get("translation", "") for row in rows)
        if not all(isinstance(value, str) for value in values):
            errors.append(f"locale contains a non-string translation: {locale}")
            continue
        characters = set(iter_visible_characters(values))
        formatting = sorted(
            ord(character)
            for character in characters
            if unicodedata.category(character) in {"Cc", "Cf"}
        )
        rendered = sorted(
            ord(character)
            for character in characters
            if unicodedata.category(character) not in {"Cc", "Cf"}
        )
        font_name = LOCALE_FONTS[locale]
        missing = sorted(set(rendered) - cmaps.get(font_name, set()))
        if missing:
            errors.append(f"font coverage is incomplete for {locale}: {len(missing)} codepoints")
        locale_results[locale] = {
            "font": font_name,
            "overlay": {"path": overlay_path.name, "sha256": sha256_file(overlay_path)},
            "imagePlan": {"path": images_path.name, "sha256": sha256_file(images_path)},
            "textUnits": len(overlay.get("units", {})),
            "imageRows": len(rows),
            "renderedCodepointCount": len(rendered),
            "renderedCodepoints": [f"U+{value:04X}" for value in rendered],
            "formattingControls": [codepoint_row(value) for value in formatting],
            "missingCodepoints": [codepoint_row(value) for value in missing],
            "shapingRequired": locale in SHAPING_REQUIRED,
            "bidirectionalLayoutRequired": locale in BIDI_REQUIRED,
            "staticCoverage": "pass" if not missing else "fail",
            "runtimeReadability": "not-run",
        }

    report = {
        "schemaVersion": 1,
        "kind": "localization-font-audit",
        "localesExpected": len(LOCALES),
        "localesAudited": len(locale_results),
        "sourceFontManifest": {
            "path": str(manifest_path.relative_to(project_root))
            if manifest_path.is_relative_to(project_root)
            else str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "fonts": fonts,
        "locales": locale_results,
        "gates": {
            "fontBinaryIntegrity": "pass" if not any("font" in error for error in errors) else "fail",
            "staticGlyphCoverage": "pass" if not any("coverage" in error for error in errors) else "fail",
            "complexScriptShaping": "not-run",
            "bidirectionalLayout": "not-run",
            "runtimeReadability": "not-run",
        },
        "errors": errors,
        "ok": not errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "locales": len(locale_results),
                "fonts": len(fonts),
                "staticCoveragePassed": sum(
                    row["staticCoverage"] == "pass" for row in locale_results.values()
                ),
                "shapingRequired": sorted(SHAPING_REQUIRED),
                "bidiRequired": sorted(BIDI_REQUIRED),
                "errors": errors,
                "ok": not errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--localization-root", type=Path, required=True)
    result.add_argument("--font-root", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(audit(parser().parse_args()))
