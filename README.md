# ai-ready

A Claude Code plugin that makes a repository **AI ready** and keeps it that way.

- **`make-ai-ready` skill**: makes the repository clean, well structured and compact. It prunes
  stale docs (deleting only with your go-ahead), merges duplicates into one place per topic,
  writes or trims a lean `CLAUDE.md`, and writes a prioritized plan to `.ai-ready/plan.md`.
- **ai-ready check**: a fast, dependency-free checker that fails when a change makes the repo
  less AI ready. It runs as Claude Code hooks, as a slash command, in GitHub Actions, and in
  pre-commit.

Why lean: `CLAUDE.md` is re-read on every turn. In a benchmark on a real repository, a
~40-line `CLAUDE.md` (commands, guardrails and gotchas, with details in linked docs) cut tokens
by 37% and cost by 28%. A longer `CLAUDE.md` cut tokens by only 26%, and it made a plain edit
task 48% more expensive. The check keeps `CLAUDE.md` within a budget and stops it from growing.

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
| `instructions-size` | error | `CLAUDE.md` / `AGENTS.md`, with their `@imports`, over budget (default 60 lines / 4000 bytes). They are re-read on every turn |
| `instructions-growth` | error | An over-budget instructions file grew past the size recorded in the baseline. It may shrink, never grow |
| `readme` | error | No README |
| `broken-link` | error | Relative Markdown links to files that don't exist |
| `missing-path-ref` | error in agent instructions, warning elsewhere | `` `inline/code/paths.ext` `` that don't exist (renamed or deleted code) |
| `missing-command` | error in agent instructions, warning elsewhere | Documented `npm/pnpm/yarn/bun run <x>` or `make <x>` with no such script or target |
| `doc-drift` | configurable | Code covered by a `doc_watch` rule changed without its docs |

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
  "max_instructions_lines": 60,
  "max_instructions_bytes": 4000,
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

- after Claude edits a Markdown file, the check runs on that file (and, for `CLAUDE.md`,
  against its budget) and reports new issues back to Claude right away;
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
