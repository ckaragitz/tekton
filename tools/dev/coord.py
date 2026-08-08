#!/usr/bin/env python3
"""Coordination helpers for .github/workflows/coord.yml (stdlib only, GITHUB_TOKEN only).

Two jobs the workflow cannot do well in bash:

  similar  Rank existing issues whose TITLE looks like a new issue's title, so a
           freshly filed issue gets a "possible duplicates" hint before two
           sessions fix the same bug twice. IDF-weighted token overlap over the
           issue list passed in; identifiers such as validate_plugin,
           schema_cache/index.json or cp1252 carry most of the weight.
             python tools/dev/coord.py similar --title "T" --self 45 --issues issues.json

  refs     Parse a PR body the way GitHub does: which issues it CLOSES on merge
           (close/closes/closed/fix/fixes/fixed/resolve/resolves/resolved #N) vs
           merely mentions, plus the "does not close #N" trap - GitHub ignores
           the negation and closes #N anyway.
             python tools/dev/coord.py refs --body-file body.txt      -> JSON

issues.json is `gh issue list --json number,title,state,assignees` output.
"""
import argparse, json, math, re, sys

STOP = frozenset("""
the a an and or of on in to for with without from by at as is are be it its this that these those
when then than not no into via per all any every each own one two make add fix run use new vs do
does did which what who how here there after before under over out up so if
""".split())

CLOSING = re.compile(r"(?<![\w-])(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)", re.I)
NEGATED = re.compile(r"\bnot\b[\s*_`~]{0,8}(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)", re.I)
MENTION = re.compile(r"(?<![\w/&])#(\d+)\b")


def _stem(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es") and (t[-3] in "sxz" or t[-4:-2] in ("ch", "sh")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokens(title: str) -> set:
    """Lower-cased content tokens of a title: whole identifiers plus their parts."""
    out = set()
    for run in re.findall(r"[a-z0-9_][a-z0-9_.\-/]*", title.lower()):
        for piece in run.strip("._-/").split("/"):
            piece = piece.strip("._-")
            if not piece or piece in STOP:
                continue
            if re.search(r"[a-z]", piece):
                out.add(_stem(piece))
            for sub in re.split(r"[._\-]", piece):
                if len(sub) >= 3 and sub not in STOP and re.search(r"[a-z]", sub):
                    out.add(_stem(sub))
    return out


def similar(title: str, issues: list, self_number: int = 0,
            threshold: float = 0.22, limit: int = 3) -> list:
    """Return [(score, issue, shared_tokens)] for issues whose title resembles `title`.

    score = IDF-weighted overlap coefficient in [0, 1]; document frequencies come
    from the candidate list itself plus the new title, so words every issue uses
    ("windows", "plugin") count little and rare identifiers count a lot.
    """
    cands = [i for i in issues if int(i.get("number", 0)) != int(self_number or 0)]
    toks = {int(i["number"]): tokens(i.get("title", "")) for i in cands}
    mine = tokens(title)
    n_docs = len(toks) + 1
    df = {}
    for s in list(toks.values()) + [mine]:
        for t in s:
            df[t] = df.get(t, 0) + 1

    def weight(t):
        return math.log((n_docs + 1) / (df.get(t, 0) + 0.5))

    mine_w = sum(weight(t) for t in mine)
    hits = []
    for i in cands:
        other = toks[int(i["number"])]
        shared = mine & other
        if not shared or not mine_w:
            continue
        den = min(mine_w, sum(weight(t) for t in other))
        score = sum(weight(t) for t in shared) / den if den else 0.0
        if score >= threshold:
            hits.append((round(score, 3), i, sorted(shared, key=lambda t: (-weight(t), t))))
    hits.sort(key=lambda h: (-h[0], int(h[1]["number"])))
    return hits[:limit]


def refs(body: str) -> dict:
    """{'closing': [...], 'refs': [...], 'negated': [...]} issue numbers found in a PR body."""
    body = re.sub(r"<!--.*?-->", " ", body or "", flags=re.S)   # template comments don't count
    closing = sorted({int(n) for _, n in CLOSING.findall(body)})
    negated = sorted({int(n) for n in NEGATED.findall(body)})
    mentioned = sorted({int(n) for n in MENTION.findall(body)} - set(closing))
    return {"closing": closing, "refs": mentioned, "negated": negated}


def _fmt_hit(score, issue, shared) -> str:
    who = ",".join("@" + a["login"] for a in (issue.get("assignees") or []) if a.get("login"))
    state = str(issue.get("state", "")).lower() or "?"
    held = f", held by {who}" if who else (", unassigned" if state == "open" else "")
    return (f"- #{issue['number']} ({state}{held}) {issue.get('title', '').strip()} "
            f"— {int(round(score * 100))}% title overlap on `{'`, `'.join(shared[:5])}`")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("similar", help="print markdown bullets for likely-duplicate issues (empty = none)")
    s.add_argument("--title", required=True)
    s.add_argument("--self", type=int, default=0, help="number of the issue being checked (excluded)")
    s.add_argument("--issues", required=True, help="JSON file: gh issue list --json number,title,state,assignees")
    s.add_argument("--threshold", type=float, default=0.22)
    s.add_argument("--limit", type=int, default=3)
    r = sub.add_parser("refs", help="print JSON {closing, refs, negated} parsed from a PR body")
    r.add_argument("--body-file", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "similar":
        with open(a.issues, encoding="utf-8") as fh:
            issues = json.load(fh)
        for hit in similar(a.title, issues, a.self, a.threshold, a.limit):
            print(_fmt_hit(*hit))
        return 0
    with open(a.body_file, encoding="utf-8", errors="replace") as fh:
        print(json.dumps(refs(fh.read())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
