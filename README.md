# claude-code-queue

> `/queue <request>` — defer a request until the current turn ends, instead of
> having it injected mid-turn at the next tool-call boundary.

📄 **Landing page** (with a live animated demo of the queue behavior): [English](https://jinhuang712.github.io/claude-code-queue/en_US.html) · [中文](https://jinhuang712.github.io/claude-code-queue/cn_ZH.html)

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

```bash
curl -fsSL https://jinhuang712.github.io/claude-code-queue/install.sh | bash
```

That drops one file — `SKILL.md` — into `~/.claude/skills/queue/`. The folder
name (`queue`) is what registers the command. Restart Claude Code (skills load
at session start) and you have a bare `/queue`. Re-run to update; to remove,
`rm -rf ~/.claude/skills/queue`.

> **Why a standalone skill and not a plugin / marketplace?** Because a bare
> `/queue` is the whole point, and a plugin can't give you one. Claude Code
> *always* namespaces a plugin's command as `/plugin-name:command` — even the
> cleanest single-`SKILL.md`-at-root plugin registers as `/queue:queue`
> (verified live against Claude Code v2.1.201 and the plugins reference). The
> frontmatter `name` field only controls the part after the colon; it can't
> drop the prefix. A bare `/queue` only comes from a standalone skill under
> `~/.claude/skills/`, so that's how this ships.

Prefer not to pipe `curl` into `bash`? Do it by hand — it's one file:

```bash
mkdir -p ~/.claude/skills/queue
curl -fsSL https://raw.githubusercontent.com/jinhuang712/claude-code-queue/master/SKILL.md \
  -o ~/.claude/skills/queue/SKILL.md
```

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
