# Work: due-dates

- **Goal:** Tasks can carry an optional due date, settable from the CLI and API, and open tasks due before today can be listed via `list --overdue` and `GET /tasks?overdue=1`, with old tasks.json files still loading.
- **Request:** add due dates. `tasklite add "pay rent" --due 2026-01-31` sets one, `tasklite list --overdue` shows only open tasks due before today, and the API takes "due" on POST /tasks and supports GET /tasks?overdue=1. Old tasks.json files without due dates must still load. Add tests.
- **Created:** 2026-10-21
- **Components:** tasklite

## 1. Add optional due field and overdue filter to Store, with store tests

- **Status:** done
- **Agent:** coder
- **Component:** tasklite
- **Files:** `tasklite/store.py`, `tests/test_store.py`
- **Verify:** `python3 -m unittest tests.test_store`
- **After:** none
- **Attempts:** 1
- **Note:** Task.due, Store.add(due), Store.overdue + tests

## 2. Add --due to add and --overdue to list in the CLI, with CLI tests

- **Status:** done
- **Agent:** coder
- **Component:** tasklite
- **Files:** `tasklite/cli.py`, `tests/test_cli.py`
- **Verify:** `python3 -m unittest tests.test_cli`
- **After:** 1
- **Attempts:** 1
- **Note:** CLI add --due, list --overdue + tests

## 3. Accept due on POST /tasks and support GET /tasks?overdue=1 in the API, with API tests

- **Status:** done
- **Agent:** coder
- **Component:** tasklite
- **Files:** `tasklite/api.py`, `tests/test_api.py`
- **Verify:** `python3 -m unittest tests.test_api`
- **After:** 1
- **Attempts:** 1
- **Note:** API due on POST, GET ?overdue=1 + tests

## 4. Document due dates in README and CLAUDE.md

- **Status:** done
- **Agent:** documenter
- **Component:** tasklite
- **Files:** `README.md`, `CLAUDE.md`
- **Verify:** none
- **After:** 2, 3
- **Attempts:** 1
- **Note:** README and CLAUDE.md updated
