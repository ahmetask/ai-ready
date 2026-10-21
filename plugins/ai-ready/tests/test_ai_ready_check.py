import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_ready_check as arc  # noqa: E402


def write(root: Path, path: str, text: str) -> None:
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class CheckerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        write(self.root, "README.md", "# Demo\nSee [setup](docs/setup.md).\n")
        write(self.root, "CLAUDE.md", "Entry point is `src/app.py`. Build with `npm run build`.\n")
        write(self.root, "docs/setup.md", "# Setup\n")
        write(self.root, "src/app.py", "x = 1\n")
        write(self.root, "package.json", json.dumps({"scripts": {"build": "tsc"}}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def issues(self, **kw):
        return arc.run_checks(self.root, arc.load_config(self.root), **kw)

    def checks(self, **kw):
        return sorted((i.check, i.file, i.key) for i in self.issues(**kw))

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = arc.main(["--root", str(self.root), *args])
        return code, out.getvalue()

    def run_hook(self, mode, payload, stream="stderr"):
        sys.stdin = io.StringIO(json.dumps(payload))
        buf = io.StringIO()
        redirect = redirect_stderr if stream == "stderr" else redirect_stdout
        try:
            with redirect(buf):
                code = arc.hook(mode)
        finally:
            sys.stdin = sys.__stdin__
        return code, buf.getvalue()

    def write_work(self, slug="add-retry"):
        write(self.root, f".ai-ready/work/{slug}.json", json.dumps({
            "goal": "Retry failed requests",
            "tasks": [
                {"id": "1", "title": "Add retry", "agent": "coder", "component": "api",
                 "files": ["src/app.py"], "verify": "true", "status": "todo"},
                {"id": "2", "title": "Document retry", "agent": "documenter", "after": ["1"],
                 "status": "todo"},
            ]}))

    def test_clean_repo_passes(self):
        self.assertEqual(self.checks(), [])
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("100/100", out)

    def test_missing_instructions_and_readme(self):
        (self.root / "CLAUDE.md").unlink()
        (self.root / "README.md").unlink()
        self.assertEqual(self.checks(), [("instructions-file", ".", "missing"),
                                         ("readme", ".", "missing")])

    def test_agents_md_counts(self):
        (self.root / "CLAUDE.md").rename(self.root / "AGENTS.md")
        self.assertEqual(self.checks(), [])

    def test_stale_references(self):
        write(self.root, "CLAUDE.md",
              "Old code in `lib/old.js` and `src/app.py:10`.\n"
              "Run `npm run deploy` then `make test`.\n"
              "Ignore `text/html`, `owner/repo` and [site](https://example.com).\n")
        write(self.root, "docs/setup.md", "See [gone](../gone.md) and [ok](../README.md#demo).\n")
        self.assertEqual(self.checks(), [
            ("broken-link", "docs/setup.md", "../gone.md"),
            ("missing-command", "CLAUDE.md", "make:test"),
            ("missing-command", "CLAUDE.md", "script:deploy"),
            ("missing-path-ref", "CLAUDE.md", "lib/old.js"),
        ])

    def test_abbreviated_and_tool_output_paths_are_not_stale(self):
        write(self.root, "CLAUDE.md", "Helpers: `app.py` in `src/`, see `src/app.py`; "
                                      "plan goes to `.ai-ready/plan.md`.\n")
        write(self.root, "docs/setup.md", "Nested: `docs/setup.md`, but `x/src/app.py` is gone.\n")
        self.assertEqual(self.checks(), [("missing-path-ref", "docs/setup.md", "x/src/app.py")])

    def test_changelogs_and_readme_case(self):
        (self.root / "README.md").rename(self.root / "Readme.md")
        write(self.root, "CHANGELOG.md", "Removed `lib/old.js`; use `make old`.\n")
        write(self.root, "History.md", "[old](gone.md)\n")
        self.assertEqual(self.checks(), [])

    def test_severity_is_lower_outside_instruction_files(self):
        write(self.root, "docs/setup.md", "Uses `lib/old.js`.\n")
        [issue] = self.issues()
        self.assertEqual(issue.severity, "warning")

    def test_fenced_blocks(self):
        write(self.root, "Makefile", "test:\n\techo ok\n")
        write(self.root, "docs/setup.md",
              "```sh\nmake test\nmake lint\nmake -C sub -j4 test V=1\n# [not a link](nowhere.md)\n```\n"
              "Make sure you `make` friends.\n")
        self.assertEqual(self.checks(), [("missing-command", "docs/setup.md", "make:lint")])

    def test_ignore_globs(self):
        write(self.root, "docs/generated/api.md", "[x](missing.md)\n")
        write(self.root, ".ai-ready/config.json", json.dumps({"ignore": ["docs/generated/**"]}))
        self.assertEqual(self.checks(), [])

    def test_baseline_only_fails_on_new_issues(self):
        write(self.root, "docs/setup.md", "[x](missing.md)\n")
        self.assertEqual(self.run_main()[0], 1)
        self.run_main("--update-baseline")
        self.assertEqual(self.run_main()[0], 0)
        write(self.root, "docs/setup.md", "[x](missing.md)\n[y](also-missing.md)\n")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("NEW error", out)
        self.assertEqual(self.run_main("--no-baseline")[0], 1)

    def test_min_score(self):
        write(self.root, "docs/setup.md", "`lib/a.js` `lib/b.js`\n")
        self.assertEqual(self.run_main()[0], 0)  # warnings only
        write(self.root, ".ai-ready/config.json", json.dumps({"min_score": 99}))
        self.assertEqual(self.run_main()[0], 1)

    def test_doc_drift(self):
        rule = {"paths": ["src/**"], "docs": ["docs/setup.md"]}
        write(self.root, ".ai-ready/config.json", json.dumps({"doc_watch": [rule]}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "config")
        self.assertEqual(self.checks(base="HEAD"), [])
        write(self.root, "src/app.py", "x = 2\n")
        self.assertEqual(self.checks(base="HEAD"), [("doc-drift", "docs/setup.md", "src/**")])
        write(self.root, "docs/setup.md", "# Setup\nUpdated.\n")
        self.assertEqual(self.checks(base="HEAD"), [])

    def test_doc_drift_against_base_branch(self):
        rule = {"paths": ["src/**"], "docs": ["docs/setup.md"]}
        write(self.root, ".ai-ready/config.json", json.dumps({"doc_watch": [rule]}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "config")
        git(self.root, "branch", "base")
        write(self.root, "src/app.py", "x = 2\n")
        git(self.root, "commit", "-qam", "change")
        self.assertEqual(self.checks(base="base"), [("doc-drift", "docs/setup.md", "src/**")])

    def test_instructions_budget_counts_lines_bytes_and_imports(self):
        write(self.root, "CLAUDE.md", "line\n" * 60)
        self.assertEqual(self.checks(), [])
        write(self.root, "CLAUDE.md", "line\n" * 61)
        self.assertEqual(self.checks(), [("instructions-size", "CLAUDE.md", "too-large")])
        write(self.root, "CLAUDE.md", "x" * 4001)
        self.assertEqual(self.checks(), [("instructions-size", "CLAUDE.md", "too-large")])
        write(self.root, "CLAUDE.md", "Rules: @docs/rules.md, mail me@example.com, `@docs/no.md`\n")
        write(self.root, "docs/rules.md", "rule\n" * 50 + "@../CLAUDE.md\n")
        self.assertEqual(self.checks(), [])
        write(self.root, "docs/no.md", "x\n" * 100)
        self.assertEqual(self.checks(), [])
        write(self.root, "docs/rules.md", "rule\n" * 60)
        [issue] = self.issues()
        self.assertEqual((issue.check, issue.severity), ("instructions-size", "error"))
        self.assertIn("61 lines", issue.message)

    def test_baselined_instructions_cannot_grow(self):
        write(self.root, "CLAUDE.md", "line\n" * 80)
        self.assertEqual(self.run_main()[0], 1)
        self.run_main("--update-baseline")
        sizes = json.loads((self.root / ".ai-ready/baseline.json").read_text())["instruction_sizes"]
        self.assertEqual(sizes, {"CLAUDE.md": {"lines": 80, "bytes": 400}})
        self.assertEqual(self.run_main()[0], 0)
        write(self.root, "CLAUDE.md", "line\n" * 70)
        self.assertEqual(self.run_main()[0], 0)  # shrinking is always fine
        write(self.root, "CLAUDE.md", "line\n" * 81)
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("instructions-growth", out)
        self.run_main("--update-baseline")
        accepted = json.loads((self.root / ".ai-ready/baseline.json").read_text())["accepted"]
        self.assertNotIn("instructions-growth|CLAUDE.md|grew", accepted)

    def test_post_edit_hook_checks_instructions_budget(self):
        write(self.root, ".ai-ready/config.json", "{}")
        payload = {"cwd": str(self.root),
                   "tool_input": {"file_path": str(self.root / "CLAUDE.md")}}
        self.assertEqual(self.run_hook("post-edit", payload)[0], 0)
        write(self.root, "CLAUDE.md", "line\n" * 61)
        code, err = self.run_hook("post-edit", payload)
        self.assertEqual(code, 2)
        self.assertIn("instructions-size", err)

    def make_monorepo(self):
        write(self.root, "pnpm-lock.yaml", "")
        write(self.root, "package.json", json.dumps({"workspaces": ["apps/*"],
                                                    "scripts": {"build": "turbo build"}}))
        write(self.root, "apps/web/package.json",
              json.dumps({"name": "web", "scripts": {"dev": "vite", "test": "vitest"}}))
        write(self.root, "apps/web/README.md", "# Web\n")
        write(self.root, "apps/web/examples/demo/package.json", "{}")
        write(self.root, "api/pyproject.toml", "[tool.pytest.ini_options]\n")
        write(self.root, "api/Makefile", "run:\n\tpython -m api\n")

    def test_discover(self):
        self.make_monorepo()
        found = {c["path"]: c for c in arc.discover(self.root, arc.load_config(self.root))}
        self.assertEqual(sorted(found), [".", "api", "apps/web"])
        self.assertTrue(found["."]["workspace_root"])
        self.assertEqual((found["apps/web"]["run"], found["apps/web"]["test"]),
                         ("cd apps/web && pnpm run dev", "cd apps/web && pnpm run test"))
        self.assertEqual(found["apps/web"]["docs"], ["apps/web/README.md"])
        self.assertEqual((found["api"]["run"], found["api"]["test"]),
                         ("cd api && make run", "cd api && python -m pytest"))

    def test_discover_single_project_keeps_same_stack_packages_inside(self):
        (self.root / "package.json").unlink()
        write(self.root, "pyproject.toml", "")
        write(self.root, "examples/app/pyproject.toml", "")
        write(self.root, "tools/gen/pyproject.toml", "")
        write(self.root, "web/package.json", json.dumps({"scripts": {"test": "jest"}}))
        paths = [c["path"] for c in arc.discover(self.root, arc.load_config(self.root))]
        self.assertEqual(paths, [".", "web"])

    def test_component_map_checks(self):
        self.make_monorepo()
        manifest = {"abstract": "", "components": [
            {"name": "web", "path": "apps/web", "responsibility": "UI", "docs": ["apps/web/README.md"],
             "run": "cd apps/web && pnpm run dev", "test": "cd apps/web && pnpm run e2e",
             "test_needs": ["network"]},
            {"name": "gone", "path": "svc/gone", "responsibility": "x"},
        ]}
        write(self.root, ".ai-ready/components.json", json.dumps(manifest))
        self.assertEqual(self.checks(), [
            ("component-command", ".ai-ready/components.json", "test:web:e2e"),
            ("component-map", ".ai-ready/components.json", "abstract"),
            ("component-path", ".ai-ready/components.json", "gone"),
            ("component-test-deps", ".ai-ready/components.json", "needs:web:network"),
            ("unmapped-component", ".ai-ready/components.json", "api"),
        ])
        manifest = {"abstract": "Demo.", "components": [
            {"name": "web", "path": "apps/web", "responsibility": "UI", "docs": ["apps/web/README.md"],
             "run": "cd apps/web && pnpm run dev", "test": "cd apps/web && pnpm run test"},
            {"name": "api", "path": "api", "responsibility": "API", "docs": ["api/CLAUDE.md"],
             "library": True, "test": "cd api && make test"},
        ]}
        write(self.root, ".ai-ready/components.json", json.dumps(manifest))
        self.assertEqual(self.checks(), [
            ("component-command", ".ai-ready/components.json", "test:api:make:test"),
            ("component-docs", ".ai-ready/components.json", "doc:api:api/CLAUDE.md"),
        ])

    def test_component_drift(self):
        self.make_monorepo()
        write(self.root, ".ai-ready/components.json", json.dumps({"abstract": "x", "components": [
            {"name": "web", "path": "apps/web", "responsibility": "UI",
             "docs": ["apps/web/README.md"], "run": "x", "test": "y"},
            {"name": "api", "path": "api", "responsibility": "API", "docs": ["README.md"],
             "run": "x", "test": "y"}]}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "map")
        self.assertEqual(self.checks(base="HEAD"), [])
        write(self.root, "apps/web/package.json", json.dumps({"name": "web", "scripts": {}}))
        write(self.root, "apps/web/src/main.ts", "")
        self.assertEqual(self.checks(base="HEAD"), [("component-drift", "apps/web/README.md", "web")])
        write(self.root, "apps/web/README.md", "# Web\nNo scripts now.\n")
        self.assertEqual(self.checks(base="HEAD"), [])

    def test_nested_claude_md_has_the_same_budget(self):
        write(self.root, "api/CLAUDE.md", "line\n" * 61)
        self.assertEqual(self.checks(), [("instructions-size", "api/CLAUDE.md", "too-large")])

    def test_explain_and_verify_tests(self):
        write(self.root, ".ai-ready/components.json", json.dumps({"abstract": "A demo app.", "components": [
            {"name": "ok", "path": "src", "responsibility": "works", "docs": ["README.md"],
             "test": "python3 -c 'print(1)'", "test_needs": ["docker"]},
            {"name": "bad", "path": "docs", "responsibility": "fails", "test": "exit 3"},
            {"name": "none", "path": "docs", "responsibility": "untested"}]}))
        code, out = self.run_main("--explain")
        self.assertEqual(code, 0)
        self.assertIn("A demo app.", out)
        self.assertIn("| ok | `src` | works | README.md | - | `python3 -c 'print(1)'` (needs docker) |", out)
        results = {r["component"]: r["status"] for r in arc.verify_tests(
            self.root, arc.load_config(self.root), None, 60)}
        self.assertEqual(results, {"ok": "passed", "bad": "failed", "none": "missing"})
        self.assertEqual(self.run_main("--verify-tests", "ok")[0], 0)
        self.assertEqual(self.run_main("--verify-tests")[0], 1)

    def test_hooks_are_inactive_without_config(self):
        write(self.root, "docs/setup.md", "[x](missing.md)\n")
        self.assertEqual(self.run_hook("stop", {"cwd": str(self.root)})[0], 0)

    def test_post_edit_hook(self):
        write(self.root, ".ai-ready/config.json", "{}")
        payload = {"cwd": str(self.root),
                   "tool_input": {"file_path": str(self.root / "docs/setup.md")}}
        self.assertEqual(self.run_hook("post-edit", payload)[0], 0)
        write(self.root, "docs/setup.md", "[x](missing.md)\n")
        code, err = self.run_hook("post-edit", payload)
        self.assertEqual(code, 2)
        self.assertIn("broken-link", err)
        code, _ = self.run_hook("post-edit", {"cwd": str(self.root),
                                              "tool_input": {"file_path": str(self.root / "src/app.py")}})
        self.assertEqual(code, 0)

    def test_stop_hook_blocks_once(self):
        write(self.root, ".ai-ready/config.json", "{}")
        self.assertEqual(self.run_hook("stop", {"cwd": str(self.root)})[0], 0)
        write(self.root, "CLAUDE.md", "See `src/removed.py`.\n")
        code, err = self.run_hook("stop", {"cwd": str(self.root / "src")})
        self.assertEqual(code, 2)
        self.assertIn("src/removed.py", err)
        self.assertEqual(self.run_hook("stop", {"cwd": str(self.root),
                                                "stop_hook_active": True})[0], 0)

    def test_work_tracker(self):
        self.assertIn("no tracked work", self.run_main("--work")[1])
        self.write_work()
        code, out = self.run_main("--work", "add-retry")
        self.assertEqual(code, 0)
        self.assertIn("(0/2 done, active)", out)
        self.assertIn("verify: true", out)
        self.assertTrue(out.rstrip().endswith("next: 1"))
        code, out = self.run_main("--work-set", "add-retry", "1", "doing")
        self.assertIn("task 1: doing (try 1)", out)
        code, out = self.run_main("--work-set", "add-retry", "1", "done", "--note", "added\n retry")
        self.assertIn("next: 2", out)
        data = json.loads((self.root / ".ai-ready/work/add-retry.json").read_text())
        self.assertEqual(data["tasks"][0]["note"], "added retry")
        self.run_main("--work-set", "add-retry", "2", "done")
        self.assertIn("(2/2 done, done)", self.run_main("--work")[1])
        self.assertEqual(self.run_main("--work-set", "add-retry", "9", "done")[0], 1)
        self.assertEqual(self.run_main("--work-set", "../x", "1", "done")[0], 1)
        self.assertEqual(self.run_main("--work-set", "add-retry", "1", "maybe")[0], 1)

    def test_work_attempt_limit_blocks(self):
        write(self.root, ".ai-ready/config.json", json.dumps({"factory": {"max_attempts": 2}}))
        self.write_work()
        for _ in range(2):
            self.run_main("--work-set", "add-retry", "1", "doing")
            self.run_main("--work-set", "add-retry", "1", "todo", "--note", "test fails")
        _, out = self.run_main("--work-set", "add-retry", "1", "doing")
        self.assertIn("task 1: blocked", out)
        self.assertIn("next: none (blocked: ask the user)", out)
        code, out = self.run_main("--work", "add-retry")
        self.assertIn("attempt limit (2) reached; last: test fails", out)

    def test_work_validation(self):
        write(self.root, ".ai-ready/work/bad.json", json.dumps({"tasks": [
            {"id": "1", "title": "x", "agent": "painter"}, {"id": "1", "after": ["7"]}]}))
        code, out = self.run_main("--work", "bad")
        self.assertEqual(code, 1)
        for problem in ("no goal", "duplicate id", "agent must be", "has no title", "unknown task 7"):
            self.assertIn(problem, out)

    def test_session_start_hook_restores_active_work(self):
        payload = {"cwd": str(self.root), "source": "compact"}
        self.write_work()
        self.assertEqual(self.run_hook("session-start", payload, "stdout")[1], "")  # no config
        write(self.root, ".ai-ready/config.json", "{}")
        code, out = self.run_hook("session-start", payload, "stdout")
        self.assertEqual(code, 0)
        self.assertIn("unfinished work add-retry: Retry failed requests", out)
        self.assertIn("/ai-ready:build add-retry", out)
        self.run_main("--work-set", "add-retry", "1", "done")
        self.run_main("--work-set", "add-retry", "2", "done")
        self.assertEqual(self.run_hook("session-start", payload, "stdout")[1], "")

    def test_prompt_hook_is_opt_in(self):
        long_prompt = {"cwd": str(self.root), "prompt": "word " * 50}
        write(self.root, ".ai-ready/config.json", "{}")
        self.assertEqual(self.run_hook("prompt", long_prompt, "stdout")[1], "")
        write(self.root, ".ai-ready/config.json", json.dumps({"factory": {"suggest": True}}))
        code, out = self.run_hook("prompt", long_prompt, "stdout")
        self.assertEqual(code, 0)
        self.assertIn("/ai-ready:build", out)
        for prompt in ("fix the typo", "/ai-ready:build " + "word " * 50):
            self.assertEqual(self.run_hook("prompt", {"cwd": str(self.root), "prompt": prompt},
                                           "stdout")[1], "")


if __name__ == "__main__":
    unittest.main()
