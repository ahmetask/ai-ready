# ai-ready

ai-ready is a Claude Code plugin, published from this repo's marketplace, that makes repositories AI ready. It maps a repo's components, prunes stale docs and keeps CLAUDE.md lean. A single stdlib Python checker then enforces that state from Claude Code hooks, slash commands, a GitHub Action and a pre-commit hook. A benchmark measures what the skill saves in tokens.

## plugin

- **Path:** `plugins/ai-ready`
- **Responsibility:** The plugin: the ai_ready_check.py checker, the make-ai-ready skill, the /ai-ready:check and /ai-ready:explain commands, the factory (/ai-ready:plan, /ai-ready:build, /ai-ready:status, the .ai-ready/work tracker and the planner, coder, tester and documenter agents), and the hooks.
- **Docs:** `plugins/CLAUDE.md`, `README.md`
- **Run:** `python3 plugins/ai-ready/scripts/ai_ready_check.py`
- **Test:** `python3 -m unittest discover -s plugins/ai-ready/tests`
- **Test needs:** none
- **Library:** yes

## integrations

- **Path:** `action.yml`
- **Responsibility:** Ways to run the checker outside Claude Code: the composite GitHub Action, .pre-commit-hooks.yaml, and this repo's CI workflow, which runs the tests and the self-check.
- **Docs:** `README.md`
- **Run:** none
- **Test:** `python3 plugins/ai-ready/scripts/ai_ready_check.py --base origin/main`
- **Test needs:** none
- **Library:** yes

## benchmark

- **Path:** `benchmark`
- **Responsibility:** Before/after token and cost benchmark of the skill and the factory on a target repo (or the in-tree tasklite example), with hidden acceptance checks and recorded results.
- **Docs:** `benchmark/CLAUDE.md`, `benchmark/README.md`
- **Run:** `python3 benchmark/run_benchmark.py run --help`
- **Test:** `python3 benchmark/run_benchmark.py compare benchmark/results/myagent-2026-10-19/before.jsonl benchmark/results/myagent-2026-10-19/after.jsonl`
- **Test needs:** none
