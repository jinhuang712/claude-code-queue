# claude-code-queue — dev notes

A single skill: `/queue <request>` defers a request until the current turn
ends. There is deliberately **no mechanism** here — no hooks, no scripts, no
storage. Read the "History" section before adding any.

## Layout

- `SKILL.md` — the whole skill: frontmatter (`disable-model-invocation: true`,
  user-invoked only) + the instruction body delivered with each queued request.
  Installed at `~/.claude/skills/queue/`, the **directory name** is what
  registers `/queue`.
- `docs/` — the entire GitHub Pages site (repo Settings → Pages → source is set
  to `/docs`, not root — keeps the repo root to just the skill + its docs).
  `en_US.html`/`cn_ZH.html` are the landing pages (symmetric names — neither
  language gets to be the unnamed default); `index.html` is a tiny meta-refresh
  stub to `en_US.html` so the bare directory URL still resolves; `install.sh`
  is the `curl … | bash` installer, fetching only `SKILL.md` from raw master
  into `~/.claude/skills/queue/` (idempotent — re-run to update); `.nojekyll`
  disables Jekyll so `install.sh` is served byte-for-byte at
  `jinhuang712.github.io/claude-code-queue/install.sh`. None of this is part
  of the mechanism.

## Ships as a standalone skill, NOT a plugin

Install is the `curl … | bash` one-liner in `install.sh` (drops `SKILL.md` into
`~/.claude/skills/queue/`). There is intentionally no `.claude-plugin/` manifest
and no marketplace. Reason (verified against the docs + a live install, July
2026): **Claude Code always namespaces a plugin's command as
`/plugin-name:command`, and nothing removes the prefix.** Evidence, strongest
first:

- The *cleanest possible* plugin — a single `SKILL.md` at the plugin root,
  `name: queue` in frontmatter, `name: "queue"` in `plugin.json`, **no**
  `skills/` or `commands/` dir (cache commit `b8525fb58468`) — loaded in a
  live v2.1.201 session as `plugin:queue:queue`. So the single-skill-at-root
  layout does **not** buy a bare command.
- The plugins reference says a root `SKILL.md`'s frontmatter `name` sets the
  "invocation name" — but that only controls the segment *after* the colon
  (without it, a marketplace install falls back to the version-hash dir name).
  It never drops the `queue:` namespace.
- Earlier probes agreed: a `commands/qtest.md` inside the plugin registered as
  `/queue:qtest`.

A bare `/queue` (the whole point) only comes from a **standalone skill** under
`~/.claude/skills/` with **no** `.claude-plugin/`. Adding a `.claude-plugin/`
back — even for the "elegant" `/plugin install` flow — turns it into a
namespaced plugin and breaks the bare command. The trade-off was put to the
user directly (bare `/queue` vs `/plugin`-install elegance); they chose the bare
command, so we ship a standalone skill with a curl installer. Don't re-add a
manifest.

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
- Don't reintroduce hooks/scripts unless native behavior regresses — verify
  against a real session transcript (`~/.claude/projects/<proj>/<sid>.jsonl`,
  `queue-operation` records) before believing any claim about delivery timing.
