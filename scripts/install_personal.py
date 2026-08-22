#!/usr/bin/env python3
"""Install this checkout into the standard personal Codex marketplace."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any


PLUGIN_NAME = "project-tooling-onboarding"
ENTRY = {
    "name": PLUGIN_NAME,
    "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools",
}


def load_marketplace(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": "personal",
            "interface": {"displayName": "Personal"},
            "plugins": [],
        }
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("name") != "personal":
        raise SystemExit("the default marketplace must be named personal")
    plugins = value.get("plugins")
    if not isinstance(plugins, list):
        raise SystemExit("personal marketplace plugins must be an array")
    return value


def updated_marketplace(value: dict[str, Any]) -> tuple[dict[str, Any], str]:
    plugins = list(value["plugins"])
    indexes = [
        index
        for index, item in enumerate(plugins)
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME
    ]
    if len(indexes) > 1:
        raise SystemExit("duplicate project-tooling-onboarding marketplace entries")
    action = "unchanged"
    if indexes:
        index = indexes[0]
        if plugins[index] != ENTRY:
            plugins[index] = ENTRY
            action = "updated"
    else:
        plugins.append(ENTRY)
        action = "added"
    result = dict(value)
    result["plugins"] = plugins
    return result, action


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix="marketplace.json.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--marketplace",
        type=Path,
        default=Path.home() / ".agents/plugins/marketplace.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.dry_run and args.install:
        parser.error("--dry-run and --install are mutually exclusive")
    plugin_root = Path(__file__).resolve().parents[1]
    expected_root = (Path.home() / "plugins" / PLUGIN_NAME).resolve()
    if plugin_root != expected_root:
        raise SystemExit(
            f"clone this plugin to the standard personal source path: {expected_root}"
        )
    if not (plugin_root / ".codex-plugin/plugin.json").is_file():
        raise SystemExit("plugin manifest is missing")
    marketplace = args.marketplace.expanduser().resolve()
    current = load_marketplace(marketplace)
    updated, action = updated_marketplace(current)
    print(
        json.dumps(
            {
                "marketplace": str(marketplace),
                "marketplace_name": updated["name"],
                "plugin": PLUGIN_NAME,
                "action": action,
                "will_install": bool(args.install),
            },
            indent=2,
        )
    )
    if args.dry_run or not args.install:
        return
    if action != "unchanged":
        atomic_write(marketplace, updated)
    subprocess.run(
        ["codex", "plugin", "add", f"{PLUGIN_NAME}@{updated['name']}"],
        check=True,
    )


if __name__ == "__main__":
    main()
