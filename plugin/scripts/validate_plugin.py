#!/usr/bin/env python3
"""validate_plugin.py -- structural self-check of the revit-automation plugin.

Asserts (per the Claude Code plugin reference, verified 2026-08):
  * .claude-plugin/plugin.json  : required `name` (kebab-case), well-typed
    optional fields (version = semver string, keywords = array, author =
    object with a name, license = string, description = string).
  * marketplace.json            : required name/owner/plugins; each plugin
    entry has name + source; relative sources start with ./ (or "./");
    plugin/marketplace.json is identical to plugin/.claude-plugin/marketplace.json.
  * skills/<name>/SKILL.md      : YAML frontmatter with a `name` and a
    `description` (description recommended; combined <= 1536 chars).
  * agents/*.md                 : frontmatter with `name` + `description`.
  * commands/*.md               : frontmatter (description) parses.
  * every plugin-relative path referenced in skill/agent/command markdown
    (scripts/, references/, assets/, examples/, lib/, skills/, agents/,
    commands/) exists on disk.
  * lib/pyproject.toml parses and its package source exists.

Exit 0 = all assertions passed; 1 = failures listed. Prints a report.

Usage:
    python plugin/scripts/validate_plugin.py [plugin-root]
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

failures: list[str] = []
notes: list[str] = []
checked = 0


def fail(msg: str) -> None:
    failures.append(msg)


def ok(msg: str) -> None:
    global checked
    checked += 1
    notes.append("ok  " + msg)


def load_json(path: str):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as e:
        fail(f"{os.path.relpath(path, ROOT)}: invalid JSON ({e})")
        return None


# ---------------------------------------------------------------- frontmatter
def parse_frontmatter(text: str) -> dict | None:
    """Tiny YAML subset: key: value lines (values may be quoted). Enough for
    the fields we assert (name, description, tools, model...)."""
    m = FM_RE.match(text)
    if not m:
        return None
    out: dict = {}
    cur_key = None
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1] in (" ", "\t") and cur_key:      # continuation / list item
            out[cur_key] = (str(out.get(cur_key) or "") + " " + raw.strip()).strip()
            continue
        if ":" not in raw:
            continue
        k, _, v = raw.partition(":")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k] = v
        cur_key = k
    return out


# ---------------------------------------------------------------- manifests
def check_plugin_json() -> dict | None:
    path = os.path.join(ROOT, ".claude-plugin", "plugin.json")
    if not os.path.isfile(path):
        fail(".claude-plugin/plugin.json missing")
        return None
    d = load_json(path)
    if d is None:
        return None
    name = d.get("name")
    if not isinstance(name, str) or not KEBAB.match(name or ""):
        fail(f"plugin.json: `name` must be a kebab-case string (got {name!r})")
    else:
        ok(f"plugin.json name={name!r} (kebab-case)")
    if "version" in d and not (isinstance(d["version"], str) and SEMVER.match(d["version"])):
        fail(f"plugin.json: `version` must be a semver string (got {d['version']!r})")
    elif "version" in d:
        ok(f"plugin.json version={d['version']}")
    if "description" in d and not isinstance(d["description"], str):
        fail("plugin.json: `description` must be a string")
    if "keywords" in d and not isinstance(d["keywords"], list):
        fail("plugin.json: `keywords` must be an array (a string here is a load error)")
    if "author" in d:
        a = d["author"]
        if not (isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"]):
            fail("plugin.json: `author` must be an object with a `name`")
        else:
            ok(f"plugin.json author={a['name']!r}")
    if "license" in d and not isinstance(d["license"], str):
        fail("plugin.json: `license` must be a string")
    # component path fields, if present, must be relative starting with ./
    for key in ("skills", "commands", "agents", "hooks", "mcpServers", "outputStyles"):
        if key in d:
            vals = d[key] if isinstance(d[key], list) else [d[key]]
            for v in vals:
                if isinstance(v, str) and not v.startswith("./"):
                    fail(f"plugin.json: `{key}` path {v!r} must start with ./")
    return d


def check_marketplace_json() -> None:
    real = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    conv = os.path.join(ROOT, "marketplace.json")
    if not os.path.isfile(real):
        fail(".claude-plugin/marketplace.json missing (the location `/plugin marketplace add` reads)")
        return
    d = load_json(real)
    if d is None:
        return
    if not (isinstance(d.get("name"), str) and KEBAB.match(d["name"])):
        fail(f"marketplace.json: `name` must be kebab-case (got {d.get('name')!r})")
    else:
        ok(f"marketplace.json name={d['name']!r}")
    if not (isinstance(d.get("owner"), dict) and d["owner"].get("name")):
        fail("marketplace.json: `owner` object with `name` required")
    else:
        ok("marketplace.json owner present")
    plugins = d.get("plugins")
    if not (isinstance(plugins, list) and plugins):
        fail("marketplace.json: `plugins` must be a non-empty array")
        return
    for i, p in enumerate(plugins):
        if not (isinstance(p, dict) and isinstance(p.get("name"), str) and KEBAB.match(p["name"])):
            fail(f"marketplace.json: plugins[{i}].name required (kebab-case)")
            continue
        src = p.get("source")
        if src is None:
            fail(f"marketplace.json: plugins[{i}].source required")
        elif isinstance(src, str):
            if not src.startswith("./"):
                fail(f"marketplace.json: plugins[{i}].source {src!r} must be a relative "
                     f"path starting with ./ (marketplace-root relative)")
            else:
                target = os.path.normpath(os.path.join(ROOT, src))
                if not os.path.isdir(target):
                    fail(f"marketplace.json: plugins[{i}].source {src!r} does not resolve to a dir")
                else:
                    ok(f"marketplace.json plugins[{i}] {p['name']!r} source={src!r} resolves")
        elif not isinstance(src, dict):
            fail(f"marketplace.json: plugins[{i}].source must be string|object")
    # the convenience copy must match the operative one
    if os.path.isfile(conv):
        try:
            with open(real) as a, open(conv) as b:
                same = json.load(a) == json.load(b)
        except Exception:
            same = False
        if same:
            ok("marketplace.json == .claude-plugin/marketplace.json (identical)")
        else:
            fail("marketplace.json differs from .claude-plugin/marketplace.json")
    else:
        fail("plugin/marketplace.json convenience copy missing")


# ---------------------------------------------------------------- components
def skill_dirs(d: str) -> list[str]:
    """Names under skills/ that are actual loadable skills.

    `_shared` is the zero-pip bootstrap package and `__pycache__` is a build
    artifact; neither carries a SKILL.md. Underscore marks both as not-a-skill.
    """
    return sorted(n for n in os.listdir(d)
                  if not n.startswith("_") and os.path.isdir(os.path.join(d, n)))


def check_skills() -> None:
    d = os.path.join(ROOT, "skills")
    if not os.path.isdir(d):
        fail("skills/ directory missing")
        return
    for name in skill_dirs(d):
        sd = os.path.join(d, name)
        sm = os.path.join(sd, "SKILL.md")
        if not os.path.isfile(sm):
            fail(f"skills/{name}: SKILL.md missing")
            continue
        text = open(sm, encoding="utf-8").read()
        fm = parse_frontmatter(text)
        if fm is None:
            fail(f"skills/{name}/SKILL.md: no YAML frontmatter (--- ... ---)")
            continue
        if not fm.get("name"):
            fail(f"skills/{name}/SKILL.md: frontmatter `name` missing")
        if not fm.get("description"):
            fail(f"skills/{name}/SKILL.md: frontmatter `description` missing")
        else:
            dl = len(fm["description"])
            if dl > 1536:
                fail(f"skills/{name}: description is {dl} chars (>1536 gets truncated)")
            ok(f"skills/{name}/SKILL.md frontmatter name={fm.get('name')!r} description={dl} chars")


def check_agents() -> None:
    d = os.path.join(ROOT, "agents")
    if not os.path.isdir(d):
        fail("agents/ directory missing")
        return
    mds = [f for f in sorted(os.listdir(d)) if f.endswith(".md")]
    if not mds:
        fail("agents/: no agent .md files")
    for f in mds:
        text = open(os.path.join(d, f), encoding="utf-8").read()
        fm = parse_frontmatter(text)
        if fm is None:
            fail(f"agents/{f}: no frontmatter")
            continue
        missing = [k for k in ("name", "description") if not fm.get(k)]
        if missing:
            fail(f"agents/{f}: frontmatter missing {missing}")
            continue
        if fm["name"] != f[:-3]:
            fail(f"agents/{f}: frontmatter name {fm['name']!r} != filename")
        body = FM_RE.sub("", text).strip()
        if not body:
            fail(f"agents/{f}: empty system prompt body")
        ok(f"agents/{f} frontmatter name/description ok; tools={fm.get('tools', '(inherit)')}")


def check_commands() -> None:
    d = os.path.join(ROOT, "commands")
    if not os.path.isdir(d):
        fail("commands/ directory missing")
        return
    mds = [f for f in sorted(os.listdir(d)) if f.endswith(".md")]
    if not mds:
        fail("commands/: no command .md files")
    for f in mds:
        text = open(os.path.join(d, f), encoding="utf-8").read()
        fm = parse_frontmatter(text)
        if fm is None:
            fail(f"commands/{f}: no frontmatter")
            continue
        if not fm.get("description"):
            fail(f"commands/{f}: frontmatter `description` missing")
        else:
            ok(f"commands/{f} frontmatter description ok (invokes as /{f[:-3]})")
        if not FM_RE.sub("", text).strip():
            fail(f"commands/{f}: empty body")


def check_lib() -> None:
    pp = os.path.join(ROOT, "lib", "pyproject.toml")
    if not os.path.isfile(pp):
        fail("lib/pyproject.toml missing")
        return
    if tomllib is not None:
        try:
            cfg = tomllib.loads(open(pp, "rb").read().decode())
            nm = cfg.get("project", {}).get("name")
            where = cfg.get("tool", {}).get("setuptools", {}).get("packages", {}) \
                       .get("find", {}).get("where", ["."])
            ok(f"lib/pyproject.toml parses; project.name={nm!r}; packages where={where}")
        except Exception as e:
            fail(f"lib/pyproject.toml: TOML parse error ({e})")
            return
    if not os.path.isfile(os.path.join(ROOT, "lib", "src", "rvt", "__init__.py")):
        fail("lib/src/rvt/__init__.py missing (package not importable)")
    else:
        n = len([f for f in os.listdir(os.path.join(ROOT, "lib", "src", "rvt")) if f.endswith(".py")])
        ok(f"lib/src/rvt package present ({n} modules)")
    for must in ("ecc.py", "container.py", "cfb_writer.py", "objects.py", "encode.py",
                 "schema.py", "writer.py", "partitions.py", "roundtrip.py",
                 "streams_edit.py", "stream_encoders.py", "mutate.py"):
        if not os.path.isfile(os.path.join(ROOT, "lib", "src", "rvt", must)):
            fail(f"lib/src/rvt/{must} missing")


# ---------------------------------------------------------------- references
REF_RE = re.compile(r"`([A-Za-z0-9_.<>\-/]+?\.(?:py|md|js|mjs|json|txt|toml|ifc))`")
PREFIXES = ("scripts/", "references/", "assets/", "examples/", "lib/", "skills/",
            "agents/", "commands/", "tests/")
PLACEHOLDER = re.compile(r"^(out|job|path|samples|extracted|docs|src|tools|vendor|"
                         r"usecases|spec|<)|[<>*$]|(^|/)(in|input|output|hardened|edited|"
                         r"model|artifact|file)\.")


def check_referenced_paths() -> None:
    """Every plugin-relative path mentioned in backticks must exist."""
    docs: list[tuple[str, str]] = []          # (owner_dir, path)
    for skill in skill_dirs(os.path.join(ROOT, "skills")):
        sd = os.path.join(ROOT, "skills", skill)
        for f in os.listdir(sd):
            if f.endswith(".md"):
                docs.append((sd, os.path.join(sd, f)))
        refdir = os.path.join(sd, "references")
        if os.path.isdir(refdir):
            for f in os.listdir(refdir):
                if f.endswith(".md"):
                    docs.append((sd, os.path.join(refdir, f)))
    for comp in ("agents", "commands"):
        cd = os.path.join(ROOT, comp)
        if os.path.isdir(cd):
            for f in os.listdir(cd):
                if f.endswith(".md"):
                    docs.append((ROOT, os.path.join(cd, f)))
    for extra in ("README.md", os.path.join("examples", "README.md"), os.path.join("lib", "README.md")):
        p = os.path.join(ROOT, extra)
        if os.path.isfile(p):
            docs.append((ROOT, p))

    seen, missing, resolved = set(), [], 0
    for owner, doc in docs:
        text = open(doc, encoding="utf-8", errors="replace").read()
        for m in REF_RE.finditer(text):
            ref = m.group(1)
            if PLACEHOLDER.search(ref):
                continue
            if not ref.startswith(PREFIXES):
                continue
            key = (owner, ref)
            if key in seen:
                continue
            seen.add(key)
            cands = [os.path.join(owner, ref), os.path.join(ROOT, ref),
                     os.path.join(os.path.dirname(doc), ref)]
            # skills/<x>/... references from anywhere resolve against plugin root
            if any(os.path.exists(c) for c in cands):
                resolved += 1
            else:
                missing.append((os.path.relpath(doc, ROOT), ref))
    ok(f"{resolved} referenced plugin-relative paths resolve on disk")
    for doc, ref in missing:
        fail(f"{doc}: referenced path does not exist: {ref}")


# ---------------------------------------------------------------- main
def main() -> int:
    print(f"== validate_plugin: {ROOT} ==")
    check_plugin_json()
    check_marketplace_json()
    check_skills()
    check_agents()
    check_commands()
    check_lib()
    check_referenced_paths()
    for n in notes:
        print("  " + n)
    print(f"\n  assertions passed: {checked}")
    if failures:
        print(f"  FAILURES: {len(failures)}")
        for f in failures:
            print("   x " + f)
        return 1
    print("  RESULT: PASS — plugin structure is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
