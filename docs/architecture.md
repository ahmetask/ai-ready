# Architecture

ai-ready is a Claude Code plugin, published from this repository's marketplace, that makes
repositories AI ready. It maps a repository's components, prunes stale docs and keeps
`CLAUDE.md` lean. A single stdlib Python checker then enforces that state from Claude Code
hooks, slash commands, a GitHub Action and a pre-commit hook. A benchmark measures what the
skill saves in tokens.

The component map is `.ai-ready/components.json`. Its checks keep this page honest, and
`python3 plugins/ai-ready/scripts/ai_ready_check.py --explain` prints it.

| Component | Path | Responsibility | Docs | Test |
|---|---|---|---|---|
| plugin | `plugins/ai-ready` | The checker, the `make-ai-ready` skill, `/ai-ready:check` and `/ai-ready:explain`, and the PostToolUse/Stop hooks | [CLAUDE.md](../plugins/CLAUDE.md), [README](../README.md) | `python3 -m unittest discover -s plugins/ai-ready/tests` |
| integrations | `action.yml` | The GitHub Action, `.pre-commit-hooks.yaml` and this repo's CI workflow | [README](../README.md#keeping-it-ai-ready) | `python3 plugins/ai-ready/scripts/ai_ready_check.py --base origin/main` |
| benchmark | `benchmark` | Before/after token benchmark of the skill, with recorded results | [CLAUDE.md](../benchmark/CLAUDE.md), [README](../benchmark/README.md) | `python3 benchmark/run_benchmark.py compare` on recorded results (offline) |

All tests run offline in seconds, with no services or credentials.

## How it fits together

Everything goes through `plugins/ai-ready/scripts/ai_ready_check.py`:

- the skill calls it to discover components (`--discover`), audit docs, run tests
  (`--verify-tests`) and enable enforcement (`--init`, `--update-baseline`);
- `hooks/hooks.json` runs it after Markdown edits (`--hook post-edit`) and before Claude ends a
  turn (`--hook stop`), but only in repositories that have `.ai-ready/config.json`;
- `/ai-ready:check` and `/ai-ready:explain` run it on demand;
- `action.yml` and `.pre-commit-hooks.yaml` run it in CI, from this repository by path.

The benchmark is separate. It drives headless `claude -p` sessions against another repository
and doesn't import the checker.
