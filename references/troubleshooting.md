# Troubleshooting

## A queued message never ran

Symptom: you typed `/queue X` while Claude seemed busy, saw
`📝 Queued (runs after the current turn, …)`, but `X` never started.

Cause: the hook thought Claude was busy when it was actually idle (so the
blocked message had no turn to drain it). This was a bug in earlier versions
that trusted a single signal; the current marker-AND-status check (see
[how-it-works.md](how-it-works.md)) should prevent it.

Fix:
```bash
Q=$(find ~/.claude -name queue-hook.py 2>/dev/null | head -1)
python3 "$Q" list     # see what's stuck
python3 "$Q" clear    # drop stale items
```
Then just send any normal prompt — the `Stop` hook drains the queue at turn end.

## Cross-session confusion

If a message queued in session A was processed by session B: you're on a version
before per-session isolation. Update to current `master`. The queue is now
`~/.claude/queue/<session_id>/`, and each session's `Stop` hook only pops its
own items.

## `/queue` after an interrupt (Esc) gets stuck

If interrupting a turn leaves the session unable to accept `/queue` normally:
this was the "marker stuck" bug, fixed by also requiring `status != "idle"`. If
you still see it, the Claude Code version may not flip `status` to idle on Esc —
run `/queue clear` or send a normal prompt to reset.

## Hooks aren't firing at all

- Confirm the plugin is enabled: `/plugin` inside Claude Code should list
  `claude-code-queue`. The plugin system auto-registers `hooks/hooks.json` —
  there's nothing to add to `~/.claude/settings.json` by hand.
- Hooks load at session start — **restart Claude Code** (or `/reload-plugins`)
  after install or update.
- `find ~/.claude -name queue-hook.py` to confirm the file actually landed on
  disk, and that you're pointing the commands below at that path.

## Debug logging

```bash
CLAUDE_QUEUE_DEBUG=1   # set in settings.json env, then restart
```
Appends per-invocation lines to `~/.claude/queue/<session_id>/.debug` showing
the event, session id, status, and decision.

## Manual operations

```bash
Q=$(find ~/.claude -name queue-hook.py 2>/dev/null | head -1)
python3 "$Q" list      # all sessions' pending items
python3 "$Q" count     # total pending
python3 "$Q" clear     # empty everything (all sessions)
python3 "$Q" add "…"   # enqueue to _global (won't auto-drain)
```
