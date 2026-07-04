---
name: claude-code-queue
description: Codex-style prompt queue for Claude Code. Use when the user wants to defer a follow-up until after the current turn — type /queue <request> to queue it instead of interrupting. Busy → waiting area (zero interruption), popped automatically when the turn ends; idle → handled immediately.
---

# claude-code-queue

A per-session FIFO prompt queue. `/queue <request>` defers a message so it runs
**after** the current turn ends, instead of being injected at the next
tool-call boundary.

## Behavior

- **Busy** (a turn is running): `/queue X` → stored in the waiting area; the
  current turn is **not interrupted**. When it ends, the oldest queued item is
  popped (`🔔 queued message popped`) and auto-started.
- **Idle**: `/queue X` → handled immediately as a normal turn (nothing to wait
  behind — no enqueue/pop round-trip).
- Multiple items drain **FIFO**, one per turn, in the **same session** (no
  cross-session theft).
- A **normal (non-`/queue`) prompt** submitted while busy preempts the queue —
  real requests always run before deferred ones.

Busy detection requires **both** `status == "busy"` **and** a self-maintained
busy marker. Each signal alone has a blind spot — stale status right after a
Stop, or a marker stuck after an interrupt (Esc) — so the AND closes both. Full
rationale in `references/how-it-works.md`.

## When to suggest `/queue`

Offer it when the user:
- says "next", "after this", "once you finish", "then…";
- sends a second request while you're still working on the first;
- is about to step away and wants follow-ups to run unattended.

Do **not** use `/queue` for the current primary task — only for things that
should wait.

## Handling a popped item

When the Stop hook pops a queued item, it's fed back as the reason to continue.
**Just handle the request directly** — don't narrate "this was queued" or
mention the queue mechanism.
