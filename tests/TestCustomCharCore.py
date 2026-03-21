import json
import os
import shutil
import unittest
import uuid
from unittest.mock import patch

from src.char.custom.CustomChar import CustomChar
from src.char.custom.CustomCharManager import CustomCharManager, DB_SCHEMA_VERSION

PREDEFINED_CHARACTER_REF = "builtin:char_zero"

class TestCustomCharCore(unittest.TestCase):
    def setUp(self):
        temp_root = os.path.join(os.getcwd(), "tests", ".tmp")
        os.makedirs(temp_root, exist_ok=True)
        self.temp_dir = os.path.join(temp_root, f"case_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.db_path = os.path.join(self.temp_dir, "db.json")
        self.features_dir = os.path.join(self.temp_dir, "features")
        os.makedirs(self.features_dir, exist_ok=True)

        self.patchers = [
            patch("src.char.custom.CustomCharManager.CUSTOM_CHARS_DIR", self.temp_dir),
            patch("src.char.custom.CustomCharManager.DB_PATH", self.db_path),
            patch("src.char.custom.CustomCharManager.FEATURES_DIR", self.features_dir),
        ]
        for patcher in self.patchers:
            patcher.start()
        CustomCharManager._instance = None

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        CustomCharManager._instance = None

    def _write_db(self, data):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def test_db_schema_migrates_legacy_combo_name(self):
        legacy = {
            "combos": {"combo_old": "skill,wait(0.1)"},
            "characters": {
                "char_legacy": {
                    "combo_name": "combo_old",
                    "feature_ids": [],
                }
            },
            "features": {},
        }
        self._write_db(legacy)

        manager = CustomCharManager()
        self.assertEqual(manager.db["schema_version"], DB_SCHEMA_VERSION)
        raw = manager.db["characters"]["char_legacy"]
        self.assertEqual(raw["combo_ref"], "combo_old")
        self.assertEqual(raw["combo_name"], "combo_old")

        info = manager.get_character_info("char_legacy")
        self.assertIsNotNone(info)
        self.assertEqual(info["combo_ref"], "combo_old")
        self.assertEqual(info["combo_name"], "combo_old")

    def test_db_schema_migrates_legacy_builtin_label(self):
        bootstrap = {
            "schema_version": DB_SCHEMA_VERSION,
            "combos": {},
            "characters": {},
            "features": {},
        }
        self._write_db(bootstrap)
        manager = CustomCharManager()
        legacy_builtin_label = manager.to_combo_label(PREDEFINED_CHARACTER_REF)

        legacy = {
            "combos": {},
            "characters": {
                "char_builtin": {
                    "combo_name": legacy_builtin_label,
                    "feature_ids": [],
                }
            },
            "features": {},
        }
        self._write_db(legacy)
        CustomCharManager._instance = None

        manager = CustomCharManager()
        info = manager.get_character_info("char_builtin")
        self.assertIsNotNone(info)
        self.assertEqual(info["combo_ref"], PREDEFINED_CHARACTER_REF)
        self.assertEqual(info["combo_name"], PREDEFINED_CHARACTER_REF)

    def test_validate_combo_syntax_reports_line_and_column(self):
        is_valid, error = CustomChar.validate_combo_syntax("skill,wait(0.5)")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        is_valid, error = CustomChar.validate_combo_syntax("skill(\nwait(0.5)")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn("line", error)
        self.assertIn("column", error)

    def test_validate_combo_rejects_unsupported_and_unknown(self):
        is_valid, error = CustomChar.validate_combo_syntax("wait(**data)")
        self.assertFalse(is_valid)
        self.assertIn("**kwargs", error or "")

        is_valid, error = CustomChar.validate_combo_syntax("not_a_command")
        self.assertFalse(is_valid)
        self.assertIn("unknown command", error or "")

    def test_validate_db_removes_missing_feature_assets_and_metadata(self):
        existing_fid = "feat_exists"
        missing_fid = "feat_missing"

        with open(os.path.join(self.features_dir, f"{existing_fid}.png"), "wb") as f:
            f.write(b"ok")

        legacy = {
            "combos": {},
            "characters": {
                "char_a": {
                    "combo_name": "",
                    "feature_ids": [existing_fid, missing_fid],
                }
            },
            "features": {
                existing_fid: {"width": 1920, "height": 1080},
                missing_fid: {"width": 1920, "height": 1080},
            },
        }
        self._write_db(legacy)

        manager = CustomCharManager()

        char_info = manager.get_character_info("char_a")
        self.assertIsNotNone(char_info)
        self.assertEqual(char_info["feature_ids"], [existing_fid])
        self.assertIn(existing_fid, manager.db["features"])
        self.assertNotIn(missing_fid, manager.db["features"])


if __name__ == "__main__":
    unittest.main()
