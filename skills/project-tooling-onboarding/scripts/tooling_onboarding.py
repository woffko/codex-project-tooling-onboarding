#!/usr/bin/env python3
"""Read-only project-tooling audit and lifecycle-hook adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any


SCHEMA_VERSION = 1
ONBOARDING_MODELS = frozenset({"gpt-5.6-sol", "gpt-6-astra"})
HOME = Path.home().resolve()
CODEX_HOME = Path(os.environ.get("CODEX_HOME", HOME / ".codex")).resolve()
STATE_HOME = Path(
    os.environ.get(
        "PROJECT_TOOLING_ONBOARDING_STATE_DIR",
        HOME / ".local/state/project-tooling-onboarding",
    )
).resolve()
PROJECT_MEMORY_REGISTRY = Path(
    os.environ.get(
        "PROJECT_MEMORY_REGISTRY",
        HOME / ".local/share/codex-project-memory/registry.json",
    )
)
LONGRUN_LAUNCHER = Path(
    os.environ.get(
        "CODEX_LONGRUN_LAUNCHER",
        HOME / ".local/share/codex-longrun-mcp/.venv/bin/codex-longrun",
    )
)
LSP_ROUTER = Path(os.environ.get("LSP_MCP_ROUTER", HOME / ".local/bin/lsp-mcp"))
IGNORED_DIRS = {
    ".git",
    ".cache",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "bin",
    "dl",
    "staging_dir",
    "build_dir",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _lookup(value: Any, names: set[str]) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in names and child not in (None, ""):
                return child
        for child in value.values():
            found = _lookup(child, names)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _lookup(child, names)
            if found not in (None, ""):
                return found
    return None


def _canonical_directory(value: str | os.PathLike[str] | None) -> Path | None:
    if not value:
        return None
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return path if path.is_dir() else None


def _git_root(cwd: Path | None) -> Path | None:
    if cwd is None:
        return None
    completed = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    root = _canonical_directory(completed.stdout.strip())
    if root in {None, HOME, HOME.parent, Path("/")}:
        return None
    return root


def _detect_backends(root: Path) -> tuple[list[str], bool]:
    detected: set[str] = set()
    scanned = 0
    capped = False
    suffixes = {
        ".c": "clangd",
        ".cc": "clangd",
        ".cpp": "clangd",
        ".cxx": "clangd",
        ".h": "clangd",
        ".hpp": "clangd",
        ".py": "basedpyright",
        ".pyi": "basedpyright",
        ".js": "typescript",
        ".jsx": "typescript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "typescript",
        ".cjs": "typescript",
        ".rs": "rust",
        ".dart": "dart",
    }
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if name not in IGNORED_DIRS]
        for name in files:
            scanned += 1
            backend = suffixes.get(Path(name).suffix.casefold())
            if backend:
                detected.add(backend)
            if scanned >= 8000:
                capped = True
                break
        if capped:
            break
    order = ["clangd", "basedpyright", "rust", "typescript", "dart"]
    return [name for name in order if name in detected], capped


def _plugin_enabled(config: dict[str, Any], name: str) -> bool:
    plugins = config.get("plugins", {})
    if not isinstance(plugins, dict):
        return False
    for key, value in plugins.items():
        if str(key).split("@", 1)[0] != name or not isinstance(value, dict):
            continue
        return value.get("enabled", True) is not False
    return False


def _local_plugin_enabled(config: dict[str, Any], name: str) -> bool:
    plugins = config.get("plugins", {})
    if not isinstance(plugins, dict):
        return False
    for key, value in plugins.items():
        if str(key).split("@", 1)[0] != name or not isinstance(value, dict):
            continue
        servers = value.get("mcp_servers", {})
        if not isinstance(servers, dict):
            continue
        server = servers.get("project_memory", {})
        return isinstance(server, dict) and server.get("enabled", True) is not False
    return False


def _instruction_text(root: Path) -> str:
    override = root / "AGENTS.override.md"
    agents = root / "AGENTS.md"
    selected = override if override.is_file() else agents
    try:
        return selected.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeError):
        return ""


def _memory_projects(root: Path) -> list[dict[str, Any]]:
    registry = _load_json(PROJECT_MEMORY_REGISTRY)
    projects = registry.get("projects", [])
    if isinstance(projects, dict):
        projects = list(projects.values())
    if not isinstance(projects, list):
        return []
    result = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        project_root = _canonical_directory(project.get("project_root"))
        if project_root == root:
            result.append(project)
    return result


def _component(name: str, connected: bool, missing: list[str], **details: Any) -> dict[str, Any]:
    return {
        "name": name,
        "connected": connected,
        "missing": missing,
        "details": details,
    }


def launch_commands(root: Path, session_id: str | None = None) -> dict[str, str | None]:
    start = shlex.join([str(LONGRUN_LAUNCHER), "-C", str(root)])
    resume = (shlex.join([str(LONGRUN_LAUNCHER), "resume", "-C", str(root), "--", session_id])
              if session_id else None)
    return {"start_command": start, "resume_command": resume, "launch_command": resume or start}


def print_audit(result: dict[str, Any]) -> None:
    if result.get("fully_connected"):
        print(f"Project tooling is fully connected: {result.get('project_root')}")
    else:
        print(f"Project: {result.get('project_root') or '<not selected>'}")
        print("Missing: " + ", ".join(result.get("missing_components", [])))
    if result.get("launch_command"):
        if not result.get("fully_connected"):
            print("After connecting the missing tooling:")
        print("Close the current Codex process, then launch this project through the Longrun bridge:")
        print(result["launch_command"])


def audit(cwd: Path | None, session_id: str | None = None) -> dict[str, Any]:
    root = _git_root(cwd)
    if root is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "session_id": session_id,
            "cwd": str(cwd) if cwd else None,
            "project_root": None,
            "fully_connected": False,
            "needs_offer": True,
            "needs_project_selection": True,
            "missing_components": ["Project root selection"],
            "components": [],
        }

    local_config_path = root / ".codex/config.toml"
    manifest_path = root / ".lsp-mcp.toml"
    local_config = _load_toml(local_config_path)
    global_config = _load_toml(CODEX_HOME / "config.toml")
    backends, scan_capped = _detect_backends(root)

    local_servers = local_config.get("mcp_servers", {})
    if not isinstance(local_servers, dict):
        local_servers = {}
    lsp_server = local_servers.get("lsp_mcpls", {})
    lsp_connected = not backends or (
        manifest_path.is_file()
        and isinstance(lsp_server, dict)
        and lsp_server.get("enabled", True) is not False
        and LSP_ROUTER.is_file()
    )
    lsp_missing: list[str] = []
    if backends:
        if not manifest_path.is_file():
            lsp_missing.append("portable .lsp-mcp.toml")
        if not isinstance(lsp_server, dict) or lsp_server.get("enabled", True) is False:
            lsp_missing.append("local lsp_mcpls server")
        if not LSP_ROUTER.is_file():
            lsp_missing.append("installed lsp-mcp router")

    projects = _memory_projects(root)
    keys = sorted(
        str(project.get("project_key", ""))
        for project in projects
        if project.get("project_key")
    )
    instructions = _instruction_text(root)
    mapped_keys = [key for key in keys if key in instructions]
    memory_missing: list[str] = []
    if not projects:
        memory_missing.append("Project Memory enrollment")
    if projects and not mapped_keys:
        memory_missing.append("Project Memory key routing in active instructions")
    if not _plugin_enabled(global_config, "project-memory"):
        memory_missing.append("installed Project Memory plugin")
    memory_connected = not memory_missing

    longrun = global_config.get("mcp_servers", {}).get("longrun", {})
    longrun_missing: list[str] = []
    allowed_roots: list[str] = []
    if isinstance(longrun, dict):
        environment = longrun.get("env", {})
        if isinstance(environment, dict):
            allowed_roots = [
                str(Path(value).expanduser().resolve())
                for value in str(environment.get("LONGRUN_ALLOWED_ROOTS", "")).split(":")
                if value
            ]
    if str(root) not in allowed_roots:
        longrun_missing.append("exact LONGRUN_ALLOWED_ROOTS enrollment")
    if not LONGRUN_LAUNCHER.is_file():
        longrun_missing.append("installed codex-longrun launcher")
    longrun_connected = not longrun_missing

    trust = global_config.get("projects", {}).get(str(root), {})
    trusted = isinstance(trust, dict) and trust.get("trust_level") == "trusted"
    trust_missing = [] if trusted else ["exact Codex project trust"]

    components = [
        _component(
            "LSP MCP",
            lsp_connected,
            lsp_missing,
            applicable=bool(backends),
            detected_backends=backends,
            scan_capped=scan_capped,
        ),
        _component(
            "Project Memory",
            memory_connected,
            memory_missing,
            project_keys=keys,
            mapped_keys=mapped_keys,
            local_profile_enabled=_local_plugin_enabled(local_config, "project-memory"),
        ),
        _component(
            "Longrun",
            longrun_connected,
            longrun_missing,
            launcher=str(LONGRUN_LAUNCHER),
            exact_root_enrolled=str(root) in allowed_roots,
        ),
        _component("Codex project trust", trusted, trust_missing),
    ]
    missing_components = [item["name"] for item in components if not item["connected"]]
    fully_connected = not missing_components
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "cwd": str(cwd) if cwd else None,
        "project_root": str(root),
        "project_name": root.name,
        "fully_connected": fully_connected,
        "needs_offer": not fully_connected,
        "needs_project_selection": False,
        "missing_components": missing_components,
        "components": components,
        "local_config": str(local_config_path),
        "portable_manifest": str(manifest_path),
        **launch_commands(root, session_id),
    }


def _fingerprint(result: dict[str, Any]) -> str:
    stable = {
        "project_root": result.get("project_root"),
        "needs_project_selection": result.get("needs_project_selection"),
        "components": [
            {
                "name": item.get("name"),
                "connected": item.get("connected"),
                "missing": item.get("missing"),
            }
            for item in result.get("components", [])
        ],
    }
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _session_state_path(session_id: str | None, cwd: Path | None) -> Path:
    identity = session_id or hashlib.sha256(str(cwd).encode("utf-8")).hexdigest()[:24]
    return STATE_HOME / "prompts" / f"{identity}.json"


def _write_state(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _hook_context(result: dict[str, Any]) -> str:
    if result.get("needs_project_selection"):
        finding = "No exact Git project root is selected for this session."
        missing = "Project root selection"
        scope = (
            "After an exact root is selected, audit the applicable LSP MCP, Project Memory, "
            "Longrun, and exact Codex project trust integrations.\n"
        )
    else:
        finding = f"Project tooling audit for {result['project_root']} found missing integrations."
        missing = ", ".join(result.get("missing_components", []))
        scope = ""
    details = []
    for component in result.get("components", []):
        if component.get("connected"):
            continue
        reasons = "; ".join(component.get("missing", [])) or "not connected"
        details.append(f"- {component['name']}: {reasons}")
    detail_text = "\n".join(details)
    return (
        "PROJECT TOOLING ONBOARDING AUDIT\n"
        "This automatic offer applies only while the active model is gpt-5.6-sol or "
        "gpt-6-astra. On any other model, ignore this automatic onboarding instruction "
        "from earlier turns and continue the user's task. Explicit user requests to "
        "connect tooling remain valid on every model.\n"
        f"{finding}\nMissing: {missing}.\n{scope}{detail_text}\n"
        "MANDATORY FIRST RESPONSE ACTION: before starting the user's requested task, ask one concise "
        "confirmation question that lists the missing components. Do not skip this question merely "
        "because the user did not mention onboarding; asking is not a mutation. Wait for the user's "
        "answer before substantive work. If the current user message already explicitly asks to "
        "connect/install/enable/configure this tooling, treat it as confirmation and use the "
        "project-tooling-onboarding skill immediately. If the user explicitly declines, follow the "
        "skill's dismiss flow and then continue the original task. Until connected or dismissed, this "
        "context will be repeated so a model cannot silently lose the offer. Do not mutate anything "
        "merely because this hook ran."
    )


def run_hook(event: str) -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    # Use the active model supplied by Codex for this hook invocation. Configuration,
    # environment defaults, and previous transcript turns can name a stale model.
    model = payload.get("model") if isinstance(payload, dict) else None
    if not isinstance(model, str) or model not in ONBOARDING_MODELS:
        return 0
    session_value = _lookup(
        payload,
        {"session_id", "sessionId", "thread_id", "threadId"},
    ) or os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")
    session_id = str(session_value) if session_value else None
    cwd_value = _lookup(
        payload,
        {"cwd", "working_directory", "workingDirectory", "project_root", "projectRoot"},
    )
    cwd = _canonical_directory(str(cwd_value)) if cwd_value else None
    if cwd is None:
        cwd = _canonical_directory(os.environ.get("PWD")) or _canonical_directory(os.getcwd())
    result = audit(cwd, session_id)
    fingerprint = _fingerprint(result)
    state_path = _session_state_path(session_id, cwd)
    previous = _load_json(state_path)
    state = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "project_root": result.get("project_root"),
        "fingerprint": fingerprint,
        "fully_connected": result.get("fully_connected"),
    }
    if event == "session-start":
        if previous.get("dismissed_fingerprint"):
            state["dismissed_fingerprint"] = previous["dismissed_fingerprint"]
        _write_state(state_path, state)
        return 0

    if result.get("fully_connected"):
        _write_state(state_path, state)
        return 0
    if previous.get("dismissed_fingerprint") == fingerprint:
        return 0

    if previous.get("dismissed_fingerprint"):
        state["dismissed_fingerprint"] = previous["dismissed_fingerprint"]
    _write_state(state_path, state)
    print(_hook_context(result))
    return 0


def dismiss(cwd: Path | None, session_id: str | None) -> dict[str, Any]:
    result = audit(cwd, session_id)
    fingerprint = _fingerprint(result)
    state_path = _session_state_path(session_id, cwd)
    state = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "project_root": result.get("project_root"),
        "fingerprint": fingerprint,
        "fully_connected": result.get("fully_connected"),
        "dismissed_fingerprint": fingerprint,
    }
    _write_state(state_path, state)
    return {
        "session_id": session_id,
        "project_root": result.get("project_root"),
        "dismissed_fingerprint": fingerprint,
        "state_path": str(state_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--cwd", type=Path, default=Path.cwd())
    audit_parser.add_argument("--session-id", default=os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID"))
    audit_parser.add_argument("--json", action="store_true")
    hook_parser = subparsers.add_parser("hook")
    hook_parser.add_argument(
        "--event", choices=("session-start", "user-prompt-submit"), required=True
    )
    dismiss_parser = subparsers.add_parser("dismiss")
    dismiss_parser.add_argument("--cwd", type=Path, default=Path.cwd())
    dismiss_parser.add_argument("--session-id", required=True)
    arguments = parser.parse_args()
    if arguments.command == "hook":
        raise SystemExit(run_hook(arguments.event))
    if arguments.command == "dismiss":
        cwd = _canonical_directory(arguments.cwd)
        print(json.dumps(dismiss(cwd, arguments.session_id), indent=2))
        return
    cwd = _canonical_directory(arguments.cwd)
    result = audit(cwd, arguments.session_id)
    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_audit(result)


if __name__ == "__main__":
    main()
