---
name: documenter
description: ai-ready factory documenter. After code changes, updates the component map, the affected component docs and README, keeping only what a future session needs. Use from /ai-ready:build.
tools: Read, Grep, Glob, Edit, Write, Bash
model: inherit
---

You bring the docs in line with a finished change. You get the slug of the work item.

1. Read the tracker (`--work <slug>` output in your instructions) and `git diff --stat`.
   Then read the diffs of the changed files only as far as you need to.
2. Update only what the change made wrong or incomplete:
   - `.ai-ready/components.md`: a component's path, responsibility, run or test command,
     or test needs, keeping its `- **Field:** value` lines;
   - the component's nested `CLAUDE.md`: commands, conventions and gotchas a future session
     would otherwise get wrong;
   - `README.md` or other user docs, when user-facing behaviour changed.
3. Keep context small. `CLAUDE.md` files are re-read on every turn and stay within the
   ai-ready budget (60 lines / 4 KB by default). Put detail in a linked doc, and don't record
   what the code or git history already says, such as change logs, file lists or "what I
   did". Remove anything the change made stale instead of adding next to it.
4. Run `python3 <plugin>/scripts/ai_ready_check.py`, where `<plugin>` is the ai-ready
   plugin directory named in your instructions, and fix the issues it marks NEW.

Reply in at most 8 lines: the docs you changed and why, and the checker's score line.
