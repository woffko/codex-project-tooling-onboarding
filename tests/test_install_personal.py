from __future__ import annotations

import importlib.util
import contextlib
import io
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


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

    def test_handoff_quotes_known_project_and_session(self) -> None:
        root = Path("/tmp/project spaces; literal")
        launcher = "/tmp/launcher directory/codex-longrun"
        session = "--id; $(literal)"
        output = io.StringIO()
        with patch.dict(os.environ, {"CODEX_LONGRUN_LAUNCHER": launcher}), contextlib.redirect_stdout(output):
            install_personal.print_launch_handoff(root, session)
        self.assertEqual(shlex.split(output.getvalue().splitlines()[-1]),
                         [launcher, "resume", "-C", str(root), "--", session])

    def test_unknown_project_produces_labeled_new_session_template(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {"CODEX_LONGRUN_LAUNCHER": "/missing/codex-longrun"}), contextlib.redirect_stdout(output):
            install_personal.print_launch_handoff(None, None)
        self.assertIn("Replace /absolute/path/to/project", output.getvalue())
        self.assertIn("Install Longrun first", output.getvalue())
        self.assertEqual(shlex.split(output.getvalue().splitlines()[-1]),
                         ["/missing/codex-longrun", "-C", "/absolute/path/to/project"])

    def test_install_emits_command_only_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            plugin = home / "plugins/project-tooling-onboarding"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / ".codex-plugin/plugin.json").write_text('{}')
            for succeeds in (True, False):
                output = io.StringIO()
                with patch.object(install_personal, "__file__", str(plugin / "scripts/install_personal.py")), \
                     patch.object(Path, "home", return_value=home), \
                     patch.dict(os.environ, {}, clear=True), \
                     patch.object(sys, "argv", ["install_personal.py", "--install"]), \
                     patch.object(install_personal.subprocess, "run") as run, contextlib.redirect_stdout(output):
                    if succeeds:
                        install_personal.main()
                        self.assertIn("Plugin installed.", output.getvalue())
                        self.assertIn("codex-longrun -C /absolute/path/to/project", output.getvalue())
                    else:
                        run.side_effect = subprocess.CalledProcessError(1, "codex plugin add")
                        with self.assertRaises(subprocess.CalledProcessError):
                            install_personal.main()
                        self.assertNotIn("Plugin installed.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
