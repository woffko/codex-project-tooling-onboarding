---
name: project-tooling-onboarding
description: Audit and connect project-scoped LSP MCP, Project Memory, Longrun, exact Codex trust, and local routing when a session reports missing tooling or the user asks to connect the project. Do not use for projects already reported fully connected.
---

# Project tooling onboarding

Use the bundled audit before proposing or changing tooling:

```bash
python3 scripts/tooling_onboarding.py audit --cwd /absolute/project/root --json
```

Resolve `scripts/tooling_onboarding.py` relative to this skill directory. The
audit is read-only and treats `/home`, the user home, and other broad parents as
non-project roots.

## Offer until resolved, then act on confirmation

- If `fully_connected` is true, do not mention onboarding.
- If no exact project root is selected, explain that project-scoped tooling
  cannot be audited safely yet and ask whether to identify the root and then
  audit/connect the applicable LSP MCP, Project Memory, Longrun, and exact
  Codex trust components. Never enroll the whole home directory.
- If integrations are missing and the current user message does not already
  authorize connecting them, list the exact missing components and ask one
  concise yes/no question before other mutations.
- If the current user message explicitly asks to connect, install, enable, or
  configure the tooling, treat it as confirmation and proceed without asking
  again.
- If the user declines, record that exact thread/audit fingerprint before
  continuing so the hook remains silent until the tooling state changes:

  ```bash
  python3 scripts/tooling_onboarding.py dismiss \
    --cwd /absolute/project/root-or-current-cwd \
    --session-id SESSION_ID
  ```

  Resolve the script relative to this skill. Do not dismiss merely because the
  model chose to ignore the offer.
- Never mutate a repository, global config, Project Memory registry, or secret
  store merely because a hook ran.

## Resolve the correct project

- Use the exact Git root associated with the task. Never enroll `/home`, the
  user's home directory, or a parent containing multiple repositories.
- For a resumed historical thread, inspect its rollout and recent substantive
  working directories. Do not mistake a later tool-pilot checkout for the
  actual project.
- Preserve dirty worktrees and existing instructions. Stage, commit, publish,
  or overwrite nothing unless separately authorized.

## Connect the selected components

### LSP MCP

- Before the first LSP setup, ask which backends the user wants. Do not select
  automatically from source files or from a default preset. If the user already
  gave an explicit selection for this project, use it without asking again.
- Obtain the full numbered question from the audit's `lsp_selection_prompt` or:

  ```bash
  python3 scripts/tooling_onboarding.py lsp-options
  ```

  Present it in the user's language, retaining the numbers, backend names, and
  language descriptions. Recommend `1 2 3 4` (C/C++, Python, JavaScript/TypeScript,
  Rust), but require an answer before configuring LSP. Ask one free-text question;
  when `request_user_input_async` is available, put the numbered list in `title`
  and omit `options`, so the user can enter multiple numbers together.
- Accept numbers in any order, separated by spaces, commas, or semicolons;
  duplicates are harmless. For example, `4 1 3` means Rust, C/C++, and
  JavaScript/TypeScript. `0` alone means no LSP; do not mix it with other numbers.
  Clarify invalid numbers rather than guessing. Silence is not a selection.
- After onboarding authorization and the user's selection, initialize a missing
  portable manifest with those numbers:

  ```bash
  python3 scripts/tooling_onboarding.py init-lsp \
    --cwd "/absolute/project/root" --selection "4 1 3"
  ```

  This creates only the chosen backend entries. It preserves an existing
  manifest, and `0` records an empty backend selection without connecting LSP.
  Keep existing settings unless the user explicitly requests a change; merge
  such changes without replacing workspace roots, build flags, or exclusions.
- Check that each selected backend is supported by the installed router and
  host profile. Identify missing prerequisites before reporting a connection;
  do not silently substitute or omit a selected backend. Selection authorizes
  only the applicable onboarding steps, not unrelated host or trust changes.
- Keep one portable `.lsp-mcp.toml` with relative, in-repository workspace
  paths. Large monorepos require narrow roots; never index the whole home.
- Merge the read-only `lsp_mcpls` table into the ignored local
  `.codex/config.toml`; preserve every existing MCP/plugin table.
- Add the semantic-navigation policy to the active instruction chain. If a
  same-directory `AGENTS.override.md` is used, repeat every same-directory
  instruction that it replaces.
- Verify each enabled language with a real read-only semantic MCP call. A
  successful executable check, build, or lexical search is not semantic proof.
  In an empty project, distinguish configured backends and verified server
  initialization from semantic checks that must wait for real source files.

### Project Memory

- Derive a stable project key from an unambiguous existing mapping or reviewed
  repository identity; never guess among same-root logical projects.
- Enroll the exact canonical root, add the key to local routing instructions,
  and enable the lean recall/read/remember/report-stale tools.
- Enable test-secret storage only when the user explicitly classifies the
  equipment as test-only. Store credentials only through encrypted test assets;
  never place plaintext in chat, source, Git, argv, environment, logs, or
  delegated prompts.
- Prefer `project_memory_stage_test_asset_for_longrun` for a finite secret stdin
  payload. Keep plaintext retrieval approval-gated and use it only when a safe
  destination exists.
- Verify enrollment and one focused recall or checkpoint read.

### Longrun

- Use the installed guarded enrollment script to add the exact root while
  preserving the global config and creating a private backup.
- Enable the inherited local `longrun` table without copying secret or mutable
  environment values into the repository.
- Verify current server health, exact allowed-root coverage, shell-disabled
  policy, and the installed protected launcher version.
- With `codex-longrun` plus an active Goal, use one `start_job` with
  `wake_policy="goal"`, require `automatic_wakeup=true`, end the turn, and call
  `get_job` once only after automatic continuation. Never poll.
- Without a pending Goal, require `bridge_reachable=true` and
  `session_wakeup_supported=true`, then use `wake_policy="session"` in its own
  executor call. The coordinator interrupts the held call and records a startup
  receipt. Do not mistake that interruption for a failed launch or submit a
  duplicate. Never create or reactivate a Goal merely to obtain wakeup.

### Trust and local files

- Add exact project trust only after user confirmation. Back up and atomically
  validate `~/.codex/config.toml`; do not trust a broad parent.
- Keep host-local `.codex/config.toml` and `AGENTS.override.md` excluded from
  Git. Leave `.lsp-mcp.toml` portable and visible for deliberate review.
- Do not weaken sandbox, approvals, network policy, hook trust, or credential
  rules as part of onboarding.

## Finish and hand off

Run the audit again. Report exact runtime evidence, anything intentionally
unverified, local ignored files, and whether the portable manifest remains
untracked. Tool/config changes require a new Codex process.

Always include a copy-paste bridge launch command in the final response after
authorized installation or project connection. The fully-connected silence rule
applies to unsolicited hook offers, not this requested completion handoff.
Use the audit's shell-quoted `launch_command`; pass the actual `--session-id`
when known (the CLI also reads `CODEX_THREAD_ID`/`CODEX_SESSION_ID`). Its
`resume_command` resumes that thread and `start_command` starts a new session.
Do not substitute plain `codex resume`, which does not start the bridge.

For a known thread, the command has this shape with actual, shell-quoted values:

```bash
"$HOME/.local/share/codex-longrun-mcp/.venv/bin/codex-longrun" \
  resume -C "/absolute/project/root" -- "SESSION_ID"
```

Without a known thread ID, provide:

```bash
"$HOME/.local/share/codex-longrun-mcp/.venv/bin/codex-longrun" \
  -C "/absolute/project/root"
```

After plugin installation alone, explain that project tooling still needs to be
audited/connected. If the project root is not selected, label the command as a
template; never choose the plugin checkout or home directory as the user's project.

Do not launch a second writer for an already active thread. If resume reports
an active writer, inspect the exact process tree and active Longrun jobs before
terminating anything.
