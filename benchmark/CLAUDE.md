# benchmark

Before/after token benchmark of the `make-ai-ready` skill; usage and flags are in `README.md`.

- `run` and `prepare` start real headless `claude -p` sessions: they need the `claude` CLI and
  an API key, and they cost money. Run them only when asked.
- Offline smoke test: `python3 benchmark/run_benchmark.py compare
  benchmark/results/myagent-2026-10-19/before.jsonl benchmark/results/myagent-2026-10-19/after.jsonl`.
- Every session runs in its own detached `git worktree` of the target repo, which is removed
  afterwards. Don't change this, because sessions would leak edits into each other.
- Each run's results go in a new `results/<repo>-<date>[-variant]/` folder with a README
  explaining it. Existing results are records; don't edit them.
- Tasks live in `tasks/<repo>.json` as `{id, prompt, expect, expect_changed}`.
