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

- **Busy** (Claude is working): the message goes to a **waiting area** and the
  current turn is **not interrupted** — no mid-tool-call injection. When the
  turn finishes, the oldest item is popped (`🔔 queued message popped`) and
  auto-starts.
- **Idle**: handled immediately as a normal request (nothing to wait behind — no
  extra ack/pop round-trip).
- Multiple items drain **FIFO**, one per turn, until the queue is empty.

## How it works

| Piece | Hook event | Job |
|---|---|---|
| `hooks/queue-hook.py enqueue` | `UserPromptSubmit` | A non-`/queue` prompt **sets a busy marker** (a turn started). A `/queue` prompt: if busy → store + **block** (waiting area, zero interruption); if idle → let the slash command handle it now as a normal turn (no enqueue, no extra round-trip). |
| `commands/queue.md` | — | Idle path only — handle the request now, like a normal prompt. |
| `hooks/queue-hook.py deliver` | `Stop` | Pop the oldest item for **this session**, print `🔔 queued message popped`, and feed it back so Claude auto-starts it. Re-sets the busy marker (the queued item is now its own turn). If the queue is empty, clear the marker (idle). |

The queue is **per-session** (`~/.claude/queue/<session_id>/`), so an item is
only ever picked up by the session that queued it — no cross-session theft.

Busy detection requires **both** a self-maintained marker **and** Claude Code's
`status == "busy"` — each covers the other's blind spot. The marker is set when
a real turn starts and cleared when the queue drains, so it guards against a
stale `status` right after a `Stop`. The `status` field catches **interrupts**
(Esc), which leave the marker stuck but flip `status` to `idle`. Either signal
alone dead-ends or interrupts; the AND closes both. A marker older than 1 hour
is treated as stale (crashed/abandoned turn).

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
| `/queue 请帮我…` (while Claude is idle) | Handled immediately, like a normal prompt. |
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

- Busy/idle is decided by a self-maintained marker (see *How it works*), not
  Claude Code's `status` field. If a queued item ever seems stuck (e.g. after a
  crash), `/queue clear` or sending any prompt resets things — the `Stop` hook
  drains the queue at turn end.
- Hooks are user-scoped (`~/.claude/settings.json`), so this works across all
  your projects.
- `/queue` is owned by this skill; don't expect another `/queue` command to
  coexist.

## License

MIT — see [LICENSE](LICENSE).
