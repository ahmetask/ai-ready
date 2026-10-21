#!/usr/bin/env python3
"""ai-ready check: verify a repository stays "AI ready".

Deterministic, stdlib-only checks that an agent (or a human) can rely on:

  instructions-file   an agent instructions file (CLAUDE.md / AGENTS.md) exists
  instructions-size   agent instructions (with their @imports) stay within the line and byte
                      budget: they are re-read on every turn of every session
  instructions-growth an over-budget instructions file grew past its size in the baseline
  readme              a README exists
  broken-link         relative markdown links point at files that exist
  missing-path-ref    `inline/code/paths.ext` in docs point at files that exist
  missing-command     `npm run x` / `make x` in docs match a real script / target
  doc-drift           code covered by a doc_watch rule changed without its docs

With a component map (.ai-ready/components.md, or the older components.json: abstract, and per
component its path,
responsibility, docs, run and test commands, and what its tests need):

  component-path      a mapped component's path exists
  component-map       the abstract and each responsibility are filled in
  component-docs      each component has docs, and they exist
  component-command   run/test commands exist and use real scripts / make targets
  component-test-deps tests that need network, a database, docker, secrets... (warning)
  unmapped-component  a directory with its own build file is missing from the map
  component-drift     a component's build/setup files changed but its docs did not

Usage:
  ai_ready_check.py [--root DIR] [--format text|json] [--base REF]
                    [--update-baseline] [--no-baseline] [--init]
  ai_ready_check.py --discover | --explain | --verify-tests [COMPONENT] [--timeout S]
  ai_ready_check.py --convert-map           (components.json -> components.md)
  ai_ready_check.py --work [SLUG] | --work-set SLUG TASK STATUS [--note TEXT]
  ai_ready_check.py --hook post-edit|stop|prompt|session-start   (hook JSON on stdin)

The factory (/ai-ready:plan and /ai-ready:build) tracks planned work in
.ai-ready/work/<slug>.md; --work prints it compactly and --work-set updates one task, so
agents never re-read or rewrite the whole tracker. Everything the plugin writes for people to
read (component map, trackers, plan) is Markdown; only config and baseline stay JSON.

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
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

CONFIG_DIR = ".ai-ready"
CONFIG_FILE = f"{CONFIG_DIR}/config.json"
BASELINE_FILE = f"{CONFIG_DIR}/baseline.json"
COMPONENTS_FILE = f"{CONFIG_DIR}/components.md"
COMPONENTS_JSON = f"{CONFIG_DIR}/components.json"  # the older format, still read
WORK_DIR = f"{CONFIG_DIR}/work"

DEFAULT_CONFIG = {
    "instruction_files": ["CLAUDE.md", "AGENTS.md"],
    "max_instructions_lines": 60,
    "max_instructions_bytes": 4000,
    "ignore": [],
    "fail_on": "error",
    "min_score": 0,
    "doc_watch": [],
}
# The optional "factory" object in config.json; merged key by key over these defaults.
DEFAULT_FACTORY = {"max_attempts": 3, "suggest": False, "suggest_min_words": 40}
TASK_STATUSES = ("todo", "doing", "done", "blocked")
AGENTS = ("coder", "tester", "documenter")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", ".venv", "venv",
    "env", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", ".next", ".nuxt",
    "coverage", "third_party", ".terraform", ".gradle", ".idea", ".vscode", CONFIG_DIR,
}
# Changelogs record history; old paths and commands in them are expected, not stale.
HISTORY_RE = re.compile(r"^(changelog|changes|history|news|releases?|release[-_]notes)(\.\w+)?$", re.I)
INSTRUCTION_NAMES = {"CLAUDE.md", "AGENTS.md", "copilot-instructions.md", ".cursorrules"}

IMPORT_RE = re.compile(r"(?:^|\s)@((?:\.{1,2}/)?[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*)")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
REF_LINK_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
SCRIPT_RE = re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+run\s+([A-Za-z0-9_:.\-]+)")
MAKE_RE = re.compile(r"(?:^|&&|;|\$\s*)\s*make\s+((?:[A-Za-z0-9_.\-/=]+\s*)+)")
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


def with_imports(path: Path, seen: set | None = None, depth: int = 0) -> list[Path]:
    """`path` plus the files it pulls in with `@file` imports, as Claude Code loads them."""
    seen = set() if seen is None else seen
    try:
        resolved = path.resolve()
        path.read_bytes()
    except OSError:
        return []
    if resolved in seen:
        return []
    seen.add(resolved)
    files = [path]
    if depth >= 5:
        return files
    text = path.read_text(encoding="utf-8", errors="replace")
    for _, line, in_fence in split_markdown(text):
        if in_fence:
            continue
        for m in IMPORT_RE.finditer(INLINE_CODE_RE.sub("", line)):
            p = path.parent / m.group(1).rstrip(".,;:")
            if p.is_file():
                files += with_imports(p, seen, depth + 1)
    return files


def footprint(path: Path) -> tuple[int, int]:
    """(bytes, lines) an instructions file costs per turn, imports included."""
    size = lines = 0
    for p in with_imports(path):
        data = p.read_bytes()
        size += len(data)
        lines += data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    return size, lines


def exists_from(root: Path, md: Path, target: str) -> bool:
    target = target.rstrip("/")
    if not target:
        return True
    if target.startswith("/"):
        return (root / target.lstrip("/")).exists()
    return (md.parent / target).exists() or (root / target).exists()


def make_goals(args: str) -> list[str]:
    """Targets named in `make` arguments, skipping options, their values and VAR=x."""
    goals, skip = [], False
    for tok in args.split():
        if skip:
            skip = False
        elif tok in ("-C", "-f", "-I", "-o", "-W", "--directory", "--file"):
            skip = True
        elif not tok.startswith("-") and "=" not in tok:
            goals.append(tok)
    return goals


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
                for target in make_goals(m.group(1)):
                    if target not in facts.targets():
                        add("missing-command", "error" if instruction else "warning",
                            f"make:{target}",
                            f"documents 'make {target}' but no Makefile defines '{target}'",
                            lineno)
    return issues


def check_instructions(root: Path, cfg: dict, f: str) -> list[Issue]:
    """Keep an instructions file lean: everything in it is paid for on every turn."""
    size, lines = footprint(root / f)
    if size == 0:
        return [Issue("instructions-file", "error", f, "agent instructions file is empty", "empty")]
    max_lines, max_bytes = int(cfg["max_instructions_lines"]), int(cfg["max_instructions_bytes"])
    if lines <= max_lines and size <= max_bytes:
        return []
    issues = [Issue(
        "instructions-size", "error", f,
        f"{lines} lines / {size} bytes with imports (budget {max_lines} lines / {max_bytes} bytes), "
        "re-read on every turn; keep commands, guardrails and gotchas here and move the rest to "
        "docs linked from it", "too-large")]
    recorded = load_sizes(root).get(f)
    if recorded and (lines > recorded.get("lines", lines) or size > recorded.get("bytes", size)):
        issues.append(Issue(
            "instructions-growth", "error", f,
            f"grew from {recorded.get('lines')} lines / {recorded.get('bytes')} bytes in the baseline "
            f"to {lines} / {size} while over budget; trim it instead of adding to it", "grew"))
    return issues


def instruction_paths(root: Path, cfg: dict) -> list[str]:
    """Root instruction files plus nested CLAUDE.md / AGENTS.md (loaded when working there)."""
    paths = [f for f in cfg["instruction_files"] if (root / f).is_file()]
    for p in walk_files(root, cfg["ignore"]):
        r = rel(root, p)
        if p.name in ("CLAUDE.md", "AGENTS.md") and r not in paths:
            paths.append(r)
    return paths


def check_repo_files(root: Path, cfg: dict) -> list[Issue]:
    issues: list[Issue] = []
    found = [f for f in cfg["instruction_files"] if (root / f).is_file()]
    if not found:
        names = " or ".join(cfg["instruction_files"])
        issues.append(Issue("instructions-file", "error", ".", f"no agent instructions file ({names})",
                            "missing"))
    for f in instruction_paths(root, cfg):
        issues += check_instructions(root, cfg, f)
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
        issues += check_components(root, cfg, base)
    else:
        mds = only
    for md in sorted(mds):
        issues += check_markdown(root, md, cfg, facts)
    return issues


# ------------------------------------------------------------------ components

BUILD_FILES = {
    "package.json": "node", "pyproject.toml": "python", "setup.py": "python", "go.mod": "go",
    "Cargo.toml": "rust", "pom.xml": "java", "build.gradle": "java", "build.gradle.kts": "java",
    "Gemfile": "ruby", "composer.json": "php", "mix.exs": "elixir", "Dockerfile": "docker",
}
# Files that decide how a component is built, run or tested; changing one may stale its docs.
SETUP_FILES = set(BUILD_FILES) | {"Makefile", "pnpm-workspace.yaml", "requirements.txt",
                                  "docker-compose.yml", "compose.yaml", "tox.ini", "setup.cfg"}
DOC_NAMES = ("CLAUDE.md", "AGENTS.md", "README.md", "readme.md", "Readme.md")
TEST_NEEDS = {"network", "database", "docker", "secrets", "cloud", "service"}
NPM_DEFAULT_TEST = "no test specified"
# Build files under these directories belong to samples or test data, not separate components.
NOT_COMPONENT_DIRS = {"examples", "example", "samples", "sample", "fixtures", "testdata",
                      "test", "tests", "docs", "doc", "benchmarks", "e2e"}


# Markdown records: the component map and work trackers are Markdown so people can read them.
# A record is "# Title", then "- **Field:** value" lines, then "## Section" blocks of the same.
FIELD_RE = re.compile(r"^\s*[-*]\s+(?:\*\*|__)?([A-Za-z][A-Za-z ]*?)(?::(?:\*\*|__)|(?:\*\*|__)?:)\s*(.*)$")
NONE_VALUES = {"", "-", "none", "n/a", "no"}


def md_value(v: str) -> str:
    v = v.strip()
    if len(v) > 1 and v[0] == v[-1] == "`" and "`" not in v[1:-1]:
        return v[1:-1]
    return v


def md_list(v) -> list[str]:
    if isinstance(v, list):
        return v
    if str(v).strip().lower() in NONE_VALUES:
        return []
    return [md_value(x) for x in str(v).split(",") if x.strip()]


def parse_record(text: str) -> tuple[str, dict, list[tuple[str, dict]]]:
    """Return (title, top fields and prose, [(section heading, fields and prose)])."""
    title, top, sections = "", {"_text": []}, []
    cur = top
    for line in text.splitlines():
        if line.startswith("# ") and not title and not sections:
            title = line[2:].strip()
        elif line.startswith("## "):
            cur = {"_text": []}
            sections.append((line[3:].strip(), cur))
        else:
            m = FIELD_RE.match(line)
            if m:
                cur[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip()
            elif line.strip():
                cur["_text"].append(line.strip())
    return title, top, sections


def md_field(name: str, value) -> str:
    if isinstance(value, list):
        value = ", ".join(f"`{v}`" for v in value) if value else "none"
    return f"- **{name}:** {value}"


def parse_components_md(text: str) -> dict:
    _, top, sections = parse_record(text)
    comps = []
    for name, f in sections:
        c = {"name": name, "path": md_value(f.get("path", "")),
             "responsibility": f.get("responsibility") or " ".join(f["_text"]),
             "docs": md_list(f.get("docs", "")), "test_needs": md_list(f.get("test_needs", ""))}
        for key in ("run", "test"):
            if md_value(f.get(key, "")).lower() not in NONE_VALUES:
                c[key] = md_value(f[key])
        if f.get("library", "").strip().lower() in ("yes", "true"):
            c["library"] = True
        comps.append(c)
    return {"abstract": top.get("abstract") or " ".join(top["_text"]), "components": comps}


def render_components_md(manifest: dict, title: str = "Components") -> str:
    out = [f"# {title}", "", str(manifest.get("abstract", "")).strip(), ""]
    for c in manifest.get("components") or []:
        out += [f"## {c.get('name') or c.get('path')}", "",
                md_field("Path", f"`{c.get('path', '')}`"),
                md_field("Responsibility", c.get("responsibility", "")),
                md_field("Docs", list(c.get("docs") or []))]
        for key in ("run", "test"):
            out.append(md_field(key.capitalize(), f"`{c[key]}`" if c.get(key) else "none"))
        out.append(md_field("Test needs", ", ".join(c.get("test_needs") or []) or "none"))
        if c.get("library"):
            out.append(md_field("Library", "yes"))
        out.append("")
    return "\n".join(out)


def components_file(root: Path) -> str:
    """The map in use: components.md, else an older components.json."""
    if not (root / COMPONENTS_FILE).is_file() and (root / COMPONENTS_JSON).is_file():
        return COMPONENTS_JSON
    return COMPONENTS_FILE


def load_components(root: Path) -> dict | None:
    if (root / COMPONENTS_FILE).is_file():
        return parse_components_md(_read(root / COMPONENTS_FILE))
    data = load_json(root / COMPONENTS_JSON, None)
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return None
    return data


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _package_manager(root: Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"),
                     ("bun.lock", "bun")):
        if (root / lock).is_file():
            return pm
    return "npm"


def _make_targets(d: Path) -> set[str]:
    try:
        lines = (d / "Makefile").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set()
    out: set[str] = set()
    for line in lines:
        m = None if line.startswith(("\t", "#", " ")) else MAKE_TARGET_RE.match(line)
        if m:
            out.update(m.group(1).split())
    return out


def _commands(root: Path, d: Path, kinds: list[str]) -> tuple[str | None, str | None]:
    """Best guess at (run, test) for a component directory."""
    prefix = "" if d == root else f"cd {rel(root, d)} && "
    run = test = None
    targets = _make_targets(d)
    for t in ("dev", "run", "start", "serve"):
        if t in targets:
            run = f"{prefix}make {t}"
            break
    if "test" in targets:
        test = f"{prefix}make test"
    if "node" in kinds:
        pm = _package_manager(root)
        scripts = (load_json(d / "package.json", {}) or {}).get("scripts") or {}
        if not run:
            run = next((f"{prefix}{pm} run {s}" for s in ("dev", "start", "serve") if s in scripts), None)
        if not test and "test" in scripts and NPM_DEFAULT_TEST not in str(scripts["test"]):
            test = f"{prefix}{pm} run test"
    if "python" in kinds and not test:
        text = ""
        for f in ("pyproject.toml", "setup.cfg", "tox.ini"):
            try:
                text += (d / f).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        uses_pytest = "pytest" in text or (d / "conftest.py").is_file()
        test = f"{prefix}{'python -m pytest' if uses_pytest else 'python -m unittest'}"
    if "go" in kinds:
        test = test or f"{prefix}go test ./..."
        if not run and (d / "main.go").is_file():
            run = f"{prefix}go run ."
    if "rust" in kinds:
        test, run = test or f"{prefix}cargo test", run or f"{prefix}cargo run"
    if "java" in kinds and not test:
        if (d / "pom.xml").is_file():
            test = f"{prefix}mvn test"
        else:
            test = f"{prefix}{'./gradlew' if (d / 'gradlew').is_file() else 'gradle'} test"
    if "ruby" in kinds and not test:
        test = f"{prefix}bundle exec {'rspec' if (d / 'spec').is_dir() else 'rake test'}"
    return run, test


def discover(root: Path, cfg: dict) -> list[dict]:
    """Candidate components: directories holding a build file, outermost first."""
    found: dict[Path, list[str]] = {}
    for p in walk_files(root, cfg["ignore"]):
        kind = BUILD_FILES.get(p.name)
        if kind:
            found.setdefault(p.parent, []).append(kind)
    dirs = [d for d in sorted(found, key=lambda d: (len(d.parts), str(d)))
            if not NOT_COMPONENT_DIRS & set(Path(rel(root, d)).parts)]
    root_kinds = set(found.get(root, []))
    workspace = root in found and len(dirs) > 1 and (
        (root / "pnpm-workspace.yaml").is_file() or (root / "go.work").is_file()
        or "workspaces" in (load_json(root / "package.json", {}) or {})
        or "[workspace]" in _read(root / "Cargo.toml") or root_kinds <= {"docker"})
    out = []
    for d in dirs:
        kinds = sorted(set(found[d]))
        if d != root:
            # A package inside another component is part of it, unless the root is a workspace
            # or the package is a different stack (a node frontend in a python repo).
            parents = [o for o in dirs if o in d.parents and (o != root or not workspace)]
            if any(o != root or set(kinds) <= root_kinds for o in parents):
                continue
        workspace_root = d == root and workspace
        pkg = load_json(d / "package.json", {}) or {}
        run, test = _commands(root, d, kinds)
        out.append({
            "name": pkg.get("name") if isinstance(pkg.get("name"), str) else (d.name or root.name),
            "path": "." if d == root else rel(root, d),
            "kinds": kinds,
            "workspace_root": bool(workspace_root),
            "docs": [rel(root, d / n) for n in DOC_NAMES if (d / n).is_file()],
            "run": run,
            "test": test,
        })
    return out


def _covered(path: str, components: list[dict]) -> bool:
    for c in components:
        cp = str(c.get("path", "")).strip("/") or "."
        if cp == "." or path == cp or path.startswith(cp + "/"):
            return True
    return False


def check_components(root: Path, cfg: dict, base: str | None) -> list[Issue]:
    manifest = load_components(root)
    if manifest is None:
        return []
    issues: list[Issue] = []
    map_file = components_file(root)
    comps = [c for c in manifest["components"] if isinstance(c, dict)]
    if not str(manifest.get("abstract", "")).strip():
        issues.append(Issue("component-map", "warning", map_file,
                            "no abstract: say in a few lines what the project is", "abstract"))
    facts = Facts(root, cfg)
    for c in comps:
        name, path = str(c.get("name") or c.get("path")), str(c.get("path", ""))
        if not path or not (root / path).exists():
            issues.append(Issue("component-path", "error", map_file,
                                f"component '{name}' points at '{path}', which does not exist", name))
            continue
        if not str(c.get("responsibility", "")).strip():
            issues.append(Issue("component-map", "warning", map_file,
                                f"component '{name}' has no responsibility", f"responsibility:{name}"))
        docs = [str(d) for d in c.get("docs") or []]
        if not docs:
            issues.append(Issue("component-docs", "warning", map_file,
                                f"component '{name}' has no docs", f"docs:{name}"))
        for d in docs:
            if not (root / d).is_file():
                issues.append(Issue("component-docs", "error", map_file,
                                    f"component '{name}' lists doc '{d}', which does not exist",
                                    f"doc:{name}:{d}"))
        for field in ("run", "test"):
            cmd = c.get(field)
            if not cmd:
                if field == "test" or not c.get("library"):
                    issues.append(Issue("component-command", "warning", map_file,
                                        f"component '{name}' has no {field} command",
                                        f"{field}:{name}"))
                continue
            for m in SCRIPT_RE.finditer(str(cmd)):
                if m.group(1) not in facts.scripts():
                    issues.append(Issue("component-command", "error", map_file,
                                        f"component '{name}' {field} command uses '{m.group(0)}', "
                                        "but no package.json defines it", f"{field}:{name}:{m.group(1)}"))
            for m in MAKE_RE.finditer(str(cmd)):
                for target in make_goals(m.group(1)):
                    if target not in facts.targets():
                        issues.append(Issue("component-command", "error", map_file,
                                            f"component '{name}' {field} command uses 'make {target}', "
                                            "but no Makefile defines it", f"{field}:{name}:make:{target}"))
        needs = sorted(set(map(str, c.get("test_needs") or [])))
        if needs:
            issues.append(Issue("component-test-deps", "warning", map_file,
                                f"component '{name}' tests need {', '.join(needs)}; make them run "
                                "offline with fakes or local stand-ins", f"needs:{name}:{','.join(needs)}"))
    for cand in discover(root, cfg):
        if cand["workspace_root"] or _covered(cand["path"], comps):
            continue
        issues.append(Issue("unmapped-component", "warning", map_file,
                            f"'{cand['path']}' looks like a component ({', '.join(cand['kinds'])}) "
                            "but is not in the component map", cand["path"]))
    changed = changed_files(root, base) or set()
    for c in comps:
        cp = str(c.get("path", "")).strip("/")
        if not cp:
            continue
        inside = [f for f in changed if cp == "." or f.startswith(cp + "/")]
        setup = sorted(f for f in inside if Path(f).name in SETUP_FILES)
        docs = [str(d) for d in c.get("docs") or [] if (root / str(d)).is_file()]
        if setup and docs and not any(d in changed for d in docs):
            issues.append(Issue("component-drift", "warning", docs[0],
                                f"{', '.join(setup[:3])} changed but the docs of component "
                                f"'{c.get('name') or cp}' did not; check its run and test commands",
                                str(c.get("name") or cp)))
    return issues


def explain(root: Path, cfg: dict) -> str:
    manifest = load_components(root)
    comps = manifest["components"] if manifest else discover(root, cfg)
    lines = [f"# {root.name}", ""]
    if manifest:
        lines += [str(manifest.get("abstract", "")).strip() or "_No abstract yet._", ""]
    else:
        lines += [f"_No {COMPONENTS_FILE} yet; these components were detected from build files. "
                  "Run the make-ai-ready skill to write the map._", ""]
    lines += ["| Component | Path | Responsibility | Docs | Run | Test |", "|---|---|---|---|---|---|"]
    for c in comps:
        if c.get("workspace_root"):
            continue
        cell = lambda v: f"`{v}`" if v else "-"  # noqa: E731
        lines.append("| {} | {} | {} | {} | {} | {}{} |".format(
            c.get("name", ""), cell(c.get("path")), c.get("responsibility") or "-",
            ", ".join(c.get("docs") or []) or "-", cell(c.get("run")), cell(c.get("test")),
            f" (needs {', '.join(c['test_needs'])})" if c.get("test_needs") else ""))
    return "\n".join(lines)


def verify_tests(root: Path, cfg: dict, only: str | None, timeout: int) -> list[dict]:
    """Run each component's test command once; report outcome and duration."""
    manifest = load_components(root)
    comps = manifest["components"] if manifest else [c for c in discover(root, cfg)
                                                     if not c["workspace_root"]]
    results = []
    for c in comps:
        name, cmd = c.get("name") or c.get("path"), c.get("test")
        if only and only not in (name, c.get("path")):
            continue
        if not cmd:
            results.append({"component": name, "command": None, "status": "missing"})
            continue
        start = time.monotonic()
        try:
            out = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True,
                                 timeout=timeout)
            status = "passed" if out.returncode == 0 else "failed"
            tail = (out.stdout + out.stderr).strip().splitlines()[-15:]
        except subprocess.TimeoutExpired:
            status, tail = "timeout", []
        results.append({"component": name, "command": cmd, "status": status,
                        "seconds": round(time.monotonic() - start, 1), "output_tail": tail})
    return results


# -------------------------------------------------------------------- work tracker

def factory_cfg(cfg: dict) -> dict:
    user = cfg.get("factory")
    return {**DEFAULT_FACTORY, **(user if isinstance(user, dict) else {})}


def work_path(root: Path, slug: str) -> Path:
    if not SLUG_RE.match(slug):
        raise ValueError(f"invalid work slug '{slug}': use lowercase letters, digits and dashes")
    return root / WORK_DIR / f"{slug}.md"


TASK_HEADING_RE = re.compile(r"^(\S+?)\.(?:\s+(.*))?$")


def parse_work_md(text: str) -> dict:
    _, top, sections = parse_record(text)
    data = {"goal": top.get("goal", ""), "request": top.get("request", ""),
            "created": top.get("created", ""), "components": md_list(top.get("components", "")),
            "tasks": []}
    for heading, f in sections:
        m = TASK_HEADING_RE.match(heading)
        tid, title = (m.group(1), m.group(2) or "") if m else ("", heading)
        task = {"id": tid, "title": title.strip(), "agent": f.get("agent", "coder").strip(),
                "component": md_value(f.get("component", "")),
                "files": md_list(f.get("files", "")),
                "after": md_list(f.get("after", "")),
                "status": f.get("status", "todo").strip().lower(),
                "attempts": int(f["attempts"]) if f.get("attempts", "").strip().isdigit() else 0,
                "note": f.get("note", "")}
        verify = md_value(f.get("verify", ""))
        if verify.lower() not in NONE_VALUES:
            task["verify"] = verify
        data["tasks"].append(task)
    return data


def render_work_md(slug: str, data: dict) -> str:
    out = [f"# Work: {slug}", "", md_field("Goal", data.get("goal", "")),
           md_field("Request", data.get("request", "")),
           md_field("Created", data.get("created", "")),
           md_field("Components", ", ".join(data.get("components") or []) or "none"), ""]
    for t in tasks_of(data):
        out += [f"## {t.get('id')}. {t.get('title', '')}", "",
                md_field("Status", t.get("status", "todo")),
                md_field("Agent", t.get("agent", "coder")),
                md_field("Component", t.get("component") or "none"),
                md_field("Files", list(t.get("files") or [])),
                md_field("Verify", f"`{t['verify']}`" if t.get("verify") else "none"),
                md_field("After", ", ".join(map(str, t.get("after") or [])) or "none"),
                md_field("Attempts", t.get("attempts") or 0)]
        if t.get("note"):
            out.append(md_field("Note", t["note"]))
        out.append("")
    return "\n".join(out)


def load_work(path: Path) -> dict | None:
    return parse_work_md(_read(path)) if path.is_file() else None


def list_work(root: Path) -> list[tuple[str, dict]]:
    """All tracked work, most recently changed first."""
    d = root / WORK_DIR
    files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
    return [(f.stem, load_work(f)) for f in files]


def validate_work(data: dict) -> list[str]:
    problems, ids = [], set()
    if not str(data.get("goal", "")).strip():
        problems.append("no goal")
    for n, t in enumerate(data.get("tasks") or []):
        if not isinstance(t, dict):
            problems.append(f"task #{n + 1} is not an object")
            continue
        tid = str(t.get("id", "")).strip()
        if not tid or tid in ids:
            problems.append(f"task #{n + 1} has a missing or duplicate id")
        ids.add(tid)
        if not str(t.get("title", "")).strip():
            problems.append(f"task {tid} has no title")
        if t.get("agent", "coder") not in AGENTS:
            problems.append(f"task {tid}: agent must be one of {', '.join(AGENTS)}")
        if t.get("status", "todo") not in TASK_STATUSES:
            problems.append(f"task {tid}: status must be one of {', '.join(TASK_STATUSES)}")
    for t in data.get("tasks") or []:
        if isinstance(t, dict):
            for dep in t.get("after") or []:
                if str(dep) not in ids:
                    problems.append(f"task {t.get('id')} waits on unknown task {dep}")
    if not data.get("tasks"):
        problems.append("no tasks")
    return problems


def tasks_of(data: dict) -> list[dict]:
    return [t for t in data.get("tasks") or [] if isinstance(t, dict)]


def ready_tasks(data: dict) -> list[dict]:
    """Tasks that can start now: not done or blocked, and everything they wait on is done."""
    done = {str(t.get("id")) for t in tasks_of(data) if t.get("status") == "done"}
    return [t for t in tasks_of(data) if t.get("status", "todo") in ("todo", "doing")
            and all(str(d) in done for d in t.get("after") or [])]


def work_state(data: dict) -> str:
    tasks = tasks_of(data)
    if tasks and all(t.get("status") == "done" for t in tasks):
        return "done"
    return "active" if ready_tasks(data) else "blocked"


def active_work(root: Path) -> tuple[str, dict] | None:
    for slug, data in list_work(root):
        if work_state(data) != "done":
            return slug, data
    return None


def work_summary(slug: str, data: dict) -> str:
    tasks = tasks_of(data)
    done = sum(t.get("status") == "done" for t in tasks)
    blocked = sum(t.get("status") == "blocked" for t in tasks)
    extra = f", {blocked} blocked" if blocked else ""
    return f"{slug}: {data.get('goal', '').strip()} ({done}/{len(tasks)} done{extra}, {work_state(data)})"


def format_work(slug: str, data: dict) -> str:
    marks = {"todo": " ", "doing": ">", "done": "x", "blocked": "!"}
    lines = [f"work {work_summary(slug, data)}"]
    for t in tasks_of(data):
        status = t.get("status", "todo")
        tries = f" try {t['attempts']}" if t.get("attempts") else ""
        after = f" after {','.join(map(str, t['after']))}" if t.get("after") else ""
        lines.append(f"  [{marks.get(status, '?')}] {t.get('id')} {t.get('agent', 'coder')}"
                     f" {t.get('component') or '-'}: {t.get('title', '')}{after}{tries}")
        if t.get("files"):
            lines.append(f"      files: {', '.join(t['files'])}")
        if t.get("verify"):
            lines.append(f"      verify: {t['verify']}")
        if t.get("note"):
            lines.append(f"      note: {t['note']}")
    nxt = ready_tasks(data)
    lines.append(f"next: {', '.join(str(t.get('id')) for t in nxt)}" if nxt else
                 "next: none" + (" (all done)" if work_state(data) == "done" else
                                 " (blocked: ask the user)"))
    for p in validate_work(data):
        lines.append(f"problem: {p}")
    return "\n".join(lines)


def set_task(root: Path, cfg: dict, slug: str, tid: str, status: str, note: str | None) -> str:
    if status not in TASK_STATUSES:
        raise ValueError(f"status must be one of {', '.join(TASK_STATUSES)}")
    path = work_path(root, slug)
    data = load_work(path)
    if data is None:
        raise ValueError(f"no work '{slug}' in {WORK_DIR}")
    task = next((t for t in tasks_of(data) if str(t.get("id")) == tid), None)
    if task is None:
        raise ValueError(f"work '{slug}' has no task {tid}")
    if status == "doing" and task.get("status") != "doing":
        task["attempts"] = int(task.get("attempts") or 0) + 1
        limit = int(factory_cfg(cfg)["max_attempts"])
        if task["attempts"] > limit:
            task["attempts"], status = limit, "blocked"
            note = f"attempt limit ({limit}) reached; last: {task.get('note') or 'no note'}"
    task["status"] = status
    if note is not None:
        task["note"] = " ".join(note.split())[:200]
    path.write_text(render_work_md(slug, data), encoding="utf-8")
    return f"task {tid}: {status}" + (f" (try {task['attempts']})" if status == "doing" else "") \
        + "\n" + format_work(slug, data).splitlines()[-1]


# ---------------------------------------------------------------------- reporting

def score(issues: list[Issue]) -> int:
    errors = sum(i.severity == "error" for i in issues)
    warnings = sum(i.severity == "warning" for i in issues)
    return max(0, 100 - 10 * errors - 2 * warnings)


def load_baseline(root: Path) -> set[str]:
    data = load_json(root / BASELINE_FILE, {})
    return set(data.get("accepted", [])) if isinstance(data, dict) else set()


def load_sizes(root: Path) -> dict:
    data = load_json(root / BASELINE_FILE, {})
    sizes = data.get("instruction_sizes") if isinstance(data, dict) else None
    return sizes if isinstance(sizes, dict) else {}


def write_baseline(root: Path, cfg: dict, issues: list[Issue]) -> None:
    (root / CONFIG_DIR).mkdir(exist_ok=True)
    sizes = {}
    for f in instruction_paths(root, cfg):
        size, lines = footprint(root / f)
        sizes[f] = {"lines": lines, "bytes": size}
    data = {"comment": "Known issues accepted when ai-ready was adopted. Fix them and re-run "
                       "--update-baseline to shrink this list; never add to it by hand. "
                       "instruction_sizes caps over-budget instruction files at their current size.",
            "accepted": sorted({i.fingerprint for i in issues if i.check != "instructions-growth"}),
            "instruction_sizes": sizes}
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
    if mode == "prompt":
        return prompt_hook(payload, cfg)
    if mode == "session-start":
        work = active_work(root)
        if work:
            print(f"ai-ready: unfinished work {work_summary(*work)}. "
                  f"`python3 {Path(__file__).resolve()} --work {work[0]}` shows its tasks; "
                  f"/ai-ready:build {work[0]} continues it.")
        return 0
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
        if r in cfg["instruction_files"] or p.name in ("CLAUDE.md", "AGENTS.md"):
            issues += check_instructions(root, cfg, r)

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


def prompt_hook(payload: dict, cfg: dict) -> int:
    """UserPromptSubmit: for a long prompt, have Claude offer the factory before starting."""
    fc = factory_cfg(cfg)
    prompt = str(payload.get("prompt") or "").strip()
    if not fc["suggest"] or prompt.startswith("/") or len(prompt.split()) < int(fc["suggest_min_words"]):
        return 0
    print("ai-ready: this looks like multi-step work. Before starting, ask the user once whether "
          "to run it through /ai-ready:build (planned, tracked tasks done by agents) or directly; "
          "direct is faster for small changes.")
    return 0


# ---------------------------------------------------------------------------- cli

def show_work(root: Path, slug: str, fmt: str) -> int:
    if slug:
        try:
            data = load_work(work_path(root, slug))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if data is None:
            print(f"error: no work '{slug}' in {WORK_DIR}", file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2) if fmt == "json" else format_work(slug, data))
        return 1 if validate_work(data) else 0
    work = list_work(root)
    if fmt == "json":
        print(json.dumps({s: d for s, d in work}, indent=2))
        return 0
    if not work:
        print(f"no tracked work in {WORK_DIR}")
        return 0
    active = active_work(root)
    if active:
        print(format_work(*active))
    others = [w for w in work if not active or w[0] != active[0]]
    if others:
        print("other work:" if active else "work:")
        print("\n".join(f"  {work_summary(*w)}" for w in others))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check that a repository is (and stays) AI ready.")
    ap.add_argument("--root", default=".", help="repository root (default: git toplevel of cwd)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--base", help="git ref to diff against for doc-drift (e.g. origin/main)")
    ap.add_argument("--no-baseline", action="store_true", help="treat every issue as new")
    ap.add_argument("--update-baseline", action="store_true",
                    help="accept all current issues into .ai-ready/baseline.json")
    ap.add_argument("--init", action="store_true", help="write a default .ai-ready/config.json")
    ap.add_argument("--hook", choices=["post-edit", "stop", "prompt", "session-start"], help="run as a Claude Code hook")
    ap.add_argument("--discover", action="store_true",
                    help="print candidate components detected from build files (JSON)")
    ap.add_argument("--explain", action="store_true",
                    help="print the abstract and component table (Markdown)")
    ap.add_argument("--verify-tests", nargs="?", const="", metavar="COMPONENT",
                    help="run each component's test command (or just COMPONENT's)")
    ap.add_argument("--timeout", type=int, default=600, help="per-component test timeout (s)")
    ap.add_argument("--work", nargs="?", const="", metavar="SLUG",
                    help=f"show tracked work in {WORK_DIR} (all, or one SLUG in full)")
    ap.add_argument("--work-set", nargs=3, metavar=("SLUG", "TASK", "STATUS"),
                    help="set a task's status: " + "|".join(TASK_STATUSES))
    ap.add_argument("--note", help="with --work-set: a one-line note kept on the task")
    ap.add_argument("--convert-map", action="store_true",
                    help=f"write {COMPONENTS_FILE} from an older {COMPONENTS_JSON}")
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
    if args.work_set:
        try:
            print(set_task(root, cfg, *args.work_set, note=args.note))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0
    if args.work is not None:
        return show_work(root, args.work, args.format)
    if args.convert_map:
        data = load_json(root / COMPONENTS_JSON, None)
        if not isinstance(data, dict) or (root / COMPONENTS_FILE).exists():
            print(f"nothing to convert: needs {COMPONENTS_JSON} and no {COMPONENTS_FILE}",
                  file=sys.stderr)
            return 1
        (root / COMPONENTS_FILE).write_text(render_components_md(data, root.name), encoding="utf-8")
        print(f"wrote {COMPONENTS_FILE}; delete {COMPONENTS_JSON} once it reads right")
        return 0
    if args.discover:
        print(json.dumps(discover(root, cfg), indent=2))
        return 0
    if args.explain:
        print(explain(root, cfg))
        return 0
    if args.verify_tests is not None:
        results = verify_tests(root, cfg, args.verify_tests or None, args.timeout)
        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                secs = f" in {r['seconds']}s" if "seconds" in r else ""
                print(f"{r['status']:8} {r['component']}: {r['command'] or 'no test command'}{secs}")
                if r["status"] in ("failed", "timeout"):
                    print("\n".join("    " + l for l in r.get("output_tail", [])))
        return 0 if all(r["status"] == "passed" for r in results) else 1
    issues = run_checks(root, cfg, base=args.base)
    if args.update_baseline:
        write_baseline(root, cfg, issues)
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
