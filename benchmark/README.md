# Token benchmark

Measures whether making a repository AI ready with the `make-ai-ready` skill makes Claude Code
cheaper to work in. The same intents run in fresh headless sessions against the repository
before and after the skill, and the token usage is compared.

Each session:

- starts in its own detached `git worktree` of one ref, removed afterwards, so no other
  session's edits leak in;
- is a cold `claude -p --output-format json` run with no user settings, no MCP servers and no
  session persistence, so only the repository differs between phases;
- may use `Read`, `Grep`, `Glob`, `Edit` and `Write` (no shell), with edits auto-accepted;
- is graded roughly: every `expect` string must appear in the answer and every `expect_changed`
  glob must match a changed file. That only guards against a cheap run that got it wrong.

Tokens are summed over every model the session used and include cache reads and writes.
Results vary run to run, so each task runs several times and the comparison uses medians.

## Run it

```
# 1. baseline on the untouched repository
python3 benchmark/run_benchmark.py run --repo ../myagent --ref main --label before \
    --tasks benchmark/tasks/myagent.json --repeat 3 --out results/before.jsonl

# 2. make it AI ready: runs /ai-ready:make-ai-ready headless in a separate worktree and
#    commits the result on a new branch
#    (review the diff before you trust it, or do this step interactively instead)
python3 benchmark/run_benchmark.py prepare --repo ../myagent --base main \
    --branch claude/ai-ready-benchmark --plugin-dir plugins/ai-ready --out results/prepare.jsonl

# 3. the same intents on the AI-ready branch
python3 benchmark/run_benchmark.py run --repo ../myagent --ref claude/ai-ready-benchmark \
    --label after --tasks benchmark/tasks/myagent.json --repeat 3 --out results/after.jsonl

# 4. compare
python3 benchmark/run_benchmark.py compare results/before.jsonl results/after.jsonl
```

Common flags: `--model` (default `sonnet`), `--jobs` (parallel sessions, default 3),
`--only <task ids>`, `--max-budget-usd` per session, and `--plugin-dir plugins/ai-ready` to
measure sessions with the plugin (hooks and commands) installed.

In CI, the `Token benchmark` workflow (`.github/workflows/benchmark.yml`, manual dispatch)
runs steps 1, 3 and 4 for two refs you name. It needs an `ANTHROPIC_API_KEY` secret, plus a
`TARGET_REPO_TOKEN` secret when the target repository is private.

## Example project

`example/tasklite/` is a small stdlib Python project (a CLI and an HTTP API over a JSON file,
with a planted bug) to benchmark on without any outside repository. `run_benchmark.py example
DEST` copies it into a fresh git repository, and `prepare` then makes that repository AI ready.
`tasks/tasklite.json` holds its prompts. Each task can name a hidden acceptance test in
`tasks/tasklite-checks/` (`check`), and the file's `test` command, the project's own tests, also
has to pass, so a run is graded on working code, not only on which files changed.

`run` flags for this: `--tools` (session tools, for example adding `Bash` and `Agent`),
`--allowed-tools` (permission rules such as `"Bash(python3 *)"`) and `--save-diffs DIR`, which
keeps each session's changes as a patch. Results:
[tasklite-2026-10-21-factory](results/tasklite-2026-10-21-factory/README.md).

## Measuring the factory

`tasks/myagent-vague.json` holds vague prompts like a developer would type. Run them twice on
the same AI-ready ref, with the plugin loaded both times, and change only the prefix. `--go`
skips the factory's "factory or direct?" question, which a headless session can't answer:

```
python3 benchmark/run_benchmark.py run --repo ../myagent --ref claude/ai-ready-benchmark-v2 \
    --label direct --tasks benchmark/tasks/myagent-vague.json --plugin-dir plugins/ai-ready \
    --out results/direct.jsonl
python3 benchmark/run_benchmark.py run --repo ../myagent --ref claude/ai-ready-benchmark-v2 \
    --label build --tasks benchmark/tasks/myagent-vague.json --plugin-dir plugins/ai-ready \
    --prompt-prefix "/ai-ready:build --go " --out results/build.jsonl
python3 benchmark/run_benchmark.py compare results/direct.jsonl results/build.jsonl
```

Expect the factory to cost more than `direct` on small prompts, since that is why it asks
first. It earns its place if it fails fewer multi-step tasks, at a cost you accept.

## Tasks

`tasks/<repo>.json` holds a list of `{id, prompt, expect, expect_changed}`. Pick intents a
developer would really ask cold: where to make a change, how something works, which commands
to run, plus at least one real edit. Keep answers short in the prompt so output length doesn't
dominate the numbers.
