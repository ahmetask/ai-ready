# Architecture

ai-ready is a Claude Code plugin, published from this repository's marketplace, that makes
repositories AI ready. It maps a repository's components, prunes stale docs and keeps
`CLAUDE.md` lean. A single stdlib Python checker then enforces that state from Claude Code
hooks, slash commands, a GitHub Action and a pre-commit hook. On top of the map, a small
factory plans work into tracked tasks and runs them through coder, tester and documenter
agents. A benchmark measures what the
skill saves in tokens.

The component map is `.ai-ready/components.json`. Its checks keep this page honest, and
`python3 plugins/ai-ready/scripts/ai_ready_check.py --explain` prints it.

| Component | Path | Responsibility | Docs | Test |
|---|---|---|---|---|
| plugin | `plugins/ai-ready` | The checker, the `make-ai-ready` skill, `/ai-ready:check` and `/ai-ready:explain`, the factory (`/ai-ready:plan`, `/ai-ready:build`, `/ai-ready:status`, the work tracker and its four agents), and the hooks | [CLAUDE.md](../plugins/CLAUDE.md), [README](../README.md) | `python3 -m unittest discover -s plugins/ai-ready/tests` |
| integrations | `action.yml` | The GitHub Action, `.pre-commit-hooks.yaml` and this repo's CI workflow | [README](../README.md#keeping-it-ai-ready) | `python3 plugins/ai-ready/scripts/ai_ready_check.py --base origin/main` |
| benchmark | `benchmark` | Before/after token benchmark of the skill and the factory, on another repo or the in-tree `tasklite` example, with recorded results | [CLAUDE.md](../benchmark/CLAUDE.md), [README](../benchmark/README.md) | `python3 benchmark/run_benchmark.py compare` on recorded results (offline) |

All tests run offline in seconds, with no services or credentials.

## How it fits together

Everything goes through `plugins/ai-ready/scripts/ai_ready_check.py`:

- the skill calls it to discover components (`--discover`), audit docs, run tests
  (`--verify-tests`) and enable enforcement (`--init`, `--update-baseline`);
- `hooks/hooks.json` runs it after Markdown edits (`--hook post-edit`) and before Claude ends a
  turn (`--hook stop`), but only in repositories that have `.ai-ready/config.json`;
- `/ai-ready:check` and `/ai-ready:explain` run it on demand;
- the factory's commands and agents keep their state in `.ai-ready/work/<slug>.json` and read
  and update it through `--work` and `--work-set`. A `SessionStart` hook (`--hook
  session-start`) restates unfinished work after a compaction, and the opt-in
  `UserPromptSubmit` hook (`--hook prompt`) offers the factory for long prompts;
- `action.yml` and `.pre-commit-hooks.yaml` run it in CI, from this repository by path.

The benchmark is separate. It drives headless `claude -p` sessions against another repository
and doesn't import the checker.
