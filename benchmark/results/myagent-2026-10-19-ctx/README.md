# myagent with ctx-harness, 2026-10-19

Follow-up to [myagent-2026-10-19](../myagent-2026-10-19/README.md). Question: can ai-ready and
[ctx-harness](https://github.com/ahmetask/ctx-harness) run together without paying twice for the
same context, and does the leaner `CLAUDE.md` fix the edit-task regression?

## Arms

Same target (`ahmetask/myagent` at `399c7e8`), same 5 tasks, 3 runs each, Sonnet, Claude Code
2.1.303, tools `Read Grep Glob Edit Write` (no shell).

| arm | what the session sees | always-loaded extra context |
|---|---|---|
| `before` | `main` (from the earlier run) | none |
| `old` | `CLAUDE.md` from the previous skill (from the earlier run) | 3.5 KB `CLAUDE.md` |
| `lean` | `main` + this PR's skill, headless on Opus | 2.2 KB `CLAUDE.md` ([copy](lean-CLAUDE.md.txt)) |
| `ctx` | `main` + `.ctx/` from `/ctx-harness:build` (Sonnet), plugin loaded | protocol + 3 KB map ([copy](ctx-map.md.txt)), prompt hints |
| `ctx-old` | `ctx` + the `old` commit cherry-picked | both, with the layout twice |
| `ctx-lean` | `ctx` + this PR's skill, which saw `.ctx/map.md` | protocol + map + 1.4 KB `CLAUDE.md` ([copy](ctx-lean-CLAUDE.md.txt)) |

ctx-harness was 0.7.0 (`2c57b98`) with one local patch: `ctxh build-index` crashed with a
`KeyError` on myagent because a TypeScript file imports a `.json` and another a `.css` file
(the module loop in `cmd_build_index` indexes `nodes[t]` without the `if t in nodes` guard the
edge filter has). That fix belongs in ctx-harness; nothing here changes it.

## Result

Sum of per-task medians (full table in [table.md](table.md)):

| arm | tokens | cost | turns | passed | edit task (todo-count) |
|---|---|---|---|---|---|
| before | 183,053 | $0.207 | 34 | 15/15 | 43,142 |
| old | 135,622 (-26%) | $0.158 (-24%) | 20 | 15/15 | 63,856 (+48%) |
| **lean** | **116,067 (-37%)** | **$0.149 (-28%)** | 18 | 15/15 | **45,542 (+6%)** |
| ctx | 145,343 (-21%) | $0.204 (-1%) | 22 | 14/15 | 47,508 (+10%) |
| ctx-old | 177,427 (-3%) | $0.204 (-2%) | 18 | 15/15 | 68,702 (+59%) |
| ctx-lean | 152,011 (-17%) | $0.191 (-8%) | 19 | 15/15 | 50,324 (+17%) |

Over all 15 runs per arm: before 534k tokens / $0.607, old 401k / $0.480, lean 362k / $0.439,
ctx 447k / $0.602, ctx-old 529k / $0.620, ctx-lean 444k / $0.570.

## Reading it

- **A lean `CLAUDE.md` is the biggest single win.** Same questions answered in the same number
  of turns as `old`, with 1.3 KB less on every turn: -37% tokens overall, and the edit task
  went from +48% to +6% against no `CLAUDE.md` at all.
- **Running both plugins naively wipes out the saving.** `ctx-old` loads the map and a
  `CLAUDE.md` that repeats its layout: -3% tokens, and the worst edit task (+59%). The
  checker now flags that `CLAUDE.md` (`context-overlap`, "names 4 paths that .ctx/map.md
  already lists").
- **Split ownership recovers most of it.** With the skill writing only what the map lacks
  (guardrails, gotchas, commands), `ctx-lean` is -17% tokens and -8% cost, every run passed,
  and the edit task is +17% instead of +59%.
- **On a repo this size ctx-harness doesn't pay for itself in these sessions.** `ctx` alone is
  -21% tokens but -1% cost, and `ctx-lean` costs more than `lean`. The map, protocol and prompt
  hints add about 2k tokens per turn (`commands`: 7.4k in one turn for `lean`, 9.2k for
  `ctx-lean`), and myagent has 150 code files. These sessions had no shell, so the protocol's
  `ctxh q` lookups were unavailable; that handicaps ctx-harness and is the first thing to
  change before judging it on a larger repo.
- One `ctx` run of `add-agent` failed its check (it omitted `wrangler.jsonc`).

## Cost of the run

Making the repo ready: `lean` 1.06M tokens / $1.10 (39 turns, Opus), `ctx-lean` 0.97M / $0.91
(50 turns, Opus), `/ctx-harness:build` $0.30 (Sonnet, plus $0.09 for the attempt that hit the
crash above). Task sessions: 60, $2.23.

## Limits

Three runs per task; single-task gaps under ~20% are noise (compare `storage` across arms).
One small repo. The `myagent` branches (`bench/lean`, `bench/ctx`, `bench/ctx-old`,
`bench/ctx-lean`) were made locally and not pushed; the generated `CLAUDE.md` files and map are
copied here.
