#!/usr/bin/env python3
"""Before/after token benchmark for making a repository AI ready.

Runs the same intents (tasks) against a target repository in fresh, isolated headless
Claude Code sessions and records token usage, cost, turns and a rough correctness check.
Run it once on the repository before the make-ai-ready skill and once after, then compare.

  run       run every task N times against one git ref of the target repo
  prepare   run the make-ai-ready skill headless on a new branch of the target repo
  compare   print a Markdown before/after table from two result files
  example   copy the in-tree example project into a fresh git repository to benchmark on

Python 3.8+, stdlib only. Needs the `claude` CLI on PATH and credentials for it.
"""

import argparse
import concurrent.futures
import fnmatch
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

# Variables that tie a nested `claude` to the session that launched it. Dropping them makes
# each run a cold, independent session even when this script runs inside Claude Code.
PARENT_SESSION_ENV = (
    "CLAUDECODE",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_REMOTE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_PROJECTS_SESSION",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD",
    "CLAUDE_ADDITIONAL_DIRECTORIES",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH",
)

TASK_TOOLS = ["Read", "Grep", "Glob", "Edit", "Write"]

PREPARE_PROMPT = (
    "/ai-ready:make-ai-ready Make this repository AI ready. You are running "
    "non-interactively and nobody can answer questions or confirm anything: do every phase "
    "without stopping and treat your own component map as confirmed. Apply the fix and merge "
    "cleanups, but do not delete any file (list proposed deletions in the plan instead). Never "
    "deploy or touch remote resources. Write .ai-ready/components.md, the lean CLAUDE.md and "
    ".ai-ready/plan.md, and turn on the check with --init and --update-baseline. Do not set up "
    "CI. Finish with a three-line summary."
)

# `git worktree add/remove` on one repository from several threads races on its lock files.
WORKTREE_LOCK = threading.Lock()


def clean_env():
    return {k: v for k, v in os.environ.items() if k not in PARENT_SESSION_ENV}


def git(repo, *args, capture=True):
    out = subprocess.run(["git", "-C", repo] + list(args), check=True,
                         stdout=subprocess.PIPE if capture else None, universal_newlines=True)
    return out.stdout.strip() if capture else ""


def add_worktree(repo, dest, ref, branch=None):
    """Check `ref` out into its own worktree at `dest`, detached unless `branch` is given."""
    with WORKTREE_LOCK:
        if branch:
            git(repo, "worktree", "add", "-q", "-B", branch, dest, ref)
        else:
            git(repo, "worktree", "add", "-q", "--detach", dest, ref)


def remove_worktree(repo, dest):
    with WORKTREE_LOCK:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", dest],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(os.path.dirname(dest), ignore_errors=True)
        git(repo, "worktree", "prune")


def run_claude(args, cwd, prompt, timeout):
    cmd = [args.claude, "-p", "--output-format", "json", "--model", args.model,
           "--no-session-persistence", "--setting-sources", "project", "--strict-mcp-config"]
    if args.effort:
        cmd += ["--effort", args.effort]
    if args.max_budget_usd:
        cmd += ["--max-budget-usd", str(args.max_budget_usd)]
    for plugin in args.plugin_dir or []:
        cmd += ["--plugin-dir", os.path.abspath(plugin)]
    cmd += getattr(args, "extra_flags", [])
    start = time.time()
    proc = subprocess.run(cmd, cwd=cwd, input=prompt, env=clean_env(), timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)
    wall = time.time() - start
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        data = {"is_error": True, "result": (proc.stdout + proc.stderr)[-2000:]}
    return data, wall


def usage_record(data):
    """Token totals summed over every model the session used (main model + helpers)."""
    rec = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    for usage in (data.get("modelUsage") or {}).values():
        rec["input"] += usage.get("inputTokens", 0)
        rec["output"] += usage.get("outputTokens", 0)
        rec["cache_read"] += usage.get("cacheReadInputTokens", 0)
        rec["cache_creation"] += usage.get("cacheCreationInputTokens", 0)
    rec["total_tokens"] = sum(rec.values())
    rec["cost_usd"] = round(data.get("total_cost_usd") or 0.0, 5)
    rec["turns"] = data.get("num_turns") or 0
    return rec


def save_diff(workdir, path):
    """Write every change the session left (tracked and untracked) as one patch."""
    git(workdir, "add", "-A")
    diff = subprocess.run(["git", "-C", workdir, "diff", "--cached", "--binary", "HEAD"],
                          check=True, stdout=subprocess.PIPE, universal_newlines=True).stdout
    with open(path, "w") as fh:
        fh.write(diff)


def run_checks(args, task, workdir):
    """Run the tasks file's project `test` command and the task's hidden `check` script in the
    session's worktree. Returns a list of failures (empty when everything passed)."""
    failures, env = [], dict(clean_env(), PYTHONPATH=workdir)
    commands = []
    if task.get("check"):
        script = os.path.join(os.path.dirname(os.path.abspath(args.tasks)), task["check"])
        commands.append(("check", [sys.executable, script]))
    if args.project_test and (task.get("check") or task.get("expect_changed")):
        commands.append(("tests", args.project_test))
    for name, cmd in commands:
        try:
            out = subprocess.run(cmd, cwd=workdir, env=env, shell=isinstance(cmd, str),
                                 timeout=300, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True)
            if out.returncode != 0:
                failures.append("{}: {}".format(name, out.stdout.strip()[-300:]))
        except subprocess.TimeoutExpired:
            failures.append(name + ": timeout")
    return failures


def changed_files(workdir):
    status = subprocess.run(["git", "-C", workdir, "status", "--porcelain",
                             "--untracked-files=all"], check=True, stdout=subprocess.PIPE,
                            universal_newlines=True).stdout
    return sorted(line[3:] for line in status.splitlines() if line.strip())


def grade(task, result_text, changed):
    """Rough correctness: every `expect` substring is in the answer and every
    `expect_changed` glob matches a changed file. It only guards against a cheaper run
    that got the wrong answer; read the answers for anything finer."""
    text = (result_text or "").lower()
    missing = [s for s in task.get("expect", []) if s.lower() not in text]
    missing += ["changed:" + g for g in task.get("expect_changed", [])
                if not any(fnmatch.fnmatch(f, g) for f in changed)]
    return not missing, missing


def run_one(args, task, rep):
    workdir = os.path.join(tempfile.mkdtemp(prefix="ai-ready-bench-"), "repo")
    try:
        add_worktree(args.repo, workdir, args.ref)
        flags = ["--tools"] + (args.tools or TASK_TOOLS)
        if args.allowed_tools:
            flags += ["--allowedTools"] + args.allowed_tools
        flags += ["--permission-mode", "acceptEdits"]
        args_ = argparse.Namespace(**vars(args), extra_flags=flags)
        data, wall = run_claude(args_, workdir, args.prompt_prefix + task["prompt"],
                                args.timeout)
        changed = changed_files(workdir)
        passed, missing = grade(task, data.get("result"), changed)
        missing += run_checks(args, task, workdir)
        passed = not missing
        if args.save_diffs:
            os.makedirs(args.save_diffs, exist_ok=True)
            save_diff(workdir, os.path.join(args.save_diffs, "{}-{}-{}.patch".format(
                args.label, task["id"], rep)))
        rec = {"label": args.label, "ref": args.ref, "task": task["id"], "rep": rep,
               "model": args.model, "prompt_prefix": args.prompt_prefix,
               "is_error": bool(data.get("is_error")),
               "passed": passed, "missing": missing, "changed_files": changed,
               "duration_s": round(wall, 1),
               "subagents": (data.get("subagent_stats") or {}).get("spawned", 0)}
        rec.update(usage_record(data))
        rec["result"] = (data.get("result") or "")[:4000]
        return rec
    finally:
        remove_worktree(args.repo, workdir)


def cmd_run(args):
    with open(args.tasks) as fh:
        spec = json.load(fh)
    tasks, args.project_test = spec["tasks"], spec.get("test")
    if args.only:
        tasks = [t for t in tasks if t["id"] in args.only]
    args.repo = os.path.abspath(args.repo)
    args.ref = git(args.repo, "rev-parse", args.ref)
    jobs = [(t, r) for r in range(args.repeat) for t in tasks]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a") as out, \
            concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_one, args, t, r): (t["id"], r) for t, r in jobs}
        for fut in concurrent.futures.as_completed(futures):
            task_id, rep = futures[fut]
            try:
                rec = fut.result()
            except Exception as exc:  # keep the other runs going
                rec = {"label": args.label, "task": task_id, "rep": rep, "is_error": True,
                       "passed": False, "error": str(exc)}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print("{label} {task} #{rep}: {tokens} tokens, ${cost}, {turns} turns, {ok}".format(
                label=args.label, task=task_id, rep=rep, tokens=rec.get("total_tokens"),
                cost=rec.get("cost_usd"), turns=rec.get("turns"),
                ok="pass" if rec.get("passed") else "FAIL " + str(rec.get("missing") or
                                                                rec.get("error"))),
                file=sys.stderr)


def cmd_prepare(args):
    repo = os.path.abspath(args.repo)
    workdir = os.path.join(tempfile.mkdtemp(prefix="ai-ready-prepare-"), "repo")
    add_worktree(repo, workdir, args.base, branch=args.branch)
    try:
        prepare_in(args, repo, workdir)
    finally:
        remove_worktree(repo, workdir)


def prepare_in(args, repo, workdir):
    flags = ["--tools", "Skill", "Read", "Grep", "Glob", "Edit", "Write", "Bash",
             "--allowedTools", "Bash(python3 *)", "Bash(git log *)", "Bash(git status *)",
             "Bash(git diff *)", "Bash(ls *)", "Bash(wc *)", "Bash(mkdir *)",
             "--permission-mode", "acceptEdits"]
    for plugin in args.plugin_dir or []:
        flags += ["--add-dir", os.path.abspath(plugin)]
    args_ = argparse.Namespace(**vars(args), extra_flags=flags)
    data, wall = run_claude(args_, workdir, args.prompt or PREPARE_PROMPT, args.timeout)
    rec = {"label": "prepare", "branch": args.branch, "model": args.model,
           "is_error": bool(data.get("is_error")), "duration_s": round(wall, 1),
           "changed_files": changed_files(workdir)}
    rec.update(usage_record(data))
    rec["result"] = data.get("result")
    if args.out:
        with open(args.out, "a") as out:
            out.write(json.dumps(rec) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "result"}, indent=2))
    print(rec["result"])
    if rec["changed_files"] and not args.no_commit:
        git(workdir, "add", "-A")
        git(workdir, "-c", "user.name=ai-ready-bench", "-c", "user.email=bench@localhost",
            "commit", "-q", "-m", "Make the repository AI ready (make-ai-ready skill)")
        print("committed on", args.branch, file=sys.stderr)


def cmd_example(args):
    """Copy the example project into DEST and commit it, so `run` and `prepare` can use it."""
    if os.path.exists(args.dest):
        sys.exit("{} already exists".format(args.dest))
    shutil.copytree(args.src, args.dest,
                    ignore=shutil.ignore_patterns("__pycache__", "tasks.json"))
    git(args.dest, "init", "-q", "-b", "main")
    git(args.dest, "add", "-A")
    git(args.dest, "-c", "user.name=ai-ready-bench", "-c", "user.email=bench@localhost",
        "commit", "-q", "-m", "Example project")
    print(args.dest)


def load(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def median(values):
    return statistics.median(values) if values else 0


def pct(before, after):
    return "n/a" if not before else "{:+.0f}%".format((after - before) * 100.0 / before)


def cmd_compare(args):
    before, after = load(args.before), load(args.after)
    tasks = sorted({r["task"] for r in before} | {r["task"] for r in after})
    metrics = [("total_tokens", "tokens"), ("cost_usd", "cost $"), ("turns", "turns"),
               ("duration_s", "seconds")]
    lines = ["| task | " + " | ".join("{0} before | {0} after | change".format(m[1])
                                     for m in metrics) + " | passed before | passed after |",
             "|---" * (len(metrics) * 3 + 3) + "|"]
    totals = {m: [0.0, 0.0] for m, _ in metrics}
    for task in tasks:
        rb = [r for r in before if r["task"] == task and not r.get("error")]
        ra = [r for r in after if r["task"] == task and not r.get("error")]
        cells = []
        for key, _ in metrics:
            mb, ma = median([r[key] for r in rb]), median([r[key] for r in ra])
            totals[key][0] += mb
            totals[key][1] += ma
            fmt = "{:.3f}" if key == "cost_usd" else "{:,.0f}"
            cells += [fmt.format(mb), fmt.format(ma), pct(mb, ma)]
        passed = ["{}/{}".format(sum(r["passed"] for r in rs), len(rs)) for rs in (rb, ra)]
        lines.append("| {} | {} | {} |".format(task, " | ".join(cells), " | ".join(passed)))
    cells = []
    for key, _ in metrics:
        mb, ma = totals[key]
        fmt = "{:.3f}" if key == "cost_usd" else "{:,.0f}"
        cells += ["**" + fmt.format(mb) + "**", "**" + fmt.format(ma) + "**",
                  "**" + pct(mb, ma) + "**"]
    passed = ["{}/{}".format(sum(r.get("passed", False) for r in rs), len(rs))
              for rs in (before, after)]
    lines.append("| **all (sum of medians)** | {} | {} |".format(" | ".join(cells),
                                                                " | ".join(passed)))
    print("Medians per task over repeated runs; tokens include cache reads and writes.\n")
    print("\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    sub.required = True

    def common(p):
        p.add_argument("--repo", required=True, help="path to a git checkout of the target repo")
        p.add_argument("--model", default="sonnet")
        p.add_argument("--effort", default="", help="optional --effort level for claude")
        p.add_argument("--claude", default="claude", help="claude executable")
        p.add_argument("--plugin-dir", action="append", help="load a plugin in each session")
        p.add_argument("--max-budget-usd", type=float, default=0)
        p.add_argument("--timeout", type=int, default=1800, help="seconds per session")

    p = sub.add_parser("run", help="run the tasks against one ref")
    common(p)
    p.add_argument("--ref", default="HEAD")
    p.add_argument("--label", required=True, help="e.g. before / after")
    p.add_argument("--tasks", required=True, help="tasks JSON file")
    p.add_argument("--only", nargs="*", help="task ids to run")
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--jobs", type=int, default=3, help="sessions in parallel")
    p.add_argument("--out", required=True, help="JSONL file to append results to")
    p.add_argument("--prompt-prefix", default="",
                   help='prepended to every task prompt, e.g. "/ai-ready:build --go "')
    p.add_argument("--tools", nargs="+", help="tools the session may use (default: {})".format(
        " ".join(TASK_TOOLS)))
    p.add_argument("--allowed-tools", nargs="+",
                   help='permission rules passed to --allowedTools, e.g. "Bash(python3 *)"')
    p.add_argument("--save-diffs", default="",
                   help="directory to save each session's changes to, as a patch")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("prepare", help="run make-ai-ready headless on a new branch")
    common(p)
    p.add_argument("--base", default="HEAD")
    p.add_argument("--branch", default="ai-ready")
    p.add_argument("--prompt", default="")
    p.add_argument("--no-commit", action="store_true")
    p.add_argument("--out", default="", help="JSONL file to append the prepare run to")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("example", help="copy the example project into a new git repository")
    p.add_argument("dest")
    p.add_argument("--src", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "example", "tasklite"))
    p.set_defaults(func=cmd_example)

    p = sub.add_parser("compare", help="Markdown table from two result files")
    p.add_argument("before")
    p.add_argument("after")
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
