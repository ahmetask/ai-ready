# ai-ready

Claude Code plugin (plus GitHub Action and pre-commit hook) that makes repositories AI ready and
checks that changes keep them that way. See `README.md` for user-facing docs.

## Layout

- `plugins/ai-ready/scripts/ai_ready_check.py`: the checker. Single file, Python 3.8+, stdlib
  only; keep it that way so it runs anywhere without installs.
- `plugins/ai-ready/skills/make-ai-ready/SKILL.md`: the audit / cleanup / plan skill, with
  `references/criteria.md` and `references/plan-template.md`.
- `plugins/ai-ready/hooks/hooks.json`, `plugins/ai-ready/commands/check.md`: Claude Code wiring.
- `action.yml`, `.pre-commit-hooks.yaml`: CI integrations; both call the checker by path.
- `.ai-ready/config.json`, `.ai-ready/components.json`: this repo dogfoods its own check and
  component map.
- `benchmark/`: before/after token benchmark of the skill on a target repo (`run_benchmark.py`,
  tasks in `benchmark/tasks/`, manual workflow `.github/workflows/benchmark.yml`). Same stdlib-only rule.

## Commands

- Tests: `python3 -m unittest discover -s plugins/ai-ready/tests -v`
- Self-check: `python3 plugins/ai-ready/scripts/ai_ready_check.py`
- Validate the plugin: `claude plugin validate plugins/ai-ready`

## Conventions

- Every check has a stable `key` without line numbers; the baseline fingerprint is
  `check|file|key`, so changing a key format invalidates users' baselines.
- Hooks must stay silent (exit 0) in repositories without `.ai-ready/config.json`, and the Stop
  hook must respect `stop_hook_active` so it never loops.
- When adding a check, add it to the table in `README.md` and a test in `plugins/ai-ready/tests/`.
