#!/usr/bin/env python
"""bisect_instance_bug.py -- THE MINIMAL BISECTION LADDER for the product-path
bug (instbug stream, 2026-08-04/05).

THE BUG.  Files that LOAD MULTIPLE family documents or PLACE INSTANCES onto
the genesis lineage trip Autodesk's open-time consistency audit
(Revit-DocumentCorruption, extractor exit -1073742517) while the same
operations on SAMPLE bases pass.  The user's own from-scratch demo
(``experiments/acceptance/DEMO_250v_room.rvt`` = certified G_ABPD + 6 panel
families + 6 placed instances, built by ``tools/frontdoor.py author
--prompt "an electrical room rated for 250V with 6 panels"``) failed on it.
The demo's ``_stages/`` ladder bundles the axes; THIS tool builds the finer
ladder that separates them, one certified-base variable per rung:

    rung        base    families  instances  walls   the ONE axis it isolates
    ---------   ------  --------  ---------  -----   -------------------------------
    BX_f1       G_ABPD  1         0          0       single family-document append
    BX_f2       G_ABPD  2         0          0       the SECOND family document (the
                                                     narrowest open axis: N>1 loads,
                                                     no instances)
    BX_f6       G_ABPD  6         0          0       the demo's full load chain alone
    BX_f1i1     G_ABPD  1         1          0       ONE placed instance (the demo's
                                                     own placement path) at N=1
    BX_f2i2     G_ABPD  2         2          0       instance scale point
    BX_f6i6     G_ABPD  6         6          0       THE DEMO SHAPE REBUILT
    BX_w_f1i1   G_ABPD  1         1          1       the full product shape; the wall
                                                     is the CERTIFIED W1 recipe
                                                     (add_wall + baked B-rep solid)
    SX_f6i6     rst     6         6          0       CROSS-CHECK: the same code path
                                                     on the Autodesk sample base --
                                                     isolates base-lineage vs
                                                     operation

EVERY rung is built by the demo's OWN code path, imported and never edited:
``rvt.frontdoor.prompt_intent.prompt_to_intent`` (the same prompt) ->
``tools/ifc_intent.py stage_load`` (rvt.famgen.loader chained,
``place=False``) -> ``tools/ifc_intent.py stage_equipment``
(``rvt.mutate.Document.add_family_instance`` on the frontdoor's
``ConstructedSpecimens`` template + ``rvt.commit.commit_new_elements``).
The wall in BX_w_f1i1 is the ONLY foreign ingredient and it is the certified
one: W1's mechanism (``rvt.mutate.add_wall`` R5-specimen clone, mode 'min',
seq-103 GElement B-rep baked via ``rvt.regadd.substitute_elements`` -- the
W1_gabpd_wall_solid PASS+RENDERS recipe), applied in the product's own
L -> W -> E order.

Every emitted rung is verified HERE (the accounting the orchestrator reads):
``rvt.validate`` 0 errors; ``rvt.famload.four_registry_census``
(save units / ContentDocuments / ContentTable / FamilyMgr) + delta vs the
rung's immediate parent; Global/PartitionTable rows; the Contents
DocumentStorageIndex counters; ElemTable adds; ``rvt.reduce_law.element_diff``
byte-strict survivor check (adds only -- 0 removed, 0 modified);
per-stream byte accounting vs the parent; and ``rvt.regdiff``
registration_of the placed instance + the unit-0 run law.

USAGE (repo root)::

    .venv/bin/python tools/bisect_instance_bug.py build            # all rungs
    .venv/bin/python tools/bisect_instance_bug.py build --only BX_f2,BX_f1i1
    .venv/bin/python tools/bisect_instance_bug.py verify           # re-run accounting
    .venv/bin/python tools/bisect_instance_bug.py stage            # probe_batch gate +
                                                                   # control G_ABPD copy

Territory: this file, ``experiments/instbug/**``, ``tests/test_instbug.py``,
``docs/inbox/instbug-bisect.md``.  Reads (never writes): the certified bases,
R5 (specimen source), the demo artifacts.  No Autodesk install dirs, no
donors; the reduction law holds by construction (pure adds).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

PROMPT = "an electrical room rated for 250V with 6 panels"      # the user's demo prompt
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
R5 = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "instbug")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
DEMO_FILE = os.path.join(ROOT, "experiments", "acceptance", "DEMO_250v_room.rvt")

#: W1's certified wall ingredients (experiments/render/g12/build_g12_probes.py,
#: W1_gabpd_wall_solid = viewer PASS + RENDERS on G_ABPD).
FINISH_MATERIAL = 600660                       # 'GEN Concrete, Cast-in-Place' (ours)
WALL_LINE_FT = ((4.0, -12.0), (24.0, -12.0))   # 20 ft, clear of the panel row at y=0
WALL_HEIGHT_FT = 12.0

#: ladder order = maximum information first (the staging / reading order)
LADDER = ("BX_f2", "BX_f1i1", "SX_f6i6", "BX_f6i6", "BX_f2i2",
          "BX_f6", "BX_f1", "BX_w_f1i1")

#: rung -> (base_path, n_families, n_instances, walls)
RUNG_SPEC: Dict[str, Tuple[str, int, int, int]] = {
    "BX_f1":     (G_ABPD, 1, 0, 0),
    "BX_f2":     (G_ABPD, 2, 0, 0),
    "BX_f6":     (G_ABPD, 6, 0, 0),
    "BX_f1i1":   (G_ABPD, 1, 1, 0),
    "BX_f2i2":   (G_ABPD, 2, 2, 0),
    "BX_f6i6":   (G_ABPD, 6, 6, 0),
    "BX_w_f1i1": (G_ABPD, 1, 1, 1),
    "SX_f6i6":   (RST,    6, 6, 0),
}


def log(msg: str) -> None:
    print(f"[instbug] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:
        return p


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def _room():
    """tools/ifc_intent.py as a module (the demo's build code, never edited)."""
    import ifc_intent as T
    return T


# ===========================================================================
# the intent (the demo's own prompt, deterministically re-derived)
# ===========================================================================

def demo_model():
    from rvt.frontdoor import prompt_intent as PP
    model, parsed = PP.prompt_to_intent(PROMPT)
    tags = [e.tag for e in model.equipment]
    if tags != [f"PP-{i}" for i in range(1, 7)]:
        raise RuntimeError(f"prompt no longer resolves to 6 panels: {tags}")
    return model


def truncate_model(model, n: int):
    """The first ``n`` panels of the demo intent (deep copy; the load order
    for a feeder-free intent is sorted tags = PP-1..PP-n, so a truncation IS
    a prefix of the demo's own chain)."""
    m = copy.deepcopy(model)
    keep = {e.tag for e in m.equipment[:n]}
    m.equipment = [e for e in m.equipment if e.tag in keep]
    m.family_plans = [p for p in m.family_plans if p.tag in keep]
    m.feeders = [ed for ed in m.feeders
                 if ed.target in keep and (ed.source in keep or ed.kind == "service")]
    return m


# ===========================================================================
# build steps (the demo's own stage functions)
# ===========================================================================

def build_chain(base_path: str, chain_dir: str, model) -> Dict[str, Any]:
    """The demo's stage L: chain rvt.famgen.loader over all six panels,
    place=False, onto ``base_path``.  Returns the stage record (with the
    non-JSON ``_loaded`` products kept for stage E)."""
    T = _room()
    os.makedirs(chain_dir, exist_ok=True)
    lrec = T.stage_load(model, base_path, chain_dir, symbol_solid=True)
    if lrec.get("blocker"):
        raise RuntimeError(f"stage_load blocked: {lrec['blocker']}")
    if lrec.get("n_loaded") != lrec.get("n_planned"):
        raise RuntimeError(f"stage_load incomplete: {lrec.get('n_loaded')}/{lrec.get('n_planned')}")
    return lrec


def chain_file(chain_dir: str, i: int, tag: str) -> str:
    return os.path.join(chain_dir, f"stage_L{i}_{tag.lower().replace('-', '')}.rvt")


def place_instances(model_n, src_rvt: str, out_path: str, base_path: str,
                    loaded_n: Dict[str, Any]) -> Dict[str, Any]:
    """The demo's stage E: ConstructedSpecimens template +
    Document.add_family_instance + commit_new_elements."""
    T = _room()
    from rvt.frontdoor import standalone as SA
    specimens = SA.ConstructedSpecimens(SA.CONSTRUCTED, base_path=base_path)
    erec, out = T.stage_equipment(model_n, src_rvt, out_path, specimens, loaded_n)
    if not out:
        raise RuntimeError(f"stage_equipment did not emit: "
                           f"{erec.get('blocker') or erec.get('error')}")
    return erec


def add_certified_wall(src_rvt: str, out_path: str, workdir: str) -> Dict[str, Any]:
    """ONE created wall by the CERTIFIED W1 mechanism (viewer PASS + RENDERS
    on G_ABPD): rvt.mutate.add_wall on an R5 specimen clone (mode 'min') +
    the seq-103 GElement B-rep solid baked in place."""
    T = _room()
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    from rvt.regadd import substitute_elements
    from rvt.render.brep import CLASS_GELEMENT, wall_rep_from_object

    specimens = T.SpecimenSet(R5)
    doc = Document.from_file(src_rvt)
    inj = specimens.inject_into(doc)
    wt = T._wall_type_of_base(doc)
    lvl = T._pick_level(doc, 0.0)
    if specimens.wall_id is None or wt is None:
        raise RuntimeError("no wall specimen / wall type available")
    p0, p1 = WALL_LINE_FT
    el = doc.add_wall(lvl, wt, p0, p1, height=WALL_HEIGHT_FT,
                      template_id=specimens.wall_id)
    clean = T._clean_wall_clone(el, doc, specimens.wall_id, mode="min")
    dangling = doc.check_references(el)
    recs = doc.serialize(el)
    if recs is None:
        raise RuntimeError("rvt.encode unavailable")
    tmp = os.path.join(workdir, "_wall_dummy.tmp.rvt")
    crep = commit_new_elements(src_rvt, tmp, [dict(recs)], [el.elemrec])
    ver = verify_written(tmp, [el.elem_id])
    d2 = Document.from_file(tmp)
    obj = d2.value(el.elem_id, 102)
    rep, geom, tags = wall_rep_from_object(
        obj, element_id=el.elem_id, root_category_id=-1,
        side_material_id=FINISH_MATERIAL, end_material_id=-1,
        with_ref_planes=False)
    srep = substitute_elements(tmp, out_path, {el.elem_id: {103: (CLASS_GELEMENT, rep)}},
                               seqs=(103,), keep_row=True, verify=True, diff=True)
    os.remove(tmp)
    if srep.problems:
        raise RuntimeError(f"wall bake problems: {srep.problems[:3]}")
    return {"wall_elem_id": el.elem_id, "wall_type": wt, "level": lvl,
            "p0_ft": list(p0), "p1_ft": list(p1), "height_ft": WALL_HEIGHT_FT,
            "clone_cleanup": clean, "n_dangling": len(dangling),
            "specimens": inj, "commit_watermark_after": crep.watermark_after,
            "verify_ok": bool(getattr(ver, "ok", ver)),
            "bake": {"verdict": srep.verdict,
                     "geometry_ft": {"length": round(geom.length, 4),
                                     "thickness": round(geom.thickness, 4),
                                     "height": round(geom.height, 4)},
                     "mechanism": "W1_gabpd_wall_solid (certified PASS + RENDERS): "
                                  "rvt.render.brep.wall_rep_from_object -> "
                                  "regadd.substitute_elements(seqs=(103,))"}}


# ===========================================================================
# the accounting instrument (regdiff + four-registry census + byte accounting)
# ===========================================================================

def _partition_table(path: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.partitions import parse_partition_table
    with open_rvt(path) as f:
        raw = f.inflate("Global/PartitionTable")
        pt = parse_partition_table(raw)
    return {"count": pt.count, "names": [e.name for e in pt.entries],
            "payload_bytes": len(raw)}


def _storage_index(path: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.stream_encoders import decode_contents
    with open_rvt(path) as f:
        payload = f.inflate("Contents")
    c = decode_contents(payload)
    return {"counters": list(c.get("counters") or []),
            "counter_g": c.get("counter_g"),
            "creation_guid": str(c.get("creation_guid")),
            "payload_bytes": len(payload)}


def _stream_digests(path: str) -> Dict[str, Tuple[int, str]]:
    """{stream name: (raw size, sha1 of raw bytes)} in ONE container pass."""
    from rvt.container import open_rvt
    out: Dict[str, Tuple[int, str]] = {}
    with open_rvt(path) as f:
        for s in f.streams():
            try:
                raw = f.raw(s.name)
            except Exception:
                out[s.name] = (s.size, "(unreadable)")
                continue
            out[s.name] = (len(raw), hashlib.sha1(raw).hexdigest())
    return out


def _elemtable_delta(parent: str, child: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.stream_encoders import decode_elemtable

    def rows(p):
        with open_rvt(p) as f:
            m = decode_elemtable(f.inflate("Global/ElemTable"))
        return {int(r[4]): r for r in m["records"]}, m

    ra, _ma = rows(parent)
    rb, mb = rows(child)
    added = sorted(set(rb) - set(ra))
    removed = sorted(set(ra) - set(rb))
    wm = max(rb) if rb else 0
    eps = sorted({int(rb[i][2]) for i in added}) if added else []
    return {"rows_before": len(ra), "rows_after": len(rb),
            "added_ids": added, "n_added": len(added),
            "removed_ids": removed, "watermark_after": wm,
            "added_modified_episodes": eps}


def four_registry(path: str) -> Dict[str, Any]:
    from rvt.famload import four_registry_census
    r = four_registry_census(path)
    return {"save_units": r["save_units"],
            "contentdocs_entries": r["contentdocs_entries"],
            "contenttable_records": r["contenttable_records"],
            "familymgr_entries": r["familymgr_entries"],
            "familymgr_guids": len(r.get("familymgr_guids") or []),
            "coherent_counts": r["coherent_counts"],
            "coherent_guids": r["coherent_guids"],
            "coherent": r["coherent"],
            "unit_guids": r["unit_guids"]}


def account(rung: str, child: str, parent: str, *, declared_base: str,
            new_ids_hint: Optional[List[int]] = None,
            instance_ids: Sequence[int] = (),
            with_regdiff: bool = True) -> Dict[str, Any]:
    """The per-rung registry + byte accounting vs the rung's immediate parent
    -- the record the charter asks for: units added, ContentDocuments /
    ContentTable / FamilyMgr rows, PartitionTable rows, StorageIndex,
    ElemTable adds, survivor byte-identity, per-stream deltas."""
    from rvt.validate import validate_file
    from rvt.reduce_law import element_diff
    from rvt.mutate import Document

    T = _room()
    rep: Dict[str, Any] = {"rung": rung, "file": relp(child),
                           "immediate_parent": relp(parent),
                           "declared_base": relp(declared_base),
                           "md5": md5_of(child)}
    t0 = time.time()
    dig_p, dig_c = _stream_digests(parent), _stream_digests(child)

    def stream_changed(name: str) -> bool:
        return dig_p.get(name) != dig_c.get(name)

    # 1. the validator gate.  HARD RULE: zero UNEXPECTED errors.  Two
    # loaded-content rules landed in rvt.validate AFTER this ladder was
    # emitted+staged (the instbug-fix stream's D1/D2 corpus laws,
    # 2026-08-05 00:02); the UNFIXED rungs carry those two findings BY
    # DESIGN -- they reproduce the demo's product path, and the fix
    # stream's BXfix_* counterparts are the A/B other half.  They are
    # classified here, not hidden.
    v = validate_file(child)
    known = {"D1_connector_manager_class": 0, "D2_contenttable_guid_order": 0}
    unexpected: List[str] = []
    for e in v.errors:
        msg = str(e)
        if "connector manager of an unlawful class" in msg:
            known["D1_connector_manager_class"] += 1
        elif "NOT ascending by ContentKey GUID" in msg:
            known["D2_contenttable_guid_order"] += 1
        else:
            unexpected.append(msg[:200])
    rep["validator"] = {"verdict": "VALID" if not v.errors else "INVALID",
                        "n_errors": len(v.errors), "n_warnings": len(v.warnings),
                        "known_instbug_findings": known,
                        "unexpected_errors": unexpected,
                        "first_errors": [str(e)[:160] for e in v.errors[:3]]}
    # 2. identity gate (ours, not the template's)
    try:
        rep["identity_gate"] = T.identity_gate(child)
    except Exception as e:                                   # pragma: no cover
        rep["identity_gate"] = {"status": "ERROR", "issues": [str(e)]}

    # 3. four-registry census + delta
    ca, cb = four_registry(parent), four_registry(child)
    rep["census"] = cb
    rep["census_delta"] = {k: (cb[k] - ca[k]) if isinstance(cb.get(k), int)
                           and isinstance(ca.get(k), int) else None
                           for k in ("save_units", "contentdocs_entries",
                                     "contenttable_records", "familymgr_entries",
                                     "familymgr_guids")}
    rep["census_parent"] = {k: ca[k] for k in ("save_units", "contentdocs_entries",
                                               "contenttable_records",
                                               "familymgr_entries", "familymgr_guids",
                                               "coherent")}

    # 4. PartitionTable + StorageIndex (the append-path suspects)
    pa, pb = _partition_table(parent), _partition_table(child)
    rep["partition_table"] = {**pb, "rows_delta": pb["count"] - pa["count"],
                              "byte_identical_to_parent":
                                  not stream_changed("Global/PartitionTable")}
    sa, sb = _storage_index(parent), _storage_index(child)
    rep["storage_index"] = {**sb,
                            "counters_delta": [y - x for x, y in zip(sa["counters"], sb["counters"])]
                                              if len(sa["counters"]) == len(sb["counters"]) else "shape changed",
                            "counter_g_delta": (sb["counter_g"] - sa["counter_g"])
                                               if isinstance(sb.get("counter_g"), int)
                                               and isinstance(sa.get("counter_g"), int) else None,
                            "byte_identical_to_parent":
                                not stream_changed("Contents")}

    # 5. ElemTable adds
    rep["elemtable"] = _elemtable_delta(parent, child)

    # 6. reduce_law-style survivor byte identity (adds only)
    da = Document.from_file(parent)
    db = Document.from_file(child)
    ed = element_diff(da, db)
    rep["element_diff"] = ed.to_json()
    rep["element_diff"]["added_ids_host"] = sorted(
        set(rep["elemtable"]["added_ids"]))
    rep["survivor_law_ok"] = (not ed.removed) and (not ed.modified)

    # 7. per-stream byte accounting
    changed = []
    for name in sorted(set(dig_p) | set(dig_c)):
        if stream_changed(name):
            bp = dig_p.get(name, (None,))[0]
            bc = dig_c.get(name, (None,))[0]
            changed.append({"stream": name, "bytes_before": bp, "bytes_after": bc,
                            "delta": (bc or 0) - (bp or 0)})
    rep["streams_changed"] = changed
    rep["streams_unchanged"] = len(set(dig_p) | set(dig_c)) - len(changed)

    # 8. regdiff: the placed instances' registration, the ADocument registry
    #    surface of EVERY added host id, and the unit-0 run law
    if with_regdiff:
        try:
            from rvt.regdiff import RegDoc, registration_of, run_law_report
            rd = RegDoc(child)
            regs = {}
            for eid in instance_ids:
                r = registration_of(rd, int(eid))
                regs[str(eid)] = {"class": r.class_name, "row": r.row,
                                  "positions": r.positions,
                                  "registry_surface": r.registry,
                                  "owned_rows": r.owned_rows}
            rep["registrations"] = regs
            added = rep["elemtable"]["added_ids"]
            if added:
                surface = rd.adoc_surface(added)
                rep["added_ids_registry_surface"] = {
                    str(i): {"class": rd.class_of(i),
                             "adocument_paths": surface.get(i) or []}
                    for i in added}
                rep["added_ids_unregistered_in_adocument"] = sorted(
                    i for i in added if not surface.get(i))
            rep["run_law"] = run_law_report(rd, 102)
        except Exception as e:                               # pragma: no cover
            rep["regdiff_error"] = f"{type(e).__name__}: {e}"

    rep["seconds"] = round(time.time() - t0, 1)
    ok = (not rep["validator"]["unexpected_errors"] and rep["survivor_law_ok"]
          and rep["census"]["coherent"])
    rep["gates_ok"] = bool(ok)
    return rep


# ===========================================================================
# the build driver
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    from rvt.frontdoor import standalone as SA
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    SA.install_schema(G_ABPD)          # the demo's schema resolution (base-embedded)
    model6 = demo_model()
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/bisect_instance_bug.py", "prompt": PROMPT,
                           "built": {}, "accounting": {}, "errors": {}}

    chains: Dict[str, Dict[str, Any]] = {}

    def chain_for(base_path: str, key: str) -> Dict[str, Any]:
        if key not in chains:
            cdir = os.path.join(BUILD_DIR, key)
            log(f"stage_load chain ({key}) on {relp(base_path)} ...")
            lrec = build_chain(base_path, cdir, model6)
            chains[key] = {"dir": cdir, "lrec": lrec, "base": base_path}
            jdump(os.path.join(cdir, "chain_load_record.json"),
                  {k: v for k, v in lrec.items() if not k.startswith("_")})
        return chains[key]

    def rung_out(name: str) -> str:
        return os.path.join(OUT_DIR, f"{name}.rvt")

    def build_rung(name: str) -> Dict[str, Any]:
        base_path, nf, ni, nw = RUNG_SPEC[name]
        key = "gabpd" if base_path == G_ABPD else "rst"
        ch = chain_for(base_path, key)
        order = ch["lrec"]["order"]
        loaded_all = ch["lrec"]["_loaded"]
        src_n = chain_file(ch["dir"], nf, order[nf - 1])
        outp = rung_out(name)
        info: Dict[str, Any] = {"rung": name, "base": relp(base_path),
                                "n_families": nf, "n_instances": ni, "n_walls": nw}
        model_n = truncate_model(model6, nf)
        loaded_n = {t: loaded_all[t] for t in order[:nf]}
        # ``src`` = the file the FINAL hop starts from; ``parent`` = the file
        # this rung is ACCOUNTED against (the immediate parent of its last hop):
        #   load-only rung  -> src = the chain file itself; parent = the
        #                      previous chain file (the base for n=1)
        #   instance rung   -> src = parent = the load file
        #   wall rung       -> the wall hop runs first (accounted separately);
        #                      src = parent = the walled file
        src = src_n
        parent = (chain_file(ch["dir"], nf - 1, order[nf - 2])
                  if (ni == 0 and nw == 0 and nf > 1)
                  else (base_path if (ni == 0 and nw == 0) else src_n))
        if nw:
            wall_dir = os.path.join(BUILD_DIR, f"{name}_wall")
            os.makedirs(wall_dir, exist_ok=True)
            walled = os.path.join(wall_dir, "stage_W_wall.rvt")
            log(f"{name}: certified W1-recipe wall onto {relp(src_n)} ...")
            info["wall"] = add_certified_wall(src_n, walled, wall_dir)
            info["wall_hop"] = {"parent": relp(src_n), "child": relp(walled)}
            src = parent = walled
        if ni:
            log(f"{name}: placing {ni} instance(s) onto {relp(src)} ...")
            erec = place_instances(model_n, src, outp, base_path, loaded_n)
            info["equipment"] = {
                "instances": [{k: i.get(k) for k in ("tag", "elem_id", "symbol",
                                                     "family", "position_ft",
                                                     "n_dangling")}
                              for i in erec.get("instances") or []],
                "elemtable_after": erec.get("elemtable_after"),
                "structurally_valid": erec.get("structurally_valid"),
            }
            info["instance_ids"] = [i["elem_id"] for i in erec.get("instances") or []]
        else:
            shutil.copyfile(src, outp)
            info["instance_ids"] = []
        info["file"] = relp(outp)
        info["md5"] = md5_of(outp)
        info["immediate_parent"] = relp(parent)
        # chain provenance: every hop from the certified base to this rung
        hops = [relp(base_path)] + [relp(chain_file(ch["dir"], i, order[i - 1]))
                                    for i in range(1, nf + 1)]
        if nw:
            hops.append(relp(parent))
        if ni or nw:
            hops.append(relp(outp))
        info["hops_from_base"] = hops
        return info

    for name in [r for r in LADDER if r in only]:
        try:
            info = build_rung(name)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]})")
        except Exception as e:                               # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=8)
            log(f"{name} FAILED: {type(e).__name__}: {e}")

    # accounting for every rung that built (+ the wall rung's intermediate hop)
    for name, info in out["built"].items():
        base_path, nf, ni, nw = RUNG_SPEC[name]
        parent = os.path.join(ROOT, info["immediate_parent"])
        try:
            if info.get("wall_hop"):
                out["accounting"][name + ".hop_wall"] = account(
                    name + ".hop_wall",
                    os.path.join(ROOT, info["wall_hop"]["child"]),
                    os.path.join(ROOT, info["wall_hop"]["parent"]),
                    declared_base=base_path,
                    instance_ids=[info["wall"]["wall_elem_id"]])
            rep = account(name, os.path.join(ROOT, info["file"]), parent,
                          declared_base=base_path,
                          instance_ids=info.get("instance_ids") or [])
            out["accounting"][name] = rep
            log(f"{name} accounting: units +{rep['census_delta']['save_units']}, "
                f"cd +{rep['census_delta']['contentdocs_entries']}, "
                f"ct +{rep['census_delta']['contenttable_records']}, "
                f"fm +{rep['census_delta']['familymgr_entries']}, "
                f"elemtable +{rep['elemtable']['n_added']}, "
                f"validator {rep['validator']['n_errors']} err, "
                f"survivor_law {'OK' if rep['survivor_law_ok'] else 'VIOLATED'}, "
                f"coherent {rep['census']['coherent']}")
        except Exception as e:                               # noqa: BLE001
            out["errors"][name + ".accounting"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".accounting.tb"] = traceback.format_exc(limit=8)
            log(f"{name} ACCOUNTING FAILED: {type(e).__name__}: {e}")

    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "accounting.json"), out)
    write_probes_json(out)
    return out


# ===========================================================================
# probes.json (the staging manifest probe_batch resolves bases from)
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "BX_f2 FAIL": "MULTIPLE family-document loads alone trip the audit (instances "
                  "exonerated); the famgen/famload append path at N>=2 on a "
                  "registry-emptied base is the bug",
    "BX_f2 PASS": "weak if the card reads 'Design is empty' (symbol-only "
                  "short-circuit, the stage_L8_lp4 lesson); read with BX_f1i1",
    "BX_f1i1 FAIL": "ONE family + ONE placed instance fails on G_ABPD (R_inst_box's "
                    "reading confirmed with the demo's own product+specimen path); "
                    "the instance/creation registration on the genesis lineage is "
                    "the bug even at N=1",
    "BX_f1i1 PASS + BX_f2i2 or BX_f6i6 FAIL": "N=1 clean, N>1 fails: the SECOND+ "
                                              "family document (or its instance) is "
                                              "the axis -- diff BX_f1i1 vs BX_f2i2 "
                                              "registration accounting",
    "SX_f6i6 PASS + BX_f6i6 FAIL": "same operation, different base => BASE-LINEAGE "
                                   "bug: what the genesis lineage's emptied "
                                   "content registries still lack for the Nth "
                                   "append / instance registration",
    "SX_f6i6 FAIL": "the OPERATION fails even on the Autodesk sample base => the "
                    "demo placement path itself (ConstructedSpecimens template / "
                    "loader chain) is defective; base exonerated. NOTE the "
                    "certified V20..V29 placements cloned REAL host specimens and "
                    "L_v2 used rvt.famload -- the constructed-template delta is "
                    "the prime suspect in this cell",
    "BX_f6i6 FAIL": "the demo reproduction control (expected: DEMO_250v_room's "
                    "verdict reproduces on a fresh build)",
    "BX_w_f1i1 FAIL with BX_f1i1 PASS": "the wall x loaded-family interaction in "
                                        "the product's L->W->E order (the "
                                        "stage_W/F_ signature) -- walls certified "
                                        "alone (W1), family+instance judged by "
                                        "BX_f1i1",
    "all BX FAIL + SX PASS": "every genesis-lineage rung fails while the sample "
                             "base passes: the bug is the base's content-registry "
                             "state interacting with ANY append; start from the "
                             "four-registry + StorageIndex deltas in "
                             "accounting.json",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    """experiments/instbug/probes.json -- ordered for maximum information
    (BX_f2 first), every entry declaring its CERTIFIED base for
    tools/probe_batch.py."""
    probes = []
    onething = {
        "BX_f2": "TWO famgen panel families loaded (chained, place=False) on "
                 "G_ABPD -- 0 instances, 0 walls. The narrowest open axis: does "
                 "the SECOND family-document append alone trip the audit?",
        "BX_f1i1": "ONE family + ONE placed instance on G_ABPD by the demo's own "
                   "placement path (ConstructedSpecimens template + "
                   "add_family_instance + commit) -- the instance forces the audit",
        "SX_f6i6": "THE CROSS-CHECK: the identical 6-family + 6-instance code path "
                   "on the Autodesk rst sample base -- isolates base-lineage vs "
                   "operation (expected PASS)",
        "BX_f6i6": "the demo shape rebuilt (G_ABPD + 6 families + 6 instances) -- "
                   "the DEMO_250v_room reproduction control (expected FAIL)",
        "BX_f2i2": "TWO families + TWO instances -- the scale point between "
                   "BX_f1i1 and BX_f6i6",
        "BX_f6": "SIX families, 0 instances, 0 walls -- the demo's full load "
                 "chain alone (symbol-only: an empty-design read is NOT an "
                 "audited pass)",
        "BX_f1": "ONE family, 0 instances, 0 walls -- the single-append control "
                 "(symbol-only caveat as BX_f6)",
        "BX_w_f1i1": "the FULL PRODUCT SHAPE: loaded family -> certified W1-recipe "
                     "wall (baked B-rep solid) -> placed instance, the product's "
                     "own L->W->E order -- the wall x family interaction with "
                     "every ingredient individually certified",
    }
    expected = {"BX_f2": "unknown (the open axis)", "BX_f1i1": "unknown (R_inst_box "
                "failed on ZA_deep; this is the G_ABPD + demo-path version)",
                "SX_f6i6": "PASS", "BX_f6i6": "FAIL (reproduction)",
                "BX_f2i2": "unknown", "BX_f6": "empty-design or FAIL",
                "BX_f1": "empty-design or FAIL (WF pair passed walls+1 family)",
                "BX_w_f1i1": "unknown (stage_W/F_ failed; WF passed -- order and "
                             "family content differ)"}
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        acct = (build_out.get("accounting") or {}).get(name) or {}
        base_path, nf, ni, nw = RUNG_SPEC[name]
        probes.append({
            "order": i,
            "rung": name,
            "file": f"experiments/instbug/{name}.rvt",
            "base": relp(base_path),
            "kind": "probe",
            "n_families": nf, "n_instances": ni, "n_walls": nw,
            "the_ONE_thing_it_tests": onething[name],
            "expected": expected[name],
            "md5": info.get("md5"),
            "immediate_parent": info.get("immediate_parent"),
            "gates": {"validator_errors_at_build": (acct.get("validator") or {}).get("n_errors"),
                      "four_registry_coherent": (acct.get("census") or {}).get("coherent"),
                      "survivor_law_ok": acct.get("survivor_law_ok"),
                      "identity": ((acct.get("identity_gate") or {}).get("status"))},
            "validator_now": ({"n_errors": vn.get("n_errors"),
                               "known_instbug_findings": vn.get("known_instbug_findings"),
                               "unexpected_errors": len(vn.get("unexpected_errors") or [])}
                              if (vn := acct.get("validator_now")) else None),
        })
    manifest = {
        "stream": "instbug: the minimal bisection ladder for the product-path "
                  "walls/families/instances bug (DEMO_250v_room's failure)",
        "prompt": PROMPT,
        "base": relp(G_ABPD),
        "note": "every rung is the demo's OWN code path (prompt_to_intent -> "
                "stage_load famgen.loader place=False -> stage_equipment "
                "ConstructedSpecimens + add_family_instance + commit); the "
                "BX_w wall is the certified W1 mechanism. Fresh GUIDs are "
                "minted per rebuild -- re-hash after any rerun.",
        "upload_order_max_information_first": list(LADDER),
        "control": {"source": relp(G_ABPD),
                    "note": "control = byte-identical G_ABPD copy "
                            "(probe_batch stage --control-from)"},
        "reading_the_matrix": READING,
        "empty_design_caveat": "BX_f1/BX_f2/BX_f6 carry loaded families and NO "
                               "model elements; per the stage_L8_lp4 lesson "
                               "(docs/inbox/render-instances.md sec.1) a 'Design is "
                               "empty' translation is an extractor short-circuit, "
                               "NOT an audited pass -- a PASS card on those three "
                               "is weak evidence, their FAIL is strong; the "
                               "instance rungs are the audited discriminators.",
        "validator_drift_note": "two rvt.validate loaded-content rules (instbug-fix "
                                "stream, 2026-08-05 00:02) landed AFTER this ladder "
                                "was emitted+staged: D1 (instance connector-manager "
                                "class) and D2 (ContentTable GUID order). The "
                                "UNFIXED rungs carry those findings BY DESIGN (they "
                                "reproduce the demo's product path exactly -- the "
                                "demo file itself reads the same two findings); "
                                "each entry's validator_now field classifies them; "
                                "unexpected errors are ZERO on every rung. The fix "
                                "stream's experiments/instbug/fix/BXfix_* files are "
                                "the corrected A/B counterparts -- upload pairs in "
                                "the SAME round for the mechanism proof.",
        "probes": probes,
        "accounting": "experiments/instbug/accounting.json",
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# verify (re-run the accounting on the emitted files) + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    """Re-run the accounting on the emitted rungs against the CURRENT
    validator, classify known-vs-unexpected findings, persist the result
    into accounting.json ('validator_now' per rung, build-time numbers kept)
    and refresh probes.json."""
    import datetime as _dt
    if not os.path.isfile(os.path.join(OUT_DIR, "accounting.json")):
        raise SystemExit("no accounting.json -- run build first")
    with open(os.path.join(OUT_DIR, "accounting.json")) as fh:
        out = json.load(fh)
    from rvt.frontdoor import standalone as SA
    SA.install_schema(G_ABPD)
    fresh = {}
    for name, info in (out.get("built") or {}).items():
        child = os.path.join(ROOT, info["file"])
        parent = os.path.join(ROOT, info["immediate_parent"])
        if not (os.path.isfile(child) and os.path.isfile(parent)):
            fresh[name] = {"error": "file(s) missing"}
            continue
        r = account(name, child, parent,
                    declared_base=RUNG_SPEC[name][0],
                    instance_ids=info.get("instance_ids") or [],
                    with_regdiff=False)
        fresh[name] = r
        va = r["validator"]
        log(f"{name}: validator {va['n_errors']} err "
            f"(known D1={va['known_instbug_findings']['D1_connector_manager_class']} "
            f"D2={va['known_instbug_findings']['D2_contenttable_guid_order']}, "
            f"unexpected={len(va['unexpected_errors'])}), "
            f"coherent {r['census']['coherent']}, "
            f"survivor_law {'OK' if r['survivor_law_ok'] else 'VIOLATED'}")
        # persist the current-validator classification next to the rung
        if name in (out.get("accounting") or {}):
            out["accounting"][name]["validator_now"] = va
    out.setdefault("verify_runs", []).append({
        "when": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "current-validator recomputation (known instbug findings D1/D2 "
                "classified; gate = zero UNEXPECTED errors)",
        "per_rung": {n: {"n_errors": r["validator"]["n_errors"],
                         "known": r["validator"]["known_instbug_findings"],
                         "unexpected": len(r["validator"]["unexpected_errors"]),
                         "gates_ok": r.get("gates_ok")}
                     for n, r in fresh.items() if "validator" in r},
    })
    jdump(os.path.join(OUT_DIR, "accounting.json"), out)
    write_probes_json(out)
    return fresh


def _campaign_global_next_batch() -> int:
    """The batch number is CAMPAIGN-GLOBAL (fleet lesson, genesis-audit
    2026-08-05): scan EVERY batch_<n>.json under experiments/, not just the
    acceptance dir, so a number staged by another campaign (e.g. the 2025
    port's batch_17 under experiments/genesis2025/) is never reused."""
    import glob
    import re
    n = 14
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "batch_*.json"),
                       recursive=True):
        m = re.match(r"batch_(\d+)\.json$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def stage() -> Dict[str, Any]:
    """Gate + stage the ladder through tools/probe_batch.py with the control
    pinned to G_ABPD (the charter's batch law: certified base + control)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_instbug_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing rungs (run build): {[relp(m) for m in missing]}")
    manifest = pb.stage_batch(files, control_from=G_ABPD,
                              batch_n=_campaign_global_next_batch(),
                              note="instbug bisection ladder: the walls/families/"
                                   "instances product-path bug, axes separated "
                                   "(see experiments/instbug/probes.json "
                                   "reading_the_matrix; accounting.json = per-rung "
                                   "four-registry + byte accounting)")
    log(f"STAGED batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the ladder (+ accounting + probes.json)")
    b.add_argument("--only", default=None,
                   help="comma-separated rung subset (default: all)")
    sub.add_parser("verify", help="re-run the accounting on the emitted rungs")
    sub.add_parser("stage", help="probe_batch gate + stage (control = G_ABPD copy)")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        bad = [r for r in (only or []) if r not in RUNG_SPEC]
        if bad:
            ap.error(f"unknown rung(s): {bad}; choose from {list(RUNG_SPEC)}")
        out = build(only)
        n_err = len([k for k in out["errors"] if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} rung(s), {n_err} error(s), "
            f"{out['seconds']}s")
        return 1 if n_err else 0
    if a.cmd == "verify":
        fresh = verify()
        bad = [n for n, r in fresh.items()
               if r.get("error") or not r.get("gates_ok")]
        log(f"verify done: {len(fresh)} rung(s), gate failures: {bad or 'none'}")
        return 1 if bad else 0
    if a.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
