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

    def run_hook(self, mode, payload):
        sys.stdin = io.StringIO(json.dumps(payload))
        err = io.StringIO()
        try:
            with redirect_stderr(err):
                code = arc.hook(mode)
        finally:
            sys.stdin = sys.__stdin__
        return code, err.getvalue()

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
              "```sh\nmake test\nmake lint\n# [not a link](nowhere.md)\n```\n"
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


if __name__ == "__main__":
    unittest.main()
