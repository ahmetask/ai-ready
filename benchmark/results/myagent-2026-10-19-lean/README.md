# myagent, 2026-10-19, lean CLAUDE.md skill

Second run, with the skill as of ai-ready `daaab0c` (lean `CLAUDE.md` budget, component map,
nested per-component `CLAUDE.md`). Every session ran in its own detached `git worktree`.

- Target: [ahmetask/myagent](https://github.com/ahmetask/myagent)
- **without**: `main` at `399c7e8` (no `CLAUDE.md`), no plugin.
- **with**: branch `claude/ai-ready-benchmark-v2` (`acd3ed0`, same tree as the `94aa656` that
  was measured), made by `run_benchmark.py prepare` in its own worktree (Opus, headless), with
  the ai-ready plugin loaded in each session. The skill wrote a 41-line `CLAUDE.md`, nested
  `CLAUDE.md` files for `apps/hub`, `workers/orchestrator` and `agents`, an architecture doc,
  `.ai-ready/components.json`, config, baseline and plan, and folded `wiki.md` into those.
- **docs-only**: the same branch without the plugin, to separate the docs from the plugin.
- Sessions: Sonnet, Claude Code 2.1.303, 5 tasks from `benchmark/tasks/myagent.json`,
  3 runs each, tools `Read Grep Glob Edit Write`.

## Result

All 45 sessions passed their checks. Medians per task, without vs. with:

| task | tokens without | tokens with | change | cost without | cost with | change | turns |
|---|---|---|---|---|---|---|---|
| add-agent | 50,968 | 17,466 | -66% | $0.049 | $0.024 | -52% | 8 → 3 |
| auth | 24,550 | 29,626 | +21% | $0.023 | $0.036 | +55% | 3 → 4 |
| commands | 30,131 | 7,851 | -74% | $0.041 | $0.010 | -76% | 6 → 1 |
| storage | 22,917 | 19,305 | -16% | $0.018 | $0.029 | +61% | 3 → 3 |
| todo-count (edit) | 45,638 | 48,930 | +7% | $0.055 | $0.058 | +5% | 8 → 7 |
| **all** | **174,204** | **123,178** | **-29%** | **$0.187** | **$0.156** | **-16%** | **28 → 18** |

Over all 15 runs per condition:

| condition | tokens | cost | turns |
|---|---|---|---|
| without | 564,522 | $0.604 | 90 |
| with (plugin loaded) | 374,147 (-34%) | $0.477 (-21%) | 53 |
| docs-only | 413,654 (-27%) | $0.481 (-20%) | 61 |

Full tables: [table-with-plugin.md](table-with-plugin.md), [table-docs-only.md](table-docs-only.md).
Raw per-session records with every answer: `without.jsonl`, `with.jsonl`, `docs-only.jsonl`,
`prepare.jsonl`.

## Reading it

- The lean `CLAUDE.md` fixed the edit-task regression of the first run (+48% tokens there,
  +7% now), and orientation questions stay much cheaper (`commands` in one turn, `add-agent`
  in three).
- Tokens fell more than cost. The new context (`CLAUDE.md`, plus the nested `CLAUDE.md` a
  session pulls in when it reads files under that directory) is written to the prompt cache
  once per session, and cache writes cost far more than the cache reads they replace. That is
  why `auth` and `storage` cost more despite equal or fewer tokens: on `storage`, cache reads
  fell from ~20.1k to ~13.4k but cache writes rose from ~2k to ~5.1k.
- The plugin itself adds almost nothing to a session; docs-only and with-plugin are within
  run-to-run noise of each other. The saving comes from the docs the skill writes.
- Making the repo AI ready cost one Opus session: 1.66M tokens, $1.35, 52 turns.

## Limits

Three runs per task. The sessions had no shell, so they could not run the documented commands,
and the tasks were written for this benchmark rather than taken from real usage.
