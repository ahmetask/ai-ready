from _common import cli, fail, tmp_store_file

f = tmp_store_file([{"id": 1, "title": "a", "done": True}, {"id": 2, "title": "b", "done": False},
                    {"id": 3, "title": "c", "done": False}])
out = cli(f, "stats")
if out.returncode != 0:
    fail("stats exited %d: %s" % (out.returncode, out.stderr[-300:]))
for want in ("total: 3", "open: 2", "done: 1"):
    if want not in out.stdout:
        fail("stats output %r lacks %r" % (out.stdout, want))
print("ok")
