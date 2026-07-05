# claude-code-queue — dev notes

A single skill: `/queue <request>` defers a request until the current turn
ends. There is deliberately **no mechanism** here — no hooks, no scripts, no
storage. Read the "History" section before adding any.

## Layout

- `SKILL.md` — the whole skill: frontmatter (`disable-model-invocation: true`,
  user-invoked only) + the instruction body delivered with each queued request.
- `commands/queue.md` — registers `/queue` (same body as SKILL.md; keep them
  in sync).
- `.claude-plugin/` — plugin/marketplace manifests for `/plugin install`.
- `assets/` — GitHub Pages landing pages (EN/ZH); not part of the mechanism.

## History — why there is no code

Earlier versions implemented queueing themselves: a UserPromptSubmit/Stop hook
pair (`queue-hook.py`), per-session storage under `~/.claude/queue/`, busy
detection, preemption counters, and a test suite. Investigation (July 2026,
Claude Code v2.1.201) showed all of it was redundant: Claude Code natively
holds any *recognized slash command* typed mid-turn until the whole turn ends
(FIFO, one per turn), while plain messages are injected at the next tool-call
boundary and naturally preempt. The hooks had in fact never fired in the
sessions where the queue "worked" — native behavior was doing everything.
The mechanism was deleted; registering the command IS the feature. See git
history (`hooks/queue-hook.py` et al.) if you need the old implementation.

## Conventions

- One concern per commit; messages explain *why* (the failure mode addressed).
- Keep `SKILL.md` and `commands/queue.md` bodies identical.
- Don't reintroduce hooks/scripts unless native behavior regresses — verify
  against a real session transcript (`~/.claude/projects/<proj>/<sid>.jsonl`,
  `queue-operation` records) before believing any claim about delivery timing.
