---
description: Queue a prompt to run after the current turn, in this session only (Codex-style queue, no mid-turn interruption)
---

The `/queue` message has **already been stored** by the UserPromptSubmit hook (scoped to this session). You do not need to run any command — just acknowledge in one line and stop:

```
📝 已入队（本任务跑完后自动开始）
```

Do not work on the queued request now. If you were mid-task, immediately resume that task after the one-line ack. The queued item will be delivered automatically when the current turn ends.

If for some reason nothing was queued (e.g. `$ARGUMENTS` is empty), run this to show the queue instead:

```bash
python3 "$HOME/.claude/hooks/queue-hook.py" list
```
