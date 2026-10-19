# ai-ready

A Claude Code plugin that makes a repository **AI ready** and keeps it that way.

- **`make-ai-ready` skill**: first works out what the repository is. It maps the abstract and
  each component's responsibility, docs, run command and test command, and records what the
  tests need, in `.ai-ready/components.json`. Then it makes the repo clean, well structured
  and compact. It prunes stale docs (deleting only with your go-ahead), keeps one place per
  topic, gives each component a short `CLAUDE.md`, writes or trims a lean root `CLAUDE.md`,
  and writes a prioritized plan to `.ai-ready/plan.md`.
- **`/ai-ready:explain`**: a read-only overview of the repo: the abstract, plus each component
  with its responsibility, docs and run/test commands.
- **ai-ready check**: a fast, dependency-free checker that fails when a change makes the repo
  less AI ready. It runs as Claude Code hooks, as a slash command, in GitHub Actions, and in
  pre-commit.

Why lean: `CLAUDE.md` is re-read on every turn. On a real repository, the first version of
the skill wrote a long `CLAUDE.md`. That cut tokens by 26% overall but made a plain edit task
48% more expensive ([results](benchmark/results/myagent-2026-10-19/README.md)). With the
current skill, which writes a 41-line `CLAUDE.md` plus per-component docs loaded on demand,
tokens fell by 29% and the edit task's overhead dropped to 7%
([results](benchmark/results/myagent-2026-10-19-lean/README.md)). The check keeps
`CLAUDE.md` within a budget and stops it from growing.

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

With a component map (`.ai-ready/components.json`):

| Check | Severity | What it catches |
|---|---|---|
| `component-path` | error | A mapped component's path no longer exists |
| `component-docs` | error if a listed doc is missing, warning if none listed | Components without docs |
| `component-command` | error if it uses an undefined script or make target, warning if missing | Run and test commands per component (`"library": true` needs no run command) |
| `component-map` | warning | No abstract, or a component without a responsibility |
| `component-test-deps` | warning | Tests that need `network`, `database`, `docker`, `secrets`, `cloud` or a `service` |
| `unmapped-component` | warning | A directory with its own build file that the map doesn't cover |
| `component-drift` | warning | A component's build or setup files changed but its docs did not |

It prints a readiness score (100, minus 10 per error and 2 per warning) and exits non-zero when
there are **new** failing issues. Pre-existing issues you accept when adopting the tool are kept
in `.ai-ready/baseline.json`, so you can turn it on today and pay the debt down over time.

```
python3 plugins/ai-ready/scripts/ai_ready_check.py [--root DIR] [--format text|json]
    [--base REF] [--no-baseline] [--update-baseline] [--init]
python3 plugins/ai-ready/scripts/ai_ready_check.py --discover        # candidate components (JSON)
python3 plugins/ai-ready/scripts/ai_ready_check.py --explain         # abstract + component table
python3 plugins/ai-ready/scripts/ai_ready_check.py --verify-tests [COMPONENT] [--timeout 600]
```

## Component map

`.ai-ready/components.json` describes the repository for agents and humans. The skill
writes it, and you can also edit it by hand:

```json
{
  "abstract": "Two or three lines: what the project is and how the parts fit together.",
  "components": [
    {
      "name": "api",
      "path": "services/api",
      "responsibility": "HTTP API; owns the orders database.",
      "docs": ["services/api/CLAUDE.md"],
      "run": "cd services/api && go run ./cmd/api",
      "test": "cd services/api && go test ./...",
      "test_needs": []
    }
  ]
}
```

`--discover` proposes candidates from build files (`package.json`, `pyproject.toml`, `go.mod`,
`Cargo.toml`, Maven/Gradle, `Gemfile`, `Dockerfile`...) and guesses their commands.
`--verify-tests` runs each component's test command once and reports pass/fail and duration,
which is useful in CI or when checking that tests really run without extra setup.

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

The components, what each is responsible for, and how to run and test them are in
[docs/architecture.md](docs/architecture.md). This repository runs ai-ready on itself: see
`.ai-ready/` for its component map, config and plan.

## Development

```
python3 -m unittest discover -s plugins/ai-ready/tests -v
python3 plugins/ai-ready/scripts/ai_ready_check.py --base origin/main
claude plugin validate plugins/ai-ready
```

Working on this repository in Claude Code with the plugin installed turns on the hooks, because
the repository has `.ai-ready/config.json`.
