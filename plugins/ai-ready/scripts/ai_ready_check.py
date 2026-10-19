#!/usr/bin/env python3
"""ai-ready check: verify a repository stays "AI ready".

Deterministic, stdlib-only checks that an agent (or a human) can rely on:

  instructions-file   an agent instructions file (CLAUDE.md / AGENTS.md) exists
  instructions-size   agent instructions stay small enough to be read every session
  readme              a README exists
  broken-link         relative markdown links point at files that exist
  missing-path-ref    `inline/code/paths.ext` in docs point at files that exist
  missing-command     `npm run x` / `make x` in docs match a real script / target
  doc-drift           code covered by a doc_watch rule changed without its docs

Usage:
  ai_ready_check.py [--root DIR] [--format text|json] [--base REF]
                    [--update-baseline] [--no-baseline] [--init]
  ai_ready_check.py --hook post-edit|stop      (reads Claude Code hook JSON on stdin)

Configuration lives in .ai-ready/config.json; accepted pre-existing issues live in
.ai-ready/baseline.json so only *new* problems fail CI and hooks.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

CONFIG_DIR = ".ai-ready"
CONFIG_FILE = f"{CONFIG_DIR}/config.json"
BASELINE_FILE = f"{CONFIG_DIR}/baseline.json"

DEFAULT_CONFIG = {
    "instruction_files": ["CLAUDE.md", "AGENTS.md"],
    "max_instructions_bytes": 40000,
    "ignore": [],
    "fail_on": "error",
    "min_score": 0,
    "doc_watch": [],
}

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", ".venv", "venv",
    "env", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", ".next", ".nuxt",
    "coverage", "third_party", ".terraform", ".gradle", ".idea", ".vscode", CONFIG_DIR,
}
# Changelogs record history; old paths and commands in them are expected, not stale.
HISTORY_RE = re.compile(r"^(changelog|changes|history|news|releases?|release[-_]notes)(\.\w+)?$", re.I)
INSTRUCTION_NAMES = {"CLAUDE.md", "AGENTS.md", "copilot-instructions.md", ".cursorrules"}

LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
REF_LINK_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
SCRIPT_RE = re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+run\s+([A-Za-z0-9_:.\-]+)")
MAKE_RE = re.compile(r"(?:^|&&|;|\$\s*)\s*make\s+((?:[A-Za-z0-9_.\-/]+\s*)+)")
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.\-/ ]+?)\s*::?(?!=)")
PATH_TOKEN_RE = re.compile(r"^(?:\./|\.\./)*[A-Za-z0-9_@.\-]+(?:/[A-Za-z0-9_@.\-]+)*/?$")


@dataclass
class Issue:
    check: str
    severity: str  # "error" | "warning"
    file: str
    message: str
    key: str  # stable detail used for the baseline fingerprint (no line numbers)
    line: int = 0

    @property
    def fingerprint(self) -> str:
        return f"{self.check}|{self.file}|{self.key}"


# --------------------------------------------------------------------------- utils

def git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def find_root(start: Path) -> Path:
    top = git(start, "rev-parse", "--show-toplevel")
    return Path(top.strip()) if top else start


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def load_config(root: Path) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    user = load_json(root / CONFIG_FILE, {})
    if isinstance(user, dict):
        cfg.update(user)
    return cfg


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def ignored(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) or path.startswith(pat.rstrip("/") + "/")
               for pat in patterns)


def walk_files(root: Path, patterns: list[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not ignored(rel(root, Path(dirpath) / d), patterns)]
        for name in filenames:
            p = Path(dirpath) / name
            if not ignored(rel(root, p), patterns):
                yield p


def is_instruction_file(path: str, cfg: dict) -> bool:
    return Path(path).name in INSTRUCTION_NAMES or path in cfg["instruction_files"]


def split_markdown(text: str):
    """Yield (lineno, line, in_fence) for each line."""
    fence = None
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
                yield i, line, True
                continue
            if m.group(1) == fence:
                fence = None
                yield i, line, True
                continue
        yield i, line, fence is not None


def exists_from(root: Path, md: Path, target: str) -> bool:
    target = target.rstrip("/")
    if not target:
        return True
    if target.startswith("/"):
        return (root / target.lstrip("/")).exists()
    return (md.parent / target).exists() or (root / target).exists()


def looks_like_path(token: str) -> bool:
    token = token.strip().rstrip(".,;:")
    if " " in token or "/" not in token or "://" in token:
        return False
    if token.startswith(("/", "~", "-", "@", "$", "http")):
        return False
    if not PATH_TOKEN_RE.match(token):
        return False
    last = token.rstrip("/").rsplit("/", 1)[-1]
    # Require an extension or a trailing slash so `owner/repo`, `text/html` etc. are skipped.
    return token.endswith("/") or ("." in last.strip(".") and not last.endswith("."))


# ----------------------------------------------------------------- project facts

class Facts:
    def __init__(self, root: Path, cfg: dict):
        self.root = root
        self.cfg = cfg
        self._scripts: set[str] | None = None
        self._targets: set[str] | None = None
        self._paths: set[str] | None = None

    def path_suffix_exists(self, token: str) -> bool:
        """True if some file or directory in the repo ends with this path.

        Docs often name paths relative to context ("`references/criteria.md`" right after
        mentioning the skill directory); those are not stale, just abbreviated.
        """
        if self._paths is None:
            self._paths = set()
            for p in walk_files(self.root, []):
                parts = rel(self.root, p).split("/")
                for i in range(len(parts)):
                    self._paths.add("/".join(parts[i:]))
                    if i + 1 < len(parts):
                        self._paths.add("/".join(parts[i:-1]))
        return token.strip("./").rstrip("/") in self._paths

    def scripts(self) -> set[str]:
        if self._scripts is None:
            self._scripts = set()
            for p in walk_files(self.root, self.cfg["ignore"]):
                if p.name == "package.json":
                    data = load_json(p, {})
                    if isinstance(data, dict) and isinstance(data.get("scripts"), dict):
                        self._scripts.update(data["scripts"].keys())
        return self._scripts

    def targets(self) -> set[str]:
        if self._targets is None:
            self._targets = set()
            for p in walk_files(self.root, self.cfg["ignore"]):
                if p.name in ("Makefile", "makefile", "GNUmakefile") or p.suffix == ".mk":
                    try:
                        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                    except OSError:
                        continue
                    for line in lines:
                        if line.startswith(("\t", "#", " ")):
                            continue
                        m = MAKE_TARGET_RE.match(line)
                        if m:
                            self._targets.update(t for t in m.group(1).split() if t)
        return self._targets


# --------------------------------------------------------------------- the checks

def check_markdown(root: Path, md: Path, cfg: dict, facts: Facts) -> list[Issue]:
    path = rel(root, md)
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    instruction = is_instruction_file(path, cfg)
    issues: list[Issue] = []

    def add(check, severity, key, message, line):
        issues.append(Issue(check, severity, path, message, key, line))

    for lineno, line, in_fence in split_markdown(text):
        code_chunks = [line] if in_fence else [m.group(2) for m in INLINE_CODE_RE.finditer(line)]

        if not in_fence:
            prose = INLINE_CODE_RE.sub("", line)
            targets = [m.group(1) for m in LINK_RE.finditer(prose)]
            ref = REF_LINK_RE.match(prose)
            if ref:
                targets.append(ref.group(1))
            for target in targets:
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target) or target.startswith("#"):
                    continue  # URLs, mailto:, in-page anchors
                clean = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if clean and not exists_from(root, md, clean):
                    add("broken-link", "error", clean,
                        f"link to '{clean}' but that file does not exist", lineno)

            for chunk in code_chunks:
                token = re.sub(r":\d+(?::\d+)?$", "", chunk.strip())  # path.py:12
                if looks_like_path(token):
                    token = token.rstrip(".,;:")
                    if token.startswith(CONFIG_DIR + "/"):
                        continue  # ai-ready's own outputs (plan, baseline) may not exist yet
                    if not exists_from(root, md, token) and not facts.path_suffix_exists(token):
                        add("missing-path-ref", "error" if instruction else "warning", token,
                            f"mentions '{token}' but that path does not exist", lineno)

        for chunk in code_chunks:
            for m in SCRIPT_RE.finditer(chunk):
                name = m.group(1)
                if name not in facts.scripts():
                    add("missing-command", "error" if instruction else "warning",
                        f"script:{name}",
                        f"documents '{m.group(0)}' but no package.json defines script '{name}'",
                        lineno)
            for m in MAKE_RE.finditer(chunk.strip()):
                for target in m.group(1).split():
                    if target.startswith("-") or "=" in target:
                        continue
                    if target not in facts.targets():
                        add("missing-command", "error" if instruction else "warning",
                            f"make:{target}",
                            f"documents 'make {target}' but no Makefile defines '{target}'",
                            lineno)
    return issues


def check_repo_files(root: Path, cfg: dict) -> list[Issue]:
    issues: list[Issue] = []
    found = [f for f in cfg["instruction_files"] if (root / f).is_file()]
    if not found:
        names = " or ".join(cfg["instruction_files"])
        issues.append(Issue("instructions-file", "error", ".", f"no agent instructions file ({names})",
                            "missing"))
    for f in found:
        size = (root / f).stat().st_size
        if size == 0:
            issues.append(Issue("instructions-file", "error", f, "agent instructions file is empty", "empty"))
        elif size > cfg["max_instructions_bytes"]:
            issues.append(Issue(
                "instructions-size", "warning", f,
                f"{size} bytes; keep it under {cfg['max_instructions_bytes']} and link to deeper docs",
                "too-large"))
    if not any(p.is_file() and p.name.lower().split(".")[0] == "readme" for p in root.iterdir()):
        issues.append(Issue("readme", "error", ".", "no README", "missing"))
    return issues


def changed_files(root: Path, base: str | None) -> set[str] | None:
    files: set[str] = set()
    outputs = [git(root, "diff", "--name-only", "HEAD"),
               git(root, "ls-files", "--others", "--exclude-standard")]
    if base:
        outputs.append(git(root, "diff", "--name-only", f"{base}...HEAD"))
    if all(o is None for o in outputs):
        return None
    for out in outputs:
        files.update(l.strip() for l in (out or "").splitlines() if l.strip())
    return files


def check_doc_drift(root: Path, cfg: dict, base: str | None) -> list[Issue]:
    rules = cfg.get("doc_watch") or []
    if not rules:
        return []
    changed = changed_files(root, base)
    if not changed:
        return []
    issues = []
    for rule in rules:
        paths, docs = rule.get("paths", []), rule.get("docs", [])
        hits = sorted(f for f in changed if any(fnmatch.fnmatch(f, p) for p in paths))
        if not hits or any(fnmatch.fnmatch(f, d) for f in changed for d in docs):
            continue
        sample = ", ".join(hits[:3]) + (" ..." if len(hits) > 3 else "")
        msg = rule.get("message") or f"{sample} changed but {', '.join(docs)} was not updated"
        for doc in docs:
            issues.append(Issue("doc-drift", rule.get("severity", "error"), doc, msg,
                                "|".join(paths)))
    return issues


def run_checks(root: Path, cfg: dict, base: str | None = None,
               only: list[Path] | None = None) -> list[Issue]:
    facts = Facts(root, cfg)
    issues: list[Issue] = []
    if only is None:
        issues += check_repo_files(root, cfg)
        mds = [p for p in walk_files(root, cfg["ignore"])
               if (p.suffix.lower() in (".md", ".mdx") or p.name in INSTRUCTION_NAMES)
               and not HISTORY_RE.match(p.name)]
        issues += check_doc_drift(root, cfg, base)
    else:
        mds = only
    for md in sorted(mds):
        issues += check_markdown(root, md, cfg, facts)
    return issues


# ---------------------------------------------------------------------- reporting

def score(issues: list[Issue]) -> int:
    errors = sum(i.severity == "error" for i in issues)
    warnings = sum(i.severity == "warning" for i in issues)
    return max(0, 100 - 10 * errors - 2 * warnings)


def load_baseline(root: Path) -> set[str]:
    data = load_json(root / BASELINE_FILE, {})
    return set(data.get("accepted", [])) if isinstance(data, dict) else set()


def write_baseline(root: Path, issues: list[Issue]) -> None:
    (root / CONFIG_DIR).mkdir(exist_ok=True)
    data = {"comment": "Known issues accepted when ai-ready was adopted. Fix them and re-run "
                       "--update-baseline to shrink this list; never add to it by hand.",
            "accepted": sorted({i.fingerprint for i in issues})}
    (root / BASELINE_FILE).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def failing(issues: list[Issue], cfg: dict) -> list[Issue]:
    levels = {"error"} if cfg.get("fail_on", "error") == "error" else {"error", "warning"}
    return [i for i in issues if i.severity in levels]


def format_text(issues: list[Issue], new: list[Issue], s: int) -> str:
    lines = [f"AI readiness score: {s}/100  ({len(issues)} issue(s), {len(new)} new)"]
    newset = {id(i) for i in new}
    for i in sorted(issues, key=lambda i: (i.file, i.line, i.check)):
        loc = f"{i.file}:{i.line}" if i.line else i.file
        tag = "NEW " if id(i) in newset else ""
        lines.append(f"  {tag}{i.severity:7} {i.check:18} {loc}  {i.message}")
    return "\n".join(lines)


# -------------------------------------------------------------------------- hooks

def hook(mode: str) -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    if os.environ.get("AI_READY_DISABLE") == "1":
        return 0
    root = find_root(Path(payload.get("cwd") or os.getcwd()))
    if not (root / CONFIG_FILE).is_file():
        return 0  # repository has not opted in
    cfg = load_config(root)
    baseline = load_baseline(root)

    if mode == "stop":
        if payload.get("stop_hook_active"):
            return 0  # we already blocked once this turn; don't loop
        issues = run_checks(root, cfg, base="HEAD")
    else:
        file_path = (payload.get("tool_input") or {}).get("file_path")
        if not file_path:
            return 0
        p = Path(file_path)
        p = p if p.is_absolute() else root / p
        try:
            r = rel(root, p.resolve())
        except ValueError:
            return 0
        if (not p.is_file() or r.startswith(CONFIG_DIR + "/") or ignored(r, cfg["ignore"])
                or not (p.suffix.lower() in (".md", ".mdx") or p.name in INSTRUCTION_NAMES)):
            return 0
        issues = run_checks(root, cfg, only=[p.resolve()])

    new = [i for i in failing(issues, cfg) if i.fingerprint not in baseline]
    if not new:
        return 0
    where = "these changes" if mode == "stop" else rel(root, p.resolve())
    msg = [f"ai-ready: {where} would leave the repository less AI ready. Fix these before finishing "
           "(or, if a finding is wrong, add an 'ignore' glob in .ai-ready/config.json):"]
    for i in new:
        loc = f"{i.file}:{i.line}" if i.line else i.file
        msg.append(f"  - [{i.check}] {loc}: {i.message}")
    print("\n".join(msg), file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check that a repository is (and stays) AI ready.")
    ap.add_argument("--root", default=".", help="repository root (default: git toplevel of cwd)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--base", help="git ref to diff against for doc-drift (e.g. origin/main)")
    ap.add_argument("--no-baseline", action="store_true", help="treat every issue as new")
    ap.add_argument("--update-baseline", action="store_true",
                    help="accept all current issues into .ai-ready/baseline.json")
    ap.add_argument("--init", action="store_true", help="write a default .ai-ready/config.json")
    ap.add_argument("--hook", choices=["post-edit", "stop"], help="run as a Claude Code hook")
    args = ap.parse_args(argv)

    if args.hook:
        return hook(args.hook)

    root = find_root(Path(args.root).resolve())
    if args.init:
        target = root / CONFIG_FILE
        if target.exists():
            print(f"{CONFIG_FILE} already exists")
        else:
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {CONFIG_FILE}")
        return 0

    cfg = load_config(root)
    issues = run_checks(root, cfg, base=args.base)
    if args.update_baseline:
        write_baseline(root, issues)
        print(f"baseline updated: {len(issues)} accepted issue(s) in {BASELINE_FILE}")
        return 0

    baseline = set() if args.no_baseline else load_baseline(root)
    new = [i for i in issues if i.fingerprint not in baseline]
    s = score(issues)
    fail = bool(failing(new, cfg)) or s < int(cfg.get("min_score", 0))

    if args.format == "json":
        print(json.dumps({"root": str(root), "score": s, "passed": not fail,
                          "issues": [dict(asdict(i), new=i in new) for i in issues]}, indent=2))
    else:
        print(format_text(issues, new, s))
        if s < int(cfg.get("min_score", 0)):
            print(f"score {s} is below min_score {cfg['min_score']}")
        print("FAILED" if fail else "OK")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
