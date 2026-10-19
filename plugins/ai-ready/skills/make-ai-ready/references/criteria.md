# AI readiness criteria

Score each dimension 0-3 and cite one line of evidence (a file, a command you ran, a grep).

| Score | Meaning |
|---|---|
| 0 | Missing or actively misleading |
| 1 | Present but stale, partial, or hard to find |
| 2 | Accurate and findable, with small gaps |
| 3 | Accurate, concise, and checked automatically |

## Dimensions

1. **Agent instructions.** `CLAUDE.md` / `AGENTS.md` exists, is accurate, and fits the budget
   (under 60 lines and 4 KB with imports; it is re-read on every turn). It holds commands,
   guardrails and gotchas, and links to deeper docs instead of copying them. A 3 means it's
   about 40 lines and nothing in it is derivable from one `ls` or one file read.
2. **Build, test, lint, run commands.** Documented exactly, match what CI runs, and work on a
   clean checkout. A 3 means a single obvious command for each.
3. **Docs accuracy.** No broken links, no references to removed files, commands, env vars or
   modules; no contradictions between docs. The `ai_ready_check.py` findings feed this score.
4. **Doc structure.** One canonical place per topic; no duplicates, contradictions, orphaned
   docs, abandoned plans or stray notes. `README.md` for humans, `CLAUDE.md` for agents,
   `docs/` one file per topic, per-directory detail in nested `CLAUDE.md` files.
5. **Components understood.** `.ai-ready/components.json` has an abstract and, for every
   component, a responsibility, docs, and run and test commands that work. There are no
   unmapped components and no source files so large an agent can't hold them in context
   (flag files over ~1,500 lines).
6. **Environment setup.** Reproducible: pinned toolchain versions, lockfiles committed,
   `.env.example` or equivalent for required config, services startable locally (compose,
   devcontainer) or mocked.
7. **Feedback loops.** Each component's tests run with one command, offline, with no
   credentials or external services (`test_needs` empty) and in minutes. Add type checking or
   linting, and CI that reports clearly. Agents fix what they can measure.
8. **Conventions.** Non-obvious rules (naming, error handling, where new code goes, how to add a
   migration) are written down once.
9. **Safety rails.** Secrets are not in the repo, destructive scripts are clearly labelled,
   and generated or vendored code is marked so agents don't hand-edit it.
10. **Staying ready.** The ai-ready check runs in CI or pre-commit, with `doc_watch` rules for docs
   that track fast-moving code.

Overall readiness is the sum (0-30). Rough bands: 0-10 not ready, 11-20 workable, 21-30 ready.
