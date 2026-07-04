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

```bash
git clone <this-repo> ~/dev/skills/claude-code-queue
cd ~/dev/skills/claude-code-queue
./scripts/install.sh        # copies hook + command + skill, wires settings.json
```

Then restart Claude Code so the hooks load. Prefer to wire it yourself? Merge
[`hooks/settings.example.json`](hooks/settings.example.json) into
`~/.claude/settings.json` (replace the placeholder path).

## Usage

| You type | What happens |
|---|---|
| `/queue 请帮我…` (busy) | Stored silently; runs after the current turn. |
| `/queue 请帮我…` (idle) | Handled immediately, like a normal prompt. |
| `/queue` | Show this session's queue. |
| `/queue clear` | Empty this session's queue. |

Shell access: `python3 ~/.claude/hooks/queue-hook.py list \| count \| clear \| add "…"`.

## Directory structure

- `SKILL.md` — the skill definition Claude loads.
- `hooks/queue-hook.py` — the whole mechanism (`enqueue` + `deliver` + CLI).
- `hooks/settings.example.json` — hook config snippet to merge into settings.
- `commands/queue.md` — the `/queue` slash command (idle path).
- `scripts/install.sh` / `uninstall.sh` — idempotent install / remove.
- `references/` — [how-it-works](references/how-it-works.md) · [troubleshooting](references/troubleshooting.md).
- `tests/` — pytest suite (`make test`).
- `CLAUDE.md` — dev notes for anyone working on this repo.

## License

MIT — see [LICENSE](LICENSE).
