---
description: Turn a prompt into a short, structured workflow using the component map, then do it
argument-hint: "<what you want done>"
allowed-tools: Read, Grep, Glob
---

The request: $ARGUMENTS

Turn the request into a short workflow, then carry it out. The goal is to load only the
context the request needs, so keep every step below as small as it can be.

1. Read `.ai-ready/components.json`. If it doesn't exist, skip the map: work out the
   affected area from the request and a quick search instead, and at the end suggest the
   `make-ai-ready` skill in one line.
2. Pick the components the request touches, usually one to three, by their `path` and
   `responsibility`. Read only those components' docs (their nested `CLAUDE.md` first) and
   nothing else up front. Don't read the other components' docs or explore outside the
   chosen paths unless a step turns out to need it.
3. If the request is a question, or a small change inside one component that the docs
   already explain, don't write a plan: say "No plan needed" and just answer or do it.
4. Otherwise, write the workflow before changing anything, in at most 15 lines:
   - **Goal**: one sentence.
   - **Components**: each chosen component, and why it is involved.
   - **Steps**: numbered, in order, each naming the exact files it changes.
   - **Verify**: each touched component's `test` command from the map, noting its
     `test_needs`.
   Keep the workflow in the conversation; don't write it to a file.
5. If the request is ambiguous in a way that changes the steps, ask one question and stop.
   Otherwise carry out the steps in order.
6. Finish with the Verify commands when you can run them, and fix what they report. If the
   change moved a component's files, responsibility, or run/test command, update
   `.ai-ready/components.json` and that component's docs so the repo stays AI ready (the
   ai-ready Stop hook checks this before you finish). End with a two-line summary of what
   changed and what was verified.
