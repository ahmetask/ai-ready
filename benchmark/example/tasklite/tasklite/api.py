"""HTTP API: GET /tasks, POST /tasks {"title": ...}, POST /tasks/<id>/done."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .store import Store


def task_json(task):
    return {"id": task.id, "title": task.title, "done": task.done}


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/tasks":
                self._send(200, [task_json(t) for t in store.all()])
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            parts = self.path.strip("/").split("/")
            if parts == ["tasks"]:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                self._send(201, task_json(store.add(body["title"])))
            elif len(parts) == 3 and parts[0] == "tasks" and parts[2] == "done":
                self._send(200, task_json(store.complete(int(parts[1]))))
            else:
                self._send(404, {"error": "not found"})

        def log_message(self, *args):
            pass

    return Handler


def serve(port=8080, store=None):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store or Store()))
    print(f"tasklite API on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve()
