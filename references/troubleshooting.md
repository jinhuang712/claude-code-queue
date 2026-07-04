# Troubleshooting

## A queued message never ran

Symptom: you typed `/queue X` while Claude seemed busy, saw
`📝 Queued (runs after the current turn, …)`, but `X` never started.

Cause: the hook thought Claude was busy when it was actually idle (so the
blocked message had no turn to drain it). This was a bug in earlier versions
that trusted a single signal; the current `status AND marker` check (see
[how-it-works.md](how-it-works.md)) should prevent it.

Fix:
```bash
python3 ~/.claude/hooks/queue-hook.py list     # see what's stuck
python3 ~/.claude/hooks/queue-hook.py clear    # drop stale items
```
Then just send any normal prompt — the `Stop` hook drains the queue at turn end.

## Cross-session confusion

If a message queued in session A was processed by session B: you're on a version
before per-session isolation. Update to current `master`. The queue is now
`~/.claude/queue/<session_id>/`, and each session's `Stop` hook only pops its
own items.

## `/queue` after an interrupt (Esc) gets stuck

If interrupting a turn leaves the session unable to accept `/queue` normally:
this was the "marker stuck" bug, fixed by also requiring `status == "busy"`. If
you still see it, the Claude Code version may not flip `status` to idle on Esc —
run `/queue clear` or send a normal prompt to reset.

## Hooks aren't firing at all

- Confirm the entries are in `~/.claude/settings.json` under
  `hooks.UserPromptSubmit` and `hooks.Stop` (run `scripts/install.sh` or merge
  `hooks/settings.example.json`).
- Hooks load at session start — **restart Claude Code** after install.
- Check the hook file exists at the path settings points to.

## Debug logging

```bash
CLAUDE_QUEUE_DEBUG=1   # set in settings.json env, then restart
```
Appends per-invocation lines to `~/.claude/queue/<session_id>/.debug` showing
the event, session id, status, and decision.

## Manual operations

```bash
python3 ~/.claude/hooks/queue-hook.py list      # all sessions' pending items
python3 ~/.claude/hooks/queue-hook.py count     # total pending
python3 ~/.claude/hooks/queue-hook.py clear     # empty everything (all sessions)
python3 ~/.claude/hooks/queue-hook.py add "…"   # enqueue to _global (won't auto-drain)
```
