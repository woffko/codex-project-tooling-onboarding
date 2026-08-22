# Codex Project Tooling Onboarding

`project-tooling-onboarding` is a local Codex plugin that audits the exact Git
project behind a new or resumed session and offers project-scoped tooling only
when something is missing.

It covers:

- semantic navigation through LSP MCP;
- local Project Memory enrollment and routing;
- guarded Longrun execution for long non-interactive commands;
- exact Codex project trust;
- local instruction and configuration files without silently committing them.

Fully connected projects stay silent. Missing integrations are listed once and
require confirmation before any mutation.

## Behavior

The plugin installs two reviewed lifecycle hooks:

- `SessionStart` performs a read-only audit for new and resumed sessions;
- `UserPromptSubmit` adds one model-visible onboarding instruction when the
  audit fingerprint is incomplete and has not already been offered in that
  thread.

Codex cannot ask a question before the first user message because no model turn
exists yet. The offer therefore appears in the first response. A declined offer
is not repeated for the same thread and audit fingerprint.

The audit never treats the user's home directory as one project or LSP
workspace. A session started outside a Git project is asked to select an exact
project root first.

## Prerequisites

- Codex CLI 0.149.0 or newer with stable plugins and hooks;
- Python 3.11 or newer;
- Git;
- the desired backends installed locally:
  - [LSP MCP](https://github.com/woffko/lsp_mcp/blob/agent/typescript-multiroot-support/INSTALL_NOTES.md);
  - [Codex Project Memory](https://github.com/woffko/codex-project-memory/tree/deepdive);
  - [Codex MCP Longrun](https://github.com/woffko/codex-mcp-longrun/tree/experimental).

The plugin audits and orchestrates those components. It does not bundle or
silently install their runtimes.

## Install from scratch

Clone to the standard personal-plugin source path:

```bash
mkdir -p "$HOME/plugins"
git clone https://github.com/woffko/codex-project-tooling-onboarding.git \
  "$HOME/plugins/project-tooling-onboarding"
cd "$HOME/plugins/project-tooling-onboarding"
```

Preview the personal marketplace change:

```bash
python3 scripts/install_personal.py --dry-run
```

Install the marketplace entry and plugin:

```bash
python3 scripts/install_personal.py --install
```

Start Codex once. Its standard hook-review screen shows the exact
`SessionStart` and `UserPromptSubmit` commands. Review and trust those hooks;
do not use `--dangerously-bypass-hook-trust` for normal installation.

Start a new session after installation. Existing on-screen processes do not
hot-load plugins, skills, hooks, MCP catalogs, or project configuration.

## What happens after confirmation

The bundled skill directs Codex to:

1. resolve the exact project root, including historical-session context;
2. preserve dirty worktrees and existing instructions;
3. enable only applicable LSP backends with bounded workspace roots;
4. enroll Project Memory with an explicit stable key;
5. enroll the exact Longrun root and verify guarded runtime health;
6. add exact project trust with a private backup;
7. verify real semantic, memory, and Longrun behavior;
8. provide a copy-paste `codex-longrun resume -C ... SESSION_ID` command.

Test-secret storage is never enabled implicitly. It requires the user to
classify the equipment as test-only, and plaintext must not enter chat, source,
Git, argv, environment, logs, metrics, checkpoints, or delegated prompts.

## Read-only audit

Run the deterministic audit without hooks:

```bash
python3 skills/project-tooling-onboarding/scripts/tooling_onboarding.py \
  audit --cwd /absolute/project/root --json
```

The result reports `fully_connected`, the detected LSP backends, exact missing
components, Project Memory mappings, Longrun root coverage, and exact project
trust.

## Update

```bash
cd "$HOME/plugins/project-tooling-onboarding"
git pull --ff-only
python3 scripts/install_personal.py --install
```

If hook commands changed, Codex marks their hashes for review again. Review the
new commands through `/hooks` before trusting them.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 -m compileall -q skills tests
```

The tests cover broad-root rejection, exact missing-component reporting,
silence for fully connected projects, and once-per-fingerprint prompting.

## Security model

- Hooks perform read-only project/config inspection and write only private
  per-thread prompt state under `~/.local/state/project-tooling-onboarding`.
- No project or global configuration changes occur before user confirmation.
- Hook trust uses Codex's native reviewed hash mechanism.
- The plugin does not weaken sandbox, approvals, network policy, or credential
  handling.
- Generated state contains project paths and connection status, never secret
  values.

## License

MIT
