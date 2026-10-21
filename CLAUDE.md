# ai-ready

Claude Code plugin that makes repositories AI ready (component map, pruned docs, lean
`CLAUDE.md`), plus a stdlib checker that keeps them that way in hooks, CI and pre-commit, and a
factory that runs planned work through coder, tester and documenter agents.

## Commands

- Test: `python3 -m unittest discover -s plugins/ai-ready/tests`
- Self-check, as CI runs it: `python3 plugins/ai-ready/scripts/ai_ready_check.py --base origin/main`
- Validate the plugin: `claude plugin validate plugins/ai-ready`
- Overview of the repo: `python3 plugins/ai-ready/scripts/ai_ready_check.py --explain`

## Guardrails

- `benchmark/run_benchmark.py run` and `prepare` start paid Claude sessions; run them only when
  asked. `compare` is offline.
- `benchmark/results/` holds recorded measurements; never edit them, add a new folder instead.
- All Python is stdlib-only and 3.8+, so the checker runs anywhere without installs.

## Gotchas

- `action.yml` and `.pre-commit-hooks.yaml` call the checker by path; moving it breaks users.
- Changing the skill, a check, a command or a hook usually means updating `README.md` too.

## Layout

- `plugins/ai-ready/`: the plugin (checker, skill, commands, factory agents, hooks, tests); see `plugins/CLAUDE.md`
- `benchmark/`: token benchmark of the skill; see its `CLAUDE.md`
- `action.yml`, `.pre-commit-hooks.yaml`, `.github/workflows/`: CI integrations
- `.ai-ready/`: this repo's own component map, config, baseline and plan

Architecture: [docs/architecture.md](docs/architecture.md).
