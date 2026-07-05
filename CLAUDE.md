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
- `assets/` — bilingual GitHub Pages landing pages (EN/ZH); unrelated to the
  plugin mechanism, just served straight from this repo's root via Pages.

## Install model

Distributed as a plugin (NOT npx/npm, NOT a settings.json-patching installer).
The plugin system auto-registers `hooks/hooks.json` on enable — never manually
edit the user's `settings.json`. Paths resolve via `${CLAUDE_PLUGIN_ROOT}`.
Users install with `/plugin marketplace add` + `/plugin install`.

## The core contract (don't break these)

`references/how-it-works.md` is the single source of truth for *how* busy
detection, idle-handling, and native-prompt preemption are implemented — don't
restate that mechanism here or in `SKILL.md`, link to it instead. (The exact
formula drifted out of sync with the code more than once from being duplicated
across docs.) What must stay true, regardless of implementation:

1. **Per-session isolation**: the Stop hook only ever pops the *current*
   session's queue — never another session's (the original cross-session-theft
   bug).
2. **Busy detection uses two independent signals, not one** — each has a blind
   spot alone; see the reference doc for which, and why.
3. **Idle `/queue` is handled immediately**, not enqueued — no ack/pop
   round-trip when there's nothing to wait behind.
4. **An interrupt (Esc) must not dead-end a future `/queue`** — busy detection
   must self-heal afterward, not require a manual `/queue clear`.

Changing the *mechanism* behind any of these is fine; changing the *guarantee*
is a breaking change — update the reference doc and its tests together.

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
