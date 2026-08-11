#!/usr/bin/env python3
"""interview.py -- the question engine on the command line (issue #684).

The prompt is the interface; the questions are the RESIDUE it leaves.  This CLI
is what a skill session drives (``plugin/skills/tekton-author/references/
INTERVIEW.md``): it reads a prompt, says what is still open, takes a few answers
at a time, and builds the family the moment it is asked to -- answered or not.

    # what does the prompt still leave open?
    python tools/interview.py ask "a transformer" --json
    python tools/interview.py ask "a 75 kVA eaton transformer"        # -> nothing
    python tools/interview.py ask "a transformer" -a vendor=hps -a kva=30

    # the whole question set of one kind, unanswered
    python tools/interview.py describe transformer --json
    python tools/interview.py kinds
    python tools/interview.py sources          # which registries answered

    # BUILD -- at any stage, answered or not.  This is hard rule 1 on the
    # command line: there is no answer you must give to get a file.
    python tools/interview.py build "a transformer" -o out/x
    python tools/interview.py build "a transformer" -a kva=225 -o out/x --json

``ask`` exits 0 when the engine has enough to build a specific product and 2
when something DECISIVE is still open (so a script can branch on it); it never
exits non-zero merely because questions remain.  ``build`` exits 0 when the
file was written -- an unanswered question is not a failure, it is an
assumption, and the report names every one.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from rvt.famgen import interview as IV                          # noqa: E402


def _parse_answers(pairs) -> dict:
    """``-a key=value`` pairs -> a dict, numbers and booleans read as such."""
    out = {}
    for raw in pairs or ():
        if "=" not in raw:
            raise SystemExit(f"--answer must be key=value, got {raw!r}")
        k, v = raw.split("=", 1)
        k, v = k.strip(), v.strip()
        low = v.lower()
        if low in ("true", "yes", "on"):
            out[k] = True
        elif low in ("false", "no", "off"):
            out[k] = False
        else:
            try:
                out[k] = float(v) if ("." in v or "e" in low) else int(v)
            except ValueError:
                out[k] = v
    return out


def _print_plan(p, n: int) -> None:
    print(p.say())
    if not p.covered:
        return
    for q in p.next(n):
        bits = [f"  [{q.key}] {q.ask}"]
        if q.choices:
            bits.append("      choices: "
                        + ", ".join(str(c.label) for c in q.choices))
        if q.withheld:
            bits.append("      not deliverable with the answers so far: "
                        + "; ".join(f"{w['value']}: {w['why']}" for w in q.withheld[:3]))
        bits.append(f"      affects: {q.affects}")
        bits.append(f"      if you skip it: {q.default!r} ({q.default_tier} -- "
                    f"{q.default_basis})")
        print("\n".join(bits))
    if p.answers:
        print("  settled already:")
        for k, a in sorted(p.answers.items()):
            src = f" from the prompt ({a.quoted!r})" if a.quoted else ""
            print(f"    {k} = {a.value!r}  [{a.tier}]{src}")


def _cmd_ask(args) -> int:
    p = IV.plan(prompt=args.prompt or "", kind=args.kind,
                answers=_parse_answers(args.answer))
    if args.json:
        print(json.dumps(p.to_json(), indent=2, default=str))
    else:
        _print_plan(p, args.n)
    if not p.covered:
        return 3
    return 0 if p.enough else 2


def _cmd_describe(args) -> int:
    d = IV.describe_kind(args.kind)
    if args.json:
        print(json.dumps(d, indent=2, default=str))
        return 0 if d.get("covered") else 3
    if not d.get("covered"):
        print(d.get("note", ""))
        return 3
    print(f"{args.kind}: {len(d['questions'])} question(s), most decisive first")
    for q in d["questions"]:
        ch = ("  choices: " + ", ".join(str(c["label"]) for c in q["choices"])
              if q["choices"] else "")
        print(f"  {q['rank']:>3}  {q['key']:<22} {q['source']:<12} {q['ask']}{ch}")
    return 0


def _cmd_kinds(args) -> int:
    ks = IV.kinds()
    if args.json:
        print(json.dumps({"kinds": list(ks),
                          "unbuildable_categories": IV.unbuildable_categories(),
                          "sources": IV.source_status()}, indent=2, default=str))
        return 0
    print("question sets: " + (", ".join(ks) or "(none)"))
    for row in IV.unbuildable_categories():
        print(f"  held but not buildable: {row['category']} -- {row['why']}")
    return 0


def _cmd_sources(args) -> int:
    st = IV.source_status()
    if args.json:
        print(json.dumps(st, indent=2, default=str))
        return 0
    for row in st["sources"]:
        mark = "yes" if row["available"] else "NO "
        print(f"  [{mark}] {row['source']:<12} {row['module']:<26} {row['answers']}")
    print(st["note"])
    return 0


def _cmd_build(args) -> int:
    p = IV.plan(prompt=args.prompt or "", kind=args.kind,
                answers=_parse_answers(args.answer))
    if not p.covered:
        # NOT a refusal to build something we can build: there is genuinely no
        # question set for this, and saying so plainly is the whole point.
        print(p.note, file=sys.stderr)
        if args.json:
            print(json.dumps(p.to_json(), indent=2, default=str))
        return 3
    r = IV.resolve(p)
    from rvt.frontdoor import famspec as FS
    problems = FS.validate(r.famspec)
    if problems:                                          # pragma: no cover
        print("famspec the engine produced is not valid: " + "; ".join(problems),
              file=sys.stderr)
        return 1
    kind, kw, _ropts = FS.normalise(r.famspec)
    prod = FS.build(kind, kw)
    out = args.out or os.path.join("out", "interview")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    path = out if out.lower().endswith((".rfa", ".rvt")) else out + ".rfa"
    report = FS.write(prod, path)
    payload = {"file": path, "interview": r.to_json(), "write": report}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"wrote {path}")
        print(r.say())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="interview.py",
        description="the ordered residue a prompt leaves, and the family it "
                    "builds at any point in the conversation")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _common(p, with_prompt=True):
        if with_prompt:
            p.add_argument("prompt", nargs="?", default="",
                           help="the request, in the user's own words")
        p.add_argument("-k", "--kind", default=None,
                       help="name the product instead of reading it from the prompt")
        p.add_argument("-a", "--answer", action="append", metavar="KEY=VALUE",
                       help="an answer (repeatable)")
        p.add_argument("--json", action="store_true", help="machine-readable output")

    a = sub.add_parser("ask", help="what the prompt still leaves open")
    _common(a)
    a.add_argument("-n", type=int, default=3,
                   help="how many questions to show (default 3 -- a few at a time)")
    a.set_defaults(fn=_cmd_ask)

    d = sub.add_parser("describe", help="the whole question set of one kind")
    d.add_argument("kind")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=_cmd_describe)

    k = sub.add_parser("kinds", help="what this engine has questions for")
    k.add_argument("--json", action="store_true")
    k.set_defaults(fn=_cmd_kinds)

    s = sub.add_parser("sources", help="which registries answered")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=_cmd_sources)

    b = sub.add_parser("build", help="build the family now, answered or not")
    _common(b)
    b.add_argument("-o", "--out", default=None, help="output .rfa (or a stem)")
    b.set_defaults(fn=_cmd_build)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
