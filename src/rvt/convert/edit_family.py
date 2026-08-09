"""rvt.convert.edit_family -- EDIT ROUTE: RFA (+ structured ops) -> RFA.

The deterministic, ops-first family editor of the routing matrix: open a
standalone ``.rfa``, apply PARAMETER / TYPE-NAME / FAMILY-NAME edits, and
re-emit a valid family file.  The mechanics are the certified modify path
and the sibling convert package's family-edit engine -- COMPOSED, not
re-implemented:

* surface   :func:`rvt.convert.modify_family.inventory_family`
            (``Document.from_file`` on the ``.rfa``; captions / specs /
            carriers / current values of every family parameter);
* apply     :func:`rvt.convert.modify_family.apply_family_edits`
            (ONE :func:`rvt.manipulate.commit_plans` commit of the
            self-``Family`` record -- re-encoded records, fresh adler32
            stamps, re-blocked unit, CRCIO reframed: the M3-certified
            modify machinery -- plus the PartAtom metadata follow);
* gates     family-mode validator + release preservation + a semantic
            RE-READ of every edited value (labels on the delivered file).

WHAT THIS MODULE ADDS over :mod:`rvt.convert.modify_family` (the prompt+RFA
combination route): the STRUCTURED OPS contract -- a schema-checked list of
op dicts and a flag-style CLI -- so scripted callers (the job runner, other
converters, tests) never round-trip through natural language:

    [{"op": "set-param",     "param": "BusRating", "value": 225},
     {"op": "set-param",     "param": "PanelName", "value": "DP-7"},
     {"op": "rename-type",   "name": "225A MCB 42ckt"},          # "type": old
     {"op": "rename-family", "name": "Panelboard DP-7 225A"}]

``value`` may carry a unit suffix (``"600 mm"``); lengths REQUIRE one
(units are never guessed -- the engine refuses otherwise).  A set-param op
may carry ``"type": "<type name>"`` to scope the edit to ONE type-table row
(scoped edits deliberately skip the current-defaults mirror -- engine
behaviour).  This module deliberately does NOT export ``parse_family_edit``:
the natural-language vocabulary stays in ``modify_family`` until the two
streams agree a shared contract (recorded in docs/inbox/convert-a.md).

CLI::

    python -m rvt.convert.edit_family <family.rfa> -o <out_dir>
        [--set "BusRating=225"] [--set "PanelName=DP-7"] [--type "400A MLO 42ckt"]
        [--rename-type "OLD=NEW" | --rename-type "NEW"]
        [--rename-family "NEW"] [--ops ops.json] [--inventory]

Territory: ``src/rvt/convert/`` (convert-a stream).
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Sequence

from . import modify_family as MF
from .add_to_project import ConvertError

__all__ = ["FamilyOpsError", "normalize_ops", "edit_family", "main"]


class FamilyOpsError(ConvertError):
    """The structured ops are malformed; the message names the bad op."""


_OPS = ("set-param", "rename-type", "rename-family")


def normalize_ops(ops: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Schema-check structured ops and normalise them into the convert
    package's family-edit JSON vocabulary (raw string values; the engine
    does the spec-driven unit conversion)."""
    if not ops:
        raise FamilyOpsError("no ops given")
    out: List[Dict[str, Any]] = []
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            raise FamilyOpsError(f"op[{i}] is not an object: {op!r}")
        kind = str(op.get("op") or "").strip().lower().replace("_", "-")
        if kind not in _OPS:
            raise FamilyOpsError(f"op[{i}]: unknown op {op.get('op')!r} "
                                 f"(one of {', '.join(_OPS)})")
        if kind == "set-param":
            param = op.get("param") or op.get("caption")
            if not param:
                raise FamilyOpsError(f"op[{i}] set-param: 'param' is required")
            if "value" not in op:
                raise FamilyOpsError(f"op[{i}] set-param {param!r}: 'value' is required")
            raw = str(op["value"])
            unit = str(op.get("unit") or "").strip()
            if unit:
                raw = f"{raw} {unit}"
            entry = {"op": "set-param", "param": str(param), "value": raw}
            # optional TYPE SCOPE (engine support landed 2026-08-04): the edit
            # targets ONE type-table row; scoped edits deliberately skip the
            # m_familyParams current-defaults mirror (engine behaviour)
            if op.get("type") or op.get("type_name"):
                entry["type"] = str(op.get("type") or op.get("type_name"))
            out.append(entry)
        elif kind == "rename-type":
            if not op.get("name"):
                raise FamilyOpsError(f"op[{i}] rename-type: 'name' is required")
            entry: Dict[str, Any] = {"op": "rename-type", "name": str(op["name"])}
            if op.get("type") or op.get("old"):
                entry["type"] = str(op.get("type") or op.get("old"))
            out.append(entry)
        else:  # rename-family
            if not op.get("name"):
                raise FamilyOpsError(f"op[{i}] rename-family: 'name' is required")
            out.append({"op": "rename-family", "name": str(op["name"])})
    return out


def edit_family(rfa_path: str, ops: Sequence[Dict[str, Any]], out_dir: str, *,
                stem: Optional[str] = None,
                validate: bool = True) -> Dict[str, Any]:
    """RFA + structured ops -> RFA.  Normalise the ops and run them through
    the convert package's family-edit engine (one manipulate commit, gated,
    manifested, always delivered).  Returns the engine's manifest record
    (with this route's name recorded)."""
    norm = normalize_ops(ops)
    payload = json.dumps({"ops": norm})
    rec = MF.modify_family(rfa_path, payload, out_dir, stem=stem, validate=validate)
    rec["route"] = "rfa+ops->rfa (rvt.convert.edit_family -> modify_family engine)"
    rec["structured_ops"] = norm
    return rec


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _flag_ops(a: argparse.Namespace) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    if a.ops:
        with open(a.ops) as fh:
            payload = json.load(fh)
        raw = payload.get("ops") if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise FamilyOpsError(f"{a.ops}: expected a list of ops (or {{'ops': [...]}})")
        ops.extend(raw)
    for spec in a.set or []:
        if "=" not in spec:
            raise FamilyOpsError(f"--set needs NAME=VALUE (got {spec!r})")
        name, val = spec.split("=", 1)
        op = {"op": "set-param", "param": name.strip(), "value": val.strip()}
        if a.type:                                   # scope every --set to ONE type row
            op["type"] = str(a.type)
        ops.append(op)
    for spec in a.rename_type or []:
        if "=" in spec:
            old, new = spec.split("=", 1)
            ops.append({"op": "rename-type", "type": old.strip(), "name": new.strip()})
        else:
            ops.append({"op": "rename-type", "name": spec.strip()})
    if a.rename_family:
        ops.append({"op": "rename-family", "name": a.rename_family.strip()})
    return ops


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rvt.convert.edit_family",
        description="RFA -> RFA: structured parameter / type-name / "
                    "family-name edits, re-emitted valid (family-mode "
                    "validated, re-read proven).")
    ap.add_argument("rfa", help="the family file to edit")
    ap.add_argument("-o", "--out-dir", default=None,
                    help="output directory (required unless --inventory)")
    ap.add_argument("--set", action="append", metavar="NAME=VALUE",
                    help="set a family parameter (repeatable); lengths need a "
                         "unit suffix, e.g. --set 'Width=600 mm'")
    ap.add_argument("--type", default=None, metavar="TYPE",
                    help="scope every --set to ONE type-table row (a multi-type "
                         "family); default: the current type + its defaults mirror")
    ap.add_argument("--rename-type", action="append", metavar="[OLD=]NEW")
    ap.add_argument("--rename-family", metavar="NEW", default=None)
    ap.add_argument("--ops", default=None, help="ops.json with structured ops")
    ap.add_argument("--stem", default=None, help="output file stem")
    ap.add_argument("--inventory", action="store_true",
                    help="print the editable surface and exit")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.inventory:
            inv = MF.inventory_family(a.rfa)
            print(json.dumps(inv.as_json(), indent=1, default=str))
            return 0
        ops = _flag_ops(a)
        if not ops:
            print("ERROR: no ops (--set / --rename-type / --rename-family / --ops)")
            return 2
        if not a.out_dir:
            print("ERROR: -o/--out-dir required")
            return 2
        rec = edit_family(a.rfa, ops, a.out_dir, stem=a.stem,
                          validate=not a.no_validate)
    except ConvertError as e:
        print(f"ERROR: {e}")
        return 2
    d = rec.get("deliverables") or {}
    print(f"delivered: {json.dumps({k: v.get('path') for k, v in d.items()})}")
    g = ((rec.get("validation") or {}).get("rfa") or {})
    fm = g.get("family_mode") or {}
    print(f"family-mode validator: {fm.get('verdict')} ({fm.get('n_errors')} errors); "
          f"re-read ok: {all(r.get('ok') for r in g.get('reread') or [])}")
    for s in rec.get("stamps") or []:
        print(f"STAMP: {s}")
    return 0


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
