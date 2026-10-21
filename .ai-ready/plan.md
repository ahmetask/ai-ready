# AI readiness plan: ai-ready

_Generated 2026-10-19 by running the make-ai-ready skill on its own repository. Checker
score: 98/100 to 100/100._

## Summary

The repository was already in good shape: small, stdlib-only, and covered by its own check in
CI. The gaps were docs that had drifted as the plugin grew. `CLAUDE.md` and the README layout
still described the skill as "audit / cleanup / plan" and didn't mention `/ai-ready:explain`.
The README and the skill quoted benchmark numbers from a run that isn't in this repository.
The benchmark had no test, and contributors' Claude Code sessions didn't load the hooks. All
of that is fixed. What remains is a lint/type-check step and tests for the benchmark's own logic.

## Scores

| Dimension | Before | After | Evidence |
|---|---|---|---|
| Agent instructions | 2 | 3 | Root `CLAUDE.md` is 32 lines and covers commands, guardrails, gotchas and one line per component. Nested `CLAUDE.md` files for the plugin and the benchmark hold the detail. Before, it was a per-file layout with stale skill and command names |
| Build/test/lint/run commands | 2 | 3 | The self-check now runs with `--base origin/main`, matching CI. Every component has a test command, and all three pass (`--verify-tests`) |
| Docs accuracy | 2 | 3 | The README layout no longer lists a stale skill description and misses no command. Benchmark numbers now link to results in `benchmark/results/` |
| Doc structure | 2 | 3 | The layout was in both README and `CLAUDE.md`; now `docs/architecture.md` is the one place, linked from both |
| Components understood | 1 | 3 | The map now has three components, including integrations, and each has docs plus a passing test. The largest file is `ai_ready_check.py` at 888 lines |
| Environment setup | 3 | 3 | Stdlib-only Python 3.8+. Only the benchmark needs the `claude` CLI and an API key, and that's documented |
| Feedback loops | 2 | 2 | 25 unit tests run in about 4s and CI runs them. There is no linter or type checker, and the benchmark's logic has no unit tests |
| Conventions | 2 | 3 | Checker conventions (stable keys, silent hooks, README table plus test per check) now sit in `plugins/CLAUDE.md`, next to the code |
| Safety rails | 2 | 3 | `CLAUDE.md` now says that `run_benchmark.py run`/`prepare` start paid sessions and that `benchmark/results/` must not be edited |
| Staying ready | 2 | 3 | The check runs in CI, `.ai-ready/baseline.json` records instruction sizes, and `doc_watch` covers the component map, commands and hooks. `.claude/settings.json` enables the plugin's hooks for contributors |
| **Total (0-30)** | **20** | **29** | |

## Components

ai-ready is a Claude Code plugin that makes repositories AI ready, plus a checker that keeps
them that way. The map is in [`components.md`](components.md).

| Component | Responsibility | Docs | Run | Test | Tests ran? | Time | Needs |
|---|---|---|---|---|---|---|---|
| plugin | Checker, skill, commands, hooks | `plugins/CLAUDE.md`, `README.md` | checker CLI | unittest | yes | 4.2s | nothing |
| integrations | GitHub Action, pre-commit hook, CI | `README.md` | n/a | self-check | yes | 0.1s | nothing |
| benchmark | Token benchmark of the skill | `benchmark/CLAUDE.md`, `benchmark/README.md` | `run_benchmark.py` | `compare` on recorded results | yes | 0.1s | nothing (real runs need the `claude` CLI and an API key) |

## Making tests easy to run

All three components' tests already run offline with one command. The benchmark's test is only
a smoke test of `compare`. Its task grading (`expect`, `expect_changed`) and token aggregation
have no unit tests (backlog item 2).

## Cleanup done

- Fixed: `README.md`: the benchmark numbers came from a run whose results never landed in this
  repo; they now cite and link the two recorded runs. The stale layout list is now a pointer to
  `docs/architecture.md`, and the development self-check matches CI.
- Fixed: `plugins/ai-ready/skills/make-ai-ready/SKILL.md`: the same benchmark numbers, corrected
  the same way.
- Merged: the layout from `README.md` and `CLAUDE.md` into the new `docs/architecture.md`.
- Moved: the checker conventions from the root `CLAUDE.md` to `plugins/CLAUDE.md`, and
  the benchmark rules to the new `benchmark/CLAUDE.md`.
- `CLAUDE.md`: 31 lines / 1.7 KB, mostly a per-file layout, became 32 lines / 1.4 KB of
  commands, guardrails, gotchas and one line per component.
- Deleted: nothing. No doc was obsolete.

## Backlog

Quick wins first. Effort: S (under an hour), M (a day), L (more).

| # | Change | Why it helps agents | Files | Effort |
|---|---|---|---|---|
| 1 | Add a CI-only `ruff check` (and optionally `mypy`) step; the code stays stdlib-only, since only CI installs the tools | Catches mistakes before review; agents fix what they can measure | `.github/workflows/ci.yml` | S |
| 2 | Unit tests for `run_benchmark.py` grading and aggregation, using the recorded JSONL | A change to the benchmark currently has no fast check | `benchmark/` | M |
| 3 | Give the benchmark component a real `test` command once item 2 lands | `--verify-tests` would then prove more than "compare runs" | `.ai-ready/components.md` | S |
| 4 | Split `ai_ready_check.py` by section if it grows past ~1,500 lines; it stays one file for users, so build it from parts or keep it under the limit | Large files cost agents context | `plugins/ai-ready/scripts/` | M |

## Keeping it ready

- Enforcement: the CI job (`.github/workflows/ci.yml`) runs the tests and the check through the
  action. `.claude/settings.json` enables the plugin, so Claude Code sessions in this repo run
  the post-edit and Stop hooks.
- `doc_watch` rules:
  - checker changes are tied to `README.md`;
  - component map changes are tied to `docs/architecture.md`;
  - command and hook changes are tied to `README.md`.

  All three report warnings, not errors.
- Baseline: 0 accepted issues. Instruction sizes are recorded for `CLAUDE.md`,
  `plugins/CLAUDE.md` and `benchmark/CLAUDE.md`.

## Open questions

- Should `.claude/settings.json` load the plugin from GitHub (it does now, so contributors get
  the released hooks), or from the working copy while developing the plugin itself?
