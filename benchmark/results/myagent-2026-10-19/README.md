# myagent, 2026-10-19

- Target: [ahmetask/myagent](https://github.com/ahmetask/myagent)
- Before: `main` at `399c7e8` (no `CLAUDE.md`)
- After: branch `claude/ai-ready-benchmark` at `b32a61e`, made by
  `run_benchmark.py prepare` (the `make-ai-ready` skill, headless, Opus): new `CLAUDE.md`,
  `.ai-ready/` config, baseline and plan, stale-doc fixes in `README.md`, `wiki.md`, `DEPLOY.md`
  and `.env.deploy.example`. Skill readiness score 10/27 before, 17/27 after.
- Sessions: Sonnet, Claude Code 2.1.303, 5 tasks from `benchmark/tasks/myagent.json`,
  3 runs each per phase, tools `Read Grep Glob Edit Write`.

## Result

All 30 sessions passed their checks. Medians per task:

| task | tokens before | tokens after | change | cost before | cost after | change | turns before | turns after |
|---|---|---|---|---|---|---|---|---|
| add-agent | 64,372 | 25,686 | -60% | $0.063 | $0.028 | -56% | 13 | 5 |
| auth | 24,940 | 18,223 | -27% | $0.030 | $0.025 | -19% | 4 | 2 |
| commands | 29,048 | 8,024 | -72% | $0.044 | $0.013 | -70% | 6 | 1 |
| storage | 21,551 | 19,833 | -8% | $0.017 | $0.032 | +85% | 3 | 4 |
| todo-count (edit) | 43,142 | 63,856 | +48% | $0.053 | $0.060 | +14% | 8 | 8 |
| **all** | **183,053** | **135,622** | **-26%** | **$0.207** | **$0.158** | **-24%** | **34** | **20** |

Over all 15 runs per phase: 533,515 tokens / $0.607 before, 400,619 tokens / $0.480 after.
The full table with durations is in [table.md](table.md); raw per-session records (including
each answer) are in `before.jsonl`, `after.jsonl` and `prepare.jsonl`.

## Reading it

- Orientation questions got much cheaper: with `CLAUDE.md` naming the layout and commands,
  "which commands" was answered in one turn with no tool calls, and "add an agent" in 5 turns
  instead of 13.
- `CLAUDE.md` is a fixed cost on every turn (about 2.5k tokens re-read from cache each time).
  On the edit task the session still needed the same 8 turns to read and change the code, so
  that cost was pure overhead: +48% tokens, but only +14% cost because cache reads are cheap.
  Keeping `CLAUDE.md` short matters for exactly this reason.
- `storage` was already cheap before (the answer sits in `wrangler.jsonc`); after, it cost more
  because the extra context was written to cache in a longer session.
- Making the repo AI ready cost one session: 1.05M tokens, $1.09 on Opus, 46 turns. At the
  saving measured here (about $0.01 per question) that pays back after roughly 100 sessions of
  this kind.

## Limits

Three runs per task is a small sample; the turn counts were stable but treat single-task
percentages as rough. The sessions had no shell, so they could not run the documented commands.
The tasks were written for this benchmark, not taken from real usage.
