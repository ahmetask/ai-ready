# ai-ready

A Claude Code plugin that makes a repository **AI ready** and keeps it that way.

- **`make-ai-ready` skill**: audits the repository the way an agent experiences it, cleans up
  stale or misleading docs (fix, merge, delete with your go-ahead), drafts `CLAUDE.md` if there
  is none, and writes a prioritized readiness plan to `.ai-ready/plan.md`.
- **ai-ready check**: a fast, dependency-free checker that fails when a change makes the repo
  less AI ready. It runs as Claude Code hooks, as a slash command, in GitHub Actions, and in
  pre-commit.

## Install

In Claude Code:

```
/plugin marketplace add ahmetask/ai-ready
/plugin install ai-ready@ai-ready
```

Then, in the repository you want to prepare, ask Claude to "make this repo AI ready" or run
`/ai-ready:make-ai-ready`.

## What the check verifies

| Check | Severity | What it catches |
|---|---|---|
| `instructions-file` | error | No `CLAUDE.md` / `AGENTS.md` (configurable), or it is empty |
| `instructions-size` | warning | Agent instructions, with their `@imports`, over `max_instructions_bytes` (default 8000, about 2k tokens). They are re-read on every turn |
| `readme` | error | No README |
| `broken-link` | error | Relative Markdown links to files that don't exist |
| `missing-path-ref` | error in agent instructions, warning elsewhere | `` `inline/code/paths.ext` `` that don't exist (renamed or deleted code) |
| `missing-command` | error in agent instructions, warning elsewhere | Documented `npm/pnpm/yarn/bun run <x>` or `make <x>` with no such script or target |
| `doc-drift` | configurable | Code covered by a `doc_watch` rule changed without its docs |
| `context-overlap` | warning | With [ctx-harness](#using-it-with-ctx-harness): `CLAUDE.md` (or a file it imports) repeats commands or a layout (4+ paths) from `.ctx/map.md`, or carries the `ctx-harness` block the hook already injects |

It prints a readiness score (100, minus 10 per error and 2 per warning) and exits non-zero when
there are **new** failing issues. Pre-existing issues you accept when adopting the tool are kept
in `.ai-ready/baseline.json`, so you can turn it on today and pay the debt down over time.

```
python3 plugins/ai-ready/scripts/ai_ready_check.py [--root DIR] [--format text|json]
    [--base REF] [--no-baseline] [--update-baseline] [--init]
```

## Configuration

`.ai-ready/config.json` (create it with `--init`). The hooks only act in repositories that have
this file.

```json
{
  "instruction_files": ["CLAUDE.md", "AGENTS.md"],
  "max_instructions_bytes": 8000,
  "ignore": ["docs/generated/**"],
  "fail_on": "error",
  "min_score": 0,
  "doc_watch": [
    { "paths": ["src/api/**"], "docs": ["docs/api.md"], "severity": "error" }
  ]
}
```

- `ignore`: globs for generated or vendored files and confirmed false positives.
- `fail_on`: `error` or `warning`.
- `min_score`: also fail when the overall score is below this.
- `doc_watch`: when files matching `paths` change and none of `docs` do, report `doc-drift`.
  Globs use `fnmatch`, so `*` also matches `/`. Changes are uncommitted and untracked files,
  plus `REF...HEAD` when `--base REF` is given.

## Keeping it AI ready

**In Claude Code** (automatic once the plugin is installed and the repo has a config):

- after Claude edits a Markdown file, the check runs on that file and reports new issues back
  to Claude right away;
- before Claude finishes a turn, the full check runs on the working tree; if it finds new
  issues, Claude is asked once to fix them. Set `AI_READY_DISABLE=1` to turn the hooks off.
- `/ai-ready:check` runs the check on demand and fixes what it finds.

**GitHub Actions**:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- uses: ahmetask/ai-ready@main
```

On pull requests the action diffs against the PR base branch for `doc_watch` rules. Inputs:
`base` (git ref) and `args` (extra flags).

**pre-commit**:

```yaml
repos:
  - repo: https://github.com/ahmetask/ai-ready
    rev: main
    hooks:
      - id: ai-ready
```

## Using it with ctx-harness

[ctx-harness](https://github.com/ahmetask/ctx-harness) injects a generated repo map
(`.ctx/map.md`: layout, modules, verified commands) at every session start and serves module
cards on demand. Everything loaded at session start is paid for again on every turn, so the two
plugins split the work instead of both describing the repository:

| | ctx-harness | ai-ready |
|---|---|---|
| Layout, modules, commands | `.ctx/map.md`, injected | not repeated in `CLAUDE.md` |
| Per-module detail | cards, read on demand | none (nested `CLAUDE.md` only without ctx-harness) |
| Guardrails and gotchas the map can't express | | a short `CLAUDE.md`, or none |
| Freshness | `.ctx/` (`ctxh check`, curate) | every other doc (this check) |

When `.ctx/map.md` exists, the check:

- leaves `.ctx/` to `ctxh check` (task archives there mention old paths on purpose) and doesn't
  flag `.ctx/...` paths that the harness creates later;
- accepts the map as agent instructions, so a missing `CLAUDE.md` is not an error;
- warns with `context-overlap` when `CLAUDE.md` repeats the map's commands or layout, or imports the ctx-harness
  block, which `ctxh init --target agents-md` writes to `AGENTS.md` for other agents.

The `make-ai-ready` skill detects the map too: it writes `CLAUDE.md` with only what the map
lacks, never edits `.ctx/`, and passes module facts to the ctx-harness curator instead of
writing them into `CLAUDE.md`. Measured effect: [benchmark/results/myagent-2026-10-19-ctx](benchmark/results/myagent-2026-10-19-ctx/README.md).

## Repository layout

- `.claude-plugin/marketplace.json`: marketplace entry, so the repo can be added with `/plugin marketplace add`
- `plugins/ai-ready/`: the plugin
  - `skills/make-ai-ready/`: the audit, cleanup and planning skill, with its scoring criteria and plan template
  - `commands/check.md`: the `/ai-ready:check` command
  - `hooks/hooks.json`: the PostToolUse and Stop hooks
  - `scripts/ai_ready_check.py`: the checker (Python 3.8+, stdlib only)
  - `tests/`: unit tests
- `action.yml`, `.pre-commit-hooks.yaml`: CI and pre-commit integrations
- `benchmark/`: before/after token benchmark for the skill; see [benchmark/README.md](benchmark/README.md)

## Development

```
python3 -m unittest discover -s plugins/ai-ready/tests -v
python3 plugins/ai-ready/scripts/ai_ready_check.py
claude plugin validate plugins/ai-ready
```
