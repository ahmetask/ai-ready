from _common import Api, cli, fail, tmp_store_file

# An old file without due dates must still load and list.
f = tmp_store_file([{"id": 1, "title": "old", "done": False}])
out = cli(f, "list")
if out.returncode != 0 or "old" not in out.stdout:
    fail("old tasks.json no longer lists: %r %r" % (out.stdout, out.stderr[-300:]))

for args in (("add", "past due", "--due", "2001-01-31"), ("add", "future", "--due", "2999-01-31"),
             ("add", "done past", "--due", "2001-02-01"), ("done", "4")):
    out = cli(f, *args)
    if out.returncode != 0:
        fail("%s exited %d: %s" % (" ".join(args), out.returncode, out.stderr[-300:]))

out = cli(f, "list", "--overdue")
if out.returncode != 0:
    fail("list --overdue exited %d: %s" % (out.returncode, out.stderr[-300:]))
if "past due" not in out.stdout:
    fail("list --overdue misses the overdue task: %r" % out.stdout)
for absent in ("future", "done past", "old"):
    if absent in out.stdout:
        fail("list --overdue shows %r: %r" % (absent, out.stdout))

api = Api(f)
try:
    status, task = api.request("POST", "/tasks", {"title": "api past", "due": "2002-03-04"})
    if status not in (200, 201) or not task or task.get("due") != "2002-03-04":
        fail("POST /tasks with due returned %s %r" % (status, task))
    status, tasks = api.request("GET", "/tasks?overdue=1")
    titles = sorted(t["title"] for t in tasks or [])
    if status != 200 or titles != ["api past", "past due"]:
        fail("GET /tasks?overdue=1 returned %s %r" % (status, titles))
    status, tasks = api.request("GET", "/tasks")
    if status != 200 or len(tasks or []) != 5:
        fail("GET /tasks returned %s with %d tasks, want 5" % (status, len(tasks or [])))
finally:
    api.close()
print("ok")
