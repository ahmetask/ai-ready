from _common import Api, cli, fail, tmp_store_file

f = tmp_store_file([{"id": 1, "title": "a", "done": False}])
out = cli(f, "done", "99")
if out.returncode != 1:
    fail("done 99 exited %d, want 1" % out.returncode)
if "no such task: 99" not in out.stdout + out.stderr:
    fail("done 99 printed %r" % (out.stdout + out.stderr)[-300:])
if "Traceback" in out.stderr:
    fail("done 99 still prints a traceback")
if cli(f, "done", "1").returncode != 0:
    fail("done 1 no longer works")
api = Api(f)
try:
    status, _ = api.request("POST", "/tasks/99/done", {})
    if status != 404:
        fail("POST /tasks/99/done answered %d, want 404" % status)
finally:
    api.close()
print("ok")
