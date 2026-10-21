# Factory vs direct on tasklite (2026-10-21)

This run compares `/ai-ready:build --go` (the factory: planner, coder, tester and documenter
agents) with plain sessions on the same four prompts. The target was the in-tree example
project, `benchmark/example/tasklite`, after the `make-ai-ready` skill had run on it. Both
sides used sonnet, three runs per task, with the plugin loaded and the same tools (Read, Grep,
Glob, Edit, Write, Bash with `python3`/`git diff`/`git status`/`ls`). The factory side also had
Agent. The plugin was the version that writes its output as Markdown.

A run passes when its answer and changed files match the task, its hidden acceptance test
passes (`tasks/tasklite-checks/`), and the project's own tests pass afterwards.

## What the plugin generated

These are readable copies in [generated/](generated/):

| File | Written by | What it is |
|---|---|---|
| [make-ai-ready/components.md](generated/make-ai-ready/components.md) | skill | Component map: abstract, then path, responsibility, docs, run and test per component (12 lines) |
| [make-ai-ready/CLAUDE-root.md](generated/make-ai-ready/CLAUDE-root.md) | skill | The project's new `CLAUDE.md` (25 lines) |
| [make-ai-ready/plan.md](generated/make-ai-ready/plan.md) | skill | Readiness scores and a prioritized backlog |
| [make-ai-ready/all-changes.patch](generated/make-ai-ready/all-changes.patch) | skill | Everything above, plus `config.json`, `baseline.json` and a README fix |
| [factory-due-dates/tracker.md](generated/factory-due-dates/tracker.md) | planner, then `--work-set` | The factory's task tracker after a finished run: goal, four tasks, status, attempts, notes |
| [factory-due-dates/docs-changes.patch](generated/factory-due-dates/docs-changes.patch) | documenter | Its README section and `CLAUDE.md` gotcha for the feature |

The skill run cost $0.15 and took 53 s. All 9 factory runs that changed code left a
Markdown tracker, and all 9 parse with no problems (`--work`).

## Result

Both sides passed every run (12/12 each). Overall the factory cost **3.1× more** ($2.43 vs
$0.79 over all runs) and took 3.1× longer. Its main session used 82% fewer turns because the
agents did the work.

| task | cost direct | cost factory | seconds direct | seconds factory | subagents | passed |
|---|---|---|---|---|---|---|
| run-tests (question) | $0.008 | $0.017 | 4 | 4 | 0 | 3/3, 3/3 |
| stats-open (one-line change) | $0.033 | $0.170 | 20 | 92 | 4 | 3/3, 3/3 |
| done-missing (bug in CLI and API) | $0.043 | $0.238 | 25 | 109 | 6 | 3/3, 3/3 |
| due-dates (feature across store, CLI, API) | $0.176 | $0.368 | 66 | 146 | 8 | 3/3, 3/3 |

These are medians per task. The full table from `compare` is in [compare.md](compare.md), and
every session's changes are in [diffs/](diffs/).

## What each side changed beyond the code

| | direct | factory |
|---|---|---|
| Added tests, `stats-open` | 3 of 3 runs | 3 of 3 |
| Added tests, `done-missing` | 2 of 3 | 3 of 3 |
| Updated docs, `stats-open` | 0 of 3 | 3 of 3 (README) |
| Updated docs, `done-missing` | 2 of 3 (`CLAUDE.md`) | 3 of 3 (`CLAUDE.md`, README in 2) |
| Updated docs, `due-dates` | 1 of 3 (README) | 3 of 3 (README and `CLAUDE.md`) |

## Reading it

- On a small single-component repository, plain sessions already pass every task, so the
  factory buys no extra correctness here. What it buys is consistency: tests every time, and
  docs kept in step with the code. At 2-6× the cost of a small task, it shouldn't be the
  default, which is why `/ai-ready:plan` and `/ai-ready:build` ask first.
- Most of the extra cost is cold starts. Each subagent writes its own prompt cache. The cheap
  fixes are to skip the separate tester when the coder's `verify` already passed, and to run
  the tester and documenter on a smaller model.
- This repository is too small to show the factory's main promise: finishing multi-step work
  that a single session gets wrong. A larger multi-component target is the next measurement.

## Reproduce

```
python3 benchmark/run_benchmark.py example /tmp/tasklite
python3 benchmark/run_benchmark.py prepare --repo /tmp/tasklite --base main --branch ai-ready \
    --plugin-dir plugins/ai-ready
common=(--repo /tmp/tasklite --ref ai-ready --tasks benchmark/tasks/tasklite.json --repeat 3
        --plugin-dir plugins/ai-ready --save-diffs diffs
        --allowed-tools "Bash(python3 *)" "Bash(git diff *)" "Bash(git status *)" "Bash(ls *)")
python3 benchmark/run_benchmark.py run "${common[@]}" --label direct \
    --tools Read Grep Glob Edit Write Bash --out direct.jsonl
python3 benchmark/run_benchmark.py run "${common[@]}" --label build \
    --tools Read Grep Glob Edit Write Bash Agent --prompt-prefix "/ai-ready:build --go " \
    --out build.jsonl
python3 benchmark/run_benchmark.py compare direct.jsonl build.jsonl
```
