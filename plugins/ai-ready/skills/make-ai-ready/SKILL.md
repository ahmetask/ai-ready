---
name: make-ai-ready
description: Make a repository clean, well structured and compact for AI agents - prune stale docs, consolidate the rest, write a lean CLAUDE.md, plan what's left, and turn on the ai-ready check. Use for "make this repo AI ready", doc cleanup, or writing or trimming CLAUDE.md/AGENTS.md.
---

# Make a repository AI ready

An AI-ready repository is **clean, well structured and compact**. An agent that arrives cold
finds a short `CLAUDE.md` with the commands, guardrails and gotchas. Every other doc is
accurate, has one obvious place, and is read only when the task needs it. Stale docs are worse
than missing docs, because agents trust them. Extra docs aren't free either: they cost tokens
whenever an agent reads them.

**Always-loaded context is paid for on every turn.** `CLAUDE.md` and its `@imports` are
re-read on every model call of every session. They pay for themselves on orientation
questions and are pure overhead on a plain edit. In a benchmark on a real repo, a ~40-line
`CLAUDE.md` (commands, guardrails, gotchas, with details in linked docs) cut tokens by 37%
and cost by 28% across tasks. A longer `CLAUDE.md` cut tokens by only 26%, and it made a
simple edit task 48% more expensive. So aim for the smallest `CLAUDE.md` that still answers
three questions: where is it, how do I run it, and what must I not do.

The deterministic checker is `${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py` (Python 3,
stdlib only). Run it from the target repository's root. `references/criteria.md` defines the
readiness dimensions; read it before phase 1. Work on a branch so the result is one reviewable
diff, and keep the user informed between phases.

## Phase 1: Audit (read-only)

1. Run the checker for a mechanical baseline:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --no-baseline --format json`.
   It reports broken links, docs that mention paths or `npm run`/`make` commands that no
   longer exist, and a missing or over-budget `CLAUDE.md`/`AGENTS.md` (60 lines / 4 KB,
   imports included).
2. Map the repository: languages, package managers, entry points, top-level layout, and how
   CI builds and tests it. The CI config is the most reliable source of the real commands.
3. Inventory every doc an agent might read: `README*`, `CLAUDE.md` (root and nested),
   `AGENTS.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.cursor/rules/`,
   `CONTRIBUTING*`, `docs/`, ADRs, nested READMEs, stray notes (`NOTES.md`, `TODO.md`,
   `old/`, `*.bak.md`) and long comment headers that act as docs.
4. Classify each doc as **keep**, **fix**, **merge** or **delete**:
   - **stale**: commands that don't match `package.json`, `Makefile`, `pyproject.toml` or
     CI; modules, env vars or config keys that no longer exist (grep for them); superseded
     versions or flows; docs whose code changed a lot since the doc did
     (`git log -1 --format=%cs -- <doc>` vs.
     `git log --since=<that date> --oneline -- <code dir> | wc -l`). Where it is cheap and
     safe (no network side effects, no deploys), run the documented commands;
   - **duplicate**: the same topic in several files, or files that contradict each other
     (README and `CLAUDE.md` disagree on the test command);
   - **dead weight**: TODO/WIP/"coming soon" docs for things that never landed, meeting
     notes, abandoned plans, generated docs nobody reads, and docs describing removed systems.
5. Score each dimension in `references/criteria.md` from 0 to 3, with one line of evidence each.

Show the user a short summary: overall readiness, the three worst gaps, and the proposed
cleanup as a list grouped by **fix**, **merge** and **delete**, with one line per file.

## Phase 2: Prune and restructure the docs

- **Delete** what is wholly obsolete. List every file you intend to delete with a one-line
  reason, and get the user's go-ahead before deleting. Never delete licenses, changelogs,
  security policies or ADRs; mark an ADR superseded instead.
- **Merge** duplicates into one canonical file per topic, and replace the others with a
  one-line pointer or remove them. A good default shape:
  - `README.md` is for humans: what it is, and how to install, run and contribute;
  - `CLAUDE.md` is for agents (phase 3);
  - `docs/` holds one file per topic (architecture, deploy, a specific subsystem), each
    linked from `README.md` or `CLAUDE.md` so nothing is orphaned;
  - per-directory detail goes in a nested `<dir>/CLAUDE.md`, which Claude Code loads only
    when it works in that directory.
- **Fix** whatever has a clear correct answer: links to moved files, renamed paths, wrong
  commands (use what CI runs) and outdated versions. Keep the author's voice, and don't
  rewrite docs that are already correct.
- When you can't tell whether something is still true, don't guess. Leave it, and record it as
  an open question in the plan.

Re-run the checker afterwards. The findings for the files you touched should be gone.

## Phase 3: Write a lean CLAUDE.md

Write `CLAUDE.md`, or trim the existing one, to the budget: **under 60 lines and 4 KB,
imports included**. That is usually 30 to 45 lines. A line belongs only if an agent couldn't
get it from the code in one or two tool calls, or would get it wrong without it:

- **Purpose**: one line.
- **Commands**: the exact build, test, lint and run commands (what CI runs), one line each.
- **Guardrails**: commands that deploy, delete or touch shared state; files that are
  generated or hold production ids and must not be hand-edited; secrets never to commit.
- **Gotchas**: non-obvious conventions and traps, one line each. For example, where a new
  module must be registered, or a builtin that shadows a script name.
- **Layout**: top-level directories only, one line each, saying what lives where.
- **Links**: the one or two deeper docs that matter, as plain links. Don't `@import` them,
  because an import is loaded every turn while a link is read only when needed.

Leave out what costs every turn but helps few tasks: directory trees, per-module detail
(move it to a nested `CLAUDE.md` or a doc), prose explanations, lists of every doc,
anything `ls` or a linked doc already shows, and history.

If the repo already uses `AGENTS.md`, keep the content there and make `CLAUDE.md` the single
line `@AGENTS.md`. The budget applies to the pair.

## Phase 4: Write the plan

Write `.ai-ready/plan.md` (create the directory if needed) from
`references/plan-template.md`. It includes:

- the dimension scores with evidence, before and after;
- what phases 2 and 3 changed (deleted, merged, fixed, `CLAUDE.md` lines before and after);
- a prioritized backlog of the remaining work. Each item says why it matters for agents,
  what to change, which files are involved, and the effort (S/M/L), with quick wins first;
- open questions only a maintainer can answer.

## Phase 5: Keep it clean

Turn on enforcement so the repo can't drift back:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --init` writes
   `.ai-ready/config.json`. Adjust it:
   - `instruction_files`: which files count as agent instructions;
   - `max_instructions_lines` / `max_instructions_bytes` (default 60 / 4000): the
     `CLAUDE.md` budget. Leave these at the defaults unless the user asks;
   - `ignore`: globs for generated or vendored docs, and for confirmed false positives;
   - `doc_watch`: rules that tie fragile docs to the code they describe, for example
     `{"paths": ["src/api/**"], "docs": ["docs/api.md"]}` (`*` also matches `/`). A change
     to those paths without a change to the doc is reported as `doc-drift`;
   - `fail_on` (`error` or `warning`) and `min_score`.
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --update-baseline` accepts
   the issues that remain, so only *new* issues fail. If `CLAUDE.md` is still over budget,
   the baseline also caps it at its current size, so it can shrink but never grow. The
   plan's backlog is how the baseline shrinks; never add to the baseline by hand.
3. Offer CI: the GitHub Action or `pre-commit` (examples are in the plugin README). With the
   plugin installed, Claude Code also runs the check as hooks: after each Markdown edit
   (including `CLAUDE.md` against its budget), and before finishing a turn.

## Finish

Report back in a few lines: readiness before and after, how many docs were deleted, merged
and fixed, `CLAUDE.md` lines before and after, where the plan is (`.ai-ready/plan.md`), and
whether enforcement is on. Don't paste the plan into chat.
