---
description: Show the ai-ready factory's tracked work - goal, tasks, attempts and what runs next
argument-hint: "[<slug>]"
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --work $ARGUMENTS 2>&1 || true`

Show the output above as is. This is read-only, so don't change any files. If a task is
blocked, add one line on what would unblock it, based on its note. If there is unfinished
work, end with `/ai-ready:build <slug>` to continue it.
