#!/usr/bin/env python
"""rft_facts.py -- mine family CATEGORY / PART TYPE facts from Revit's
default ``.rft`` family templates, and check the shipped table against them
(issue #516).

WHY.  ``rvt.famgen.category_facts`` carries one row per family kind:
category id, part type, work-plane flag, and the template that is its
citation.  Those rows were mined by this tool, and this tool re-mines them,
so the table is reproducible rather than hand-typed -- and ``check`` proves
the shipped table still matches the templates on any machine that has them.

QUARANTINE.  The templates are third-party material and live ONLY in the
git-ignored ``samples/rft/`` (or a dir given with ``--dir``).  Nothing this
tool emits contains template CONTENT: the output is integers and the source
file's NAME.  With no templates present every subcommand says so and exits
0 -- a fresh clone has none, and that is not a failure.

USAGE (repo root)::

    .venv/bin/python tools/rft_facts.py mine                 # the table, as JSON
    .venv/bin/python tools/rft_facts.py mine --json out.json
    .venv/bin/python tools/rft_facts.py check                # shipped vs mined
    .venv/bin/python tools/rft_facts.py params --kind Door   # per-template params

TERRITORY: this file, ``src/rvt/famgen/category_facts.py``,
``tests/test_category_facts.py``, ``docs/inbox/rft-mining.d/**``.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "src"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_DIR = os.path.join(ROOT, "samples", "rft")


def _templates(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(glob.glob(os.path.join(directory, "**", "*.rft"),
                            recursive=True))


def _deref(v: Any) -> Any:
    if isinstance(v, dict) and "ptr_class" in v and "value" in v:
        return v["value"]
    return v


def _type_id(v: Any) -> Optional[str]:
    v = _deref(v)
    return v.get("m_typeId") if isinstance(v, dict) else v


def read_template(path: str) -> Dict[str, Any]:
    """Decode one template's self-Family facts + its family parameters.
    Values only -- never bytes, never geometry."""
    import importlib.util

    from rvt.families import FamilyIndex
    from rvt.objects import ObjectDecoder

    spec = importlib.util.spec_from_file_location(
        "_rft_probe", os.path.join(HERE, "rft_probe.py"))
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)                       # type: ignore[union-attr]

    els, facts = rp.load_rft_elements(path)
    idx = FamilyIndex(path)
    dec = ObjectDecoder(idx.schema)
    recs = idx.unit_records(0)

    def obj(eid: int) -> Optional[Dict[str, Any]]:
        r = recs.get(102, {}).get(eid)
        if r is None:
            return None
        o = dec.decode_record(r.class_id, r.payload)
        return o.value if o else None

    sf = obj(facts["self_family"]) or {}
    params = []
    for e in els:
        if e.class_name != "ParamElemFamily":
            continue
        pd = _deref((obj(e.elem_id) or {}).get("m_pParamDef")) or {}
        params.append({
            "name": pd.get("m_caption"),
            "spec": _type_id(pd.get("m_specTypeId")),
            "group": _type_id(pd.get("m_groupTypeId")),
            "instance": bool((obj(e.elem_id) or {}).get("m_instanceParam")),
            "visible": pd.get("m_userVisible"),
        })
    return {
        "template": os.path.basename(path),
        "n_elements": len(els),
        "category": facts.get("category"),
        "part_type": facts.get("part_type"),
        "work_plane_based": bool(sf.get("m_isWorkPlaneBased")),
        "ref_type_ids": sf.get("m_refTypeIds"),
        "locked_bips": sf.get("m_lockedParameterIdsForDirectManipulation"),
        "family_params": params,
    }


def mine(directory: str) -> Dict[str, Any]:
    rows = {}
    for p in _templates(directory):
        try:
            rows[os.path.basename(p)[:-4]] = read_template(p)
        except Exception as exc:                                  # noqa: BLE001
            rows[os.path.basename(p)[:-4]] = {
                "template": os.path.basename(p),
                "error": f"{type(exc).__name__}: {exc}"}
    return {"dir": os.path.relpath(directory, ROOT), "n": len(rows),
            "templates": rows}


def check(directory: str) -> Dict[str, Any]:
    """Shipped table vs the templates on disk.  Returns a report; the
    caller decides the exit code."""
    from rvt.famgen import category_facts as CF

    mined = mine(directory)
    by_template = {v.get("template"): v for v in mined["templates"].values()}
    problems: List[str] = []
    checked = 0
    for key, f in sorted(CF.CATEGORY_FACTS.items()):
        got = by_template.get(f.template)
        if got is None:
            continue                       # template absent -- not a failure
        if "error" in got:
            problems.append(f"{key}: {f.template} did not decode: "
                            f"{got['error']}")
            continue
        checked += 1
        for field, shipped in (("category", f.category),
                               ("part_type", f.part_type),
                               ("work_plane_based", f.work_plane_based)):
            if got.get(field) != shipped:
                problems.append(
                    f"{key}: {field} shipped={shipped!r} "
                    f"template({f.template})={got.get(field)!r}")
    return {"dir": mined["dir"], "templates_present": mined["n"],
            "rows_checked": checked, "self_check": CF.check_facts(),
            "problems": problems}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("mine", "check", "params"))
    ap.add_argument("--dir", default=DEFAULT_DIR,
                    help="template directory (default samples/rft/)")
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--kind", default=None,
                    help="params: one template stem (e.g. Door)")
    a = ap.parse_args(argv)

    present = _templates(a.dir)
    if not present:
        print(f"[rft_facts] no .rft templates under "
              f"{os.path.relpath(a.dir, ROOT)} -- nothing to mine (a fresh "
              f"clone has none; this is not a failure).")
        return 0

    if a.cmd == "mine":
        out = mine(a.dir)
    elif a.cmd == "params":
        if not a.kind:
            ap.error("params needs --kind")
        path = os.path.join(a.dir, f"{a.kind}.rft")
        if not os.path.exists(path):
            print(f"[rft_facts] no such template: {a.kind}.rft")
            return 2
        out = read_template(path)
    else:
        out = check(a.dir)

    text = json.dumps(out, indent=1, default=str)
    if a.json_out:
        with open(a.json_out, "w") as fh:
            fh.write(text + "\n")
        print(f"[rft_facts] wrote {a.json_out}")
    else:
        print(text)

    if a.cmd == "check":
        bad = list(out.get("problems") or []) + list(out.get("self_check") or [])
        if bad:
            print(f"[rft_facts] {len(bad)} problem(s)", file=sys.stderr)
            return 1
        print(f"[rft_facts] clean: {out['rows_checked']} row(s) match the "
              f"templates on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
