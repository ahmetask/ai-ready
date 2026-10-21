# tasklite

Task tracker: CLI + JSON HTTP API over one JSON file. Python 3.8+, stdlib only (keep it so).

## Commands
- Test (all, <1s, offline): `python3 -m unittest discover -s tests -t .`
- CLI: `python3 -m tasklite add|list|done|stats`
- API: `python3 -m tasklite.api` (127.0.0.1:8080)
- No linter or CI is configured.

## Guardrails
- `tasks.json` is user data (gitignored): don't commit or hand-edit it.
- Tests should pass a temp-file `Store(path)`, not rely on the default path.

## Gotchas
- `store.DEFAULT_PATH` reads `TASKLITE_FILE` at import time; setting it later has no effect.
- `Store.complete` raises `KeyError` on an unknown id; neither the CLI nor the API handles it.
- `Task.due` is an optional `YYYY-MM-DD` string (default None, so old `tasks.json` still loads). `Store.add(..., due=)` raises `ValueError` on a bad date (CLI maps it to a parser error, API to 400). `Store.overdue(today=None)` is open tasks due strictly before today.
- New CLI commands: subparser plus `if` branch in `cli.py`. New API routes: `do_GET`/`do_POST` in `api.py`.

## Layout
- `tasklite/store.py`: `Task` dataclass and `Store` (load/save/add/complete/all)
- `tasklite/cli.py`, `tasklite/api.py`: front ends sharing a `Store`
- `tests/`: one test module per source module

Map: `.ai-ready/components.md`. Plan: `.ai-ready/plan.md`.
