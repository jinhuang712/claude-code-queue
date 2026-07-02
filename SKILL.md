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
| `hooks/queue-hook.py enqueue` | `UserPromptSubmit` | Intercepts `/queue`. If Claude is **busy** → store + block (zero mid-turn injection). If **idle** → let the slash command handle it. |
| `commands/queue.md` (`/queue`) | — | Idle-path fallback: enqueues with a one-line ack. |
| `hooks/queue-hook.py deliver` | `Stop` | When a turn ends, pops the oldest queued item and feeds it back to Claude so it keeps working. Drains the whole queue in FIFO order. |

Busy/idle is detected from Claude Code's own per-session `status` field
(`~/.claude/sessions/*.json`). Anything that isn't explicitly `idle` is treated
as busy, so the safe default is "don't interrupt."

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
