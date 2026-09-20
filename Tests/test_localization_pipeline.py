import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "Scripts" / "extract-localization-assets.py"
SPEC = importlib.util.spec_from_file_location("localization_assets", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
localization_assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(localization_assets)


class RuntimeIdentifierSafetyTests(unittest.TestCase):
    def test_checked_in_runtime_exact_manifest_matches_compiled_ink(self) -> None:
        localization_root = PROJECT_ROOT / "Documentation" / "Localization"
        inventory = json.loads((localization_root / "inventory.json").read_text(encoding="utf-8"))
        story = json.loads((localization_root / "story.en.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            (localization_root / "runtime-exact-values.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest,
            localization_assets.build_runtime_exact_manifest(inventory, story),
        )
        self.assertEqual(len(manifest["controls"]), 49)
        self.assertEqual(
            sum(1 for row in manifest["controls"] if row["overlayRequired"]),
            45,
        )
        self.assertEqual(len(manifest["inlinePrefixes"]), 5)

    def test_runtime_exact_validation_rejects_translated_control_and_prefix(self) -> None:
        inventory = {
            "source": {"fingerprint": "source"},
            "story": {"storySha256": "story"},
        }
        manifest = {
            "sourceFingerprint": "source",
            "sourceStorySha256": "story",
            "controls": [
                {"id": "control", "value": "True", "overlayRequired": True}
            ],
            "inlinePrefixes": [
                {"id": "wife", "prefix": "Conductor’s Wife:: "}
            ],
        }
        artifact = {"units": {"control": "Vrai", "wife": "Épouse:: Bonjour"}}
        errors = localization_assets.runtime_exact_errors(inventory, artifact, manifest)
        self.assertEqual(
            [row["error"] for row in errors],
            ["runtime control value changed", "runtime inline prefix changed"],
        )

    def test_save_slot_collision_guards_cover_every_locale(self) -> None:
        localization_root = PROJECT_ROOT / "Documentation" / "Localization"
        inventory = json.loads((localization_root / "inventory.json").read_text(encoding="utf-8"))
        locales = sorted(localization_assets.LOCALE_FALLBACK_FONTS)
        self.assertEqual(len(locales), 30)
        for locale in locales:
            with self.subTest(locale=locale):
                overlay = json.loads(
                    (localization_root / f"{locale}.overlay.json").read_text(encoding="utf-8")
                )
                effective = localization_assets.effective_level0_layout_overrides(overlay)
                self.assertEqual(
                    effective["unity:level0:1538:m_text"],
                    {"m_fontSize": 18.0, "m_fontSizeBase": 18.0},
                )
                self.assertLessEqual(
                    effective["unity:level0:1553:m_text"]["m_fontSize"], 28.0
                )
                self.assertLessEqual(
                    effective["unity:level0:1553:m_text"]["m_fontSizeBase"], 28.0
                )
                self.assertEqual(
                    localization_assets.validate_layout_overrides(inventory, overlay), []
                )

        russian = json.loads((localization_root / "ru.overlay.json").read_text(encoding="utf-8"))
        rings = "unity:defaultgroup:-4932669119767755847:m_text"
        self.assertEqual(russian["units"][rings], "КОЛЬЦА")
        self.assertEqual(
            russian["layoutOverrides"][rings],
            {"m_fontSize": 46.0, "m_fontSizeBase": 46.0},
        )

    def test_save_slot_collision_guard_rejects_larger_locale_override(self) -> None:
        overlay = {
            "layoutOverrides": {
                "unity:level0:1538:m_text": {
                    "m_fontSize": 24.0,
                    "m_fontSizeBase": 24.0,
                }
            }
        }
        with self.assertRaises(SystemExit):
            localization_assets.effective_level0_layout_overrides(overlay)

    def test_layout_overrides_reject_runtime_or_unknown_fields(self) -> None:
        inventory = {
            "units": [
                {
                    "id": "unity:defaultgroup:1:m_text",
                    "sourceAsset": localization_assets.DEFAULTGROUP_BUNDLE,
                }
            ]
        }
        overlay = {
            "layoutOverrides": {
                "unity:defaultgroup:1:m_text": {
                    "m_fontSize": 46.0,
                    "m_text": "changed",
                }
            }
        }
        self.assertEqual(
            localization_assets.validate_layout_overrides(inventory, overlay),
            ["unsupported layout fields for unity:defaultgroup:1:m_text: m_text"],
        )

    def test_level0_layout_override_patches_only_requested_font_fields(self) -> None:
        import struct

        text = "Вагон"
        encoded = text.encode("utf-8")
        padding = b"\0" * ((4 - len(encoded) % 4) % 4)
        text_end = 92 + len(encoded) + len(padding)
        raw = bytearray(text_end + 240)
        raw[88:92] = len(encoded).to_bytes(4, "little")
        raw[92 : 92 + len(encoded)] = encoded
        struct.pack_into("<f", raw, text_end + 192, 36.0)
        struct.pack_into("<f", raw, text_end + 196, 36.0)
        patched = localization_assets.replace_level0_layout(
            bytes(raw),
            {"m_fontSize": 28.0, "m_fontSizeBase": 28.0},
            "unity:level0:1553:m_text",
        )
        self.assertEqual(struct.unpack_from("<f", patched, text_end + 192)[0], 28.0)
        self.assertEqual(struct.unpack_from("<f", patched, text_end + 196)[0], 28.0)
        self.assertEqual(patched[: text_end + 192], bytes(raw[: text_end + 192]))
        self.assertEqual(patched[text_end + 200 :], bytes(raw[text_end + 200 :]))
        self.assertEqual(
            localization_assets.read_level0_layout(
                patched,
                ("m_fontSize", "m_fontSizeBase"),
                "unity:level0:1553:m_text",
            ),
            {"m_fontSize": 28.0, "m_fontSizeBase": 28.0},
        )

    def test_level0_layout_override_is_allowed(self) -> None:
        inventory = {
            "units": [
                {
                    "id": "unity:level0:1553:m_text",
                    "sourceAsset": "level0",
                }
            ]
        }
        overlay = {
            "layoutOverrides": {
                "unity:level0:1553:m_text": {
                    "m_fontSize": 28.0,
                    "m_fontSizeBase": 28.0,
                }
            }
        }
        self.assertEqual(
            localization_assets.validate_layout_overrides(inventory, overlay), []
        )

    def test_level0_rtl_flag_tracks_the_padded_localized_text_end(self) -> None:
        text = "واجهة"
        encoded = text.encode("utf-8")
        padding = b"\0" * ((4 - len(encoded) % 4) % 4)
        text_end = 92 + len(encoded) + len(padding)
        raw = bytearray(text_end + 8)
        raw[88:92] = len(encoded).to_bytes(4, "little")
        raw[92 : 92 + len(encoded)] = encoded
        patched = localization_assets.replace_level0_rtl(
            bytes(raw), True, "unity:level0:1:m_text"
        )
        self.assertEqual(patched[text_end], 1)
        self.assertEqual(patched[:text_end], bytes(raw[:text_end]))
        self.assertEqual(patched[text_end + 1 :], bytes(raw[text_end + 1 :]))

    def test_managed_control_strings_are_never_confirmed_ui(self) -> None:
        self.assertTrue(localization_assets.PROTECTED_MANAGED_CONTROL_STRINGS)
        self.assertTrue(
            localization_assets.PROTECTED_MANAGED_CONTROL_STRINGS.isdisjoint(
                localization_assets.CONFIRMED_MANAGED_UI
            )
        )

    def test_dialogue_translation_preserves_speaker_key_and_separator(self) -> None:
        row = {
            "id": "test:dialogue",
            "original": "^Conductor:: Hello ",
            "body": " Hello ",
        }
        self.assertEqual(
            localization_assets.localized_story_value(row, " Здравствуйте "),
            "^Conductor:: Здравствуйте ",
        )

    def test_location_translation_preserves_establishing_shot_shell(self) -> None:
        row = {
            "id": "test:location",
            "original": "^>>>>EstablishingShot(Dining Car)",
            "body": "Dining Car",
            "textPrefix": "^>>>>EstablishingShot(",
            "textSuffix": ")",
        }
        self.assertEqual(
            localization_assets.localized_story_value(row, "Вагон-ресторан"),
            "^>>>>EstablishingShot(Вагон-ресторан)",
        )

    def test_player_and_hidden_speaker_keys_do_not_get_display_mappings(self) -> None:
        units = [
            {"speaker": "Barry"},
            {"speaker": "NamelessMC"},
            {"speaker": "Conductor"},
            {"speaker": "Conductor"},
        ]
        labels = localization_assets.speaker_display_label_units(units)
        self.assertEqual([row["runtimeKey"] for row in labels], ["Conductor"])

    def test_save_locations_use_display_mappings_without_changing_stage_keys(self) -> None:
        localization_root = PROJECT_ROOT / "Documentation" / "Localization"
        inventory = json.loads((localization_root / "inventory.json").read_text(encoding="utf-8"))
        overlay = json.loads((localization_root / "ru.overlay.json").read_text(encoding="utf-8"))
        debug_map_buttons = {
            row["context"].split("/WindowRoot/", 1)[1].split("/", 1)[0]
            for row in inventory["units"]
            if "/DebugMapScreen/WindowRoot/" in (row.get("context") or "")
        }
        debug_map_environments = {
            "Prologue" if value == "DiningCar" else value
            for value in debug_map_buttons
        }
        story_environments = {
            match.group(1)
            for row in inventory["units"]
            for match in [re.search(r">>>>\s*ChangeEnvironment\(([^)]+)\)", row.get("original", ""))]
            if match is not None
        }
        self.assertEqual(
            debug_map_environments | story_environments,
            set(localization_assets.SAVE_LOCATION_ENVIRONMENT_UNITS),
        )
        labels = dict(localization_assets.save_location_display_labels(inventory, overlay))
        self.assertEqual(labels["Library"], "Вагон-библиотека")
        self.assertEqual(labels["Conductor  Car"], "Вагон Проводника")
        self.assertEqual(labels["Dining Car"], "Вагон-ресторан")
        self.assertEqual(labels["Saloon"], "Вагон-салун")
        self.assertEqual(labels["Casino"], "Вагон-казино")
        self.assertEqual(labels["Lounge"], "Вагон-гостиная")
        self.assertEqual(labels["Final  Push"], "Финальный рывок")
        self.assertNotIn("Conductor_Car", labels)
        self.assertNotIn("Conductor Car", labels)
        self.assertEqual(len(localization_assets.SAVE_LOCATION_ENVIRONMENT_UNITS), 13)
        self.assertEqual(len(labels), 11)

    def test_checked_in_inventory_and_overlay_follow_runtime_contract(self) -> None:
        localization_root = PROJECT_ROOT / "Documentation" / "Localization"
        inventory = json.loads((localization_root / "inventory.json").read_text(encoding="utf-8"))
        overlay = json.loads((localization_root / "ru.overlay.json").read_text(encoding="utf-8"))
        by_path = {row.get("sourcePath"): row for row in inventory["managedStrings"]}
        for source_path in localization_assets.PROTECTED_MANAGED_CONTROL_STRINGS:
            row = by_path[source_path]
            self.assertFalse(row["translatable"])
            self.assertEqual(row["technicalStatus"], "runtime-control-identifier")
            self.assertNotIn(row["id"], overlay["units"])
        labels = [row for row in inventory["units"] if row.get("kind") == "speaker-display-label"]
        self.assertEqual(len(labels), 17)
        self.assertTrue(all(overlay["units"].get(row["id"]) for row in labels))
        locations = [row for row in inventory["units"] if row.get("kind") == "location-display-label"]
        self.assertEqual(len(locations), 6)
        for row in locations:
            localized = localization_assets.localized_story_value(row, overlay["units"][row["id"]])
            self.assertTrue(localized.startswith("^>>>>EstablishingShot("))
            self.assertTrue(localized.endswith(")"))


class LocalizationFontTests(unittest.TestCase):
    def test_prepared_fonts_and_exact_corpus_audit_are_pinned(self) -> None:
        font_root = PROJECT_ROOT / "LocalizationAssets" / "Fonts"
        localization_root = PROJECT_ROOT / "Documentation" / "Localization"
        manifest = json.loads((font_root / "manifest.json").read_text(encoding="utf-8"))
        complex_manifest = json.loads(
            (font_root / "Complex" / "manifest.json").read_text(encoding="utf-8")
        )
        report = json.loads(
            (localization_root / "Fonts" / "font-audit.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(manifest["outputs"]), 9)
        for filename, metadata in manifest["outputs"].items():
            digest = hashlib.sha256((font_root / filename).read_bytes()).hexdigest()
            self.assertEqual(digest, metadata["sha256"], filename)
        self.assertEqual(len(complex_manifest["outputs"]), 5)
        for filename, metadata in complex_manifest["outputs"].items():
            digest = hashlib.sha256((font_root / "Complex" / filename).read_bytes()).hexdigest()
            self.assertEqual(digest, metadata["sha256"], filename)
            map_path = font_root / "Complex" / metadata["shapingMap"]
            self.assertTrue(map_path.is_file())

        self.assertTrue(report["ok"])
        self.assertEqual(report["localesExpected"], 30)
        self.assertEqual(report["localesAudited"], 30)
        self.assertEqual(set(report["locales"]), set(localization_assets.LOCALE_FALLBACK_FONTS))
        for locale, row in report["locales"].items():
            self.assertEqual(row["font"], localization_assets.LOCALE_FALLBACK_FONTS[locale])
            self.assertEqual(row["textUnits"], 3547)
            self.assertEqual(row["imageRows"], 10)
            self.assertEqual(row["staticCoverage"], "pass")
            self.assertEqual(row["missingCodepoints"], [])

        self.assertEqual(report["gates"]["staticGlyphCoverage"], "pass")
        self.assertEqual(report["gates"]["complexScriptShaping"], "pass")
        self.assertEqual(
            report["gates"]["bidirectionalLayout"], "static-pass-runtime-not-run"
        )
        self.assertEqual(report["gates"]["runtimeReadability"], "not-run")

    def test_complex_shaping_preserves_known_tmp_tags_but_shapes_visible_actions(self) -> None:
        font_root = PROJECT_ROOT / "LocalizationAssets" / "Fonts" / "Complex"
        shaping = localization_assets.load_shaping_map(
            font_root / "ar.shaping.json",
            "ar",
            PROJECT_ROOT / "Documentation" / "Localization" / "ar.overlay.json",
            font_root / "NotoSansArabicLatin-ar-Shaped.ttf",
        )
        logical = next(
            value
            for value in shaping["exact"]
            if value.startswith("<")
            and ">" in value
            and not value.lower().startswith(("<style", "<size", "<color", "<i>", "<br>"))
            and localization_assets.contains_complex_script(value, shaping["mode"])
        )
        shaped = localization_assets.shape_text(logical, shaping)
        self.assertNotEqual(shaped, logical)
        self.assertTrue(any(0xE000 <= ord(character) <= 0xF8FF for character in shaped))


if __name__ == "__main__":
    unittest.main()
