from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/install_personal.py"
SPEC = importlib.util.spec_from_file_location("install_personal", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
install_personal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_personal)


class PersonalInstallerTests(unittest.TestCase):
    def test_missing_marketplace_gets_valid_personal_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace.json"

            current = install_personal.load_marketplace(marketplace)
            updated, action = install_personal.updated_marketplace(current)

        self.assertEqual(action, "added")
        self.assertEqual(updated["name"], "personal")
        self.assertEqual(updated["interface"]["displayName"], "Personal")
        self.assertEqual(updated["plugins"], [install_personal.ENTRY])

    def test_existing_entry_is_updated_in_place_without_reordering(self) -> None:
        current = {
            "name": "personal",
            "interface": {"displayName": "My Personal Plugins"},
            "plugins": [
                {"name": "first"},
                {"name": install_personal.PLUGIN_NAME, "category": "Old"},
                {"name": "last"},
            ],
        }

        updated, action = install_personal.updated_marketplace(current)

        self.assertEqual(action, "updated")
        self.assertEqual(updated["interface"], current["interface"])
        self.assertEqual(updated["plugins"][0], current["plugins"][0])
        self.assertEqual(updated["plugins"][1], install_personal.ENTRY)
        self.assertEqual(updated["plugins"][2], current["plugins"][2])

    def test_duplicate_entries_are_rejected(self) -> None:
        current = {
            "name": "personal",
            "plugins": [
                {"name": install_personal.PLUGIN_NAME},
                {"name": install_personal.PLUGIN_NAME},
            ],
        }

        with self.assertRaises(SystemExit):
            install_personal.updated_marketplace(current)


if __name__ == "__main__":
    unittest.main()
