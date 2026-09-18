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
    def test_russian_fit_fixes_use_locale_layout_overrides(self) -> None:
        localization_root = PROJECT_ROOT / "Documentation" / "Localization"
        inventory = json.loads((localization_root / "inventory.json").read_text(encoding="utf-8"))
        overlay = json.loads((localization_root / "ru.overlay.json").read_text(encoding="utf-8"))
        identifier = "unity:defaultgroup:-4932669119767755847:m_text"
        self.assertEqual(overlay["units"][identifier], "КОЛЬЦА")
        self.assertEqual(
            overlay["layoutOverrides"][identifier],
            {"m_fontSize": 46.0, "m_fontSizeBase": 46.0},
        )
        self.assertEqual(
            overlay["layoutOverrides"]["unity:level0:1538:m_text"],
            {"m_fontSize": 18.0, "m_fontSizeBase": 18.0},
        )
        self.assertEqual(
            overlay["layoutOverrides"]["unity:level0:1553:m_text"],
            {"m_fontSize": 28.0, "m_fontSizeBase": 28.0},
        )
        self.assertEqual(localization_assets.validate_layout_overrides(inventory, overlay), [])

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


if __name__ == "__main__":
    unittest.main()
