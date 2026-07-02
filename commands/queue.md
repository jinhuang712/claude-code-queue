---
description: Queue a prompt to run after the current turn (Codex-style queue, no mid-turn interruption)
---

You are receiving a `/queue` command. The user wants this request **deferred**, not executed right now.

Run this single command to enqueue it (the request is passed via stdin so any quotes / newlines / unicode are safe):

```bash
python3 "$HOME/.claude/hooks/queue-hook.py" add <<'__QUEUE_MSG__'
$ARGUMENTS
__QUEUE_MSG__
```

Then reply with **exactly one line** and stop — do not engage with the request content, do not start working on it:

```
📝 已入队（当前任务跑完后自动开始）
```

Notes:
- If you were mid-task when this arrived, immediately resume that task after the one-line ack.
- If `$ARGUMENTS` is empty, instead of enqueuing run `python3 "$HOME/.claude/hooks/queue-hook.py" list` and show the current queue.
