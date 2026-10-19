# AI readiness plan: <repository>

_Generated <date> by the ai-ready skill. Checker score: <before>/100 to <after>/100._

## Summary

<Two or three sentences: how ready the repo is, the biggest gap, the first thing to do.>

## Scores

| Dimension | Before | After cleanup | Evidence |
|---|---|---|---|
| Agent instructions | | | |
| Build/test/lint/run commands | | | |
| Docs accuracy | | | |
| Doc structure | | | |
| Components understood | | | |
| Environment setup | | | |
| Feedback loops | | | |
| Conventions | | | |
| Safety rails | | | |
| Staying ready | | | |
| **Total (0-30)** | | | |

## Components

<The abstract, then one row per component. Link `.ai-ready/components.json`.>

| Component | Responsibility | Docs | Run | Test | Tests ran? | Time | Needs |
|---|---|---|---|---|---|---|---|
| | | | | | yes / failed / no command | | network, database, ... |

## Making tests easy to run

<For each component whose tests failed, were missing, were slow, or needed services or
secrets: the concrete change (a fake or in-memory adapter, SQLite, recorded fixtures, one
`make test`, splitting unit from integration tests). Each one also goes in the backlog.>

## Cleanup done

- Fixed: `<file>`: <what and why>
- Merged: `<file>` into `<file>`
- Deleted: `<file>`: <why it was obsolete>
- `CLAUDE.md`: <lines/bytes before> to <after>; moved <what> to <where>

## Backlog

Quick wins first. Effort: S (under an hour), M (a day), L (more).

| # | Change | Why it helps agents | Files | Effort |
|---|---|---|---|---|
| 1 | | | | S |

## Keeping it ready

- Enforcement: <CI job / pre-commit / Claude Code hooks, and whether they are on>
- `doc_watch` rules: <which docs are tied to which code>
- Baseline: <N> accepted issues in `.ai-ready/baseline.json`; the backlog above removes them.

## Open questions

- <Things only a maintainer can answer, e.g. "Is docs/deploy.md still the real deploy process?">
