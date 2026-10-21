---
description: Turn a prompt into a tracked plan of tasks for the ai-ready factory (asks first; small changes go direct)
argument-hint: "[--go] <what you want done>"
allowed-tools: Bash(python3:*), Read, Grep, Glob
---

The request: $ARGUMENTS

Plugin directory: !`echo "${CLAUDE_PLUGIN_ROOT}"`

Tracked work so far:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --work 2>&1 || true`

1. **Triage.** Read `.ai-ready/components.md` if it exists, and nothing else yet. Call the
   request *small* if it is a question, or a change inside one component that touches a few
   files and needs no design. Otherwise call it *large*.
2. **Ask once.** Unless the request starts with `--go`, ask the user one question: run it
   through the factory (a tracked plan, done by coder, tester and documenter agents) or do it
   directly. Recommend direct for small requests, because the factory costs extra agent
   sessions, and the factory for large ones. If they pick direct, do the request now: read
   only the touched component's docs, make the change, run its `test` command, and stop here.
3. **Plan.** Pick a short kebab-case slug for the work (at most five words). Launch the
   ai-ready `planner` subagent with the request, the slug and the plugin directory above.
4. **Show** the subagent's summary as is, including any open question. End with one line:
   `/ai-ready:build <slug>` runs it. Don't start the tasks yourself.
