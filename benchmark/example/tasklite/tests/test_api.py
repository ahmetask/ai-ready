import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from tasklite.api import make_handler
from tasklite.store import Store


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.dir.name, "tasks.json"))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.dir.cleanup()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        with urlopen(Request(self.base + path, data=data, method=method)) as resp:
            return json.loads(resp.read())

    def test_create_and_list(self):
        self.request("POST", "/tasks", {"title": "call bob"})
        self.request("POST", "/tasks/1/done", {})
        self.assertEqual(self.request("GET", "/tasks"),
                         [{"id": 1, "title": "call bob", "done": True}])
