#!/usr/bin/env python3
"""rvt_job.py — THE FRONT DOOR: the ONE deterministic pipeline the product
promise runs through:

    "a simple prompt, or uploaded project files + requirements, in
     -> a valid Revit file out"

There is NO LLM inside this runner.  The plugin skill (see
docs/inbox/job-runner.md) turns a user prompt into a spec / an ops list;
this script is what that skill INVOKES.  Three entry modes, each ending in
the same hard gates and a DELIVERABLE MANIFEST written next to the output
(``<out>.manifest.json``):

  (A) CREATE   rvt_job.py create --spec job.json [--base base.rvt] -o out.rvt
        seed/content audit (tools/seed_audit logic; report gaps, proceed on
        USABLE) -> spec_to_rvt build (walls, equipment, hosting via
        rvt.hosting when an equipment item names a spec ``hostWall``,
        circuits via --auto-circuits or spec ``circuits``) ->
        rvt.commit.commit_new_elements -> gates -> manifest.

  (B) EDIT     rvt_job.py edit in.rvt --ops ops.json -o out.rvt
        ops.json = a list of {op: delete|rename|set-mark|set-level|set-param|
        move|retype|add-instance|add-circuit, ...} applied via
        rvt.manipulate (every manipulate op = ONE commit_plans) and
        rvt.mutate (add-* ops = one commit_new_elements on that result) ->
        gates -> manifest.

  (C) FROM-IFC rvt_job.py from-ifc design.ifc [--base base.rvt] -o out.rvt
        tools/ifc_to_spec extraction -> the CREATE pipeline (the Claude-
        Design path: the user's Chicago-plenum flow).

HARD GATES (any failure => non-zero exit, the .rvt is NOT a product):
  * structural  — rvt.commit.verify_written / rvt.manipulate.verify_manipulated
                  (CRC / ECC / walker / stamps / counts / sentinels).
  * validation  — rvt.validate.validate_file: ZERO errors REQUIRED
                  (warnings allowed); full report in <out>.validation.json.
  * identity    — the file asserts OUR identity (rvt.identity): author /
                  client == our product string, username empty, last-save
                  path scrubbed to the bare output name (no directories),
                  central-model path empty.  Document GUID coherence with
                  History[0] is preserved so the L2 consistency check holds.

STATUS GATE (recorded honestly, not an exit failure unless
--require-deliverable):
  * base_provenance — the P0 genesis gate G1 (rvt.provenance) ledgering the
    OUTPUT against the BASE it descends from.  On OUR pinned composed
    genesis base the ledger uses the base's authorship census
    (rvt.frontdoor.census, #143): only its residue is Autodesk-derived, and
    the reason names the open TRACKER gates G2/G3 + the residue; on an
    Autodesk sample everything inherited is the sample's.  Either way the
    honest status today is "PROOF-ONLY, NOT-DELIVERABLE" -- a LABEL, the
    file is always delivered.  Only a base + build that pass the genesis
    provenance check flip the status to DELIVERABLE.

Exit codes: 0 = all hard gates passed (status may still be PROOF-ONLY);
2 = planning / seed / spec failure; 3 = structural; 4 = validation;
5 = identity; 6 = --require-deliverable and the output is not deliverable;
1 = usage / unexpected error.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "lib", "src"))          # plugin layout

TOOL_VERSION = "1.0"
FT_PER_M = 3.280839895
SAMPLES_DIR = os.path.join(ROOT, "samples")

# exit codes -----------------------------------------------------------------
EX_OK, EX_ERR, EX_PLAN, EX_STRUCT, EX_VALIDATE, EX_IDENTITY, EX_NOT_DELIVERABLE = 0, 1, 2, 3, 4, 5, 6


# ===========================================================================
# lazy tool imports (degrade gracefully — a missing optional module never
# takes the front door down; it degrades that gate to SKIPPED and says so)
# ===========================================================================
def _load_tool_module(name: str):
    """Import a sibling tools/<name>.py as a module (single source of truth)."""
    p = os.path.join(HERE, f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_rvtjob_{name}", p)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load tools/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Optional:
    """Holder for optionally-available capabilities with the import error kept."""

    def __init__(self):
        self.errors: Dict[str, str] = {}

    def get(self, key: str, loader):
        try:
            return loader()
        except Exception as e:                                        # noqa: BLE001
            self.errors[key] = f"{type(e).__name__}: {e}"
            return None


OPT = _Optional()


def _spec_to_rvt():
    return OPT.get("spec_to_rvt", lambda: _load_tool_module("spec_to_rvt"))


def _seed_audit():
    return OPT.get("seed_audit", lambda: _load_tool_module("seed_audit"))


def _ifc_to_spec():
    return OPT.get("ifc_to_spec", lambda: _load_tool_module("ifc_to_spec"))


def _provenance_mod():
    def _l():
        from rvt import provenance as P
        return P
    return OPT.get("rvt.provenance", _l)


# ===========================================================================
# small helpers
# ===========================================================================
def m2ft(v: float) -> float:
    return float(v) * FT_PER_M


def sha256_of(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _jsonable(o):
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, bytes):
        return f"<{len(o)} bytes>"
    if hasattr(o, "to_json"):
        try:
            return o.to_json()
        except Exception:
            pass
    return str(o)


def _abs(p: Optional[str]) -> Optional[str]:
    return os.path.abspath(p) if p else None


def is_autodesk_sample(path: Optional[str]) -> bool:
    """A base living in samples/ (or one of the six known corpus names) is an
    Autodesk sample project => any output cloned from it is PROOF-ONLY."""
    if not path:
        return False
    ap = os.path.abspath(path)
    if ap.startswith(os.path.abspath(SAMPLES_DIR) + os.sep):
        return True
    base = os.path.basename(ap).lower()
    return any(k in base for k in (
        "rmebasicsampleproject", "racbasicsampleproject", "racadvancedsampleproject",
        "rstbasicsampleproject", "rstadvancedsampleproject", "dach-sample-project",
        "sampleproject"))


def resolve_base(base: Optional[str], template_key: str) -> str:
    """--base wins; else the named research template's sample file."""
    if base:
        if not os.path.exists(base):
            raise FileNotFoundError(f"base .rvt not found: {base}")
        return os.path.abspath(base)
    s2r = _spec_to_rvt()
    if s2r is None:
        raise RuntimeError("spec_to_rvt unavailable and no --base given: "
                           + OPT.errors.get("spec_to_rvt", "?"))
    rel = s2r.TEMPLATES[template_key]["sample"]
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        raise FileNotFoundError(f"template sample not found: {p}")
    return p


# ===========================================================================
# identity (gate G2): OUR BasicFileInfo, path scrubbed, GUID coherent
# ===========================================================================
def history_head_guid(path: str) -> Optional[str]:
    """History entry[0] GUID of ``path`` — the newest save-episode GUID.

    The writer's minimal commit reuses the CURRENT episode for new/edited
    elements (no new History row), so the document's identity GUID must
    stay == History[0] to keep the L2 invariant 'BasicFileInfo Unique
    Document GUID == History entry[0]' true.  We therefore hand this GUID
    to the identity scrub instead of minting a fresh (incoherent) one.
    """
    try:
        from rvt.container import open_rvt
        from rvt.elemtable import inflate_global_stream
        from rvt.stream_encoders import decode_history
        with open_rvt(path) as f:
            hist = decode_history(inflate_global_stream(f.raw("Global/History")).payload)
        ents = hist.get("entries") or []
        return str(ents[0][0]) if ents else None
    except Exception:
        return None


def scrub_identity(path: str, *, document_guid: Optional[str] = None) -> dict:
    """Rewrite ``path``'s BasicFileInfo with OUR identity (in place).

    Used after a manipulate commit (commit_plans does not touch
    BasicFileInfo).  Reads the CFB, replaces the ONE unframed stream via
    rvt.identity.own_basic_file_info, re-writes the container.
    """
    from rvt.cfb_writer import write_cfb
    from rvt.identity import own_basic_file_info
    from rvt.roundtrip import read_entries
    entries = read_entries(path)
    out_entries, done = [], False
    for e in entries:
        if e.entry_type == "stream" and e.path == "BasicFileInfo":
            e = dataclasses.replace(e, data=own_basic_file_info(
                e.data, out_path=path, document_guid=document_guid))
            done = True
        out_entries.append(e)
    if not done:
        raise RuntimeError("BasicFileInfo stream not found; identity not scrubbed")
    tmp = path + ".idtmp"
    write_cfb(tmp, out_entries)
    os.replace(tmp, path)
    return {"scrubbed": True, "document_guid": document_guid}


def identity_gate(path: str) -> dict:
    """Prove the output asserts OUR identity (not the template's)."""
    gate: Dict[str, Any] = {"status": "FAIL", "issues": [], "identity": None}
    try:
        from rvt import identity as ID
        from rvt.container import open_rvt
        from rvt.stream_encoders import decode_basic_file_info
        with open_rvt(path) as f:
            m = decode_basic_file_info(f.raw("BasicFileInfo"))
        ident = {k: m.get(k) for k in (
            "author", "client_app_name", "username", "last_save_path",
            "central_model_path", "unique_document_guid", "central_episode_guid",
            "format", "build", "locale", "unique_document_increments")}
        gate["identity"] = ident
        issues = gate["issues"]
        lsp = str(m.get("last_save_path") or "")
        if "\\" in lsp or "/" in lsp:
            issues.append(f"last_save_path not scrubbed (contains directories): {lsp!r}")
        if str(m.get("username") or ""):
            issues.append(f"username not scrubbed: {m.get('username')!r}")
        if str(m.get("central_model_path") or ""):
            issues.append(f"central_model_path not scrubbed: {m.get('central_model_path')!r}")
        if str(m.get("author") or "") != ID.DEFAULT_AUTHOR:
            issues.append(f"author {m.get('author')!r} != our identity {ID.DEFAULT_AUTHOR!r}")
        if str(m.get("client_app_name") or "") != ID.DEFAULT_CLIENT_APP:
            issues.append(f"client_app_name {m.get('client_app_name')!r} != {ID.DEFAULT_CLIENT_APP!r}")
        # coherence (informational here; the validator enforces it as L2)
        h0 = history_head_guid(path)
        gate["history_head_guid"] = h0
        if h0 and str(m.get("unique_document_guid") or "").lower() != h0.lower():
            issues.append("unique_document_guid != History[0] (would trip the validator)")
        gate["status"] = "PASS" if not issues else "FAIL"
        gate["our_identity"] = {"author": ID.DEFAULT_AUTHOR,
                                "client_app_name": ID.DEFAULT_CLIENT_APP}
    except Exception as e:                                            # noqa: BLE001
        gate["status"] = "FAIL"
        gate["issues"] = [f"identity check crashed: {type(e).__name__}: {e}"]
    return gate


# ===========================================================================
# structural gate (create: verify_written / edit: verify_manipulated)
# ===========================================================================
def structural_gate_from_written(v: dict, expect_ids: List[int]) -> dict:
    found = {}
    try:
        found = {int(s): sum(1 for x in (v.get("new_ids_found") or {}).get(s, {}).values()
                          if x.get("clean")) for s in (101, 102, 103)}
    except Exception:
        pass
    ok = (v.get("crc_failures") == 0 and v.get("ecc_mismatches") == 0
          and v.get("walker_errors") == 0 and bool(v.get("stamps_ok"))
          and v.get("elemtable_count") == v.get("header_count")
          and all((v.get("sentinel_last") or {}).values())
          and all(n == len(expect_ids) for n in found.values()))
    return {"status": "PASS" if ok else "FAIL", "kind": "verify_written",
            "expected_new": len(expect_ids), "new_found_clean_per_seq": found,
            "report": {k: v.get(k) for k in (
                "crc_failures", "ecc_mismatches", "walker_errors", "stamps_ok",
                "elemtable_count", "header_count", "sentinel_last")}}


def structural_gate_from_manipulated(v: dict) -> dict:
    edited_ok = all(all(s.get("clean") is not False for s in per.values())
                    for per in (v.get("edited") or {}).values())
    ok = (v.get("crc_failures") == 0 and v.get("ecc_mismatches") == 0
          and v.get("walker_errors") == 0 and bool(v.get("stamps_ok"))
          and v.get("elemtable_count") == v.get("header_count")
          and all((v.get("sentinel_last") or {}).values())
          and not any((v.get("deleted_still_present") or {}).values())
          and not (v.get("deleted_in_elemtable") or [])
          and edited_ok)
    keep = {k: v.get(k) for k in (
        "crc_failures", "ecc_mismatches", "walker_errors", "isize_identity_mismatches",
        "stamps_ok", "elemtable_count", "header_count", "sentinel_last",
        "deleted_still_present", "deleted_in_elemtable", "elemtable_ids_sorted",
        "unit0_ids_equal_elemtable")}
    warnings = []
    # Block-header A/C counter identity: the known commit.py off-by-4*A defect
    # on element-INSERT blocks.  The calibrated arbiter (rvt.validate) rates
    # it a READER-TOLERATED WARNING (every accepted V20-V29 file carries it;
    # strict mode escalates), so it is surfaced here but never a lone hard
    # failure — the validation gate owns that severity decision.
    if (v.get("isize_identity_mismatches") or 0) > 0:
        warnings.append(f"{v.get('isize_identity_mismatches')} block(s) with the "
                        "reader-tolerated A/C counter defect (rvt.validate WARNING)")
    return {"status": "PASS" if ok else "FAIL", "kind": "verify_manipulated",
            "edited": v.get("edited"), "warnings": warnings, "report": keep}


# ===========================================================================
# validation gate (rvt.validate — 0 errors REQUIRED)
# ===========================================================================
def validation_gate(path: str, out_json: str, *, layers: Optional[List[str]] = None,
                    strict: bool = False) -> dict:
    from rvt.validate import ALL_LAYERS, validate_file
    lay = list(layers) if layers else list(ALL_LAYERS)
    t0 = time.time()
    rep = validate_file(path, layers=lay, strict=strict)
    payload = rep.to_json()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)) or ".", exist_ok=True)
        with open(out_json, "w") as fh:
            json.dump(payload, fh, indent=1)
    except OSError:
        out_json = None
    findings = [f.to_json() for f in rep.findings if f.severity != "info"]
    return {
        "status": "PASS" if rep.ok else "FAIL",
        "errors": len(rep.errors), "warnings": len(rep.warnings), "infos": len(rep.infos),
        "layers": lay, "strict": strict, "elapsed_s": round(time.time() - t0, 1),
        "summary_line": rep.format_text(max_findings=0).splitlines()[1].strip()
        if rep.format_text() else "",
        "top_findings": findings[:25],
        "stats": rep.stats,
        "report_json": _abs(out_json) if out_json else None,
    }


# ===========================================================================
# base provenance / genesis status gate (P0 G1)
# ===========================================================================
def _base_census(base_path: Optional[str]):
    """The authorship census iff ``base_path`` IS a pinned composed genesis
    base (exact sha256; rvt.frontdoor.census, #143) -- else None."""
    if not base_path or is_autodesk_sample(base_path):
        return None
    try:
        from rvt.frontdoor import census as C
        return C.for_file(base_path)
    except Exception:                                                 # noqa: BLE001
        return None


#: why a build on OUR certified base is still PROOF-ONLY (TRACKER.md P0)
PINNED_BASE_OPEN_GATES = (
    "G2 identity block (#19: our BasicFileInfo, no inherited build strings / paths / GUIDs)",
    "G3 counsel (#23: C1 author string, C4 the two shipped schema corpora, C5 footer token)",
    "the element residue (#21: base slots still byte-identical to the Autodesk ancestor)",
)


def _gate_reason(gate: Dict[str, Any], g1: Dict[str, Any]) -> str:
    """The manifest sentence for a failing G1 -- worded by what the base IS."""
    kind = gate.get("base_kind")
    if kind == "pinned-composed-genesis":
        res = gate.get("residue") or {}
        return (f"P0 gates still open on the certified composed genesis base "
                f"{res.get('base_id')} (Revit {res.get('revit_release')}): "
                + "; ".join(PINNED_BASE_OPEN_GATES)
                + f". G1 element ledger against that residue: {g1.get('verdict')} "
                f"(the base's own {res.get('ours_by_composition'):,} composed elements and this "
                f"build's created content are ours). PROOF-ONLY is a label: the file is delivered.")
    if gate.get("base_is_autodesk_sample"):
        return (f"P0 genesis gate G1 fails (the base is an Autodesk sample project): "
                f"{g1.get('verdict')}. Nothing built on a sample base is a "
                "product; ship only from a certified genesis base.")
    return (f"P0 genesis gate G1 fails (a user-supplied base with no authorship census; "
            f"everything inherited from it is ledgered as the base's): {g1.get('verdict')}. "
            "Deliverability needs a certified genesis base plus TRACKER gates G2 (#19) / G3 (#23).")


def provenance_gate(out_path: str, base_path: Optional[str], *,
                    skip: bool = False) -> dict:
    """Ledger the OUTPUT against the BASE it descends from and evaluate G1.

    Three kinds of base, ledgered honestly (``base_kind``):

    * ``pinned-composed-genesis`` -- OUR certified composed base (exact sha256
      of a ``genesis_base.json`` pin).  Its authorship census
      (``rvt.frontdoor.census``) says which of its slots still carry the
      Autodesk ancestor's bytes; ONLY those are Autodesk-derived, every other
      inherited element is ours by composition, and created content is
      ``transitive-cloned`` only through lineage into that residue.  Still
      PROOF-ONLY today: TRACKER gates G2 (#19) / G3 (#23) and the residue
      (#21) are open -- said in those words, never as "sample base".
    * ``autodesk-sample`` -- a sample project: everything inherited is
      Autodesk's (v1 wording, unchanged).
    * ``user-base`` -- an explicit ``--base`` with no census: ledgered like a
      sample (nothing can be presumed ours), worded as unattributed.

    G1 PASSES only when NO Autodesk-derived expression remains; the status is
    a LABEL in the manifest -- the file is always delivered (hard rule 1).
    """
    census = _base_census(base_path)
    gate: Dict[str, Any] = {"status": "UNKNOWN", "deliverable": False,
                            "base": _abs(base_path),
                            "base_is_autodesk_sample": is_autodesk_sample(base_path),
                            "base_kind": ("pinned-composed-genesis" if census is not None
                                          else "autodesk-sample" if is_autodesk_sample(base_path)
                                          else "user-base" if base_path else None)}
    if census is not None:
        gate["residue"] = census.summary()
    if skip:
        gate["status"] = "SKIPPED (--no-provenance) => treated as NOT-DELIVERABLE"
        gate["reason"] = "provenance ledger not run; deliverability unproven"
        return gate
    P = _provenance_mod()
    if P is None:
        gate["status"] = "DEGRADED — rvt.provenance unavailable => NOT-DELIVERABLE"
        gate["reason"] = OPT.errors.get("rvt.provenance", "import failed")
        return gate
    if not base_path:
        gate["status"] = "PROOF-ONLY, NOT-DELIVERABLE"
        gate["reason"] = "no base recorded — provenance unattributable"
        return gate
    try:
        from rvt.mutate import Document
        t0 = time.time()
        cand = Document.from_file(out_path)
        base = Document.from_file(base_path)
        rep = P.provenance(cand, base, examples=0, with_units=True,
                           composed_residue_ids=(census.residue_ids
                                                 if census is not None else None))
        g1 = P.gate_G1(rep)
        gate["elapsed_s"] = round(time.time() - t0, 1)
        gate["g1"] = {"passes": bool(g1.get("passes")), "verdict": g1.get("verdict"),
                      "blocking": g1.get("blocking", [])[:12]}
        gate["provenance_totals"] = rep.get("provenance_totals")
        gate["created_elements"] = rep.get("created_elements")
        gate["modified_elements"] = rep.get("modified_elements")
        if g1.get("passes"):
            gate["status"] = "DELIVERABLE"
            gate["deliverable"] = True
        else:
            gate["status"] = "PROOF-ONLY, NOT-DELIVERABLE"
            gate["reason"] = _gate_reason(gate, g1)
    except Exception as e:                                            # noqa: BLE001
        gate["status"] = "DEGRADED — provenance run failed => NOT-DELIVERABLE"
        gate["reason"] = f"{type(e).__name__}: {e}"
    return gate


# ===========================================================================
# seed / content audit gate (create + from-ifc)
# ===========================================================================
def seed_gate(base_path: str, spec: dict) -> dict:
    """tools/seed_audit logic: NOT READY blocks; USABLE (with gaps) proceeds
    with every gap + plain-English fix recorded in the manifest."""
    sa = _seed_audit()
    if sa is None:
        return {"status": "SKIPPED", "reason": OPT.errors.get("seed_audit", "unavailable"),
                "proceed": True}
    t0 = time.time()
    rep = sa.audit(base_path, spec)
    cov = rep.get("coverage") or {}
    verdict = cov.get("verdict") or "UNKNOWN"
    rows = []
    for section in ("levels", "wall_types", "doors", "equipment", "other"):
        for r in (cov.get(section) or []):
            if r.get("status") in ("OK", "INFO"):
                continue
            rows.append({"section": section, "item": r.get("item"),
                         "status": r.get("status"), "seed": r.get("seed"),
                         "fix": r.get("fix")})
    inv = rep.get("inventory") or {}
    st = inv.get("stats") or {}
    gate = {
        "status": {"SEED READY": "PASS", "SEED USABLE WITH GAPS": "WARN",
                   "SEED NOT READY": "FAIL"}.get(verdict, "WARN"),
        "verdict": verdict, "proceed": verdict != "SEED NOT READY",
        "counts": cov.get("counts"), "gaps": rows,
        "writer_would_use": cov.get("writer_would_use"),
        "seed_inventory": {k: st.get(k) for k in ("levels", "wall_types", "symbols")},
        "elapsed_s": round(time.time() - t0, 1),
    }
    return gate


# ===========================================================================
# manifest
# ===========================================================================
def _describe_new_elements(out_path: str, ids: List[int]) -> List[dict]:
    """Re-open the WRITTEN file and describe each created element (proof it
    landed as a real, decodable Revit object)."""
    out = []
    if not ids:
        return out
    try:
        from rvt.mutate import Document
        d = Document.from_file(out_path)
        for eid in ids:
            v = d.value(eid) or {}
            name = None
            for k in ("m_text", "m_name", "m_number"):
                nv = v.get(k)
                if isinstance(nv, dict) and "value" in nv:
                    nv = nv.get("value")
                if nv:
                    name = str(nv)
                    break
            out.append({"id": eid, "class": d.class_of(eid),
                        "category": d.category_of(eid), "name": name,
                        "in_elemtable": eid in d.et_by_id})
    except Exception as e:                                            # noqa: BLE001
        out.append({"error": f"readback failed: {type(e).__name__}: {e}"})
    return out


def write_manifest(out_path: str, manifest: dict) -> str:
    mp = out_path + ".manifest.json"
    manifest.setdefault("output", {})
    manifest["output"].update({"path": _abs(out_path),
                               "bytes": os.path.getsize(out_path) if os.path.exists(out_path) else None,
                               "sha256": sha256_of(out_path)})
    with open(mp, "w") as fh:
        json.dump(manifest, fh, indent=1, default=_jsonable)
    return mp


def _print_summary(manifest: dict) -> None:
    g = manifest.get("gates", {})
    print("\n=== rvt_job DELIVERABLE MANIFEST ===")
    print(f"  mode      : {manifest.get('mode')}")
    print(f"  output    : {manifest['output']['path']} "
          f"({manifest['output'].get('bytes')} bytes)")
    for key in ("seed_audit", "structural", "validation", "identity", "base_provenance"):
        if key in g:
            st = g[key].get("status")
            extra = ""
            if key == "validation" and "errors" in g[key]:
                extra = f" (errors={g[key]['errors']} warnings={g[key]['warnings']})"
            if key == "seed_audit" and g[key].get("verdict"):
                extra = f" ({g[key]['verdict']})"
            print(f"  gate {key:16s}: {st}{extra}")
    print(f"  STATUS    : {manifest.get('status')}")
    if manifest.get("gates", {}).get("base_provenance", {}).get("reason"):
        print(f"  reason    : {manifest['gates']['base_provenance']['reason']}")
    print(f"  manifest  : {manifest['output']['path']}.manifest.json")


# ===========================================================================
# the shared gate runner (structural report already computed by the mode)
# ===========================================================================
def run_gates(mode: str, out_path: str, base_path: Optional[str], manifest: dict, *,
              structural: dict, args) -> int:
    gates = manifest.setdefault("gates", {})
    gates["structural"] = structural

    # -- validation (0 errors REQUIRED) -------------------------------------
    if args.no_validate:
        gates["validation"] = {"status": "SKIPPED", "reason": "--no-validate"}
    else:
        print("[rvt_job] validating (rvt.validate, all layers)...", flush=True)
        gates["validation"] = validation_gate(
            out_path, out_path + ".validation.json",
            layers=(args.layers.split(",") if getattr(args, "layers", None) else None),
            strict=getattr(args, "strict_validate", False))

    # -- identity ------------------------------------------------------------
    gates["identity"] = identity_gate(out_path)

    # -- base provenance / genesis status ------------------------------------
    print("[rvt_job] provenance ledger (P0 gate G1)...", flush=True)
    gates["base_provenance"] = provenance_gate(out_path, base_path,
                                               skip=args.no_provenance)

    # -- roll-up -------------------------------------------------------------
    hard_ok = (structural.get("status") == "PASS"
               and gates["validation"].get("status") in ("PASS", "SKIPPED")
               and gates["identity"].get("status") == "PASS")
    deliverable = bool(hard_ok and gates["base_provenance"].get("deliverable"))
    manifest["hard_gates_passed"] = hard_ok
    manifest["deliverable"] = deliverable
    if not hard_ok:
        failed = [k for k in ("structural", "validation", "identity")
                  if (gates.get(k, {}).get("status") if k != "structural"
                      else structural.get("status")) not in ("PASS", "SKIPPED")]
        manifest["status"] = "FAILED (" + ", ".join(failed) + ")"
    elif deliverable:
        manifest["status"] = "DELIVERABLE"
    else:
        manifest["status"] = "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)"

    manifest["elapsed_s"] = round(time.time() - manifest.pop("_t0", time.time()), 1)
    write_manifest(out_path, manifest)
    _print_summary(manifest)

    if structural.get("status") != "PASS":
        return EX_STRUCT
    if gates["validation"].get("status") not in ("PASS", "SKIPPED"):
        return EX_VALIDATE
    if gates["identity"].get("status") != "PASS":
        return EX_IDENTITY
    if args.require_deliverable and not deliverable:
        return EX_NOT_DELIVERABLE
    return EX_OK


# ===========================================================================
# (A) CREATE
# ===========================================================================
def _needs_hosting(spec: dict) -> bool:
    """True when any equipment item asks to be wall-mounted (``hostWall`` =
    a spec wall id, or ``mounting`` = wall)."""
    for e in (spec.get("equipment") or []):
        if str(e.get("hostWall") or "").strip():
            return True
        if str(e.get("mounting") or "").lower() in ("wall", "wall-mounted", "hosted"):
            return True
    return False


def build_hosted(spec: dict, doc, tpl: dict, offset_m=(0.0, 0.0),
                 panel_host=None, auto_circuits: bool = False,
                 plane_ref: str = "dummy") -> Tuple[list, list, list]:
    """The spec_to_rvt.build recipe EXTENDED with rvt.hosting: an equipment
    item carrying ``"hostWall": "<spec wall id>"`` (or ``"mounting":
    "wall"`` = the nearest wall of this run) is MOUNTED on that wall's face
    (SketchPlane + face-hosted instance) instead of placed free-standing.
    Everything else (walls, free equipment, circuits) is the certified
    spec_to_rvt path, called through the SAME Document primitives.
    """
    from rvt import hosting as H
    ox, oy = m2ft(offset_m[0]), m2ft(offset_m[1])
    default_level = tpl["levels"]["L1"]
    level_map = {}
    for lv in spec.get("levels", []):
        level_map[lv["id"]] = tpl["levels"].get(lv["id"], default_level)

    records, plans, log = [], [], []
    elements, by_name = [], {}
    walls_by_id: Dict[str, Any] = {}

    # ---- walls ------------------------------------------------------------
    wall_type = tpl.get("wall_type")
    tpl_wall = doc._template_wall(wall_type) if wall_type else None
    if wall_type is None and spec.get("walls"):
        log.append("SKIP  walls: template has no placed wall to clone")
    for w in (spec.get("walls", []) if wall_type is not None else []):
        p0 = (m2ft(w["start"][0]) + ox, m2ft(w["start"][1]) + oy, 0.0)
        p1 = (m2ft(w["end"][0]) + ox, m2ft(w["end"][1]) + oy, 0.0)
        h = m2ft(w.get("height", 3.0))
        el = doc.add_wall(default_level, wall_type, p0, p1, height=h, template_id=tpl_wall)
        elements.append(el)
        walls_by_id[str(w.get("id", ""))] = el
        log.append(f"wall  {w.get('id','?'):10s} id={el.elem_id} type={wall_type} "
                   f"{p0[:2]} -> {p1[:2]} ft, h={h:.2f} ft")

    # ---- equipment (hosted / free) ---------------------------------------
    for eq in spec.get("equipment", []):
        kind = str(eq.get("kind", "")).lower()
        if kind not in tpl["equipment"]:
            log.append(f"SKIP  {eq.get('name','?')}: unsupported kind {kind!r}")
            continue
        sym, tinst, _hosting_hint = tpl["equipment"][kind]
        if tinst is None:
            tinst = doc._template_instance(sym, doc.category_of(sym))
        x, y = eq["position"][0], eq["position"][1]
        z = float(eq.get("elevation", 0.0))
        pos = (m2ft(x) + ox, m2ft(y) + oy, m2ft(z))
        rot = math.radians(float(eq.get("rotationDeg", 0.0)))
        lvl = level_map.get(eq.get("level", "L1"), default_level)

        # -- resolve a wall-mount request -----------------------------------
        want_wall = str(eq.get("hostWall") or "").strip()
        want_mount = str(eq.get("mounting") or "").lower() in ("wall", "wall-mounted", "hosted")
        wall_el = None
        if want_wall:
            wall_el = walls_by_id.get(want_wall)
            if wall_el is None:
                log.append(f"WARN  {eq.get('name','?')}: hostWall {want_wall!r} is not a wall "
                           "created in this run -> falling back to free-standing")
        elif want_mount and walls_by_id:
            # nearest wall of this run to the equipment position
            wall_el = _nearest_wall(doc, walls_by_id, pos)
        if wall_el is not None:
            g = H.wall_geometry(doc, wall_el)
            # distance along the wall = projection of the mount point on the
            # location line; mounting height = spec elevation above wall base
            t = ((pos[0] - g.start[0]) * g.dir[0] + (pos[1] - g.start[1]) * g.dir[1])
            t = max(0.0, min(g.length, t))
            elev_above_base = max(pos[2] - g.base_z, 0.0)
            side = H.side_facing_point(doc, wall_el, pos)
            try:
                sp, inst = H.host_instance_on_wall(
                    doc, symbol_id=sym, wall=wall_el, distance_along_ft=t,
                    elevation_ft=elev_above_base, side=side,
                    level_id=lvl, plane_ref=plane_ref, template_instance_id=tinst)
                elements.extend([sp, inst])
                by_name[str(eq.get("name", ""))] = (inst, kind)
                log.append(f"equip {eq.get('name','?'):12s} {kind:11s} id={inst.elem_id} symbol={sym} "
                           f"MOUNTED on wall {g.wall_id} (SketchPlane {sp.elem_id}, "
                           f"face tag {side}, plane_ref={plane_ref}) {t:.2f} ft along, "
                           f"{elev_above_base:.2f} ft above base")
                continue
            except Exception as e:                                    # noqa: BLE001
                log.append(f"WARN  {eq.get('name','?')}: hosting failed ({type(e).__name__}: "
                           f"{e}) -> falling back to free-standing")
        # -- free-standing ---------------------------------------------------
        host_id = int(panel_host) if (kind == "panelboard" and panel_host is not None) else None
        el = doc.add_family_instance(sym, lvl, position=pos, rotation=rot,
                                     host_id=host_id, template_instance_id=tinst)
        elements.append(el)
        by_name[str(eq.get("name", ""))] = (el, kind)
        log.append(f"equip {eq.get('name','?'):12s} {kind:11s} id={el.elem_id} symbol={sym} "
                   f"at ({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.2f}) ft rot={eq.get('rotationDeg',0)}deg "
                   f"{'host='+str(host_id) if host_id else 'free-standing'}")

    # ---- circuits (same recipe as spec_to_rvt) ---------------------------
    circuits = list(spec.get("circuits") or [])
    if auto_circuits and not circuits:
        panels = [n for n, (e, k) in by_name.items() if k == "panelboard"]
        loads = [n for n, (e, k) in by_name.items() if k in ("transformer", "switchboard")]
        if panels:
            for i, ln in enumerate(loads, 1):
                circuits.append({"panel": panels[0], "load": ln, "number": str(i),
                                 "description": f"{ln} feeder"})
    for i, c in enumerate(circuits, 1):
        pn, ln = str(c.get("panel", "")), str(c.get("load", ""))
        if pn not in by_name or ln not in by_name:
            log.append(f"SKIP  circuit {pn}->{ln}: both ends must be created in this run")
            continue
        cel = doc.add_circuit(by_name[pn][0], by_name[ln][0],
                              number=str(c.get("number", i)),
                              description=c.get("description") or f"{ln} feeder",
                              rating=c.get("rating"), poles=c.get("poles"))
        elements.append(cel)
        log.append(f"circ  {c.get('number', i)!s:6} id={cel.elem_id} panel {pn} -> load {ln}")

    # ---- serialize AFTER wiring -------------------------------------------
    for el in elements:
        records.append(dict(doc.serialize(el)))
        plans.append(el.elemrec)
    return records, plans, log


def _nearest_wall(doc, walls_by_id: dict, pos):
    from rvt import hosting as H
    best, bd = None, float("inf")
    for wel in walls_by_id.values():
        try:
            g = H.wall_geometry(doc, wel)
        except Exception:
            continue
        # distance from point to the wall segment
        sx, sy, _ = g.start
        dx, dy = g.dir
        t = max(0.0, min(g.length, (pos[0] - sx) * dx + (pos[1] - sy) * dy))
        px, py = sx + dx * t, sy + dy * t
        d = math.hypot(pos[0] - px, pos[1] - py)
        if d < bd:
            best, bd = wel, d
    return best


def _plan_create(spec: dict, base_path: str, template_key: str, args) -> Tuple[list, list, list, dict]:
    """Return (records, plans, log, template_cfg) via the certified builder,
    switching to the hosting-extended builder when the spec asks for it."""
    s2r = _spec_to_rvt()
    if s2r is None:
        raise RuntimeError("spec_to_rvt unavailable: " + OPT.errors.get("spec_to_rvt", "?"))
    from rvt.mutate import Document
    offset = tuple(args.offset_m)
    if _needs_hosting(spec):
        doc = Document.from_file(base_path)
        # named research template => its proven ids; else discover from the base
        use_named = (not args.base) and template_key in s2r.TEMPLATES
        tpl = dict(s2r.TEMPLATES[template_key]) if use_named else s2r.discover_template(doc, spec)
        if args.wall_type:
            tpl["wall_type"] = int(args.wall_type)
        records, plans, log = build_hosted(spec, doc, tpl, offset, args.panel_host,
                                           args.auto_circuits, plane_ref=args.plane_ref)
        return records, plans, log, tpl
    # certified spec_to_rvt path (byte-identical to the accepted proofs)
    if args.base:
        records, plans, log = s2r.build(spec, template_key, offset, args.panel_host,
                                        template_rvt=base_path,
                                        wall_type_override=args.wall_type,
                                        auto_circuits=args.auto_circuits)
        tpl = {"note": "discovered from --base via spec_to_rvt.discover_template"}
    else:
        try:
            # named template: the curated, viewer-certified ids (Document.load
            # reads the pre-extracted research corpus)
            records, plans, log = s2r.build(spec, template_key, offset, args.panel_host,
                                            wall_type_override=args.wall_type,
                                            auto_circuits=args.auto_circuits)
        except (FileNotFoundError, OSError):
            # no extracted corpus on this machine -> read the sample file directly
            records, plans, log = s2r.build(spec, template_key, offset, args.panel_host,
                                            template_rvt=base_path,
                                            wall_type_override=args.wall_type,
                                            auto_circuits=args.auto_circuits)
        tpl = {k: v for k, v in s2r.TEMPLATES[template_key].items() if k != "sample"}
    return records, plans, log, tpl


def create_from_spec(spec: dict, spec_source: str, args, *, mode: str = "create") -> int:
    """The CREATE pipeline shared by `create` and `from-ifc`."""
    from rvt.commit import commit_new_elements, verify_written
    t0 = time.time()
    out_path = os.path.abspath(args.out)
    base_path = resolve_base(args.base, args.template)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    manifest: Dict[str, Any] = {
        "tool": "rvt_job", "tool_version": TOOL_VERSION, "mode": mode,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {"spec": _abs(spec_source), "base": _abs(base_path),
                   "template": None if args.base else args.template,
                   "offset_m": list(args.offset_m), "auto_circuits": bool(args.auto_circuits),
                   "wall_type_override": args.wall_type, "panel_host": args.panel_host,
                   "hosting_requested": _needs_hosting(spec)},
        "project": (spec.get("project") or {}),
        "spec_counts": {k: len(spec.get(k) or []) for k in
                        ("levels", "walls", "equipment", "circuits", "doors", "rooms", "floors")},
        "base": {"path": _abs(base_path), "sha256": sha256_of(base_path),
                 "is_autodesk_sample": is_autodesk_sample(base_path),
                 "history_head_guid": None},
        "_t0": t0,
    }
    if mode == "from-ifc":
        manifest["inputs"]["ifc"] = _abs(getattr(args, "ifc", None))

    # ---- 1. seed / content audit -----------------------------------------
    print(f"[rvt_job] seed audit of base {os.path.basename(base_path)} vs spec...", flush=True)
    sg = seed_gate(base_path, spec)
    manifest.setdefault("gates", {})["seed_audit"] = sg
    print(f"[rvt_job]   verdict: {sg.get('verdict')} {sg.get('counts') or ''}")
    for r in (sg.get("gaps") or [])[:20]:
        print(f"[rvt_job]     [{r['status']}] {r['section']}: {r['item']}"
              + (f"  FIX: {r['fix']}" if r.get("fix") else ""))
    if not sg.get("proceed") and not args.allow_not_ready:
        manifest["status"] = "FAILED (seed audit: SEED NOT READY)"
        _write_stub_manifest(out_path, manifest)
        print("[rvt_job] SEED NOT READY -> aborting (pass --allow-not-ready to force). "
              "See the gap list above / in the manifest.", file=sys.stderr)
        return EX_PLAN

    # ---- 2. build --------------------------------------------------------
    print("[rvt_job] planning elements...", flush=True)
    try:
        records, plans, log, tpl = _plan_create(spec, base_path, args.template, args)
    except Exception as e:
        traceback.print_exc()
        manifest["status"] = f"FAILED (planning: {type(e).__name__}: {e})"
        _write_stub_manifest(out_path, manifest)
        return EX_PLAN
    for line in log:
        print("  " + line)
    manifest["build"] = {"planned": len(plans), "log": log, "template": tpl}
    if not records:
        manifest["status"] = "FAILED (nothing to write — spec produced no supported elements)"
        _write_stub_manifest(out_path, manifest)
        print("[rvt_job] nothing to write", file=sys.stderr)
        return EX_PLAN

    # ---- 3. commit with OUR identity (GUID coherent with History[0]) ------
    hist0 = history_head_guid(base_path)
    manifest["base"]["history_head_guid"] = hist0
    print(f"[rvt_job] committing {len(plans)} element(s)...", flush=True)
    rep = commit_new_elements(base_path, out_path, records, plans,
                              identity={"document_guid": hist0} if hist0 else {})
    ids = [p.elem_id for p in plans]
    manifest["commit"] = {"elemtable_before": rep.elemtable_count_before,
                          "elemtable_after": rep.elemtable_count_after,
                          "watermark_after": rep.watermark_after,
                          "partition": rep.partition, "new_ids": ids}
    manifest["elements"] = {"created": _describe_new_elements(out_path, ids)}

    # ---- 4. structural proof ----------------------------------------------
    print("[rvt_job] structural verification...", flush=True)
    v = verify_written(out_path, ids)
    structural = structural_gate_from_written(v, ids)

    # ---- 5..7 gates + manifest ---------------------------------------------
    return run_gates(mode, out_path, base_path, manifest, structural=structural, args=args)


def _write_stub_manifest(out_path: str, manifest: dict) -> None:
    """Manifest for a run that never wrote the .rvt (early failure)."""
    mp = out_path + ".manifest.json"
    manifest.setdefault("output", {"path": _abs(out_path), "written": False})
    manifest.pop("_t0", None)
    try:
        with open(mp, "w") as fh:
            json.dump(manifest, fh, indent=1, default=_jsonable)
        print(f"[rvt_job] manifest: {mp}")
    except OSError:
        pass


def cmd_create(args) -> int:
    with open(args.spec) as fh:
        spec = json.load(fh)
    return create_from_spec(spec, args.spec, args, mode="create")


# ===========================================================================
# (C) FROM-IFC — Claude-Design path
# ===========================================================================
def cmd_from_ifc(args) -> int:
    i2s = _ifc_to_spec()
    if i2s is None:
        print("[rvt_job] ifc_to_spec unavailable: "
              + OPT.errors.get("ifc_to_spec", "?"), file=sys.stderr)
        return EX_ERR
    print(f"[rvt_job] extracting spec from {args.ifc} (ifc_to_spec)...", flush=True)
    spec = i2s.extract(args.ifc)
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    spec_out = args.spec_out or (out_path + ".spec.json")
    with open(spec_out, "w") as fh:
        json.dump(spec, fh, indent=2)
    kinds: Dict[str, int] = {}
    for e in spec.get("equipment", []):
        kinds[e.get("kind")] = kinds.get(e.get("kind"), 0) + 1
    print(f"[rvt_job]   derived spec: {len(spec['levels'])} level(s), {len(spec['walls'])} wall(s), "
          f"{len(spec['equipment'])} equipment {kinds} -> {spec_out}")
    args.base = args.base            # explicit; template default applies otherwise
    rc = create_from_spec(spec, spec_out, args, mode="from-ifc")
    return rc


# ===========================================================================
# (B) EDIT — ops.json applied to an existing project
# ===========================================================================
OP_MANIPULATE = {"delete", "rename", "rename-panel", "set-mark", "set-level",
                 "set-param", "move", "retype"}
OP_CREATE = {"add-instance", "add-circuit"}


def _op_key(op: dict) -> str:
    return str(op.get("op") or op.get("type") or "").strip().lower()


def plan_edit_ops(doc, ops: List[dict]) -> Tuple[list, list, list, list, list]:
    """Turn ops into (manipulate_plans, add_ops, log, edited_ids, deleted_ids).
    Fails LOUDLY (raises) on an unplannable op — a partial edit is worse
    than none.  DependentsError propagates with its full report."""
    from rvt import manipulate as M
    plans, adds, log, edited, deleted = [], [], [], [], []
    for n, op in enumerate(ops, 1):
        k = _op_key(op)
        if k == "delete":
            eid = int(op["id"])
            pl = M.delete_element(doc, eid, cascade=bool(op.get("cascade", False)))
            plans.append(pl)
            gone = list(getattr(pl, "ids_to_remove", []) or [eid])
            deleted.extend(gone)
            log.append(f"op{n} delete   id={eid} cascade={bool(op.get('cascade'))} "
                       f"-> removes {len(gone)} element(s)")
        elif k in ("rename", "rename-panel"):
            eid = int(op["id"])
            plans.append(M.rename_panel(doc, eid, str(op["name"])))
            edited.append(eid)
            log.append(f"op{n} rename   id={eid} panel name -> {op['name']!r}")
        elif k == "set-mark":
            eid = int(op["id"])
            plans.append(M.set_mark(doc, eid, str(op["mark"])))
            edited.append(eid)
            log.append(f"op{n} set-mark id={eid} mark -> {op['mark']!r}")
        elif k == "set-level":
            eid = int(op["id"])
            ft = float(op["elevation_ft"] if "elevation_ft" in op
                       else m2ft(op["elevation_m"]))
            plans.append(M.set_level_elevation(doc, eid, ft))
            edited.append(eid)
            log.append(f"op{n} set-level id={eid} elevation -> {ft:.3f} ft")
        elif k == "set-param":
            eid = int(op["id"])
            plans.append(M.set_param(doc, eid, int(op["param_id"]), op["value"]))
            edited.append(eid)
            log.append(f"op{n} set-param id={eid} param {op['param_id']} -> {op['value']!r}")
        elif k == "move":
            eid = int(op["id"])
            rot = math.radians(float(op["rotation_deg"])) if op.get("rotation_deg") is not None else None
            if "delta" in op:
                xyz = tuple(float(c) for c in op["delta"])
                plans.append(M.move_instance(doc, eid, xyz, rotation=rot, delta=True))
                log.append(f"op{n} move     id={eid} delta {xyz} ft"
                           + (f" rot {op['rotation_deg']}deg" if rot is not None else ""))
            else:
                xyz = tuple(float(c) for c in (op.get("to") or op.get("position_ft")))
                plans.append(M.move_instance(doc, eid, xyz, rotation=rot, delta=False))
                log.append(f"op{n} move     id={eid} to {xyz} ft"
                           + (f" rot {op['rotation_deg']}deg" if rot is not None else ""))
            edited.append(eid)
        elif k == "retype":
            eid = int(op["id"])
            plans.append(M.retype_instance(doc, eid, int(op["symbol"]),
                                           allow_family_change=bool(op.get("allow_family_change"))))
            edited.append(eid)
            log.append(f"op{n} retype   id={eid} -> symbol {op['symbol']}")
        elif k in OP_CREATE:
            adds.append(op)
            log.append(f"op{n} {k:8s} deferred to the create stage")
        else:
            raise ValueError(f"op #{n}: unknown op {k!r} (allowed: "
                             f"{sorted(OP_MANIPULATE | OP_CREATE)})")
    return plans, adds, log, edited, deleted


def apply_add_ops(src_path: str, out_path: str, adds: List[dict], *,
                  document_guid: Optional[str]) -> Tuple[list, list, dict]:
    """Stage 2 of an edit: add-instance / add-circuit ops via rvt.mutate on
    the (already manipulated) intermediate file. Returns (new_ids, log, verify)."""
    from rvt.commit import commit_new_elements, verify_written
    from rvt.mutate import Document
    doc = Document.from_file(src_path)
    lv = doc.levels()
    default_level = None
    for l in lv:
        if str(l.get("name") or "").strip().lower() == "level 1":
            default_level = l["id"]
    if default_level is None and lv:
        default_level = lv[0]["id"]
    log, els, by_name = [], [], {}
    for op in adds:
        k = _op_key(op)
        if k == "add-instance":
            sym = int(op["symbol"])
            lvl = int(op["level"]) if op.get("level") is not None else default_level
            pos_ft = op.get("position_ft")
            if pos_ft is None and op.get("position_m") is not None:
                pos_ft = [m2ft(c) for c in op["position_m"]]
            pos = tuple(float(c) for c in (pos_ft or (0.0, 0.0, 0.0)))
            if len(pos) == 2:
                pos = (pos[0], pos[1], 0.0)
            rot = math.radians(float(op.get("rotation_deg", 0.0)))
            tinst = op.get("template_instance")
            if tinst is None:
                tinst = doc._template_instance(sym, doc.category_of(sym))
            el = doc.add_family_instance(sym, lvl, position=pos, rotation=rot,
                                         host_id=(int(op["host"]) if op.get("host") is not None else None),
                                         template_instance_id=int(tinst))
            els.append(el)
            by_name[str(op.get("name") or el.elem_id)] = (el, "instance")
            log.append(f"add-instance id={el.elem_id} symbol={sym} level={lvl} "
                       f"at ({pos[0]:.2f},{pos[1]:.2f},{pos[2]:.2f}) ft")
        elif k == "add-circuit":
            pn, ln = str(op.get("panel", "")), str(op.get("load", ""))
            if pn not in by_name or ln not in by_name:
                log.append(f"SKIP add-circuit {pn}->{ln}: both ends must be add-instance "
                           "names created in THIS ops run (circuiting existing "
                           "elements needs in-place connector edits — phase 2)")
                continue
            cel = doc.add_circuit(by_name[pn][0], by_name[ln][0],
                                  number=str(op.get("number", 1)),
                                  description=op.get("description") or f"{ln} feeder",
                                  rating=op.get("rating"), poles=op.get("poles"))
            els.append(cel)
            log.append(f"add-circuit id={cel.elem_id} panel {pn} -> load {ln}")
    if not els:
        return [], log, {}
    records = [dict(doc.serialize(e)) for e in els]
    plans = [e.elemrec for e in els]
    commit_new_elements(src_path, out_path, records, plans,
                        identity={"document_guid": document_guid} if document_guid else {})
    ids = [p.elem_id for p in plans]
    return ids, log, verify_written(out_path, ids)


def cmd_edit(args) -> int:
    in_path = os.path.abspath(args.file)
    if not os.path.exists(in_path):
        print(f"[rvt_job] input .rvt not found: {in_path}", file=sys.stderr)
        return EX_ERR
    # plan / commit / verify / validate under the INPUT file's own release
    # (issue #70): a Revit 2025/2024 project keeps its release's framing and
    # schema and the output declares the input's release; a native file enters
    # no context; joins the front door's context when called from --rvt --edit
    from rvt.frontdoor.release_ctx import enter_host_release
    with contextlib.ExitStack() as stack:
        note = enter_host_release(stack, in_path)
        if note:
            print(f"[rvt_job] warning: {note}", file=sys.stderr)
        return _cmd_edit(args, in_path, note)


def _cmd_edit(args, in_path: str, release_note: Optional[str]) -> int:
    from rvt import manipulate as M
    from rvt import versions as V
    from rvt.mutate import Document
    t0 = time.time()
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(args.ops) as fh:
        ops = json.load(fh)
    if isinstance(ops, dict):
        ops = ops.get("ops") or []
    if not isinstance(ops, list) or not ops:
        print("[rvt_job] ops.json must be a non-empty list of ops (or {\"ops\": [...]})",
              file=sys.stderr)
        return EX_PLAN

    manifest: Dict[str, Any] = {
        "tool": "rvt_job", "tool_version": TOOL_VERSION, "mode": "edit",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {"file": in_path, "ops": _abs(args.ops), "op_count": len(ops)},
        "base": {"path": in_path, "sha256": sha256_of(in_path),
                 "is_autodesk_sample": is_autodesk_sample(in_path),
                 "release": V.detect_release(in_path)},
        "_t0": t0,
    }
    if release_note:
        manifest["base"]["release_note"] = release_note
    hist0 = history_head_guid(in_path)
    manifest["base"]["history_head_guid"] = hist0

    # ---- plan every op (fail loudly on the first unplannable one) ----------
    print(f"[rvt_job] planning {len(ops)} op(s) against {os.path.basename(in_path)}...", flush=True)
    doc = Document.from_file(in_path)
    try:
        plans, adds, log, edited, deleted = plan_edit_ops(doc, ops)
    except M.DependentsError as e:
        rep = getattr(e, "report", {}) or {}
        manifest["status"] = "FAILED (delete has dependents; pass cascade:true or fix the model)"
        manifest["dependents_report"] = {
            "elem_id": getattr(e, "elem_id", None),
            "dependents": (rep.get("dependents") or [])[:60],
            "referrers": (rep.get("referrers") or [])[:60],
            "cascade_count": len(rep.get("cascade_ids") or []),
        }
        _write_stub_manifest(out_path, manifest)
        print(f"[rvt_job] {manifest['status']}", file=sys.stderr)
        return EX_PLAN
    except Exception as e:
        traceback.print_exc()
        manifest["status"] = f"FAILED (planning: {type(e).__name__}: {e})"
        _write_stub_manifest(out_path, manifest)
        return EX_PLAN
    for line in log:
        print("  " + line)
    manifest["edit"] = {"ops": ops, "log": log, "edited_ids": edited,
                        "deleted_ids": deleted, "created_ids": [],
                        "plans": [pl.to_json() for pl in plans],
                        "stages": []}

    # ---- stage 1: every manipulate plan in ONE commit --------------------
    src_for_adds = in_path
    if plans:
        print(f"[rvt_job] committing {len(plans)} manipulate plan(s) (ONE commit)...", flush=True)
        rep = M.commit_plans(in_path, out_path, plans)
        manifest["edit"]["stages"].append({"stage": "manipulate", "plans": len(plans),
                                          "removed_ids": rep.removed_ids,
                                          "elemtable_before": rep.elemtable_count_before,
                                          "elemtable_after": rep.elemtable_count_after})
        src_for_adds = out_path

    # ---- stage 2: add-* ops via rvt.mutate on the manipulated result -----
    new_ids: List[int] = []
    add_verify: dict = {}
    if adds:
        print(f"[rvt_job] committing {len(adds)} add op(s) (rvt.mutate)...", flush=True)
        if src_for_adds == out_path:
            staging = out_path + ".stage1.rvt"
            shutil.copyfile(out_path, staging)
        else:
            staging = src_for_adds
        try:
            new_ids, add_log, add_verify = apply_add_ops(staging, out_path, adds,
                                                        document_guid=hist0)
        finally:
            if staging.endswith(".stage1.rvt") and os.path.exists(staging):
                os.remove(staging)
        for line in add_log:
            print("  " + line)
        manifest["edit"]["log"] += add_log
        manifest["edit"]["created_ids"] = new_ids
        manifest["edit"]["stages"].append({"stage": "create", "new_ids": new_ids})
        manifest["elements"] = {"created": _describe_new_elements(out_path, new_ids)}
    if not plans and not adds:
        print("[rvt_job] no effective ops -> nothing written", file=sys.stderr)
        _write_stub_manifest(out_path, manifest)
        return EX_PLAN

    # ---- identity: manipulate never touches BasicFileInfo -> scrub it now.
    # (commit_new_elements already scrubbed with the coherent GUID if adds ran)
    if not adds:
        print("[rvt_job] asserting OUR identity (BasicFileInfo scrub)...", flush=True)
        scrub_identity(out_path, document_guid=hist0)

    # ---- structural proof -------------------------------------------------
    print("[rvt_job] structural verification...", flush=True)
    v = M.verify_manipulated(out_path, deleted_ids=deleted, edited_ids=edited + new_ids)
    structural = structural_gate_from_manipulated(v)
    if add_verify:
        structural["create_stage"] = structural_gate_from_written(add_verify, new_ids)
        if structural["create_stage"]["status"] != "PASS":
            structural["status"] = "FAIL"

    return run_gates("edit", out_path, in_path, manifest, structural=structural, args=args)


# ===========================================================================
# CLI
# ===========================================================================
def _add_common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--no-validate", action="store_true",
                    help="skip rvt.validate (NOT a shippable run; debugging only)")
    ap.add_argument("--layers", default=None,
                    help="validator layers, comma list (default: structure,consistency,semantic)")
    ap.add_argument("--strict-validate", action="store_true",
                    help="validator strict mode (one-way connector links etc. become errors)")
    ap.add_argument("--no-provenance", action="store_true",
                    help="skip the P0 provenance ledger (status becomes NOT-DELIVERABLE/unproven)")
    ap.add_argument("--require-deliverable", action="store_true",
                    help="exit non-zero (6) unless the output is DELIVERABLE (genesis base)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="rvt_job",
                                 description="THE FRONT DOOR: spec / IFC / ops in -> a "
                                             "gated, validated .rvt + deliverable manifest out.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Modes:\n  create   --spec job.json [--base base.rvt] -o out.rvt\n"
                                        "  edit     in.rvt --ops ops.json -o out.rvt\n"
                                        "  from-ifc design.ifc [--base base.rvt] -o out.rvt")
    sub = ap.add_subparsers(dest="mode", required=True)

    # ---- create ----------------------------------------------------------
    pc = sub.add_parser("create", help="build a project from a spec.json")
    pc.add_argument("--spec", required=True, help="the building/room spec.json")
    pc.add_argument("-o", "--out", required=True, help="output .rvt")
    pc.add_argument("--base", default=None,
                    help="base .rvt to author against (a firm seed). Default: the "
                         "research template's sample => PROOF-ONLY output.")
    _add_create_flags(pc)
    _add_common(pc)

    # ---- from-ifc ------------------------------------------------------------
    pi = sub.add_parser("from-ifc", help="Claude-Design IFC -> spec -> .rvt")
    pi.add_argument("ifc", help="the (hardened) IFC exported by Claude Design")
    pi.add_argument("-o", "--out", required=True, help="output .rvt")
    pi.add_argument("--base", default=None, help="base .rvt (default: research template sample)")
    pi.add_argument("--spec-out", default=None, help="where to save the derived spec.json "
                                                     "(default: <out>.spec.json)")
    _add_create_flags(pi)
    _add_common(pi)

    # ---- edit ------------------------------------------------------------------
    pe = sub.add_parser("edit", help="apply ops.json to an existing .rvt")
    pe.add_argument("file", help="input .rvt")
    pe.add_argument("--ops", required=True, help="ops.json: list of {op: ..., ...}")
    pe.add_argument("-o", "--out", required=True, help="output .rvt")
    _add_common(pe)
    return ap


def _add_create_flags(p: argparse.ArgumentParser) -> None:
    tpl_choices = None
    try:
        s = _spec_to_rvt()
        tpl_choices = list(s.TEMPLATES) if s else None
    except Exception:
        tpl_choices = None
    p.add_argument("--template", default="rmebasicsampleproject", choices=tpl_choices,
                   help="named research template (used only when --base is absent)")
    p.add_argument("--offset-m", nargs=2, type=float, default=[10.0, -25.0], metavar=("X", "Y"),
                   help="place the spec origin at this world offset (metres)")
    p.add_argument("--auto-circuits", action="store_true",
                   help="one circuit per transformer/switchboard off the first panelboard")
    p.add_argument("--wall-type", type=int, default=None, help="override the wall type id")
    p.add_argument("--panel-host", default=None,
                   help="SketchPlane id to face-host panelboards on (spec_to_rvt free path)")
    p.add_argument("--plane-ref", default="dummy", choices=("dummy", "geom"),
                   help="face plane style when the spec asks for wall-mounted gear "
                        "(hostWall): dummy = regeneration-independent (default), "
                        "geom = true GeomOnPlaneRef association")
    p.add_argument("--allow-not-ready", action="store_true",
                   help="proceed even when the seed audit says SEED NOT READY")


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        if args.mode == "create":
            return cmd_create(args)
        if args.mode == "from-ifc":
            return cmd_from_ifc(args)
        if args.mode == "edit":
            return cmd_edit(args)
    except KeyboardInterrupt:
        return EX_ERR
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        return EX_ERR
    ap.error("unknown mode")
    return EX_ERR


if __name__ == "__main__":
    raise SystemExit(main())
