---
name: make-ai-ready
description: Audit how well agents can work in a repo, fix stale docs, write a lean CLAUDE.md and a readiness plan, and turn on the ai-ready check. Use for "make this repo AI ready", doc cleanup, or writing CLAUDE.md/AGENTS.md.
---

# Make a repository AI ready

An AI-ready repository is one where an agent arriving cold can learn how to build, test and
change the code from files in the repo, and where what those files say is true. Stale docs are
worse than missing docs: an agent will trust them. The job has four phases. Do them in order and
keep the user informed between phases.

**Context costs tokens on every turn.** Whatever Claude Code loads at session start
(`CLAUDE.md`, its `@imports`, hook injections) is re-read on every model call of every session.
It pays for itself on orientation questions and is pure overhead on a plain edit, so the target
is the smallest always-loaded context that still answers "where is it, how do I run it, what
must I not do". Everything else stays on demand: linked docs, nested `CLAUDE.md` files (Claude
Code loads `<dir>/CLAUDE.md` only when it works in `<dir>`), or ctx-harness cards.

The deterministic checker lives at `${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py`
(Python 3, stdlib only). Run it from the target repository's root. `references/criteria.md`
defines the readiness dimensions and how to score them; read it before phase 1.

## Phase 1: Audit (read-only)

0. Check for ctx-harness: if `.ctx/map.md` exists, the repo already gets a generated map
   (layout, modules, verified commands) injected at every session start, and module cards on
   demand. Read the map once. In this repo ai-ready owns doc accuracy and the few rules the
   map can't express; ctx-harness owns navigation. Never edit `.ctx/` (its curator does), and
   never copy the map's content into `CLAUDE.md`.
1. Run the checker for a mechanical baseline:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --no-baseline --format json`
   It reports broken links, docs mentioning paths that no longer exist, documented
   `npm run` / `make` commands that don't exist, and missing or oversized instruction files.
2. Map the repository: languages, package managers, entry points, top-level layout, how CI
   builds and tests it (read the CI config, it is the most reliable source of the real commands).
3. Inventory every doc an agent might read: `README*`, `CLAUDE.md`, `AGENTS.md`,
   `.github/copilot-instructions.md`, `.cursorrules`, `.cursor/rules/`, `CONTRIBUTING*`,
   `docs/`, ADRs, nested READMEs, and long comment headers that act as docs.
4. For each doc, judge staleness beyond what the checker can see:
   - commands that do not match `package.json`, `Makefile`, `pyproject.toml`, CI config, etc.
     Where it is cheap and safe (no network side effects, no deploys), actually run the
     documented build/test/lint commands to confirm they work;
   - described architecture, modules, env vars or config keys that no longer exist
     (grep for them);
   - version numbers, tool names or flows superseded by newer files;
   - docs whose subject code changed a lot since the doc did
     (`git log -1 --format=%cs -- <doc>` vs. `git log --since=<that date> --oneline -- <code dir> | wc -l`);
   - duplicated or contradictory instructions across files (e.g. README and CLAUDE.md
     disagree on the test command);
   - TODO/WIP/"coming soon" docs describing things that never landed.
5. Score each dimension in `references/criteria.md` 0-3 with one line of evidence each.

Present a short summary to the user: overall readiness, the worst three gaps, and the
cleanup you propose (next phase), grouped as **fix**, **merge**, **delete**.

## Phase 2: Clean up stale docs

Apply the cleanup on the current branch so it is reviewable as a diff.

- **Fix** in place anything with a clear correct answer: broken links to moved files, renamed
  paths, wrong commands (use what CI runs), outdated versions. Keep the author's voice; don't
  rewrite docs that are correct.
- **Merge** duplicates into one canonical place and replace the others with a one-line pointer.
- **Delete** only docs that are wholly obsolete (describe removed systems, abandoned plans).
  List every file you intend to delete, with a one-line reason each, and get the user's
  go-ahead before deleting; never delete licenses, changelogs, security policies or ADRs
  (mark an ADR superseded instead).
- When you can't tell whether something is still true, don't guess: leave it, and record it
  as an open question in the plan.

Re-run the checker afterwards; the mechanical findings you touched should be gone.

## Phase 3: Write the plan

Write `.ai-ready/plan.md` (create the directory if needed) using
`references/plan-template.md`. It must contain:

- the dimension scores with evidence, before and after the cleanup;
- what the cleanup already changed (fixed / merged / deleted, one line each);
- a prioritized backlog of remaining work, each item with: why it matters for agents, the
  concrete change, the files involved, and an effort estimate (S/M/L). Quick wins first.
  Typical items: write or trim `CLAUDE.md`/`AGENTS.md`, document the real build/test/lint
  commands, add an architecture overview, add `.env.example`, make tests runnable offline,
  add type checking, split very large files, add `doc_watch` rules for fragile docs;
- open questions only a maintainer can answer.

If the repository has no agent instructions file, draft `CLAUDE.md` now (it is the highest
leverage item); if it has one, trim it the same way. Budget: under ~60 lines and 4 KB. Put a
line in only if an agent could not get it from the code in one or two tool calls, or would get
it wrong:

- purpose in one line;
- exact build/test/lint/run commands (what CI runs), one line each;
- guardrails: commands that deploy, delete or touch shared state, and generated files not to
  hand-edit;
- non-obvious conventions and gotchas, one line each;
- a short layout list of top-level directories only, with what lives where. Skip anything
  `ls` shows.

Leave out what costs every turn and helps few: directory trees, per-module detail (move it to
a nested `<dir>/CLAUDE.md`, which loads only when an agent works there), prose explanations,
lists of every doc (link the one or two that matter), and anything a linked doc already says.
Don't `@import` long docs; a plain link is read only when needed.

**With ctx-harness** (`.ctx/map.md` exists): the map already carries the layout, modules and
verified commands, so `CLAUDE.md` keeps only guardrails, gotchas and commands the map lacks,
often under 20 lines, and it is fine to have none. No layout section, no module notes (those
belong in cards; list facts the curator should add in the plan, or append one line each to
`.ctx/tasks/notes.md`), no nested `CLAUDE.md` files, and no `@import` of a file holding the
`ctx-harness:begin` block. The checker's `context-overlap` warning flags lines repeated from
the map.

If the repo already uses `AGENTS.md`, extend that instead and keep a one-line `CLAUDE.md` that
says `@AGENTS.md` only if the user wants both (with ctx-harness, keep its generated block out
of what `CLAUDE.md` imports).

## Phase 4: Keep it AI ready

Turn on enforcement so future changes can't silently regress:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --init` writes
   `.ai-ready/config.json`. Adjust it:
   - `instruction_files`: which files count as agent instructions;
   - `max_instructions_bytes` (default 8000, imports included): leave it unless the user asks;
   - `ignore`: globs for generated or vendored docs, and for confirmed false positives;
   - `doc_watch`: rules tying fragile docs to the code they describe, e.g.
     `{"paths": ["src/api/**"], "docs": ["docs/api.md"]}` (`*` also matches `/`);
     a change to those paths without touching the doc is reported as `doc-drift`. Don't
     watch `.ctx/`; ctx-harness tracks its own freshness;
   - `fail_on` (`error` or `warning`) and `min_score`.
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --update-baseline` records
   whatever issues remain as accepted, so only *new* issues fail. The plan's backlog is how the
   baseline shrinks; never add to it by hand.
3. Offer CI: a GitHub Actions job using this repository's action, or `pre-commit`. Examples
   are in the plugin README. With the plugin installed, Claude Code also runs the check as
   hooks: after each Markdown edit, and before finishing a turn (blocking once with the list of
   new issues).

## Finish

Report back in a few lines: readiness before and after, what was cleaned up, where the plan is
(`.ai-ready/plan.md`), and whether enforcement is on. Don't paste the plan into chat.
