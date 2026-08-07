"""genesis/y2025_a.py -- THE Y2025 SETTINGS + CATALOG RUNGS (stream y2025-settings).

The certified 2026 substitution ladder's Y1..Y7 (tools/genesis_substitute_v3.py,
docs/writer/substitution-ladder-v3.md) mirrored onto the CERTIFIED Revit-2025
family-free base **B2025_K4** (experiments/genesis2025/reduce/B2025_K4.rvt --
ORCHESTRATOR VERDICTS #28, docs/inbox/genesis-audit.md: the whole 2025
reduction lineage certified in one viewer round; the v3 engine's
``assert_certified`` gate ACCEPTS this base, no override needed).

WHAT THIS MODULE ADDS (v3, the X builders, port2025 and residue_b2 are
IMPORTED, never edited):

1.  **The 2025 rung table** (:func:`rungs_2025`): nine rungs named
    ``Y1_2025..Y7_2025`` (cumulative) + the two SINGLE-CHANGE bisection
    probes ``Y1s_2025`` (base + ONLY the pen table -- content-identical to
    Y1_2025, emitted as its own file and md5-cross-checked) and ``Y6s_2025``
    (base + ONLY the built-in catalog).  The layer map is the 2026 ladder's:
    Y1 pen table, Y2 browser/navigator, Y3 named singletons, Y4 MEP
    settings+sizes, Y5 remaining settings/trackers, Y6 the complete built-in
    category/GStyle catalog IN PLACE, Y7 patterns + materials + the palette
    property sets.
2.  **The Y7 palette union** (build key ``X7P``): ``genesis_substitute.
    build_X7`` (patterns + 13 house materials) UNIONED with the
    viewer-certified corrected palette-bucket constructors of
    ``rvt.genesis.residue_b2`` (Z_palette_v2, verdicts #21/#23): the
    extended surplus materials + the STRUCTURAL / THERMAL
    ``PropertySetElement`` assets re-valued over each slot's own skeleton --
    int params correctly keyed and ascending param-id order BY CONSTRUCTION
    (the 2026 palette lesson: residue_b's swapped (value, id) tuples,
    docs/inbox/genesis-palette-fix.md).  The X7 half is planned provisionally
    first so the palette half only takes the slots X7 leaves free -- the
    final in-place plan is proven identical for the X7 records (same corr,
    same referrer ranking, same slot-fill order).
3.  **The 2025 run context** (:func:`y2025_context`): EVERYTHING runs inside
    ``tools/genesis_2025.py::context_2025`` -- versions.reading + the SEVEN
    module-local 2026-baked framing constants (reduce BLOCK/TRL, manipulate
    BLOCK/TRAILER, commit TRL, writer TRL, famgen CD_SEPARATOR/CD_END_RECORD)
    + the ADocument default decoder -- PLUS the port-layer swaps the
    genesis-2025-port stream proved out (experiments/genesis2025/subst/
    run_ladder2025.py): the default encoder / regadd / regdiff codecs to the
    pinned 2025 schema, ``genesis_substitute_v3._class_id`` resolving by NAME
    against 2025, the catalog enum/profile loaders redirected to the
    2025-mined tables (1,068 categories / 1,399 style keys incl. the 4
    differing flag words), and every X-builder record passed through
    ``rvt.genesis.port2025.adapt_record`` (the confirmed field maps, incl.
    the BrowserOrganizationTracking v6->v5 hook -- which an IN-PLACE rung
    never writes: Global/Latest stays byte-identical, asserted per rung).
    All swaps restore on exit.
4.  **The pen-table scale-key preflight** (:func:`pen_scale_key_check`):
    the charter's "verify the 2025 corpus scale keys, do not assume 2026's"
    -- the base's OWN project pen table (m_famId -1) is decoded and its
    ``m_modelPenInfo`` scale set compared against
    ``settings.PEN_SCALE_BREAKPOINTS`` before Y1_2025 is built; mismatch
    aborts the ladder.
5.  **probes.json** (:func:`write_probes`): bisection-first (Y7_2025
    deepest, then the singles, then the intermediates deep->shallow), every
    entry naming base B2025_K4 with its ledger entry AND the verdict-#28
    citation, plus the staged control (CTRL_B2025_K4_base.rvt,
    md5-identical to the base) -- and a recorded ``tools/probe_batch.py``
    gate check (the standing-controls law; the gate passes now that the
    base is certified).

Usage (repo root)::

    .venv/bin/python -m rvt.genesis.y2025_a                 # the whole ladder
    .venv/bin/python -m rvt.genesis.y2025_a --only Y1_2025
    .venv/bin/python -m rvt.genesis.y2025_a --manifest-only

Territory: this module, tests/test_y2025_a.py,
experiments/genesis/subst_k4_2025/*, docs/inbox/y2025-settings.md.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))                    # repo root (src/rvt/genesis/..)

DEFAULT_BASE_2025 = os.path.join(ROOT, "experiments", "genesis2025", "reduce",
                                 "B2025_K4.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025")

#: the certification citation every probes.json entry carries (the charter:
#: "each naming base B2025_K4 (certified, cite verdict #28)")
VERDICT_28 = (
    "ORCHESTRATOR VERDICTS #28 (docs/inbox/genesis-audit.md, 2026-08-04 ~23:05): "
    "ALL FOUR PASS -- the untouched 2025 sample (control: the viewer reads 2025), "
    "R9_2025, K3_2025 and B2025_K4 (the 2025 family-free base). The whole 2025 "
    "reduction lineage certified in ONE round; B2025_K4 is listed in "
    "docs/coverage/viewer-certified.json 'certified'.")

LINEAGE_2025 = (
    "B2025_K4 = the genesis-2025-reduce stream's family-free 2025 base "
    "(sha256 276be333..., 851,968 B, 3,333 host elements): "
    "samples/2025/rstbasicsampleproject -> R5..R9_2025 (maxgc, every rung "
    "validator-0-errors + reduce_law EDIT-FREE) -> K3_2025 (usage nulls, the "
    "certified 2026 K3 recipe, edits == neutralised set exactly) -> B2025_K4 "
    "(all 52 embedded family documents removed, four-registry coherent 1/0/0/0, "
    "residual GUID bytes 0).  VIEWER-CERTIFIED: " + VERDICT_28)

#: bisection-first upload order (the charter: Y7_2025 deepest, then singles,
#: then the intermediates deep->shallow)
UPLOAD_ORDER = ["Y7_2025", "Y1s_2025", "Y6s_2025",
                "Y6_2025", "Y5_2025", "Y4_2025", "Y3_2025", "Y2_2025", "Y1_2025"]

LADDER = ["Y1_2025", "Y2_2025", "Y3_2025", "Y4_2025", "Y5_2025", "Y6_2025",
          "Y7_2025"]
SINGLES = ["Y1s_2025", "Y6s_2025"]


def _tools() -> None:
    """Make tools/ importable (genesis_2025, genesis_substitute[_v3])."""
    for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def log(msg: str) -> None:
    print(msg, flush=True)


# ===========================================================================
# 1. THE 2025 RUNG TABLE (the 2026 ladder's Y1..Y7, renamed and re-parented)
# ===========================================================================

def rungs_2025() -> list:
    """The nine Rung3 entries of this stream, in BUILD order (cumulative
    ladder first, then the two single-change probes off the base)."""
    _tools()
    import genesis_substitute_v3 as V3

    R = V3.Rung3
    mirror = ("Mirrors the certified 2026 rung {src} (docs/writer/"
              "substitution-ladder-v3.md) onto the certified 2025 base "
              "B2025_K4; constructors pass through rvt.genesis.port2025 "
              "(the confirmed 2026->2025 field maps).  ")
    return [
        R(name="Y1_2025", parent="BASE", build="X1",
          label="the project pen table (PenWidthTableElem, m_famId -1) -> OUR pen table, IN PLACE",
          description=(mirror.format(src="Y1")
                       + "The 2025 corpus scale-key set is VERIFIED against the base's own "
                         "table before this rung is built (pen_scale_key_check; the six "
                         "model breakpoints [10, 20, 50, 100, 200, 500] hold in 2025 -- "
                         "mined by genesis-2025-port, re-proven here, never assumed)."),
          tests=("Whether the 2025 reader accepts OUR pen-table CONTENT when nothing but "
                 "the object bytes at Autodesk's own registration change."),
          if_pass="Our pen constructor's values load at a 2025 registration (the 2026 Y1 result transfers).",
          if_fail=("Our pen VALUES are what the 2025 reader rejects (the only variable): diff "
                   "our record vs the base's project pen table field by field.")),
        R(name="Y2_2025", parent="Y1_2025", build="X2",
          label="BrowserOrganization set + system-navigator constellation -> ours, IN PLACE",
          description=(mirror.format(src="Y2")
                       + "The BrowserOrganization sortParameter->m_sortParamId field map is "
                         "applied by port2025; the BrowserOrganizationTracking v6->v5 map "
                         "(three ElementId fields) is an ADocument registry concern an "
                         "in-place rung NEVER writes -- Global/Latest is byte-identical to "
                         "the parent, asserted."),
          tests="Whether the 2025 reader accepts our browser / navigator OBJECTS at Autodesk's registrations.",
          if_pass="Our browser / navigator constructors are 2025-reader-accepted.",
          if_fail="Bisect the organizations from the navigator (two single-class in-place probes)."),
        R(name="Y3_2025", parent="Y2_2025", build="X3",
          label="StructSettings / wall-join / auto-join / keynote pair -> ours, IN PLACE",
          description=(mirror.format(src="Y3")
                       + "StructSettingsElem drops one field in 2025 (the confirmed 1-field "
                         "delta); KeynoteTable OURS = EMPTY, and its 2025 form drops "
                         "m_hasUserCustomizedKeynote -- both handled by the adapt() walk."),
          tests="Whether the 2025 reader accepts our named settings singletons (incl. an EMPTY keynote table).",
          if_pass="The named singleton constructors are 2025-reader-accepted.",
          if_fail="Bisect the keynote pair from the joins pair from StructSettings."),
        R(name="Y4_2025", parent="Y3_2025", build="X4",
          label="Rbs* settings + sizes tables (wire/duct/pipe/conduit/cable-tray) -> ours, IN PLACE",
          description=(mirror.format(src="Y4")
                       + "The corrected 2025 values apply: RbsWireSettingsElem gains the three "
                         "2025-only doubles (0.02 / 0.03 / 303.15000000000003 K), "
                         "RbsWireSizesElem drops m_bInitialized, RbsWireType's max conductor "
                         "size becomes the referenced size cell's own LABEL -- all mined from "
                         "the 2025 corpus (port2025 hooks), verified in the emitted file."),
          tests="Whether the 2025 reader accepts our MEP settings + OUR size-table DATA at Autodesk's slots.",
          if_pass="Our MEP settings / sizes constructors + data are 2025-reader-accepted.",
          if_fail="Bisect settings vs sizes vs the conduit/cable-tray pair."),
        R(name="Y5_2025", parent="Y4_2025", build="X5",
          label="every remaining settings singleton / tracker with a constructor -> ours, IN PLACE",
          description=(mirror.format(src="Y5")
                       + "The tracker constellation, revisions + numbering (the 2025 "
                         "NumberingSchema shape via the port2025 hook set: partition-"
                         "description creator, min digits, per-scope schemaTypeGuid, "
                         "matching flag), print / worksharing / export / area / energy / "
                         "reinforcement (2025 default m_numberVaryingLengthRebarsIndividually "
                         "= True) / route-analysis / fabrication settings, model graphics "
                         "styles (2025 GDI flag False), area schemes."),
          tests="Whether the 2025 reader accepts the WHOLE our-settings constellation at Autodesk's slots.",
          if_pass="Every settings constructor we own is 2025-reader-accepted; the settings layer is retired.",
          if_fail="Bisect Y5 by tier (mep / trackers / revisions)."),
        R(name="Y6_2025", parent="Y5_2025", build="X6a",
          label="the built-in-category GStyle CATALOG swapped in place, row for row (2025 enum + profile)",
          description=(mirror.format(src="Y6")
                       + "The catalog loaders are redirected to the 2025-MINED tables for this "
                         "run: builtin_category_enum_2025 (1,068 categories, 331 cuttable) and "
                         "builtin_style_profile_2025 (1,399 (category, style-type) keys over "
                         "4,197 rows; 4 keys carry a different header flag word than 2026 -- "
                         "-2000710..713 type 1: 0x400200e -> 0x400201e -- and the emitted rows "
                         "carry the 2025 values, verified in the file).  Rows the base lacks "
                         "are NOT added (ours-not-landed; the add path is not this ladder's "
                         "variable)."),
          tests=("Whether the 2025 reader accepts OUR object-styles VALUES row for row at "
                 "Autodesk's own catalog registrations."),
          if_pass="Our catalog values are 2025-reader-accepted.",
          if_fail=("Our catalog VALUES are the 2025 reader's objection -- diff a rejected "
                   "(category, type) row vs the base's (field diff sample in the report).")),
        R(name="Y7_2025", parent="Y6_2025", build="X7P",
          label=("line/fill patterns + materials + the palette PROPERTY SETS "
                 "(structural/thermal, corrected constructors) -> ours, IN PLACE"),
          description=(mirror.format(src="Y7 + Z_palette_v2")
                       + "The UNION of two viewer-certified 2026 layers: build_X7 (our 4 line "
                         "patterns, 5 fill patterns, 13 materials by role + slot-fill) and the "
                         "corrected palette bucket of rvt.genesis.residue_b2 (the extended "
                         "surplus materials + every STRUCTURAL / THERMAL PropertySetElement "
                         "re-valued over its slot's OWN skeleton).  The 2026 palette lesson is "
                         "enforced by construction and re-checked on the emitted file: int "
                         "params correctly keyed -- residue_b's original swapped the "
                         "(value, id) tuples -- and param sets serialised in ASCENDING "
                         "param-id order (the 300/300 corpus law).  AppearanceAssetElem / "
                         "PropertySetLibrary stay residue (no constructor)."),
          tests=("Whether the 2025 reader accepts OUR pattern + material + property-set "
                 "OBJECTS at Autodesk's palette registrations (the deepest rung of this "
                 "stream: a PASS proves the whole settings + catalog + palette chain on 2025)."),
          if_pass=("Every constructor of this stream loads at 2025 registrations; the Y8/Y9 "
                   "(datum + view) rungs and compose are the remaining campaign steps."),
          if_fail=("Bisect patterns+materials (the certified X7 half) from the property sets "
                   "(the certified residue_b2 half) -- two single-layer in-place probes off "
                   "Y6_2025; read the death signature (AUDIT vs CRASH).")),
        # ---- the two single-change bisection probes (straight off the base) ----
        R(name="Y1s_2025", parent="BASE", build="X1",
          label="the base + ONLY our pen table in place (single-change probe)",
          description=("The smallest possible OUR-content probe on 2025: the certified base "
                       "with exactly ONE object swapped (our pen table at the project "
                       "PenWidthTableElem).  Content-identical to Y1_2025 (same parent, same "
                       "build); emitted as its own file and md5-cross-checked against "
                       "Y1_2025 -- a determinism proof and a standalone upload."),
          tests="Y1_2025's question isolated: ONE our-object at a 2025 registration.",
          if_pass="Our pen table loads on 2025 in isolation.",
          if_fail=("Even ONE our-object at a 2025 registration fails: the object-content "
                   "layer is the defect; expect the whole ladder to fail until fixed.")),
        R(name="Y6s_2025", parent="BASE", build="X6a",
          label="the base + ONLY the built-in GStyle catalog in place (single-change probe)",
          description=("The certified base with exactly ONE class layer swapped: every "
                       "present built-in-category GStyleElem row -> OUR row of the same "
                       "(category, style-type) from the 2025-mined enum/profile, nothing "
                       "else touched."),
          tests="Whether OUR catalog values load at 2025 registrations, isolated from every other constructor.",
          if_pass="Our catalog values are 2025-reader-accepted in isolation.",
          if_fail=("Our catalog VALUES are rejected in isolation on 2025 -- diff a rejected "
                   "row's pen / colour / pattern values against the base's row.")),
    ]


# ===========================================================================
# 2. THE Y7 PALETTE UNION (build key X7P)
# ===========================================================================

def _build_X7P(ctx, out_dir: str):
    """build_X7 (patterns + house materials) UNIONED with residue_b2's
    corrected palette bucket (extended surplus materials + structural /
    thermal property sets), as ONE in-place SubstBuild.

    The X7 half is PLANNED PROVISIONALLY first (plan_inplace is pure), so the
    palette half's slot selection sees exactly the material slots X7 leaves
    free -- the ZB5 pairing rule, computed instead of assumed.  The final
    merged plan lands the X7 records in the SAME slots as the provisional
    plan: the palette corr only claims slots the provisional plan left free,
    every palette slot is already in X7's old_ids (so referrer ranking and
    slot-fill ordering are unchanged), and plan_inplace is deterministic."""
    _tools()
    import genesis_substitute as GS
    import genesis_substitute_v3 as V3
    from rvt.genesis import residue_b2 as B2

    sb7 = GS.build_X7(ctx)
    chain = V3.derivation_chain(V3.rung_by_name("Y7_2025"))
    protected = V3.previously_landed(out_dir, chain)
    plan7 = V3.plan_inplace(ctx, sb7, slot_fill=True, protected=set(protected))
    landed_now: Dict[int, Any] = {int(s): r for s, r in protected.items()}
    for p in plan7.pairs:
        landed_now[int(p.slot)] = "Y7_2025:x7-provisional"

    ext_records: List[Any] = []
    ext_corr: Dict[int, int] = {}
    pal_notes: List[str] = []
    traces: List[dict] = []
    n_mat = B2._materials(ctx, landed_now, ext_records, ext_corr, pal_notes)
    n_s, n_t = B2._propsets_v2(ctx, landed_now, ext_records, ext_corr, pal_notes, traces)

    # merge: palette corr wins on any slot X7 role-mapped but did not land
    # (an unconsumed sibling of a many-to-one role group)
    sb7_corr = {int(k): int(v) for k, v in sb7.corr.items()}
    reclaimed = sorted(set(ext_corr) & set(sb7_corr))
    corr = dict(sb7_corr)
    corr.update({int(k): int(v) for k, v in ext_corr.items()})
    old_ids = sorted({int(o) for o in sb7.old_ids} | set(ext_corr))
    fam_mismatch = [t for t in traces if not t.get("family_match")]
    notes = (list(sb7.notes)
             + [f"[palette-bucket] {n}" for n in pal_notes]
             + [(f"Y7_2025 = X7 (patterns + materials) UNION the corrected palette bucket "
                 f"(residue_b2, viewer-certified as Z_palette_v2): +{n_mat} extended "
                 f"materials, +{n_s} structural + {n_t} thermal PropertySetElement assets "
                 f"re-valued over their slots' own skeletons (int params correctly keyed, "
                 f"ascending param-id order by construction)."),
                (f"provisional X7 plan: {len(plan7.pairs)} landed; palette corr reclaimed "
                 f"{len(reclaimed)} unconsumed X7 role-sibling slot(s): {reclaimed[:12]}")])
    info = {**dict(sb7.info or {}),
            "palette_bucket_v2": {
                "materials_extended": n_mat, "structural_v2": n_s, "thermal_v2": n_t,
                "revalue_traces": traces,
                "family_mismatches": fam_mismatch,
                "x7_provisional_landed": len(plan7.pairs),
                "sibling_slots_reclaimed_by_palette": reclaimed,
            }}
    return GS.SubstBuild(old_ids=old_ids, records=list(sb7.records) + ext_records,
                         corr=corr, new_only=list(sb7.new_only or []), notes=notes,
                         residue=dict(sb7.residue or {}), info=info)


def _dispatch_build_for(out_dir: str, orig_build_for):
    """V3.build_for with the X7P key added (everything else delegates)."""
    def build_for_2025(rung, ctx):
        if rung.build == "X7P":
            return _build_X7P(ctx, out_dir)
        return orig_build_for(rung, ctx)
    return build_for_2025


def _adapted_build_for(inner):
    """Wrap a build_for so every record passes through port2025.adapt_record
    (2025 class ordinals, 2025-shaped bodies, the confirmed field maps).
    Re-implementation of the genesis-2025-port stream's proven adapter
    (experiments/genesis2025/subst/run_ladder2025.py) so this module has no
    import dependency on a script outside src/."""
    _tools()
    from rvt.genesis import port2025 as P25
    import genesis_substitute as GS

    def adapted(rung, ctx):
        sb = inner(rung, ctx)
        allrecs = list(sb.records) + list(sb.new_only or [])
        names: Dict[int, str] = {}
        for r in allrecs:
            nm = GS._rec_name(r) or GS._catalog_name(r)
            if nm:
                names[int(r.elem_id)] = nm
        resolve = lambda i: names.get(int(i))                     # noqa: E731

        def port(records, dropped):
            out = []
            for r in records:
                try:
                    out.append(P25.adapt_record(r, resolve_name=resolve))
                except P25.Missing2025 as ex:
                    dropped.append({"ours": int(r.elem_id), "class": r.class_name,
                                    "name": names.get(int(r.elem_id), ""),
                                    "reason": str(ex)})
            return out

        dropped: List[dict] = []
        kept = port(sb.records, dropped)
        kept_new = port(sb.new_only or [], dropped)
        kept_ids = {int(r.elem_id) for r in kept}
        corr = {int(k): int(v) for k, v in sb.corr.items() if int(v) in kept_ids}
        notes = list(sb.notes) + [
            f"[port2025] {len(kept) + len(kept_new)} records adapted to the Revit-2025 "
            f"schema (2025 class ordinals, confirmed field maps; rvt.genesis.port2025); "
            f"{len(dropped)} record(s) of 2026-only classes emit nothing on 2025"
            + (": " + ", ".join(sorted({d["class"] for d in dropped})) if dropped else "")]
        out = GS.SubstBuild(old_ids=list(sb.old_ids), records=kept, corr=corr,
                            new_only=kept_new, notes=notes,
                            residue=dict(sb.residue or {}),
                            info={**dict(sb.info or {}),
                                  "port2025": {"adapted": len(kept) + len(kept_new),
                                               "dropped_2026_only": dropped}})
        extra = getattr(sb, "extra_records_for_resolution", None)
        if extra is not None:
            out.extra_records_for_resolution = extra
        return out

    return adapted


# ===========================================================================
# 3. THE PEN-TABLE SCALE-KEY PREFLIGHT (verify, never assume)
# ===========================================================================

def pen_scale_key_check(base_path: str) -> dict:
    """Decode the base's OWN project pen table (m_famId -1) and compare its
    model scale-key set + pen count + persp/draft markers against our
    constructor's constants.  Returns the comparison; ``match`` must be True
    before Y1_2025 may build (the charter's 'verify the 2025 scale keys')."""
    _tools()
    from rvt.genesis import settings as SETT
    from rvt.mutate import Document

    doc = Document.from_file(base_path)
    found: Optional[dict] = None
    elem = None
    for eid in sorted(doc.et_by_id):
        try:
            v = doc.value(int(eid), 102) or {}
        except Exception:
            continue
        if "m_pPenWidthTable" in v and int(v.get("m_famId", 0) or 0) == -1:
            found, elem = v, int(eid)
            break
    if found is None:
        return {"match": False, "error": "no project pen table (m_famId -1) in the base"}
    tbl = ((found.get("m_pPenWidthTable") or {}).get("value") or {})
    model = ((tbl.get("m_modelPenInfo") or {}).get("value")
             if isinstance(tbl.get("m_modelPenInfo"), dict) else tbl.get("m_modelPenInfo")) or []
    if isinstance(model, dict):
        model = model.get("value") or []
    scales = []
    pens_per = set()
    for pi in model:
        piv = (pi.get("value") if isinstance(pi, dict) and "value" in pi else pi) or {}
        scales.append(int(piv.get("m_invertedScale")))
        pens = piv.get("m_pens")
        if isinstance(pens, dict):
            pens = pens.get("value")
        pens_per.add(len(pens or []))

    def _marker(key: str) -> Optional[int]:
        x = tbl.get(key)
        xv = (x.get("value") if isinstance(x, dict) and "value" in x else x) or {}
        if isinstance(xv, dict) and "m_invertedScale" in xv:
            return int(xv["m_invertedScale"])
        return None

    ours = list(SETT.PEN_SCALE_BREAKPOINTS)
    rep = {
        "base_pen_table_elem": elem,
        "base_model_scales": sorted(scales),
        "our_constructor_scales": sorted(ours),
        "pens_per_scale": sorted(pens_per),
        "perspective_marker": _marker("m_perspectiveModelPenInfo"),
        "draft_marker": _marker("m_draftPenInfo"),
        "match": (sorted(scales) == sorted(ours) and pens_per == {16}
                  and _marker("m_perspectiveModelPenInfo") == -1
                  and _marker("m_draftPenInfo") == -1),
        "meaning": ("the 2025 corpus scale-key set VERIFIED against the base's own "
                    "project pen table -- the 2026 constant holds iff match=True "
                    "(charter: never assume 2026's set)"),
    }
    return rep


# ===========================================================================
# 4. THE RUN CONTEXT (context_2025 + the port-layer swaps)
# ===========================================================================

@contextlib.contextmanager
def y2025_context(base_path: str, out_dir: str = OUT_DIR):
    """tools/genesis_2025.py::context_2025(base) -- versions.reading + the
    SEVEN module-local framing constants + the ADocument default decoder --
    PLUS the port-layer swaps (default codecs, by-name class ids, 2025
    catalog tables, the rung table, the adapted build_for).  Everything
    restores on exit."""
    _tools()
    import genesis_2025 as G25
    import genesis_substitute_v3 as V3
    from rvt import encode as ENC
    from rvt import regadd, regdiff, versions
    from rvt.genesis import catalog as CAT
    from rvt.genesis import port2025 as P25
    from rvt.objects import ObjectDecoder

    rel = versions.detect_release(base_path)
    if rel != 2025:
        raise RuntimeError(f"base {base_path} is Revit {rel}, not 2025 -- refusing "
                           "(release mixing inside one ladder is the trap "
                           "rvt.versions.require_release exists for)")
    dec25, _enc25, schema25 = P25._S25()
    enum25, prof25 = P25.load_2025_catalog_constants()

    saved: List[Tuple[Any, str, Any]] = []

    def swap(mod, name, value):
        saved.append((mod, name, getattr(mod, name)))
        setattr(mod, name, value)

    base_rel = _relp(os.path.abspath(base_path))
    had_lineage = base_rel in V3.BASE_LINEAGE
    with G25.context_2025(base_path) as ords:
        swap(ENC, "_DEFAULT_ENCODER", ENC.ObjectEncoder(decoder=dec25))
        swap(regadd, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(regdiff, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(V3, "_class_id", P25.class_id_2025)
        swap(CAT, "load_builtin_category_enum", lambda *a, **k: enum25)
        swap(CAT, "load_builtin_style_profile", lambda *a, **k: prof25)
        swap(V3, "RUNGS", rungs_2025())
        V3.BASE_LINEAGE.setdefault(base_rel, LINEAGE_2025)
        swap(V3, "build_for", _adapted_build_for(_dispatch_build_for(out_dir, V3.build_for)))
        try:
            yield ords
        finally:
            for mod, name, val in reversed(saved):
                setattr(mod, name, val)
            if not had_lineage:
                V3.BASE_LINEAGE.pop(base_rel, None)


# ===========================================================================
# 5. probes.json (bisection-first; base + verdict #28 + control per entry)
# ===========================================================================

def single_change_crosscheck(out_dir: str = OUT_DIR) -> dict:
    """Y1s_2025 must be byte-identical to Y1_2025 (same parent, same build --
    a determinism proof recorded in the manifest)."""
    a = os.path.join(out_dir, "Y1_2025.rvt")
    b = os.path.join(out_dir, "Y1s_2025.rvt")
    if not (os.path.exists(a) and os.path.exists(b)):
        return {"checked": False, "reason": "Y1_2025.rvt / Y1s_2025.rvt not both built"}
    ma, mb = _md5(a), _md5(b)
    return {"checked": True, "Y1_2025_md5": ma, "Y1s_2025_md5": mb, "identical": ma == mb,
            "meaning": ("Y1s_2025 is the single-change pen probe; identical bytes prove the "
                        "build is deterministic and the two files carry ONE verdict")}


def gate_check(out_dir: str = OUT_DIR, order: Optional[List[str]] = None) -> dict:
    """Run tools/probe_batch.py's check (dry-run; stages nothing) over the
    built rungs and record the result: with B2025_K4 certified (verdict #28)
    the standing-controls gate must ACCEPT every entry."""
    _tools()
    import probe_batch as PB
    files = [os.path.join(out_dir, f"{n}.rvt") for n in (order or UPLOAD_ORDER)]
    files = [f for f in files if os.path.exists(f)]
    if not files:
        return {"ran": False, "reason": "no rung files built"}
    manifest = os.path.join(out_dir, "probes.json")
    entries, violations = PB.check_batch(
        files, manifest_override=manifest if os.path.exists(manifest) else None)
    return {
        "ran": True, "files": [_relp(f) for f in files],
        "violations": list(violations),
        "admissible": not violations,
        "entries": [{"file": e.file, "kind": e.kind, "base": (e.base.base if e.base else None),
                     "base_status": e.base_status} for e in entries],
        "meaning": ("tools/probe_batch.py check_batch dry-run: admissible=True means the "
                    "standing-controls gate resolves every rung's declared base to the "
                    "CERTIFIED B2025_K4 -- the K1 law satisfied, nothing staged/uploaded"),
    }


def write_probes(out_dir: str, base_path: str, control: dict,
                 pen: Optional[dict] = None, singles: Optional[dict] = None,
                 gate: Optional[dict] = None) -> str:
    """The upload manifest: bisection-first order, every entry naming the
    certified base (with the verdict-#28 citation) and the control."""
    _tools()
    import genesis_substitute_v3 as V3

    table = {r.name: r for r in rungs_2025()}
    reps: Dict[str, dict] = {}
    for name in table:
        p = os.path.join(out_dir, f"{name}.json")
        if os.path.exists(p):
            with open(p) as fh:
                reps[name] = json.load(fh)
    base_cert = V3.certification_of(base_path)
    base_block = {"file": _relp(os.path.abspath(base_path)),
                  "certification": base_cert,
                  "certified_by": VERDICT_28,
                  "lineage": LINEAGE_2025}
    entries: List[dict] = []
    for order, name in enumerate(UPLOAD_ORDER, 1):
        rung = table[name]
        rep = reps.get(name) or {}
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        plan = rep.get("plan") or {}
        e = {
            "order": order, "rung": name,
            "file": f"{_relp(out_dir)}/{name}.rvt",
            "release": 2025,
            "class_layer_substituted": rung.label,
            "base": base_block,
            "derived_from": rep.get("parent") or (
                _relp(os.path.abspath(base_path)) if rung.parent == "BASE"
                else f"{_relp(out_dir)}/{rung.parent}.rvt"),
            "parent_rung": rung.parent,
            "the_ONE_thing_it_tests": rung.tests,
            "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
            "mechanism": rep.get("mechanism"),
            "elements_substituted_in_place": {"landed": plan.get("landed"),
                                              "by_class": plan.get("landed_by_class"),
                                              "by_match": plan.get("by_match")},
            "ours_not_landed": (rep.get("ours_not_landed") or {}).get("by_class"),
            "residue_left_in_place": (rep.get("residue_olds_left_in_place") or {}).get("count"),
            "byte_delta": ({k: bd.get(k) for k in (
                "only_partition_differs", "records_changed_count", "expected_slots",
                "unexpected_changed_ids", "records_added_ids", "records_removed_ids",
                "elemtable_identical", "adocument_identical", "assertion_holds")} if bd else None),
            "registry_parity": (rep.get("parity") or {}).get("parity"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"),
                          "warnings": v.get("warnings")},
            "structural_ok": (rep.get("structural") or {}).get("ok"),
            "document_coherence": rep.get("coherence"),
            "verdict": rep.get("verdict", "not built"),
            "self_check": rep.get("FAILED_SELF_CHECK"),
            "bytes": rep.get("bytes"),
            "control_to_upload_with_batch": control,
            "report": f"{_relp(out_dir)}/{name}.json",
        }
        if name == "Y1s_2025" and singles and singles.get("checked"):
            e["identical_to"] = {"rung": "Y1_2025",
                                 "byte_identical": singles.get("identical"),
                                 "note": ("byte-identical to Y1_2025 (single-change pen probe "
                                          "== ladder rung 1): ONE upload may serve both names "
                                          "if the viewer dedupes; both files are staged")}
        entries.append(e)
    manifest = {
        "stream": ("y2025-settings (THE Y2025 SETTINGS + CATALOG RUNGS -- the certified "
                   "2026 ladder's Y1..Y7 on the CERTIFIED 2025 base B2025_K4, constructors "
                   "through rvt.genesis.port2025, run inside tools/genesis_2025.py::"
                   "context_2025)"),
        "release": 2025,
        "situation": (
            "VERDICTS #28: the whole 2025 reduction lineage certified in one round -- "
            "B2025_K4 is a CERTIFIED base and the v3 engine's assert_certified gate "
            "accepts it (no --allow-uncertified anywhere in this ladder). These rungs "
            "put OUR constructors' output at Autodesk's own 2025 registrations, one "
            "class layer at a time, zero registration motion."),
        "the_operation": (
            "In-place substitution (rvt.regadd.substitute_elements): our constructor's "
            "OBJECT record (seq-102) replaces the base's at the SAME element id -- same "
            "ElemTable row, same record position, same registry slots; Global/Latest and "
            "Global/ElemTable BYTE-IDENTICAL to the parent (asserted per rung); nothing "
            "added, nothing deleted. Every rung: validator 0 errors, structural proof, "
            "four-registry coherence (1/0/0), registry parity, a regdiff registration "
            "sample, and the byte-delta assertion table (only the landed slots' seq-102 "
            "records change)."),
        "base": base_block,
        "standing_control": control,
        "controls_discipline": (
            "EVERY batch is uploaded with the certified control (CTRL_B2025_K4_base.rvt, "
            "md5-identical to the certified base; tools/probe_batch.py stage will mint its "
            "own CTRL_..._b<n> copy). If the CONTROL fails, the batch is VOID (oracle / "
            "service health) and NOTHING about our constructors is read from it."),
        "upload_order_bisection_first": [e["rung"] for e in entries],
        "reading_the_results": {
            "how": ("Upload in the listed order (control first). Y7_2025 is the deepest "
                    "cumulative rung of this stream: PASS proves every settings + catalog + "
                    "palette constructor loads at 2025 registrations in one verdict. "
                    "Y7_2025 FAIL -> read the singles: Y1s_2025 (one pen object) and "
                    "Y6s_2025 (only the catalog) bracket the layer; then the intermediates "
                    "deep->shallow -- the first FAIL whose parent PASSED convicts exactly "
                    "that rung's class layer, every registration variable already "
                    "eliminated by construction."),
            "Y1s_2025 FAIL": ("even ONE our-object at a 2025 registration fails: the object "
                              "CONTENT layer is the defect (diff our pen record vs the "
                              "base's project table)."),
            "Y1s_2025 PASS + Y6s_2025 FAIL": "our catalog VALUES are the 2025 reader's objection, isolated.",
            "singles PASS, Y7_2025 FAIL": ("a settings constructor (Y2..Y5), the cumulative "
                                           "catalog (Y6) or the palette layer (Y7) -- the "
                                           "intermediates name it."),
            "ALL PASS": ("every constructor this stream owns loads on 2025. Next campaign "
                         "steps (other streams): the Y8/Y9 datum + view rungs, the residue "
                         "layers, then tools/genesis_compose.py under the same 2025 context "
                         "=> G_ABPD_2025 => the front door's 2025 slot."),
        },
        "pen_scale_key_verification": pen,
        "single_change_identity": singles,
        "probe_batch_gate_check": gate,
        "next_steps_other_streams": (
            "Y8_2025 (datum + identity) and Y9_2025 (view layer) mirror v3's Y8/Y9 on top "
            "of Y7_2025; then the residue rounds; then compose (genesis_compose) => "
            "experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt -- the path "
            "src/rvt/frontdoor/assets/genesis_base.json releases.2025 awaits."),
        "probes": entries,
        "derivation_chain": [f"{r.name} <- {r.parent}" for r in rungs_2025()],
    }
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\n[probes] wrote {_relp(p)} ({len(entries)} entries)")
    return p


# ===========================================================================
# 6. THE DRIVER
# ===========================================================================

def run(base: str = DEFAULT_BASE_2025, out_dir: str = OUT_DIR, only: str = "",
        manifest_only: bool = False) -> int:
    _tools()
    import genesis_substitute_v3 as V3

    base_path = os.path.abspath(base)
    out_dir = os.path.abspath(out_dir)
    if not os.path.exists(base_path):
        log(f"base {base_path} does not exist")
        return 2
    # THE GATE: B2025_K4 must be viewer-certified -- and it is (verdict #28).
    # NO allow_uncertified anywhere in this stream.
    cert = V3.assert_certified(base_path)
    log(f"[base] {_relp(base_path)} -- CERTIFIED: {str(cert.get('proves'))[:120]}")
    log(f"[base] {VERDICT_28[:150]}...")
    os.makedirs(out_dir, exist_ok=True)
    control = V3.stage_control(base_path, out_dir)
    log(f"[control] staged {control['file']} (md5 {control['md5']})")

    want = [s.strip() for s in only.split(",") if s.strip()]
    pen: Optional[dict] = None
    if not manifest_only:
        with y2025_context(base_path, out_dir):
            pen = pen_scale_key_check(base_path)
            log(f"[pen-preflight] base scales {pen.get('base_model_scales')} vs ours "
                f"{pen.get('our_constructor_scales')}; pens/scale {pen.get('pens_per_scale')}; "
                f"match={pen.get('match')}")
            if not pen.get("match"):
                raise RuntimeError(f"2025 pen scale-key set does NOT match our constructor's: "
                                   f"{pen} -- the Y1 constructor must be re-mined first")
            for rung in rungs_2025():
                if want and rung.name not in want:
                    continue
                parent = V3.parent_path_of(rung, base_path, out_dir)
                if not os.path.exists(parent):
                    log(f"\n== {rung.name}: parent {_relp(parent)} missing -- SKIPPED")
                    continue
                try:
                    V3.substitute_inplace(rung, parent, base_path, out_dir, control=control)
                except Exception as ex:
                    import traceback
                    tb = traceback.format_exc()
                    log(f"\n== {rung.name}: BUILD ABORTED -- {ex!r}\n{tb}")
                    V3._write_report(out_dir, rung.name,
                                     {"rung": rung.name, "label": rung.label,
                                      "verdict": "NOT-BUILT", "abort": repr(ex),
                                      "traceback": tb})
                    bad = os.path.join(out_dir, f"{rung.name}.rvt")
                    if os.path.exists(bad):
                        os.remove(bad)                 # never leave a half-built rung
                    if not want and rung.name in LADDER:
                        break                          # the cumulative ladder stops honestly
    else:
        pen_p = os.path.join(out_dir, "probes.json")
        if os.path.exists(pen_p):
            try:
                with open(pen_p) as fh:
                    pen = (json.load(fh) or {}).get("pen_scale_key_verification")
            except Exception:
                pen = None

    singles = single_change_crosscheck(out_dir)
    if singles.get("checked"):
        log(f"[singles] Y1s_2025 == Y1_2025 byte-identical: {singles['identical']}")
    write_probes(out_dir, base_path, control, pen, singles, None)
    gate = gate_check(out_dir)
    if gate.get("ran"):
        log(f"[gate] probe_batch check: admissible={gate['admissible']}"
            + (f"; violations: {gate['violations'][:2]}" if gate["violations"] else ""))
    write_probes(out_dir, base_path, control, pen, singles, gate)

    log("\n=== Y2025 SETTINGS + CATALOG LADDER SUMMARY ===")
    ok = True
    for name in LADDER + SINGLES:
        p = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            if not want:
                ok = False
            continue
        with open(p) as fh:
            rep = json.load(fh)
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        plan = rep.get("plan") or {}
        verdict = rep.get("verdict", "?")
        if verdict != "VALID":
            ok = False
        log(f"  {name:<9} {verdict:<10} validator errors={v.get('errors')} "
            f"warnings={v.get('warnings')}  landed {plan.get('landed', '-')}  changed "
            f"{bd.get('records_changed_count', '-')}  latest-identical "
            f"{bd.get('adocument_identical', '-')}  {rep.get('bytes', 0) or 0:>9,} B")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=DEFAULT_BASE_2025)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--only", default="", help="comma list of rungs (Y1_2025,...)")
    ap.add_argument("--manifest-only", action="store_true",
                    help="only re-write probes.json from the existing reports")
    args = ap.parse_args(argv)
    return run(args.base, args.out_dir, args.only, args.manifest_only)


if __name__ == "__main__":
    sys.exit(main())
