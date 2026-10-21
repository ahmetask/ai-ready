# ai-ready

A Claude Code plugin that makes a repository **AI ready** and keeps it that way.

- **`make-ai-ready` skill**: first works out what the repository is. It maps the abstract and
  each component's responsibility, docs, run command and test command, and records what the
  tests need, in `.ai-ready/components.md`. Then it makes the repo clean, well structured
  and compact. It prunes stale docs (deleting only with your go-ahead), keeps one place per
  topic, gives each component a short `CLAUDE.md`, writes or trims a lean root `CLAUDE.md`,
  and writes a prioritized plan to `.ai-ready/plan.md`.
- **`/ai-ready:explain`**: a read-only overview of the repo: the abstract, plus each component
  with its responsibility, docs and run/test commands.
- **The factory** (`/ai-ready:plan`, `/ai-ready:build`, `/ai-ready:status`): turns a prompt
  into a tracked plan of tasks and has coder, tester and documenter agents work through it,
  retrying failed tests, until it is done. It asks before it starts, since small changes are
  faster without it. See [The factory](#the-factory).
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

## The factory

For work bigger than a quick edit, the factory plans the work, tracks it, and runs it through
agents, each in its own context, so the main session stays small.

| Piece | What it does |
|---|---|
| `/ai-ready:plan [--go] <prompt>` | Triages the request and asks once whether to use the factory, recommending direct for small changes. Then the `planner` agent writes the plan |
| `.ai-ready/work/<slug>.md` | The tracker, in Markdown you can read: a goal and 2-8 tasks, each with agent, component, files, a narrow `verify` command, dependencies (`after`), status, attempts and a one-line note |
| `/ai-ready:build [<slug> \| [--go] <prompt>]` | The loop. For each ready task, `coder` makes the change, `tester` runs `verify` and reports `PASS` or `FAIL` with a short cause, and a failure goes back to the coder. After 3 attempts (`max_attempts`) the task is blocked and left for you. Ends with the `documenter` and the full check |
| `/ai-ready:status [<slug>]` | Shows the tracker: tasks, attempts, notes, what runs next |
| `planner`, `coder`, `tester`, `documenter` | The agents. Each one reads only its component's docs and replies in 8 to 12 lines. The tester waits on slow tests and CI in the background. The documenter updates the component map and docs, keeping only what a future session needs |

Context stays low by design. The orchestrating session reads summaries, not code or logs, and
gets state from `--work` rather than by reading the tracker. After a compaction or resume, a hook adds one line
about unfinished work. Nothing is added to ordinary turns: the commands cost nothing until you
run them, and the prompt hook that offers the factory for long prompts is opt-in. Commit
`.ai-ready/work/` to share and resume work across machines, or ignore it.

What it costs: on the small `tasklite` example, the factory passed the same 12 of 12 runs as
plain sessions but cost 3.2× more. Every change it made came with tests, and features came
with docs, which plain sessions did only sometimes
([results](benchmark/results/tasklite-2026-10-21-factory/README.md)). Use it for multi-step
work, not one-liners.

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

With a component map (`.ai-ready/components.md`):

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
python3 plugins/ai-ready/scripts/ai_ready_check.py --work [SLUG]  # factory tracker
python3 plugins/ai-ready/scripts/ai_ready_check.py --work-set SLUG TASK todo|doing|done|blocked [--note TEXT]
python3 plugins/ai-ready/scripts/ai_ready_check.py --convert-map    # components.json -> .md
```

## Component map

`.ai-ready/components.md` describes the repository for agents and humans. It's Markdown, so it
reads like a doc. The skill writes it, and you can also edit it by hand, keeping one
`- **Field:** value` line per field so the checker can parse it:

```markdown
# shop

Two or three lines: what the project is and how the parts fit together.

## api

- **Path:** `services/api`
- **Responsibility:** HTTP API; owns the orders database.
- **Docs:** `services/api/CLAUDE.md`
- **Run:** `cd services/api && go run ./cmd/api`
- **Test:** `cd services/api && go test ./...`
- **Test needs:** none
```

The older `.ai-ready/components.json` is still read. `--convert-map` turns it into
`components.md`.

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
  ],
  "factory": { "max_attempts": 3, "suggest": false, "suggest_min_words": 40 }
}
```

- `ignore`: globs for generated or vendored files and confirmed false positives.
- `fail_on`: `error` or `warning`.
- `min_score`: also fail when the overall score is below this.
- `doc_watch`: when files matching `paths` change and none of `docs` do, report `doc-drift`.
  Globs use `fnmatch`, so `*` also matches `/`. Changes are uncommitted and untracked files,
  plus `REF...HEAD` when `--base REF` is given.
- `factory`: `max_attempts` per task before it is blocked. With `suggest`, a prompt of at
  least `suggest_min_words` words that isn't a slash command makes Claude offer the factory
  first.

## Keeping it AI ready

**In Claude Code** (automatic once the plugin is installed and the repo has a config):

- after Claude edits a Markdown file, the check runs on that file (and, for `CLAUDE.md`,
  against its budget) and reports new issues back to Claude right away;
- before Claude finishes a turn, the full check runs on the working tree; if it finds new
  issues, Claude is asked once to fix them. Set `AI_READY_DISABLE=1` to turn the hooks off.
- `/ai-ready:check` runs the check on demand and fixes what it finds.
- after a compaction or resume, unfinished factory work is restated in one line; with
  `factory.suggest`, long prompts get a one-line nudge to offer the factory.

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
