---
name: claude-code-queue
description: Codex-style prompt queue for Claude Code — defer a message so it runs AFTER the current turn instead of being injected at the next tool-call boundary. Suggest /queue when the user wants to line up a follow-up task without interrupting work in progress.
---

# claude-code-queue

A FIFO prompt queue for Claude Code that gives you Codex-style **queue** semantics.

## The problem it solves

By default, when you press Enter while Claude Code is mid-turn, your message is
injected at the **next tool-call boundary** — i.e. it interrupts and redirects
the current task (this is Codex's "steer" behavior). There has been no way to
say "don't interrupt, just run this after I finish."

This skill adds that. Type:

```
/queue 请帮我重构 auth 模块
```

and the request is stored and delivered **only after the current turn ends**.

## How it works

Three pieces cooperate:

| Piece | Event | Role |
|---|---|---|
| `hooks/queue-hook.py enqueue` | `UserPromptSubmit` | A non-`/queue` prompt **sets a busy marker** (a turn started). A `/queue` prompt stores the message scoped to this session; if the marker is fresh it's **blocked** (waiting area, zero interruption), otherwise let through so it pops immediately. |
| `commands/queue.md` (`/queue`) | — | One-line ack (idle path only). |
| `hooks/queue-hook.py deliver` | `Stop` | When a turn ends, pops the oldest queued item **for this session**, prints `🔔 queued message popped`, and feeds it back so Claude auto-starts it. Re-sets the busy marker; clears it when the queue empties. |

The queue is **per-session** (`~/.claude/queue/<session_id>/`), so an item is
only picked up by the session that queued it. Busy/idle requires **both** a
self-maintained marker **and** Claude Code's `status == "busy"` — the marker
guards against stale status after a `Stop`, and `status` catches interrupts
(Esc), which leave the marker stuck but flip status to idle.

## When Claude should suggest `/queue`

Offer `/queue` when the user:
- mentions doing something "next", "after this", "once you finish", "then…";
- sends a second request while you're visibly still working on the first;
- is about to step away and wants follow-ups to run unattended.

Do **not** use `/queue` for the current, primary task — only for things that
should wait.

## Manual operations

```bash
python3 ~/.claude/hooks/queue-hook.py list     # show pending
python3 ~/.claude/hooks/queue-hook.py count    # just the count
python3 ~/.claude/hooks/queue-hook.py clear    # empty the queue
python3 ~/.claude/hooks/queue-hook.py add "…"  # enqueue from shell
```

Inside Claude Code, `/queue` (no args) also lists the queue, and
`/queue clear` empties it.
