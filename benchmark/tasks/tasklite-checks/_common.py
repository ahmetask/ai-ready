"""Helpers for the hidden acceptance checks. Each check runs with the session's worktree as
its working directory and on PYTHONPATH, and exits non-zero with a reason on failure."""

import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def tmp_store_file(tasks=None):
    path = os.path.join(tempfile.mkdtemp(), "tasks.json")
    if tasks is not None:
        with open(path, "w") as fh:
            json.dump(tasks, fh)
    return path


def cli(store_file, *args):
    env = dict(os.environ, TASKLITE_FILE=store_file)
    return subprocess.run([sys.executable, "-m", "tasklite", *args], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=60)


class Api:
    def __init__(self, store_file):
        from tasklite.api import make_handler
        from tasklite.store import Store
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Store(store_file)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.server.server_port

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        try:
            with urlopen(Request(self.base + path, data=data, method=method), timeout=10) as r:
                return r.status, json.loads(r.read() or b"null")
        except HTTPError as e:
            return e.code, None

    def close(self):
        self.server.shutdown()
        self.server.server_close()
