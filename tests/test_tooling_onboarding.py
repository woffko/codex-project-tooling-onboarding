from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    PLUGIN_ROOT
    / "skills/project-tooling-onboarding/scripts/tooling_onboarding.py"
)
SPEC = importlib.util.spec_from_file_location("tooling_onboarding", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
tooling_onboarding = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tooling_onboarding)


class ToolingOnboardingTests(unittest.TestCase):
    def _git_project(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)

    def test_home_directory_is_never_a_project_root(self) -> None:
        result = tooling_onboarding.audit(tooling_onboarding.HOME, "thread")

        self.assertIsNone(result["project_root"])
        self.assertTrue(result["needs_project_selection"])

    def test_missing_project_lists_each_integration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git_project(root)
            (root / "app.js").write_text("export function run() {}\n", encoding="utf-8")
            with patch.object(tooling_onboarding, "CODEX_HOME", root / "codex-home"), patch.object(
                tooling_onboarding, "PROJECT_MEMORY_REGISTRY", root / "registry.json"
            ), patch.object(tooling_onboarding, "LONGRUN_LAUNCHER", root / "missing-longrun"), patch.object(
                tooling_onboarding, "LSP_ROUTER", root / "missing-lsp"
            ):
                result = tooling_onboarding.audit(root, "thread")

        self.assertFalse(result["fully_connected"])
        self.assertEqual(
            result["missing_components"],
            ["LSP MCP", "Project Memory", "Longrun", "Codex project trust"],
        )

    def test_fully_connected_project_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            root.mkdir()
            self._git_project(root)
            (root / "app.js").write_text("export function run() {}\n", encoding="utf-8")
            (root / ".lsp-mcp.toml").write_text(
                'schema_version = 1\n[project]\nworkspace = "."\n[backends.typescript]\nenabled = true\n',
                encoding="utf-8",
            )
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(
                '[mcp_servers.lsp_mcpls]\nenabled = true\n', encoding="utf-8"
            )
            (root / "AGENTS.override.md").write_text(
                "Project Memory key `owner/project`.\n", encoding="utf-8"
            )
            codex_home = base / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                f'''[projects."{root}"]
trust_level = "trusted"
[plugins."project-memory@personal"]
enabled = true
[mcp_servers.longrun]
command = "server"
[mcp_servers.longrun.env]
LONGRUN_ALLOWED_ROOTS = "{root}"
''',
                encoding="utf-8",
            )
            registry = base / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "projects": [
                            {"project_key": "owner/project", "project_root": str(root)}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            launcher = base / "codex-longrun"
            launcher.touch()
            router = base / "lsp-mcp"
            router.touch()
            with patch.object(tooling_onboarding, "CODEX_HOME", codex_home), patch.object(
                tooling_onboarding, "PROJECT_MEMORY_REGISTRY", registry
            ), patch.object(tooling_onboarding, "LONGRUN_LAUNCHER", launcher), patch.object(
                tooling_onboarding, "LSP_ROUTER", router
            ):
                result = tooling_onboarding.audit(root, "thread")

        self.assertTrue(result["fully_connected"])
        self.assertEqual(result["missing_components"], [])

    def test_prompt_hook_repeats_until_fingerprint_is_dismissed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git_project(root)
            state = root / "state"
            payload = json.dumps(
                {"session_id": "thread-1", "working_directory": str(root)}
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "PROJECT_TOOLING_ONBOARDING_STATE_DIR": str(state),
                    "CODEX_HOME": str(root / "codex-home"),
                    "PROJECT_MEMORY_REGISTRY": str(root / "registry.json"),
                    "CODEX_LONGRUN_LAUNCHER": str(root / "missing-longrun"),
                    "LSP_MCP_ROUTER": str(root / "missing-lsp"),
                }
            )
            command = [
                sys.executable,
                str(SCRIPT),
                "hook",
                "--event",
                "user-prompt-submit",
            ]
            first = subprocess.run(
                command,
                input=payload,
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )
            second = subprocess.run(
                command,
                input=payload,
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )
            dismissed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "dismiss",
                    "--cwd",
                    str(root),
                    "--session-id",
                    "thread-1",
                ],
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )
            third = subprocess.run(
                command,
                input=payload,
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )

        self.assertIn("PROJECT TOOLING ONBOARDING AUDIT", first.stdout)
        self.assertIn("MANDATORY FIRST RESPONSE ACTION", first.stdout)
        self.assertIn("PROJECT TOOLING ONBOARDING AUDIT", second.stdout)
        self.assertIn("dismissed_fingerprint", json.loads(dismissed.stdout))
        self.assertEqual(third.stdout, "")

    def test_legacy_prompted_state_does_not_suppress_offer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            prompt_state = state / "prompts"
            prompt_state.mkdir(parents=True)
            (prompt_state / "019f57b4-fa48-7ed2-a414-9109e7e17dff.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "session_id": "019f57b4-fa48-7ed2-a414-9109e7e17dff",
                        "project_root": None,
                        "fingerprint": "legacy-fingerprint",
                        "fully_connected": False,
                        "prompted_fingerprint": "legacy-fingerprint",
                    }
                ),
                encoding="utf-8",
            )
            payload = json.dumps(
                {
                    "session_id": "019f57b4-fa48-7ed2-a414-9109e7e17dff",
                    "working_directory": str(tooling_onboarding.HOME),
                }
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "PROJECT_TOOLING_ONBOARDING_STATE_DIR": str(state),
                    "CODEX_HOME": str(root / "codex-home"),
                    "PROJECT_MEMORY_REGISTRY": str(root / "registry.json"),
                    "CODEX_LONGRUN_LAUNCHER": str(root / "missing-longrun"),
                    "LSP_MCP_ROUTER": str(root / "missing-lsp"),
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "hook",
                    "--event",
                    "user-prompt-submit",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )

        self.assertIn("PROJECT TOOLING ONBOARDING AUDIT", completed.stdout)
        self.assertIn("No exact Git project root is selected", completed.stdout)
        self.assertIn("LSP MCP, Project Memory, Longrun", completed.stdout)
        self.assertIn("MANDATORY FIRST RESPONSE ACTION", completed.stdout)


if __name__ == "__main__":
    unittest.main()
