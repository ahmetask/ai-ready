# tasklite

A tiny task tracker with a command line and a JSON HTTP API. Both front ends share one `Store` class, which reads and writes a single `tasks.json` file.

## tasklite

- **Path:** `tasklite`
- **Responsibility:** CLI (`cli.py`), HTTP API (`api.py`) and JSON-file storage (`store.py`); standard library only.
- **Docs:** `README.md`
- **Run:** `python3 -m tasklite list`
- **Test:** `python3 -m unittest discover -s tests -t .`
- **Test needs:** none
