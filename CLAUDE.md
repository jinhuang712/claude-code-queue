# claude-code-queue — dev notes

This repo is a Claude Code **plugin** (a skill + hooks + a slash command) that
adds a prompt queue. `CLAUDE.md` is the entry point for anyone
(human or agent) working on this repo.

## Layout

- `.claude-plugin/plugin.json` — plugin manifest (name, metadata; no `version`
  → git SHA versioning, every commit is a new release).
- `.claude-plugin/marketplace.json` — makes this repo its own single-plugin
  marketplace (install via `/plugin marketplace add jinhuang712/claude-code-queue`).
- `hooks/hooks.json` — declares the `UserPromptSubmit` + `Stop` hooks; commands
  use `${CLAUDE_PLUGIN_ROOT}` so the plugin is self-contained.
- `hooks/queue-hook.py` — the whole mechanism. Modes: `enqueue`
  (UserPromptSubmit) and `deliver` (Stop). Also the CLI for manual ops.
- `commands/queue.md` — the `/queue` slash command (handles the idle path).
- `SKILL.md` — the skill definition Claude loads (frontmatter + behavior).
- `references/` — design + troubleshooting deep dives.
- `tests/test_queue_hook.py` — exercises the hook via subprocess.

## Install model

Distributed as a plugin (NOT npx/npm, NOT a settings.json-patching installer).
The plugin system auto-registers `hooks/hooks.json` on enable — never manually
edit the user's `settings.json`. Paths resolve via `${CLAUDE_PLUGIN_ROOT}`.
Users install with `/plugin marketplace add` + `/plugin install`.

## The core contract (don't break these)

1. **Per-session queue**: storage is `~/.claude/queue/<session_id>/*.msg`. The
   Stop hook only ever pops the *current* session — never another session's
   items (that was the original cross-session-theft bug).
2. **Busy = `status == "busy"` AND marker set.** Neither signal alone is enough;
   see `references/how-it-works.md`. Don't simplify to one signal.
3. **Idle `/queue` is not enqueued** — it's handled immediately as a normal
   turn (no ack/pop round-trip). Enqueueing + popping only happens when busy.
4. **Interrupt must not dead-end**: relying on `status` flipping to idle on Esc
   is what makes this survive interrupts. Don't go back to marker-only.

## Working on the hook

- The hook is re-read on every invocation (`python3 … queue-hook.py`), so edits
  take effect without restarting Claude Code.
- Test before pushing: `make test` (or `python3 -m pytest tests -q`).
- Manual inspection: `python3 hooks/queue-hook.py list|count|clear`.
- Keep the CLI modes (`add`, `list`, `count`, `clear`) working — they're part of
  the public surface and the tests use them.

## Conventions

- One concern per commit. Commit messages explain *why* (the failure mode the
  change addresses), not just *what*.
- No hardcoded absolute paths in shipped files — hook commands use
  `${CLAUDE_PLUGIN_ROOT}`; the plugin is self-contained and copied to the cache
  on install, so absolute paths would break.
- Don't add an `install.sh`/settings-patching layer — the plugin system handles
  install and hook registration.
