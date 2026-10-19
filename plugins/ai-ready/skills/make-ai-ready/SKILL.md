---
name: make-ai-ready
description: Audit a repository for how well AI coding agents can work in it, clean up stale or misleading docs, write a prioritized plan to make it AI ready, and turn on the ai-ready check so it stays that way. Use when the user asks to "make this repo AI ready", "prepare the codebase for Claude/agents", "clean up stale docs", "audit our docs", "write CLAUDE.md / AGENTS.md", or asks how agent-friendly a repository is.
---

# Make a repository AI ready

An AI-ready repository is one where an agent arriving cold can learn how to build, test and
change the code from files in the repo, and where what those files say is true. Stale docs are
worse than missing docs: an agent will trust them. The job has four phases. Do them in order and
keep the user informed between phases.

The deterministic checker lives at `${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py`
(Python 3, stdlib only). Run it from the target repository's root. `references/criteria.md`
defines the readiness dimensions and how to score them; read it before phase 1.

## Phase 1: Audit (read-only)

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
leverage item): project purpose in two lines, layout map, exact build/test/lint/run commands,
conventions that aren't obvious from code, and pointers to deeper docs. Keep it under ~200
lines; agents read it every session. If the repo already uses `AGENTS.md`, extend that instead
and keep a one-line `CLAUDE.md` that says `@AGENTS.md` only if the user wants both.

## Phase 4: Keep it AI ready

Turn on enforcement so future changes can't silently regress:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --init` writes
   `.ai-ready/config.json`. Adjust it:
   - `instruction_files`: which files count as agent instructions;
   - `ignore`: globs for generated or vendored docs, and for confirmed false positives;
   - `doc_watch`: rules tying fragile docs to the code they describe, e.g.
     `{"paths": ["src/api/**"], "docs": ["docs/api.md"]}` (`*` also matches `/`);
     a change to those paths without touching the doc is reported as `doc-drift`;
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
