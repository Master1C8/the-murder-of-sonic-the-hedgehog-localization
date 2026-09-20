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
)

SHAPING_REQUIRED = {"ar", "fa", "hi", "th"}
BIDI_REQUIRED = {"ar", "fa", "he"}
COMPLEX_LOCALES = {"ar", "fa", "he", "hi", "th"}
SCRIPT_RANGES = {
    "ar": ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)),
    "fa": ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)),
    "he": ((0x0590, 0x05FF),),
    "hi": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "th": ((0x0E00, 0x0E7F),),
}
TMP_TAG = re.compile(
    r"<br>|</?(?:style|size|color|i)(?:=[^<>]*)?>",
    re.IGNORECASE,
)


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


def has_target_script(locale: str, value: str) -> bool:
    return any(
        start <= ord(character) <= end
        for character in value
        for start, end in SCRIPT_RANGES[locale]
    )


def font_path(font_root: Path, locale: str) -> Path:
    filename = LOCALE_FONTS[locale]
    return font_root / "Complex" / filename if locale in COMPLEX_LOCALES else font_root / filename


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
    complex_manifest_path = font_root / "Complex" / "manifest.json"
    complex_manifest: dict[str, Any] = {}
    if not complex_manifest_path.is_file():
        raise SystemExit(f"Complex-script font manifest is missing: {complex_manifest_path}")
    complex_manifest = json.loads(complex_manifest_path.read_text(encoding="utf-8"))

    fonts: dict[str, dict[str, Any]] = {}
    cmaps: dict[str, set[int]] = {}
    errors: list[str] = []
    for locale in LOCALES:
        filename = LOCALE_FONTS[locale]
        if filename in fonts:
            continue
        path = font_path(font_root, locale)
        if not path.is_file():
            errors.append(f"font is missing: {filename}")
            continue
        details, cmap = inspect_font(path)
        source_manifest = complex_manifest if locale in COMPLEX_LOCALES else font_manifest
        expected = source_manifest.get("outputs", {}).get(filename, {}).get("sha256")
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
        shaping_result: dict[str, Any] | None = None
        if locale in COMPLEX_LOCALES:
            map_path = font_root / "Complex" / f"{locale}.shaping.json"
            if not map_path.is_file():
                errors.append(f"shaping map is missing: {locale}")
            else:
                shaping_map = json.loads(map_path.read_text(encoding="utf-8"))
                exact = {
                    row["logical"]: row["shaped"]
                    for key in ("runtimeEntries", "imageEntries")
                    for row in shaping_map.get(key, [])
                }
                script_values = [value for value in values if has_target_script(locale, value)]
                unmapped = [value for value in script_values if value not in exact]
                malformed = []
                generated_pua = set()
                for logical, shaped in exact.items():
                    if has_target_script(locale, TMP_TAG.sub("", shaped)):
                        malformed.append(logical)
                    if [match.group(0) for match in TMP_TAG.finditer(logical)] != [
                        match.group(0) for match in TMP_TAG.finditer(shaped)
                    ]:
                        malformed.append(logical)
                    generated_pua.update(
                        ord(character)
                        for character in shaped
                        if 0xE000 <= ord(character) <= 0xF8FF
                    )
                missing_pua = sorted(generated_pua - cmaps.get(font_name, set()))
                manifest_row = next(
                    (
                        row
                        for row in complex_manifest.get("locales", [])
                        if row.get("locale") == locale
                    ),
                    {},
                )
                map_errors = []
                if shaping_map.get("locale") != locale:
                    map_errors.append("locale")
                if shaping_map.get("overlay", {}).get("sha256") != sha256_file(overlay_path):
                    map_errors.append("overlay-hash")
                if shaping_map.get("imagePlan", {}).get("sha256") != sha256_file(images_path):
                    map_errors.append("image-hash")
                if shaping_map.get("preparedFontSha256") != sha256_file(font_path(font_root, locale)):
                    map_errors.append("font-hash")
                if manifest_row.get("mapSha256") != sha256_file(map_path):
                    map_errors.append("manifest-map-hash")
                if shaping_map.get("rightToLeft") is not (locale in BIDI_REQUIRED):
                    map_errors.append("direction")
                if unmapped:
                    map_errors.append(f"unmapped:{len(unmapped)}")
                if malformed:
                    map_errors.append(f"malformed:{len(set(malformed))}")
                if missing_pua:
                    map_errors.append(f"missing-pua:{len(missing_pua)}")
                if map_errors:
                    errors.append(f"complex-script preparation failed for {locale}: {', '.join(map_errors)}")
                shaping_result = {
                    "map": map_path.name,
                    "mapSha256": sha256_file(map_path),
                    "exactEntries": len(exact),
                    "spanEntries": len(shaping_map.get("spanEntries", [])),
                    "generatedPuaCodepoints": len(generated_pua),
                    "unmappedScriptValues": len(unmapped),
                    "malformedEntries": len(set(malformed)),
                    "missingPuaCodepoints": [f"U+{value:04X}" for value in missing_pua],
                    "staticPreparation": "pass" if not map_errors else "fail",
                }
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
            "complexScript": shaping_result,
            "runtimeReadability": "not-run",
        }

    complex_ready = {
        locale: (locale_results.get(locale, {}).get("complexScript") or {}).get(
            "staticPreparation"
        )
        == "pass"
        for locale in COMPLEX_LOCALES
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
        "complexScriptManifest": {
            "path": str(complex_manifest_path.relative_to(project_root))
            if complex_manifest_path.is_relative_to(project_root)
            else str(complex_manifest_path),
            "sha256": sha256_file(complex_manifest_path),
        },
        "fonts": fonts,
        "locales": locale_results,
        "gates": {
            "fontBinaryIntegrity": "pass" if not any("font" in error for error in errors) else "fail",
            "staticGlyphCoverage": "pass" if not any("coverage" in error for error in errors) else "fail",
            "complexScriptShaping": (
                "pass" if all(complex_ready.values()) else "fail"
            ),
            "bidirectionalLayout": (
                "static-pass-runtime-not-run"
                if all(complex_ready[locale] for locale in BIDI_REQUIRED)
                else "fail"
            ),
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
