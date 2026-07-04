# claude-code-queue

> Codex-style **queue** for Claude Code: `/queue …` runs *after* the current
> turn when Claude is busy — not injected at the next tool-call boundary.

## Why

Pressing Enter while Claude Code is mid-turn injects your message at the next
tool-call boundary (Codex calls this *steer*) — it interrupts and redirects the
running task. This skill adds the missing *queue*: the message waits, then runs
when the turn ends, in the same session.

- **Busy**: goes to a waiting area; the current turn is **not** interrupted.
  Popped and auto-started when it finishes (`🔔 queued message popped`).
- **Idle**: handled immediately as a normal turn (nothing to wait behind).
- Multiple items drain **FIFO**, one per turn, per session.

## Install

In Claude Code:

```text
/plugin marketplace add jinhuang712/claude-code-queue
/plugin install claude-code-queue@claude-code-queue
```

Restart Claude Code (or `/reload-plugins`) so the hooks load. The plugin
auto-registers its hooks — **no `settings.json` editing needed.**

Updates: `/plugin update claude-code-queue@claude-code-queue` (or just push —
with no `version` set, every commit is a new version).

<details><summary>Manual / dev install (no marketplace)</summary>

Clone into the skills dir — loads as `claude-code-queue@skills-dir`:

```bash
git clone https://github.com/jinhuang712/claude-code-queue ~/.claude/skills/claude-code-queue
```

</details>

## Usage

| You type | What happens |
|---|---|
| `/queue refactor the auth module` (busy) | Stored silently; runs after the current turn. |
| `/queue refactor the auth module` (idle) | Handled immediately, like a normal prompt. |
| `/queue` | Show this session's queue. |
| `/queue clear` | Empty this session's queue. |

Shell access: `python3 ~/.claude/hooks/queue-hook.py list \| count \| clear \| add "…"`.

## Examples

**Queue a follow-up while Claude is busy** (the main use case — no interruption):

```text
# Claude is mid-turn refactoring auth.py. Line up the next task without
# cutting in:
/queue then run the test suite and fix anything that breaks
# → 📝 Queued (runs after the current turn, 1 pending): then run the test…
# Claude keeps working; when the turn ends:
# → 🔔 queued message popped (queue empty): then run the test suite…
#   …and it auto-starts.
```

**Line up several follow-ups** (FIFO, one per turn):

```text
/queue update the README with the new flag
/queue commit and push
# queue: [update the README…] → [commit and push]
```

**A real prompt preempts the queue** — normal (non-`/queue`) prompts submitted
while busy always run *before* deferred ones:

```text
/queue polish the docs later              # deferred
actually fix this blocking bug first      # real prompt — runs first
```

**Idle `/queue`** is just a normal prompt (nothing to wait behind):

```text
/queue generate a type for the config
# handled immediately, no waiting-area ceremony
```

**Inspect / clear**:

```text
/queue           # show this session's queue
/queue clear     # empty this session's queue
```

```bash
# shell CLI (works outside Claude Code too)
python3 ~/.claude/hooks/queue-hook.py list       # all sessions' pending items
python3 ~/.claude/hooks/queue-hook.py count      # total pending
python3 ~/.claude/hooks/queue-hook.py clear      # empty everything (all sessions)
python3 ~/.claude/hooks/queue-hook.py add "…"    # enqueue to _global (won't auto-drain)
```

## Core Files

- `.claude-plugin/plugin.json` — plugin manifest (name, metadata).
- `.claude-plugin/marketplace.json` — makes this repo a single-plugin marketplace.
- `SKILL.md` — the skill definition Claude loads.
- `hooks/hooks.json` — declares the `UserPromptSubmit` + `Stop` hooks (uses `${CLAUDE_PLUGIN_ROOT}`).
- `hooks/queue-hook.py` — the whole mechanism (`enqueue` + `deliver` + CLI).
- `commands/queue.md` — the `/queue` slash command (idle path).
- `references/` — [how-it-works](references/how-it-works.md) · [troubleshooting](references/troubleshooting.md).
- `tests/` — pytest suite (`make test`).
- `CLAUDE.md` — dev notes.

## License

MIT — see [LICENSE](LICENSE).
