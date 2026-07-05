# claude-code-queue

> `/queue <request>` — defer a request until the current turn ends, instead of
> having it injected mid-turn at the next tool-call boundary.

📄 **Landing page**: [English](https://jinhuang712.github.io/claude-code-queue/assets/en_US.html) · [中文](https://jinhuang712.github.io/claude-code-queue/assets/cn_ZH.html)

## How it works (it's simpler than you'd think)

Claude Code natively treats plain messages and slash commands differently
while a turn is running:

- A **plain message** typed mid-turn is injected at the next tool-call
  boundary — it interrupts and can redirect the running task.
- A **recognized slash command** typed mid-turn is held in the native prompt
  queue and only delivered after the whole turn ends — FIFO, one per turn.

So all a "queue" needs is to make `/queue` a recognized slash command. That's
this entire project: a command definition. No hooks, no daemon, no storage —
Claude Code's own scheduler does the queueing.

The command body adds one genuinely useful layer: queued requests usually run
after you've stepped away, so it instructs Claude to proceed unattended (no
clarifying questions; note assumptions; end with a one-line summary).

## Install

Clone into your skills directory — the folder name **must** be `queue`, because
that's what becomes the command:

```bash
git clone https://github.com/jinhuang712/claude-code-queue ~/.claude/skills/queue
```

Restart Claude Code (skills load at session start). You now have a bare `/queue`.

> **Why not a plugin / marketplace?** Claude Code *always* namespaces a plugin's
> commands as `/plugin-name:command` — a marketplace install would give you
> `/queue:queue`, not `/queue`. A bare `/queue` only comes from a standalone
> skill under `~/.claude/skills/`, so that's how this ships. (Verified against
> the docs and a live install.)

Then:

| You type | What happens |
|---|---|
| `/queue refactor the auth module` (while busy) | Held natively; runs after the current turn. |
| `/queue refactor the auth module` (while idle) | Runs immediately, like a normal prompt. |
| several `/queue …` while busy | Delivered FIFO, one per turn. |
| a plain message while busy | Injected at the next tool-call boundary — it preempts anything queued. |

`disable-model-invocation: true` is set, so Claude never triggers this skill
on its own — only you do, by typing `/queue`.

## License

MIT — see [LICENSE](LICENSE).
