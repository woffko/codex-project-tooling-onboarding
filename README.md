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

Fully connected projects stay silent. Missing integrations are offered until
the user confirms or explicitly declines, and require confirmation before any
mutation.

## Behavior

Automatic offers are enabled only for `gpt-5.6-sol` and `gpt-6-astra`.
Both hooks check the top-level `model` field supplied by Codex on each invocation,
so switching models takes effect on the next hook call. Other models, missing
model fields, and malformed model values produce no output and skip the audit
and prompt-state writes. Suppression does not record a user decline.
The hooks never infer the active model from configuration defaults or old
transcript entries. See the official [hook input documentation](https://learn.chatgpt.com/docs/hooks#common-input-fields).

Explicit user requests to audit or connect tooling remain available on every
model through the skill and the `audit` command.

For the two eligible models, the plugin installs two reviewed lifecycle hooks:

- `SessionStart` performs a read-only audit for new and resumed sessions;
- `UserPromptSubmit` adds a model-visible onboarding instruction while the
  audit fingerprint is incomplete and has not been explicitly dismissed in
  that thread.

Codex cannot ask a question before the first user message because no model turn
exists yet. The offer therefore appears in the first response. Until tooling is
connected or the user explicitly declines, the hook repeats the onboarding
context so a model cannot silently skip it. A decline is stored for that thread
and exact audit fingerprint; a later tooling-state change makes the offer
eligible again.

The audit never treats the user's home directory as one project or LSP
workspace. A session started outside a Git project is asked to select an exact
project root first.

## LSP selection

After onboarding authorization, the agent asks one free-text question with
numbered backend choices and descriptions, in the user's language:

1. C/C++ and CUDA — `clangd`.
2. Python — `basedpyright`.
3. JavaScript/TypeScript, including JSX/TSX — `typescript`.
4. Rust — `rust` (`rust-analyzer`).
5. Dart/Flutter — `dart`.
6. HLSL — `shader` (`shader-language-server`).
7. GLSL — `glsl` (`glsl_analyzer`).
8. WGSL — `wgsl` (`wgsl-analyzer`).

Reply with numbers in any order: `4 1 3`, `2, 4`, and `4; 1; 3` are valid.
Duplicates are ignored. `0` alone skips LSP for this project. The recommended
general-purpose set is `1 2 3 4`, but it is never selected without the user's
answer. An existing explicit selection is not asked again. This also applies to
new empty projects; detected source languages are hints, not authorization.

Print the full selection question or apply the user's answer:

```bash
python3 skills/project-tooling-onboarding/scripts/tooling_onboarding.py lsp-options
python3 skills/project-tooling-onboarding/scripts/tooling_onboarding.py \
  init-lsp --cwd "/absolute/path/to/project" --selection "4 1 3"
```

`init-lsp` requires a selection, creates only an absent `.lsp-mcp.toml`, and
never overwrites existing configuration. `0` records an empty backend selection
so later audits respect that choice. The command does not install host servers,
connect the local MCP entry, or grant trust; those remain part of authorized
onboarding. Selected servers must be supported and available in the host profile.
Report missing prerequisites instead of silently dropping a selected backend.
Verify real semantic behavior where source files exist; for empty projects,
report configuration and server initialization separately from deferred semantic
checks. Fully configured existing projects retain their previous selection.

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

The installer prints a bridge launch command after a successful installation.
To include the exact project and a known session in that command, use:

```bash
python3 scripts/install_personal.py --install \
  --project-root "/absolute/path/to/project" --session-id "SESSION_ID"
```

The session ID defaults to `CODEX_THREAD_ID`/`CODEX_SESSION_ID` when available.
Without an ID, the installer prints a new-session command. Without
`--project-root`, it prints a clearly marked project-path template; it never
uses the plugin checkout as the target project. Installation alone does not
enroll that project or install Longrun. The output identifies those prerequisites.

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

After project connection, run the final audit with the actual session ID:

```bash
python3 skills/project-tooling-onboarding/scripts/tooling_onboarding.py \
  audit --cwd "/absolute/path/to/project" --session-id "SESSION_ID"
```

The human-readable output prints the shell-quoted bridge command. JSON output
includes `start_command`, `resume_command`, and the selected `launch_command`.
Paths with spaces and shell metacharacters are preserved. For example:

```bash
"$HOME/.local/share/codex-longrun-mcp/.venv/bin/codex-longrun" \
  resume -C "/absolute/path/to/project" -- "SESSION_ID"
```

Close the old Codex process before running that command. Omit `resume` and the
session ID for a new session. Ordinary `codex` does not start the Longrun bridge.
The same launcher supports Goal and non-Goal continuation; see the
[Longrun launch guide](https://github.com/woffko/codex-mcp-longrun#start-a-session-through-the-bridge).
Fully connected projects remain silent in lifecycle hooks; the explicit final
installation/onboarding response still includes the command.

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
silence for fully connected projects, repeated prompting until confirmation or
dismissal, migration from the legacy offered-state format, model filtering, and
switching between eligible and ineligible models in the same thread.

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
