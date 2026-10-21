"""Task storage: a JSON file holding a list of tasks."""

import json
import os
from dataclasses import asdict, dataclass

DEFAULT_PATH = os.environ.get("TASKLITE_FILE", "tasks.json")


@dataclass
class Task:
    id: int
    title: str
    done: bool = False


class Store:
    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        self.tasks = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return {}
        with open(self.path) as fh:
            return {t["id"]: Task(**t) for t in json.load(fh)}

    def save(self):
        with open(self.path, "w") as fh:
            json.dump([asdict(t) for t in self.tasks.values()], fh, indent=2)

    def add(self, title):
        task = Task(id=max(self.tasks, default=0) + 1, title=title)
        self.tasks[task.id] = task
        self.save()
        return task

    def complete(self, task_id):
        self.tasks[task_id].done = True
        self.save()
        return self.tasks[task_id]

    def all(self):
        return sorted(self.tasks.values(), key=lambda t: t.id)
