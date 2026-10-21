# AI readiness plan: tasklite

_Generated 2026-10-21 by the ai-ready skill. Checker score: 100/100 to 100/100 (the checker had nothing to flag before, because there were no docs to contradict)._

## Summary

A 224-line stdlib Python project with a good README and passing offline tests, but no agent instructions and no component map. The biggest gap is the lack of CI and linting; the first thing to do is handle unknown ids, which both front ends mishandle.

## Scores

| Dimension | Before | After cleanup | Evidence |
|---|---|---|---|
| Agent instructions | 0 | 3 | No `CLAUDE.md` before; now 24 lines |
| Build/test/lint/run commands | 2 | 2 | Test command in README works (0.6s); no lint, no CI to compare with |
| Docs accuracy | 2 | 3 | README lacked the `stats` command; added |
| Doc structure | 3 | 3 | One README, no duplicates or stray notes |
| Components understood | 0 | 3 | `.ai-ready/components.md` added |
| Environment setup | 2 | 2 | stdlib only, no pinned Python version (README says 3.8+) |
| Feedback loops | 2 | 2 | Tests are offline and fast; no linter or type check |
| Conventions | 1 | 2 | Where new commands and routes go is now in `CLAUDE.md` |
| Safety rails | 2 | 3 | `tasks.json` gitignored; now flagged as user data |
| Staying ready | 0 | 2 | Check enabled with a baseline; no CI (by request) |
| **Total (0-30)** | 14 | 25 | |

## Components

A tiny task tracker with a command line and a JSON HTTP API. Both front ends share one `Store` class over `tasks.json`. Map: [`.ai-ready/components.md`](components.md).

| Component | Responsibility | Docs | Run | Test | Tests ran? | Time | Needs |
|---|---|---|---|---|---|---|---|
| tasklite | CLI, HTTP API, JSON storage | `README.md` | `python3 -m tasklite list` | `python3 -m unittest discover -s tests -t .` | yes | 0.6s | none |

## Making tests easy to run

Nothing to change: tests run offline with one command. Coverage gaps are in the backlog.

## Cleanup done

- Fixed: `README.md`: added the undocumented `stats` command to the usage block.
- Added: `CLAUDE.md` (0 to 24 lines), `.ai-ready/components.md`, `.ai-ready/config.json`.
- Merged: none. Deleted: none. Proposed deletions: none.

## Backlog

| # | Change | Why it helps agents | Files | Effort |
|---|---|---|---|---|
| 1 | Handle unknown ids in `Store.complete` (clear error, 404 from the API, message from the CLI) and add tests | Agents hit an unhandled `KeyError` | `tasklite/store.py`, `cli.py`, `api.py`, `tests/` | S |
| 2 | Add a test for `stats` and for the invalid-JSON/missing-title API path | Gives agents feedback on those paths | `tests/` | S |
| 3 | Add a linter config (e.g. ruff) and one `make check` | One command for the whole feedback loop | new `Makefile`, `pyproject.toml` | S |
| 4 | Add CI running the tests and `ai_ready_check.py` | Keeps the repo ready; deliberately not set up in this run | `.github/workflows/` | S |
| 5 | Make `DEFAULT_PATH` resolve `TASKLITE_FILE` lazily | Removes an import-time gotcha | `tasklite/store.py` | S |

## Keeping it ready

- Enforcement: the Claude Code plugin hooks, if the plugin is installed. No CI or pre-commit.
- `doc_watch` rules: none; the only doc is a short README.
- Baseline: 0 accepted issues in `.ai-ready/baseline.json`.

## Open questions

- Is the API meant to stay unauthenticated and localhost-only?
- Should unknown ids be an error or a no-op?
