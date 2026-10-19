---
description: Explain this repository - abstract, components, responsibilities, docs, how to run and test each
allowed-tools: Bash(python3:*), Read, Grep, Glob
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ai_ready_check.py" --explain 2>&1 || true`

This is read-only: don't change any files.

If the output above comes from `.ai-ready/components.json`, present it as is: the abstract,
then one line per component with its responsibility, where its docs are, and how to run and
test it. Flag any component whose test command is missing or whose tests need network,
a database, Docker or secrets.

If there is no component map yet, the table lists components detected from build files. Fill
in the gaps by reading each component's README, entry points and CI config, then present the
same overview. End with one line suggesting the `make-ai-ready` skill to save it as
`.ai-ready/components.json` with matching docs.
