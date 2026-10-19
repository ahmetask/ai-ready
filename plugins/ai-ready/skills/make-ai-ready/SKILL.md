---
name: make-ai-ready
description: Make a repository understandable, clean and compact for AI agents - map its components (purpose, docs, how to run and test each), prune stale docs, write a lean CLAUDE.md, plan what's left, and turn on the ai-ready check. Use for "make this repo AI ready", onboarding a repo AI has never touched, doc cleanup, or writing or trimming CLAUDE.md/AGENTS.md.
---

# Make a repository AI ready

An AI-ready repository is **understood, clean, well structured and compact**. An agent that
arrives cold can tell what the project is and what its components are. For each component
it can find what it is responsible for, where its docs are, and how to run and test it. It
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

## Phase 1: Understand the repo

Do this first, before changing anything. It also suits a repo no agent has worked in before.

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --discover` lists candidate
   components. These are directories with their own build file, together with guessed run
   and test commands and the docs found in each. Treat this as a starting point, not the
   answer. Group packages that only make sense together (for example `crates/*` behind one
   CLI) into a single component whose path is their parent directory. Add components that
   have no build file, such as a `scripts/` folder or infrastructure code.
2. For each component, read its README, entry points, CI jobs and build file. Then work out:
   - its **responsibility**, in one line, plus what it talks to;
   - its **docs**: the files that explain it. A nested `<path>/CLAUDE.md` is the default
     home for agent notes;
   - how to **run** it: the exact command, taken from CI or the build file rather than
     guessed. Set `"library": true` if the component isn't run on its own;
   - how to **test** it: the exact command, for that component alone;
   - what its tests **need** (`test_needs`): `network`, `database`, `docker`, `secrets`,
     `cloud` or `service`. Leave it empty when the tests run offline with no setup.
3. Write the **abstract**: two or three lines on what the project is, who uses it, and the
   main flow between components.
4. Run the test commands where that is safe (no deploys, no writes to shared state):
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --verify-tests`, or with a
   component name to run just that one. Record which tests pass, how long they take, and
   what they actually needed. Tests that need services, credentials or a long setup become
   plan items (phase 5), with the concrete fix: a fake or in-memory adapter, SQLite instead
   of a server, recorded HTTP fixtures, a `make test` that sets everything up, or a split
   between fast unit tests and integration tests.
5. Save the map as `.ai-ready/components.json`:

   ```json
   {"abstract": "...",
    "components": [{"name": "api", "path": "services/api", "responsibility": "...",
                    "docs": ["services/api/CLAUDE.md"], "run": "cd services/api && make dev",
                    "test": "cd services/api && go test ./...", "test_needs": []}]}
   ```

   The check then keeps the map honest. It flags paths that no longer exist, missing docs,
   undefined run or test commands, new components that aren't mapped, and components whose
   build files changed while their docs didn't.
6. Show the user the result of `--explain`: the abstract plus a table of components. Ask
   them to correct anything wrong before you go on, because everything after this builds on
   the map.

## Phase 2: Audit the docs (read-only)

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

## Phase 3: Prune and restructure the docs

- **Delete** what is wholly obsolete. List every file you intend to delete with a one-line
  reason, and get the user's go-ahead before deleting. Never delete licenses, changelogs,
  security policies or ADRs; mark an ADR superseded instead.
- **Merge** duplicates into one canonical file per topic, and replace the others with a
  one-line pointer or remove them. A good default shape:
  - `README.md` is for humans: what it is, and how to install, run and contribute;
  - `CLAUDE.md` is for agents (phase 4);
  - `docs/architecture.md` holds the abstract and the component table from the map
    (`--explain` prints it). Keep it in sync with `.ai-ready/components.json`;
  - `docs/` holds one file per topic beyond that (deploy, a specific subsystem), each linked
    from `README.md` or `CLAUDE.md` so nothing is orphaned;
  - each component gets a nested `<path>/CLAUDE.md` of at most ~30 lines, covering what it
    does, how to run and test it on its own, its gotchas and its guardrails. Claude Code
    loads that file only when it works in that directory, so it costs nothing elsewhere.
    Reuse a good component README instead of duplicating it.
- **Fix** whatever has a clear correct answer: links to moved files, renamed paths, wrong
  commands (use what CI runs) and outdated versions. Keep the author's voice, and don't
  rewrite docs that are already correct.
- When you can't tell whether something is still true, don't guess. Leave it, and record it as
  an open question in the plan.

Re-run the checker afterwards. The findings for the files you touched should be gone.

## Phase 4: Write a lean CLAUDE.md

Write `CLAUDE.md`, or trim the existing one, to the budget: **under 60 lines and 4 KB,
imports included**. That is usually 30 to 45 lines. A line belongs only if an agent couldn't
get it from the code in one or two tool calls, or would get it wrong without it:

- **Purpose**: one line.
- **Commands**: the exact build, test, lint and run commands (what CI runs), one line each.
- **Guardrails**: commands that deploy, delete or touch shared state; files that are
  generated or hold production ids and must not be hand-edited; secrets never to commit.
- **Gotchas**: non-obvious conventions and traps, one line each. For example, where a new
  module must be registered, or a builtin that shadows a script name.
- **Layout**: one line per component from the map, saying what lives where. Detail stays in
  each component's own `CLAUDE.md` and in `docs/architecture.md`.
- **Links**: the one or two deeper docs that matter, as plain links. Don't `@import` them,
  because an import is loaded every turn while a link is read only when needed.

Leave out what costs every turn but helps few tasks: directory trees, per-module detail
(move it to a nested `CLAUDE.md` or a doc), prose explanations, lists of every doc,
anything `ls` or a linked doc already shows, and history.

If the repo already uses `AGENTS.md`, keep the content there and make `CLAUDE.md` the single
line `@AGENTS.md`. The budget applies to the pair.

## Phase 5: Write the plan

Write `.ai-ready/plan.md` (create the directory if needed) from
`references/plan-template.md`. It includes:

- the dimension scores with evidence, before and after;
- the component map (link it), with any component missing docs, a run command or a test command;
- test ease: for each component, whether its tests ran, how long they took, and what they
  needed, plus the steps to make them run offline with one command;
- what phases 3 and 4 changed (deleted, merged, fixed, `CLAUDE.md` lines before and after);
- a prioritized backlog of the remaining work. Each item says why it matters for agents,
  what to change, which files are involved, and the effort (S/M/L), with quick wins first;
- open questions only a maintainer can answer.

## Phase 6: Keep it clean

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

Report back in a few lines: the abstract, the number of components, how many have working
offline tests, readiness before and after, how many docs were deleted, merged
and fixed, `CLAUDE.md` lines before and after, where the plan is (`.ai-ready/plan.md`), and
whether enforcement is on. Don't paste the plan into chat.
