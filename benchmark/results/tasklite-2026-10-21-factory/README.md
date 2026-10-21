# Factory vs direct on tasklite (2026-10-21)

This run compares `/ai-ready:build --go` (the factory: planner, coder, tester and documenter
agents) with plain sessions on the same four prompts. The target was the in-tree example
project, `benchmark/example/tasklite`, after the `make-ai-ready` skill had run on it. Both
sides used sonnet, three runs per task, with the plugin loaded and the same tools (Read, Grep,
Glob, Edit, Write, Bash with `python3`/`git diff`/`git status`/`ls`). The factory side also had
Agent.

A run passes when its answer and changed files match the task, its hidden acceptance test
passes (`tasks/tasklite-checks/`), and the project's own tests pass afterwards.

## Result

Both sides passed every run (12/12 each). Overall the factory cost **3.2× more** ($2.31 vs
$0.69 over all runs) and took 2.7× longer. Its main session used 62% fewer turns because the
agents did the work.

| task | cost direct | cost factory | seconds direct | seconds factory | subagents | passed |
|---|---|---|---|---|---|---|
| run-tests (question) | $0.007 | $0.016 | 3 | 5 | 0 | 3/3, 3/3 |
| stats-open (one-line change) | $0.025 | $0.158 | 14 | 65 | 4, 0, 4 | 3/3, 3/3 |
| done-missing (bug in CLI and API) | $0.045 | $0.243 | 21 | 91 | 6 each | 3/3, 3/3 |
| due-dates (feature across store, CLI, API) | $0.179 | $0.396 | 57 | 99 | 8-10 | 3/3, 3/3 |

Medians per task. The full table from `compare` is in [compare.md](compare.md).

## What each side produced

From the saved patches in [diffs/](diffs/):

| | direct | factory |
|---|---|---|
| Added tests for `stats-open` | 1 of 3 runs | 3 of 3 |
| Added tests for `done-missing` | 1 of 3 | 3 of 3 |
| Updated README and `tasklite/CLAUDE.md` for `due-dates` | 0 of 3 | 3 of 3 |
| Left a tracker in `.ai-ready/work/` | n/a | 8 of 9 changes (one `stats-open` run was judged small and done directly) |

An example tracker is in [diffs/build-due-dates-0.patch](diffs/build-due-dates-0.patch).
The planner split the feature into store, CLI, API and docs tasks, with the CLI and API tasks
both waiting on the store task. The store task needed a second attempt before its verify
passed. The documenter added one gotcha line to `tasklite/CLAUDE.md` and a section to the
README.

What `make-ai-ready` generated for the example (cost $0.18, 81 s) is in
[generated/make-ai-ready.patch](generated/make-ai-ready.patch): a component map, an
18-line `CLAUDE.md`, a 13-line `tasklite/CLAUDE.md`, a plan, the config and baseline, and a
README fix.

## Reading it

- On a small single-component repository, plain sessions already pass every task, so the
  factory buys no extra correctness here. What it buys is consistency: every change gets tests,
  and features get docs. That is worth something, but at 3-6× the cost on small tasks it
  should not be the default. That is why `/ai-ready:plan` and `/ai-ready:build` ask first. With
  `--go`, as here, the factory still sometimes handled a small task directly.
- Most of the extra cost is cold starts. Each subagent writes its own prompt cache, and cache
  writes were 338k tokens on the factory side vs 74k on the direct side. Two ways to cut it:
  skip the separate tester when the coder already ran `verify` successfully, and run the tester
  and documenter on a smaller model.
- This repository is too small to show the factory's main promise, finishing multi-step work
  that a single session gets wrong. A larger multi-component target (for example `myagent`
  with `tasks/myagent-vague.json`) is the next measurement.

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
