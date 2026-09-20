#!/usr/bin/env python3
"""Shape the exact complex-script corpora into deterministic TMP-safe PUA fonts.

TextMesh Pro 3.0 in the supported Unity 2021 player exposes no GSUB shaping
path while generating text geometry. This build-time tool uses HarfBuzz,
duplicates positioned glyph outlines into the BMP private-use area, and emits
a logical-to-shaped map. RTL strings stay in logical order and use TMP's own
``isRightToLeftText`` path exactly once. Authored overlays remain unchanged;
only derived runtime payloads consume the map.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import fontTools
import uharfbuzz
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


FONTTOOLS_VERSION = "4.60.2"
UHARFBUZZ_VERSION = "0.51.7"
PUA_START = 0xE000
PUA_END = 0xF8FF

LOCALE_SPECS = {
    "ar": {
        "source": "NotoSansArabicLatin-Regular.ttf",
        "output": "NotoSansArabicLatin-ar-Shaped.ttf",
        "script": "arab",
        "language": "ar",
        "baseDirection": "R",
        "ranges": ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)),
    },
    "fa": {
        "source": "NotoSansArabicLatin-Regular.ttf",
        "output": "NotoSansArabicLatin-fa-Shaped.ttf",
        "script": "arab",
        "language": "fa",
        "baseDirection": "R",
        "ranges": ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)),
    },
    "he": {
        "source": "NotoSansHebrewLatin-Regular.ttf",
        "output": "NotoSansHebrewLatin-he-Shaped.ttf",
        "script": "hebr",
        "language": "he",
        "baseDirection": "R",
        "ranges": ((0x0590, 0x05FF),),
    },
    "hi": {
        "source": "NotoSansDevanagariLatin-Regular.ttf",
        "output": "NotoSansDevanagariLatin-hi-Shaped.ttf",
        "script": "deva",
        "language": "hi",
        "baseDirection": "L",
        "ranges": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    },
    "th": {
        "source": "NotoSansThaiLatin-Regular.ttf",
        "output": "NotoSansThaiLatin-th-Shaped.ttf",
        "script": "thai",
        "language": "th",
        "baseDirection": "L",
        "ranges": ((0x0E00, 0x0E7F),),
    },
}

KNOWN_TMP_TAG = re.compile(
    r"<br>|</?(?:style|size|color|i)(?:=[^<>]*)?>",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def image_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    images = document.get("images")
    if isinstance(images, list):
        return images
    if isinstance(images, dict):
        return list(images.values())
    raise ValueError("images must be an array or object")


class FontAugmenter:
    def __init__(self, source: Path, spec: dict[str, Any]) -> None:
        self.source = source
        self.spec = spec
        self.font = TTFont(source)
        if "glyf" not in self.font:
            raise ValueError(f"Complex shaping requires a TrueType glyf font: {source}")
        self.source_glyph_order = list(self.font.getGlyphOrder())
        self.source_glyph_set = self.font.getGlyphSet()
        data = source.read_bytes()
        self.hb_face = uharfbuzz.Face(data)
        self.hb_font = uharfbuzz.Font(self.hb_face)
        self.hb_font.scale = (self.hb_face.upem, self.hb_face.upem)
        self.next_pua = PUA_START
        self.instances: dict[tuple[int, int, int, int], tuple[int, str]] = {}
        self.rows: list[dict[str, Any]] = []
        self.new_glyph_names: list[str] = []
        self.span_mappings: dict[str, str] = {}

    def is_script_character(self, character: str) -> bool:
        codepoint = ord(character)
        return any(start <= codepoint <= end for start, end in self.spec["ranges"])

    def is_span_character(self, character: str) -> bool:
        return (
            self.is_script_character(character)
            or character in {"\u200c", "\u200d"}
            or unicodedata.category(character).startswith("M")
        )

    def has_script(self, value: str) -> bool:
        return any(self.is_script_character(character) for character in value)

    def map_glyph(
        self,
        glyph_id: int,
        x_advance: int,
        x_offset: int,
        y_offset: int,
    ) -> str:
        if glyph_id <= 0 or glyph_id >= len(self.source_glyph_order):
            raise ValueError(f"HarfBuzz returned invalid glyph ID {glyph_id}")
        key = (glyph_id, x_advance, x_offset, y_offset)
        existing = self.instances.get(key)
        if existing is not None:
            return chr(existing[0])
        if self.next_pua > PUA_END:
            raise ValueError("Complex-script glyph instances exhausted the BMP private-use area")

        pua = self.next_pua
        self.next_pua += 1
        source_name = self.source_glyph_order[glyph_id]
        source_advance, source_lsb = self.font["hmtx"].metrics[source_name]
        if x_offset == 0 and y_offset == 0 and x_advance == source_advance:
            output_name = source_name
            duplicate = False
        else:
            output_name = f"vnrevival.{pua:04X}"
            pen = TTGlyphPen(self.source_glyph_set)
            transformed = TransformPen(pen, (1, 0, 0, 1, x_offset, y_offset))
            self.source_glyph_set[source_name].draw(transformed)
            glyph = pen.glyph()
            self.font["glyf"].glyphs[output_name] = glyph
            glyph.recalcBounds(self.font["glyf"])
            lsb = getattr(glyph, "xMin", source_lsb + x_offset)
            self.font["hmtx"].metrics[output_name] = (max(0, x_advance), lsb)
            self.new_glyph_names.append(output_name)
            duplicate = True

        self.instances[key] = (pua, output_name)
        self.rows.append(
            {
                "codepoint": f"U+{pua:04X}",
                "glyph": output_name,
                "sourceGlyph": source_name,
                "sourceGlyphId": glyph_id,
                "xAdvance": x_advance,
                "xOffset": x_offset,
                "yOffset": y_offset,
                "outlineDuplicated": duplicate,
            }
        )
        return chr(pua)

    def shape_span(
        self,
        characters: str,
    ) -> str:
        codepoints = [ord(character) for character in characters]
        buffer = uharfbuzz.Buffer()
        buffer.add_codepoints(codepoints)
        buffer.direction = "rtl" if self.spec["baseDirection"] == "R" else "ltr"
        buffer.script = self.spec["script"]
        buffer.language = self.spec["language"]
        uharfbuzz.shape(self.hb_font, buffer)
        result: list[str] = []
        for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
            result.append(
                self.map_glyph(
                    info.codepoint,
                    position.x_advance,
                    position.x_offset,
                    position.y_offset,
                )
            )
        if self.spec["baseDirection"] == "R":
            result.reverse()
        shaped = "".join(result)
        previous = self.span_mappings.get(characters)
        if previous is not None and previous != shaped:
            raise ValueError(f"Inconsistent shaping for span {characters!r}")
        self.span_mappings[characters] = shaped
        return shaped

    def shape_plain_text(self, value: str) -> str:
        if not self.has_script(value):
            return value
        output: list[str] = []
        index = 0
        while index < len(value):
            if self.is_span_character(value[index]):
                end = index + 1
                while end < len(value) and self.is_span_character(value[end]):
                    end += 1
                output.append(self.shape_span(value[index:end]))
                index = end
            else:
                output.append(value[index])
                index += 1
        return "".join(output)

    def shape_rich_text(self, value: str) -> str:
        if not self.has_script(value):
            return value
        output: list[str] = []
        position = 0
        for match in KNOWN_TMP_TAG.finditer(value):
            output.append(self.shape_plain_text(value[position : match.start()]))
            output.append(match.group(0))
            position = match.end()
        output.append(self.shape_plain_text(value[position:]))
        return "".join(output)

    def save(self, output: Path) -> None:
        if self.new_glyph_names:
            self.font.setGlyphOrder(self.font.getGlyphOrder() + self.new_glyph_names)
        for table in self.font["cmap"].tables:
            if table.isUnicode() and table.format in {4, 12}:
                for row in self.rows:
                    table.cmap[int(row["codepoint"][2:], 16)] = row["glyph"]
        self.font.recalcTimestamp = False
        self.font["head"].created = 2082844800
        self.font["head"].modified = 2082844800
        output.parent.mkdir(parents=True, exist_ok=True)
        self.font.save(output)


def unique_strings(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def known_tag_sequence(value: str) -> list[str]:
    return [match.group(0) for match in KNOWN_TMP_TAG.finditer(value)]


def validate_shaped_value(
    logical: str,
    shaped: str,
    augmenter: FontAugmenter,
    description: str,
) -> None:
    if known_tag_sequence(logical) != known_tag_sequence(shaped):
        raise ValueError(f"TMP tag sequence changed in {description}: {logical!r}")
    visible = KNOWN_TMP_TAG.sub("", shaped)
    if any(augmenter.is_script_character(character) for character in visible):
        raise ValueError(f"Unshaped target-script character remains in {description}: {logical!r}")
    if any(character in {"\u200c", "\u200d"} for character in visible):
        raise ValueError(f"Unshaped joiner remains in {description}: {logical!r}")


def prepare_locale(
    locale: str,
    spec: dict[str, Any],
    localization_root: Path,
    font_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    overlay_path = localization_root / f"{locale}.overlay.json"
    images_path = localization_root / f"{locale}.images.manual.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    images = json.loads(images_path.read_text(encoding="utf-8"))
    if overlay.get("targetLocale") != locale or images.get("targetLocale") != locale:
        raise ValueError(f"Target-locale mismatch for {locale}")
    overlay_values = unique_strings(overlay.get("units", {}).values())
    image_values = unique_strings(row["translation"] for row in image_rows(images))

    source_font = font_root / spec["source"]
    augmenter = FontAugmenter(source_font, spec)
    runtime_entries = []
    for logical in overlay_values:
        shaped = augmenter.shape_rich_text(logical)
        if shaped != logical:
            validate_shaped_value(logical, shaped, augmenter, f"{locale} runtime entry")
            runtime_entries.append({"logical": logical, "shaped": shaped})
    image_entries = []
    for logical in image_values:
        shaped = augmenter.shape_rich_text(logical)
        if shaped != logical:
            validate_shaped_value(logical, shaped, augmenter, f"{locale} image entry")
            image_entries.append({"logical": logical, "shaped": shaped})

    font_path = output_root / spec["output"]
    augmenter.save(font_path)
    reloaded = TTFont(font_path, lazy=True)
    prepared_cmap = reloaded.getBestCmap() or {}
    missing_pua = [
        row["codepoint"]
        for row in augmenter.rows
        if int(row["codepoint"][2:], 16) not in prepared_cmap
    ]
    if missing_pua:
        raise ValueError(
            f"Prepared font {font_path.name} is missing {len(missing_pua)} generated PUA mappings"
        )
    reloaded.close()
    map_path = output_root / f"{locale}.shaping.json"
    shaping_map = {
        "schemaVersion": 1,
        "kind": "vn-revival-complex-script-map",
        "locale": locale,
        "sourceFont": spec["source"],
        "sourceFontSha256": sha256_file(source_font),
        "preparedFont": spec["output"],
        "preparedFontSha256": sha256_file(font_path),
        "overlay": {"path": overlay_path.name, "sha256": sha256_file(overlay_path)},
        "imagePlan": {"path": images_path.name, "sha256": sha256_file(images_path)},
        "runtimeEntries": runtime_entries,
        "imageEntries": image_entries,
        "spanEntries": [
            {"logical": logical, "shaped": shaped}
            for logical, shaped in sorted(augmenter.span_mappings.items())
        ],
        "rightToLeft": spec["baseDirection"] == "R",
        "glyphInstances": augmenter.rows,
        "puaRange": {
            "first": f"U+{PUA_START:04X}",
            "lastUsed": f"U+{augmenter.next_pua - 1:04X}",
            "count": len(augmenter.rows),
        },
        "toolchain": {
            "fontTools": fontTools.__version__,
            "uharfbuzz": uharfbuzz.__version__,
            "harfBuzzRuntime": uharfbuzz.version_string(),
        },
    }
    map_path.write_text(
        json.dumps(shaping_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "locale": locale,
        "font": spec["output"],
        "fontSha256": sha256_file(font_path),
        "fontBytes": font_path.stat().st_size,
        "map": map_path.name,
        "mapSha256": sha256_file(map_path),
        "runtimeEntries": len(runtime_entries),
        "imageEntries": len(image_entries),
        "glyphInstances": len(augmenter.rows),
        "logicalCorpusSha256": compact_sha256(overlay_values + image_values),
    }


def prepare(args: argparse.Namespace) -> int:
    if fontTools.__version__ != FONTTOOLS_VERSION:
        raise SystemExit(f"FontTools {FONTTOOLS_VERSION} is required; found {fontTools.__version__}")
    if uharfbuzz.__version__ != UHARFBUZZ_VERSION:
        raise SystemExit(
            f"uharfbuzz {UHARFBUZZ_VERSION} is required; found {uharfbuzz.__version__}"
        )
    localization_root = args.localization_root.resolve()
    font_root = args.font_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    results = [
        prepare_locale(locale, spec, localization_root, font_root, output_root)
        for locale, spec in LOCALE_SPECS.items()
    ]
    manifest = {
        "schemaVersion": 1,
        "kind": "vn-revival-complex-script-fonts",
        "locales": results,
        "outputs": {
            row["font"]: {
                "sha256": row["fontSha256"],
                "bytes": row["fontBytes"],
                "locale": row["locale"],
                "shapingMap": row["map"],
            }
            for row in results
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output_root), "locales": results}, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--localization-root", type=Path, required=True)
    result.add_argument("--font-root", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(prepare(parser().parse_args()))
