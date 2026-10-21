# plugins/ai-ready

The plugin: `scripts/ai_ready_check.py` (the checker that everything calls), the
`make-ai-ready` skill, `/ai-ready:check` and `/ai-ready:explain`, the factory
(`commands/plan.md`, `build.md`, `status.md` and the four agents in `agents/`), and the hooks
in `hooks/hooks.json`.

- Test: `python3 -m unittest discover -s plugins/ai-ready/tests` (offline, a few seconds; each
  test builds a throwaway git repo).
- The checker is one file, organised by section: utils, project facts, checks, components,
  reporting, hooks, cli. A check returns `Issue(check, severity, file, message, key)`.
- The baseline fingerprint is `check|file|key`. Keep line numbers out of `key`, and never change
  an existing key's format: that silently invalidates users' baselines.
- Hooks must exit 0 in repositories without `.ai-ready/config.json`, and the Stop hook must
  return early when `stop_hook_active` is set, or it loops.
- A new check needs a row in the check table in the root `README.md` and a test.
- `SKILL.md` refers to its own phases by number ("phase 4"); renumber those references when
  adding a phase.
- This file lives outside `plugins/ai-ready/` so it is not shipped with the plugin.
- Factory state lives only in `.ai-ready/work/<slug>.json`. Commands and agents change it
  through `--work-set`, never by rewriting the file, and only the orchestrating command
  calls it. Agent replies are capped at a few lines because the orchestrator keeps them in
  its context.
- Agent and command descriptions are loaded into every session, so keep them to one line.
- `${CLAUDE_PLUGIN_ROOT}` is the plugin directory at runtime; commands and hooks reach the
  checker through it.
