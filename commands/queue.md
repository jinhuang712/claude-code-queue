---
description: Queue a prompt — runs after the current turn if Claude is busy, or immediately if idle (same session)
---

The user typed `/queue` with the request below. The UserPromptSubmit hook determined Claude is **idle** right now (no turn running), so there is nothing to wait behind. Handle the request immediately, as if the user had typed it directly. Do not mention the queue or that this was queued — just respond to the request:

$ARGUMENTS
