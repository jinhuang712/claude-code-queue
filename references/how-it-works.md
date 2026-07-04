# How it works

claude-code-queue gives Claude Code a **prompt queue**: a message typed
while Claude is busy is held in a waiting area and runs only after the current
turn ends — it is **not** injected at the next tool-call boundary (which is how
Claude Code handles queued input by default).

## Three pieces

| Piece | Hook event | Job |
|---|---|---|
| `hooks/queue-hook.py enqueue` | `UserPromptSubmit` | Route `/queue`. A non-`/queue` prompt **sets a busy marker**. A `/queue` prompt: **busy → store + block**; **idle → let the slash command handle it now**. |
| `commands/queue.md` | — | Idle path only — handle the request now as a normal turn. |
| `hooks/queue-hook.py deliver` | `Stop` | Pop the oldest item for **this session**, print `🔔 queued message popped`, feed it back so Claude auto-starts it. Re-set the marker; clear it when the queue empties. |

Storage is per-session: `~/.claude/queue/<session_id>/*.msg` (one file per item,
FIFO by filename) plus a `.busy` marker file.

## Why busy detection needs BOTH signals

`busy = (status == "busy") AND (marker set)`. Neither signal alone is reliable.

**The status field can be stale.** Right after a normal `Stop`, Claude Code's
per-session `status` (`~/.claude/sessions/<pid>.json`) may still read `"busy"`
for a moment. If we trusted it alone, a `/queue` typed in that window would be
blocked while actually idle → **dead message** (no turn running to drain it).

**The marker can get stuck.** The marker is set on turn start
(`UserPromptSubmit`, non-`/queue`) and cleared on a normal `Stop`. But an
**interrupt (Esc) fires no `Stop`**, so the marker stays set. If we trusted it
alone, every `/queue` after an interrupt would be blocked forever → dead message.

**The AND closes both:**
- *Interrupt*: marker stuck, but `status` flips to `idle` → not busy → `/queue`
  allowed. ✅
- *Stale status after Stop*: `status` reads busy, but marker cleared → not busy
  → allowed. ✅
- *Genuinely working*: both set → busy → block (zero interruption). ✅

A marker older than 1 hour is treated as stale (crashed/abandoned turn).

## Why idle `/queue` is not enqueued

If idle `/queue X` were enqueued and then popped, it would cost **two model
turns** (an ack turn, then the actual handling turn) plus a noisy Stop-hook pop.
Since there's nothing to wait behind when idle, the hook just lets `/queue X`
through and the slash command handles `X` as a **single normal turn**. The queue
is only involved when Claude is actually busy.

## Normal prompts preempt the queue

A non-`/queue` prompt submitted while Claude is busy goes to **Claude Code's
native queue** (prompts held until the turn ends). Without care, our `Stop`
hook would drain our queue at every turn end and **preempt** that real prompt —
deferred items cutting in front of the user's actual request.

So the enqueue hook counts normal prompts submitted while busy
(`~/.claude/queue/<sid>/.native`), and the `Stop` hook **yields** while that
counter is positive — it allows the stop, Claude Code delivers the real prompt,
and our queue only resumes once no real prompt is waiting. Net effect: a real
prompt always runs before deferred `/queue` items.

## Why blocking (not "ack then continue")

The whole point is zero interruption: a busy `/queue X` must not inject anything
into the running turn. Blocking the `UserPromptSubmit` is the only way to
achieve that. The trade-off is the dead-message constraint above, which the AND
handles.

One residual: when a queued item is popped at turn end, Claude Code shows a
`Stop hook feedback:` banner with the message — that's its fixed UI for a
Stop-hook block, not something this skill can hide. It only appears in the
genuine busy-then-pop path.
