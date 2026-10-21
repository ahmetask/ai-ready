---
description: Run the ai-ready factory - plan if needed, then code, test and iterate on each tracked task with agents until done
argument-hint: "[<slug> | [--go] <what you want done>]"
allowed-tools: Bash(python3:*), Read, Grep, Glob
---

Arguments: $ARGUMENTS

Plugin directory: !`echo "${CLAUDE_PLUGIN_ROOT}"`

Tracked work so far:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --work 2>&1 || true`

`TRACK` below means `python3 "<plugin directory>/scripts/ai_ready_check.py"`.

You orchestrate. Agents do the reading, coding and testing in their own contexts, and the
tracker holds the state, so keep your own context small. Don't read source files or full test
logs yourself. Pass each agent only its task line and the previous agent's summary, and get
the state from `TRACK --work <slug>`, never by reading the JSON.

## 1. Pick the work

- If the arguments name a slug listed above, continue that work.
- If they are empty, continue the unfinished work listed first. If there is none, ask what
  to build.
- Otherwise they are a new request. Read `.ai-ready/components.json`, then decide whether the
  request is small (a question, or a few files in one component) or large. Unless the
  arguments start with `--go`, ask the user once: factory or direct? Recommend direct for
  small requests. If they pick direct, do it directly and stop. For the factory, pick a
  kebab-case slug and launch the ai-ready `planner` subagent with the request, the slug and
  the plugin directory. If it reports an open question that changes the tasks, ask the user
  and stop.

## 2. Loop over the tasks

Repeat until `TRACK --work <slug>` prints `next: none`:

1. For each id on the `next:` line, run `TRACK --work-set <slug> <id> doing`. If that prints
   `blocked`, the task ran out of attempts: leave it. Tasks on the same `next:` line in
   different components can run as parallel subagents.
2. Run the task's agent (`coder`, `tester` or `documenter`, from the task line) as the
   ai-ready subagent of that name. Give it the slug, the task line, the plugin directory
   and, on a retry, the tester's last failure summary.
3. For a `coder` task with a `verify` command, then run the ai-ready `tester` subagent on it.
   A `tester` task's own agent is already the test.
4. If the tester replied `PASS`, or the task has no `verify` and its agent succeeded, run
   `TRACK --work-set <slug> <id> done --note "<one line: what changed>"`. On `FAIL`, run
   `TRACK --work-set <slug> <id> todo --note "<one line: the cause>"`. The next round retries
   it with the failure summary. The tracker counts attempts and blocks a task after the
   configured limit (default 3).

Waiting on signals: slow test runs and CI checks are the tester's job (it runs them in the
background and polls). Don't sleep or poll in this session.

## 3. Finish

- If the work changed code but has no `documenter` task, or code changed after one ran, run
  the ai-ready `documenter` subagent once.
- Run `TRACK` (the full check) and fix the issues it marks NEW.
- Reply in at most 8 lines: the goal, the tasks done, any blocked tasks with their notes and
  what you need from the user to unblock them, and what was verified. Don't commit or push
  unless the user asked to.
