"""Command line: python3 -m tasklite add|list|done|stats."""

import argparse
import sys

from .store import Store


def main(argv=None, store=None):
    parser = argparse.ArgumentParser(prog="tasklite")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a task")
    add.add_argument("title")
    sub.add_parser("list", help="list tasks")
    done = sub.add_parser("done", help="mark a task done")
    done.add_argument("id", type=int)
    sub.add_parser("stats", help="summary of tasks")
    args = parser.parse_args(argv)
    store = store or Store()

    if args.command == "add":
        task = store.add(args.title)
        print(f"added {task.id}: {task.title}")
    elif args.command == "list":
        for task in store.all():
            print(f"[{'x' if task.done else ' '}] {task.id} {task.title}")
    elif args.command == "done":
        task = store.complete(args.id)
        print(f"done {task.id}: {task.title}")
    elif args.command == "stats":
        print(f"total: {len(store.all())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
