# tasklite

A tiny task tracker: a command line and a JSON HTTP API over one JSON file. Python 3.8+,
standard library only.

```
python3 -m tasklite add "buy milk"
python3 -m tasklite list
python3 -m tasklite done 1
python3 -m tasklite.api          # API on http://127.0.0.1:8080
```

Tasks are stored in `tasks.json` in the current directory (override with `TASKLITE_FILE`).

Tests: `python3 -m unittest discover -s tests -t .`
