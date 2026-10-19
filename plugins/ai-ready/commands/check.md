---
description: Run the ai-ready check on this repository and fix any new issues it reports
argument-hint: "[--base <git ref>]"
allowed-tools: Bash(python3:*), Read, Edit, Grep, Glob
---

Run the ai-ready checker from the repository root:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" $ARGUMENTS 2>&1 || true`

Explain the result in a few lines. For each issue marked NEW, fix the doc (update the path,
link or command to what the code now has) or, if the finding is a false positive, say so and
suggest an `ignore` glob for `.ai-ready/config.json`. If the repository has no
`.ai-ready/config.json` yet, suggest running the `make-ai-ready` skill first.
