# claude-code-queue

> Codex-style **queue** for Claude Code: type `/queue …` and the request runs
> *after* the current turn — not injected at the next tool-call boundary.

## Why

When you press Enter while Claude Code is mid-turn, your message is injected at
the next tool-call boundary. That **interrupts and redirects** the running task
(Codex calls this *steer*). There's been no built-in way to say *"don't
interrupt — just queue this for when you finish."* This skill adds that.

```
/queue 请帮我重构 auth 模块，并补上测试
```

- **Busy** (Claude is working): the message is stored; the current turn is
  **not** interrupted. When the turn ends, Claude picks it up automatically.
- **Idle**: the message is queued and starts immediately on the next turn.
- Multiple items drain **FIFO**, one per turn, until the queue is empty.

## How it works

| Piece | Hook event | Job |
|---|---|---|
| `hooks/queue-hook.py enqueue` | `UserPromptSubmit` | Intercept `/queue`. **Busy → store + block** (no mid-turn injection). **Idle → pass through** to the slash command. |
| `commands/queue.md` | — | Idle-path enqueue + one-line ack. |
| `hooks/queue-hook.py deliver` | `Stop` | Pop the oldest item and feed it back so Claude keeps going. Drains FIFO. |

Busy/idle is read from Claude Code's own per-session `status` field
(`~/.claude/sessions/*.json`). Anything not explicitly `idle` is treated as
busy — so the safe default is "don't interrupt."

This is the **B-class** queue (single-session, don't-interrupt), distinct from
rate-limit batching tools like `JCSnap/claude-code-queue` (which survive 5-hour
token windows by feeding prompts to headless `claude -p`).

## Install

```bash
git clone <this-repo> ~/dev/claude-code-queue
cd ~/dev/claude-code-queue
./install.sh
```

Then **restart Claude Code** (or open a new session) so the hooks load.

Requirements: Claude Code, Python 3 (standard on macOS/Linux).

## Usage

| You type | What happens |
|---|---|
| `/queue 请帮我…` (while Claude is busy) | Stored silently; runs after the current turn. |
| `/queue 请帮我…` (while Claude is idle) | Acked, then runs immediately. |
| `/queue` | Show the current queue. |
| `/queue clear` | Empty the queue. |

Shell access for scripting / inspection:

```bash
python3 ~/.claude/hooks/queue-hook.py list      # show pending
python3 ~/.claude/hooks/queue-hook.py count     # count
python3 ~/.claude/hooks/queue-hook.py add "…"   # enqueue
python3 ~/.claude/hooks/queue-hook.py clear     # empty
```

Queue entries live in `~/.claude/queue/*.msg` (one file per item, plain text).
Survives restarts.

## Uninstall

```bash
./uninstall.sh
```

Removes the hooks from `settings.json` and deletes installed files. Queue data
at `~/.claude/queue/` is left untouched.

## Notes / limitations

- Busy detection relies on Claude Code writing `"status"` to session files. If
  the status can't be determined, the hook defaults to **busy** (blocks) to
  protect the "don't interrupt" guarantee. If a queued item ever seems stuck,
  send any prompt — the `Stop` hook drains the queue at turn end.
- Hooks are user-scoped (`~/.claude/settings.json`), so this works across all
  your projects.
- `/queue` is owned by this skill; don't expect another `/queue` command to
  coexist.

## License

MIT — see [LICENSE](LICENSE).
