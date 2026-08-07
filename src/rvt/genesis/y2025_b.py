"""rvt.genesis.y2025_b -- THE Y2025 DATUM/VIEWS + RESIDUE RUNGS (stream
y2025-views): Y8_2025 / Y9_2025 + the residue rounds RA_2025 / RB_2025 /
RC_2025 on the CERTIFIED 2025 base, emitted into
``experiments/genesis/subst_k4_2025/``.

SITUATION (2026-08-04, verdicts #28 of docs/inbox/genesis-audit.md): the
ENTIRE 2025 reduction lineage certified in one viewer round -- the untouched
2025 sample (control), R5_2025 (implicitly via lineage), R9_2025, K3_2025 and
**B2025_K4** (``experiments/genesis2025/reduce/B2025_K4.rvt``) ALL LOAD.
B2025_K4 is in ``docs/coverage/viewer-certified.json`` ``certified`` -- the
substitution engine's gate (``genesis_substitute_v3.assert_certified``)
accepts it WITHOUT any override.  The goal of the campaign is G_ABPD_2025
(the composed 2025 genesis base) at
``experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt``.

THIS STREAM builds the 2026 ladder's Y8/Y9 + residue A/B/C equivalents for
2025, every rung the certified v3 IN-PLACE mechanism
(``rvt.regadd.substitute_elements``, seq-102 object records only unless a
rung declares otherwise, ``Global/Latest`` + ``Global/ElemTable``
byte-identical, nothing added / nothing deleted) with every record passed
through the ``rvt.genesis.port2025`` field maps (2025 class ordinals,
2025-shaped bodies -- the port stream's confirmed table, incl. the four
layout deltas the plan missed: DBView ``m_viewPositionId`` ABSENT in 2025,
DBViewDrafting ``m_sheetTitleBlockId`` absent, Viewport v13->10,
BrowserOrganizationTracking v6->5):

  Y8_2025   identity / site / project info + the level & phase layer
            (v3's Y8 split of X8+X9)
  Y9_2025   the 19 project view types + the view constellations + document
            sun (v3's Y9 split of X9) -- the constructors emit the 2025
            layout (no m_viewPositionId anywhere; proven per record by the
            2025 encode->decode->re-encode self-check inside the live emit)
  RA_2025   the residue-A round in ONE cumulative rung (2026's ZA_deep):
            sub-categories (X6b layer), annotation types + fonts +
            arrowheads, datum content (grids + surplus levels), the pattern
            surplus, the appearance assets
  RB_2025   the residue-B round scoped by the charter: RB1 = the parameter
            DEFINITIONS layer (OUR definitions at the 2025 file's own
            shared-parameter GUID registry keys) and RB2 = the MEP catalog
            (wire materials / insulations / temperature ratings + pipe
            schedules / materials / connections + pipe segments).  The
            2026-only conductor CATALOG (CustomElement / NamingCell /
            RbsConductor*) does not exist in the 2025 class map: any record
            of those classes is dropped LOUDLY by the port layer and listed
            per class -- their 2025 representation is the string-valued
            wire-type field (port2025 hook).
  Z_RC_2025 the compose-consumable slice of residue C: OUR names on the
            operating-year schedules, the stale Autodesk-rendered type
            preview caches nulled, and the residue drafting view's
            RvtLinkOverrides display map EMPTIED (+ its header cleaned) --
            all slots UNTOUCHED by any Y rung, so the one-call composer can
            merge this rung (law 1 disjointness / law 4 parent coherence).
  RC_2025_inplace  the remaining residue-C fixes that OVERLAP Y-rung slots
            (never one-call-composable; the 2026 precedent is the second
            compose from certified G_ABPD): the five landed view slots'
            seq-101 headers re-emitted without the RvtLinkSymbol deletion-
            parent entry, and the AreaMeasureElem unwired from the content-
            bearing plan topology (deletion finding 2's fix).
  RC_2025   the lawful straggler deletions per the reduction law (maxgc +
            rvt.reduce.delete_elements + reduce_law.assert_edit_free): the
            external-link trio (symbol delete-reachable only after the
            header/link-override fixes), the zero-referrer vendor
            DataStorage blob, the locked-EQ constraint dimension + its
            reference planes, and the room constellation atomically with
            its containing plan topology.

COMPOSER HANDOFF (tools/genesis_compose_2025.py watches
``experiments/genesis/subst_k4_2025/**/Z*.rvt`` + ``**/D_*.json``): RA_2025 /
RB_2025 are aliased as ``Z_RA_2025.rvt`` / ``Z_RB_2025.rvt`` (md5-identical
copies whose reports name their parents), ``Z_RC_2025`` is Z-named directly,
and the three PIN-FREE deletion sets (proven by maxgc on this chain) are
written as ``D_2025_*.json`` specs.  The header-cleanup / area-unwiring
layers and the symbol+room deletions are NOT handed to the one-call
composer (slot overlap with Y2/Y5/Y9 -- composition law 1): they are the
RC_zero-2025 second-compose stage, proven here on the chain.

BASE + PARENT RESOLUTION.  The BASE of every rung is the certified
``experiments/genesis2025/reduce/B2025_K4.rvt`` (no --allow-uncertified
anywhere).  The settings stream owns Y1_2025..Y7_2025 in the same directory;
Y8_2025 builds FROM ``Y7_2025.rvt`` the moment it exists.  Until then the
chain is PROTOTYPED on the port stream's Y7 (``experiments/genesis2025/
subst/Y7.rvt`` -- built on md5-identical B2025_K4 bytes, certification
PENDING), the parent mode is recorded in EVERY report
(``parent_mode: prototype-parent`` vs ``settings-chain``), and ``--rebase``
rebuilds the whole chain once the settings rungs land.

Every emission runs inside :func:`context_y2025` -- ``tools/genesis_2025.py
context_2025`` (the SEVEN 2026-baked framing constants + the ADocument
decoder) PLUS the per-release default codecs, the 2025 catalog constants,
v3's class-id resolution and the port2025 build adaptation.  Everything is
restored on exit; nothing leaks into the 2026 creation path.

Territory: this module, ``tests/test_y2025_b.py``,
``experiments/genesis/subst_k4_2025/{Y8,Y9,RA,RB,RC,Z_R,D_2025,CTRL}*``,
``docs/inbox/y2025-views.md``.  Everything else IMPORTED, never edited.

Reproduce (repo root)::

    .venv/bin/python -m rvt.genesis.y2025_b            # the whole chain
    .venv/bin/python -m rvt.genesis.y2025_b --stage y89
    .venv/bin/python -m rvt.genesis.y2025_b --stage ra,rb,rc
    .venv/bin/python -m rvt.genesis.y2025_b --rebase   # after Y7_2025 lands
"""
from __future__ import annotations

import collections
import contextlib
import copy
import dataclasses
import functools
import glob as _glob
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if _p not in sys.path:                                     # pragma: no cover
        sys.path.insert(0, _p)

OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025")
BASE_2025 = os.path.join(ROOT, "experiments", "genesis2025", "reduce", "B2025_K4.rvt")
PROTOTYPE_DIR = os.path.join(ROOT, "experiments", "genesis2025", "subst")
PROTOTYPE_Y7 = os.path.join(PROTOTYPE_DIR, "Y7.rvt")
PROTOTYPE_CHAIN = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"]
SETTINGS_CHAIN = ["Y1_2025", "Y2_2025", "Y3_2025", "Y4_2025", "Y5_2025",
                  "Y6_2025", "Y7_2025"]
SAMPLES_2025_DIR = os.path.join(ROOT, "samples", "2025")
ASSET_PROFILE_2025 = os.path.join(OUT_DIR, "generic_asset_profile_2025.json")
RECORD_MD = os.path.join(ROOT, "docs", "inbox", "y2025-views.md")

#: my chain, base-side first (after the settings chain / prototype parent)
MY_CHAIN = ["Y8_2025", "Y9_2025", "RA_2025", "RB1_defs_2025", "RB2_mepcat_2025",
            "Z_RC_2025", "RC_2025_inplace"]

#: classes that make a plan-topology CONTENT-BEARING (the room constellation)
ROOM_CONTENT_CLASSES = ("CurveElem", "LevelRoomPlan", "RoomElem")


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1,
                  default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o))


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# lazy imports (tools/ modules)
# ---------------------------------------------------------------------------
def _V3():
    import genesis_substitute_v3 as V3                             # noqa: E402
    return V3


def _GS():
    import genesis_substitute as GS                                # noqa: E402
    return GS


def _G25():
    import genesis_2025 as G25                                     # noqa: E402
    return G25


def _GD():
    import genesis_deletion as GD                                  # noqa: E402
    return GD


# ---------------------------------------------------------------------------
# 1. parent resolution: the settings stream's Y7_2025, else the prototype Y7
# ---------------------------------------------------------------------------
def deep_parent() -> Tuple[str, str, List[str], bool]:
    """(path, mode, protection_chain_names_nearest_first, prototype?) of the
    file Y8_2025 derives from RIGHT NOW.  ``protection_chain`` names the
    reports whose landed slots must be protected (nearest first)."""
    settled = os.path.join(OUT_DIR, "Y7_2025.rvt")
    if os.path.exists(settled):
        return settled, "settings-chain (Y7_2025 landed by the settings stream)", \
            list(reversed(SETTINGS_CHAIN)), False
    if os.path.exists(PROTOTYPE_Y7):
        return PROTOTYPE_Y7, (
            "prototype-parent: experiments/genesis2025/subst/Y7.rvt (the port "
            "stream's Y1..Y7 on md5-identical B2025_K4 bytes; certification "
            "PENDING) -- REBASE onto Y7_2025 when the settings stream lands "
            "(run --rebase)"), [], True
    return BASE_2025, ("bare-base prototype: no Y7 exists anywhere yet -- "
                       "cumulative resolution (our Y7 palette names) unavailable"), [], True


# ---------------------------------------------------------------------------
# 2. the 2025 run context
# ---------------------------------------------------------------------------
def _source_aware_hooks(P25) -> Dict[Tuple[str, str], Callable]:
    """port2025's HOOKS exist to SYNTHESIZE a 2025 field from 2026 data.  When
    the source object ALREADY CARRIES the 2025 field (a subtree copied from a
    decoded 2025 parent -- residue planners do this), the hook must not
    clobber it: carry the source value instead."""
    def wrap(field: str, orig: Callable) -> Callable:
        def hook(src, ctx, _f=field, _o=orig):
            if isinstance(src, dict) and _f in src:
                return copy.deepcopy(src[_f])
            return _o(src, ctx)
        return hook
    return {k: wrap(k[1], fn) for k, fn in P25.HOOKS.items()}


@contextlib.contextmanager
def context_y2025(base_path: str = BASE_2025, *, prototype: bool = False):
    """genesis_2025.context_2025 (the seven framing-constant patches + the
    ADocument decoder) PLUS the per-release default codecs, the 2025 catalog
    constants, v3's class-id resolution, the port2025 build adaptation and
    (prototype mode) chain-report merging.  Restores everything on exit."""
    from rvt import encode as ENC
    from rvt import regadd, regdiff
    from rvt.genesis import catalog as CAT
    from rvt.genesis import port2025 as P25
    from rvt.genesis import residue_a as RA
    from rvt.objects import ObjectDecoder
    G25 = _G25()
    V3 = _V3()

    dec25, enc25, schema25 = P25._S25()
    saved: List[Tuple[Any, str, Any]] = []

    def swap(mod, name, value):
        saved.append((mod, name, getattr(mod, name)))
        setattr(mod, name, value)

    with G25.context_2025(base_path) as ords:
        swap(ENC, "_DEFAULT_ENCODER", ENC.ObjectEncoder(decoder=dec25))
        swap(regadd, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(regdiff, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(V3, "_class_id", P25.class_id_2025)
        enum25, prof25 = P25.load_2025_catalog_constants()
        swap(CAT, "load_builtin_category_enum", lambda *a, **k: enum25)
        swap(CAT, "load_builtin_style_profile", lambda *a, **k: prof25)
        swap(P25, "HOOKS", _source_aware_hooks(P25))
        orig_build_for = V3.build_for
        swap(V3, "build_for", _make_adapted_build_for(orig_build_for))
        # chain-report merging: protection + prior correspondence must see the
        # PROTOTYPE chain's reports (they live in the port stream's dir under
        # Y1..Y7 names) when Y8 is prototyped on the prototype Y7
        orig_prev, orig_prior = V3.previously_landed, V3.prior_correspondence
        if prototype:
            def prev_merged(out_dir, chain):
                out = orig_prev(out_dir, chain)
                for slot, name in orig_prev(PROTOTYPE_DIR, PROTOTYPE_CHAIN).items():
                    out.setdefault(slot, f"proto:{name}")
                return out

            def prior_merged(out_dir, chain):
                proto = orig_prior(PROTOTYPE_DIR, PROTOTYPE_CHAIN)
                ours = orig_prior(out_dir, chain)
                return {**proto, **ours}
            swap(V3, "previously_landed", prev_merged)
            swap(V3, "prior_correspondence", prior_merged)
        # v3 rung table: append the 2025-named rung descriptors (chain names)
        added = my_rungs(prototype=prototype)
        V3.RUNGS.extend(added)
        # residue-A: the self-check + asset profile must be 2025-bound
        swap(RA, "check_object", _check_object_2025)
        prof = load_asset_profile_2025()
        swap(RA, "load_generic_asset_profile", lambda *a, **k: prof)
        # base lineage banner for reports
        V3.BASE_LINEAGE.setdefault(_relp(base_path), (
            "B2025_K4 = the certified 2025 family-free base (viewer round of "
            "2026-08-04, verdicts #28): samples/2025/rstbasicsampleproject -> "
            "R5..R9_2025 (maxgc, EDIT-FREE) -> K3_2025 (usage nulls) -> B2025_K4 "
            "(all 52 embedded documents removed, four-registry coherent 1/0/0/0). "
            "docs/inbox/genesis-2025-reduce.md"))
        try:
            yield ords
        finally:
            for r in added:
                V3.RUNGS.remove(r)
            for mod, name, val in reversed(saved):
                setattr(mod, name, val)


def _check_object_2025(class_name: str, value: dict) -> dict:
    """residue_a.check_object under the pinned 2025 codec (the per-object
    honesty gate of every residue plan)."""
    from rvt.genesis import port2025 as P25
    dec, enc, _s = P25._S25()
    cid = P25.class_id_2025(class_name)
    body = enc.encode_object(cid, value)
    got = dec.decode_record(cid, body)
    re = enc.encode_object(cid, got.value) if got.clean else b""
    return {"class": class_name, "bytes": len(body), "clean": bool(got.clean),
            "byte_exact": (re == body), "errors": (got.errors or [])[:3],
            "ok": bool(got.clean and re == body)}


# ---------------------------------------------------------------------------
# 3. port2025 adaptation of builds (v3 SubstBuilds + residue-A Obj plans)
# ---------------------------------------------------------------------------
def _adapt_substbuild(sb):
    """Every record of a ``genesis_substitute.SubstBuild`` through
    ``port2025.adapt_record``; 2026-only classes dropped LOUDLY."""
    from rvt.genesis import port2025 as P25
    GS = _GS()
    allrecs = list(sb.records) + list(sb.new_only or [])
    names: Dict[int, str] = {}
    for r in allrecs:
        nm = GS._rec_name(r) or GS._catalog_name(r)
        if nm:
            names[int(r.elem_id)] = nm
    resolve = lambda i: names.get(int(i))                          # noqa: E731

    dropped: List[dict] = []

    def port(records):
        out = []
        for r in records:
            try:
                out.append(P25.adapt_record(r, resolve_name=resolve))
            except P25.Missing2025 as ex:
                dropped.append({"ours": int(r.elem_id), "class": r.class_name,
                                "name": names.get(int(r.elem_id), ""),
                                "reason": str(ex)})
        return out

    kept = port(sb.records)
    kept_new = port(sb.new_only or [])
    kept_ids = {int(r.elem_id) for r in kept}
    corr = {int(k): int(v) for k, v in sb.corr.items() if int(v) in kept_ids}
    notes = list(sb.notes) + [
        f"[port2025] {len(kept) + len(kept_new)} records adapted to the Revit-2025 "
        f"schema (2025 class ordinals, confirmed field maps); {len(dropped)} "
        f"record(s) of 2026-only classes emit nothing on 2025"
        + (": " + ", ".join(sorted({d["class"] for d in dropped})) if dropped else "")]
    adapted = GS.SubstBuild(
        old_ids=list(sb.old_ids), records=kept, corr=corr, new_only=kept_new,
        notes=notes, residue=dict(sb.residue or {}),
        info={**dict(sb.info or {}),
              "port2025": {"adapted": len(kept) + len(kept_new),
                           "dropped_2026_only": dropped}})
    extra = getattr(sb, "extra_records_for_resolution", None)
    if extra is not None:
        adapted.extra_records_for_resolution = extra
    return adapted


def _make_adapted_build_for(orig_build_for):
    def adapted_build_for(rung, ctx):
        return _adapt_substbuild(orig_build_for(rung, ctx))
    return adapted_build_for


def adapt_obj_plans(plans: Dict[int, Any]) -> Tuple[Dict[int, Any], List[dict]]:
    """residue-A ``Obj`` plans -> 2025 shape: value through ``port2025.adapt``
    (source-aware hooks active), class id -> the 2025 ordinal."""
    from rvt.genesis import port2025 as P25
    out: Dict[int, Any] = {}
    dropped: List[dict] = []
    for slot, o in plans.items():
        try:
            v25 = P25.adapt(o.class_name, o.value)
            out[int(slot)] = dataclasses.replace(
                o, class_id=P25.class_id_2025(o.class_name), value=v25)
        except P25.Missing2025 as ex:
            dropped.append({"slot": int(slot), "class": o.class_name, "reason": str(ex)})
    return out, dropped


# ---------------------------------------------------------------------------
# 4. the 2025 generic appearance-asset profile (mined from the 2025 corpus)
# ---------------------------------------------------------------------------
def derive_asset_profile_2025(*, verbose: bool = True) -> dict:
    """The Protein GenericSchema appearance-asset PROPERTY SKELETON mined
    over the SIX 2025 samples (the 2025 twin of residue_a's 2026 profile:
    property names / order / APropertyXxx classes + the values IDENTICAL in
    every specimen; free properties carry no value -- they are OURS).  Must
    run inside :func:`context_y2025` (2025 framing)."""
    from rvt.genesis.residue_a import GENERIC_ASSET_OURS
    from rvt.mutate import Document
    samples = sorted(_glob.glob(os.path.join(SAMPLES_2025_DIR, "*.rvt")))
    order: Dict[str, List[int]] = collections.defaultdict(list)
    types: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    values: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    present: collections.Counter = collections.Counter()
    n = 0
    for s in samples:
        doc = Document.from_file(s)
        for e in doc.et_by_id:
            if doc.class_of(int(e)) != "AppearanceAssetElem":
                continue
            v = doc.value(int(e)) or {}
            a = ((v.get("m_pAppearanceAsset") or {}).get("value") or {})
            asset = a.get("m_Asset") or {}
            if asset.get("m_sName") != "GenericSchema":
                continue
            n += 1
            for i, p in enumerate(asset.get("m_aAProperties") or []):
                pv = p.get("value") or {}
                name = pv.get("m_sName")
                if not name:
                    continue
                present[name] += 1
                order[name].append(i)
                types[name][p.get("ptr_class")] += 1
                values[name][json.dumps(pv.get("m_value"), sort_keys=True,
                                        default=str)] += 1
        if verbose:
            log(f"   [asset-profile-2025] {os.path.basename(s)}: cumulative "
                f"Generic assets {n}")
    props = []
    for name in sorted(present, key=lambda k: (sum(order[k]) / max(1, len(order[k])))):
        cnt = present[name]
        cls_ = types[name].most_common(1)[0][0]
        val, val_n = values[name].most_common(1)[0]
        constant = (val_n == cnt) and (cnt >= n)
        props.append({
            "name": name, "aproperty_class": cls_,
            "present_in": cnt, "of": n,
            "modal_ordinal": collections.Counter(order[name]).most_common(1)[0][0],
            "constant": bool(constant and name not in GENERIC_ASSET_OURS),
            "value": (json.loads(val) if (constant and name not in GENERIC_ASSET_OURS)
                      else None),
            "corpus_top_value": json.loads(val),
            "corpus_top_share": round(val_n / cnt, 3),
        })
    prof = {
        "generator": "rvt.genesis.y2025_b.derive_asset_profile_2025",
        "derived_from": [_relp(s) for s in samples], "generic_specimens": n,
        "note": ("The 2025 Protein GenericSchema appearance-asset property "
                 "skeleton (per-release library constant, mined from the six "
                 "quarantined 2025 samples). Free properties (name / colour / "
                 "gloss / description / ...) carry no value: OURS at "
                 "construction time."),
        "properties": props,
    }
    _write_json(ASSET_PROFILE_2025, prof)
    if verbose:
        log(f"   [asset-profile-2025] wrote {_relp(ASSET_PROFILE_2025)} "
            f"({n} specimens, {len(props)} properties)")
    return prof


def load_asset_profile_2025() -> dict:
    prof = _read_json(ASSET_PROFILE_2025)
    if prof is not None:
        return prof
    return derive_asset_profile_2025()


# ---------------------------------------------------------------------------
# 5. Y8_2025 / Y9_2025 (v3's Y8/Y9 builders, 2025-named rung descriptors)
# ---------------------------------------------------------------------------
def my_rungs(*, prototype: bool) -> List[Any]:
    """The 2025-named v3 rung descriptors this stream appends to V3.RUNGS
    (name = report/file stem; the parent NAME drives derivation_chain /
    slot protection -- prototype mode resolves the chain via the merged
    report readers instead)."""
    V3 = _V3()
    rungs: List[Any] = []
    if not prototype:
        parent = "BASE"
        for k, name in enumerate(SETTINGS_CHAIN):
            b = ["X1", "X2", "X3", "X4", "X5", "X6a", "X7"][k]
            rungs.append(V3.Rung3(
                name=name, label=f"(settings stream) 2025 twin of the v3 {b} rung",
                parent=parent, build=b,
                description="settings-stream rung (chain stub for derivation)",
                tests="(settings stream)", if_pass="", if_fail=""))
            parent = name
        y8_parent = "Y7_2025"
    else:
        y8_parent = "BASE"
    rungs.append(V3.Rung3(
        name="Y8_2025",
        label="levels + phases (+ set/filter) + units / site / base points / project info -> ours, IN PLACE (2025)",
        parent=y8_parent, build="Y8",
        description=("The 2025 twin of the certified v3 Y8: the datum + identity layer's "
                     "objects replaced in place on the 2025 chain -- our L1/L2 levels at the "
                     "plan-bearing level slots, level type, phases + phase set + filter, "
                     "units, true north, geo sites / locations, base points, ProjectInfo. "
                     "Every record port2025-adapted (identical layout for this layer per the "
                     "confirmed table)."),
        tests=("Whether the 2025 reader accepts our datum + identity objects at Autodesk's "
               "own 2025 registrations."),
        if_pass="Our datum/identity constructors load at 2025 registrations.",
        if_fail="Bisect levels+phases vs units vs site/base-points vs project info."))
    rungs.append(V3.Rung3(
        name="Y9_2025",
        label="the 19 project view types + every view constellation (+ document sun) -> ours, IN PLACE (2025)",
        parent="Y8_2025", build="Y9",
        description=("The 2025 twin of the certified v3 Y9: the view layer in place. The "
                     "port layer emits the 2025 layout -- DBView has NO m_viewPositionId, "
                     "DBViewDrafting no m_sheetTitleBlockId, Viewport v13->10 (m_viewPosition/"
                     "m_viewAnchor dropped) -- proven per record by the in-emit 2025 "
                     "encode->decode->re-encode self-check."),
        tests=("Whether the 2025 reader accepts our view/view-type/sun objects (2025 layout) "
               "at Autodesk's own registrations -- the deepest cumulative Y rung."),
        if_pass="Every constructor of the Y chain loads at 2025 registrations.",
        if_fail="Bisect view types vs the 3D constellation vs the plans."))
    return rungs


def build_y89(*, only: Sequence[str] = ("Y8_2025", "Y9_2025")) -> Dict[str, dict]:
    """Emit Y8_2025 / Y9_2025 into OUT_DIR from the deepest available parent."""
    V3 = _V3()
    parent_path, mode, _chain, prototype = deep_parent()
    os.makedirs(OUT_DIR, exist_ok=True)
    reports: Dict[str, dict] = {}
    with context_y2025(BASE_2025, prototype=prototype):
        cert = V3.assert_certified(BASE_2025)
        log(f"[base] {_relp(BASE_2025)} -- CERTIFIED: {cert.get('proves', '')[:100]}")
        log(f"[parent] {_relp(parent_path)} -- {mode}")
        control = V3.stage_control(BASE_2025, OUT_DIR)
        for name in ("Y8_2025", "Y9_2025"):
            if name not in only:
                continue
            rung = V3.rung_by_name(name)
            p = parent_path if name == "Y8_2025" else os.path.join(OUT_DIR, "Y8_2025.rvt")
            if not os.path.exists(p):
                log(f"== {name}: parent {_relp(p)} missing -- SKIPPED")
                continue
            rep = V3.substitute_inplace(rung, p, BASE_2025, OUT_DIR, control=control)
            rep["parent_mode"] = mode
            rep["stream"] = "y2025-views"
            V3._write_report(OUT_DIR, name, rep)
            reports[name] = rep
    return reports


# ---------------------------------------------------------------------------
# 6. RA_2025 (the residue-A round, one cumulative rung)
# ---------------------------------------------------------------------------
def _landed_map_for(parent_names_nearest_first: Sequence[str], *,
                    prototype: bool, upto: Optional[str] = None) -> Dict[int, str]:
    """{slot: rung} landed by every rung STRICTLY BEFORE ``upto`` on this
    chain (``upto=None`` = the whole chain -- for the final census).  A rung
    being (re)built must never see its OWN prior report as landed."""
    from rvt.genesis import residue_a as RA
    chain = [n for n in MY_CHAIN]
    if upto is not None and upto in chain:
        chain = chain[:chain.index(upto)]
    landed = RA.ladder_landed(OUT_DIR, tuple(chain + list(parent_names_nearest_first)))
    if prototype:
        for slot, name in RA.ladder_landed(PROTOTYPE_DIR, tuple(PROTOTYPE_CHAIN + ["Y8", "Y9"])).items():
            # the prototype chain's Y8/Y9 reports are NOT this stream's rungs --
            # only its Y1..Y7 slots are protected parents; our own Y8_2025/Y9_2025
            # reports supersede via `chain` above
            if name in PROTOTYPE_CHAIN:
                landed.setdefault(slot, f"proto:{name}")
    return landed


def build_ra() -> dict:
    """RA_2025 = the Group-A residue layers in ONE cumulative in-place rung on
    Y9_2025 (sub-categories + annotation types/fonts/arrowheads + datum
    content + pattern surplus + appearance assets), every object
    port2025-adapted and 2025-round-trip-gated."""
    from rvt.genesis import residue_a as RA
    V3 = _V3()
    parent_file = os.path.join(OUT_DIR, "Y9_2025.rvt")
    if not os.path.exists(parent_file):
        raise SystemExit("RA_2025: Y9_2025.rvt missing -- build stage y89 first")
    _pp, mode, _c, prototype = deep_parent()
    with context_y2025(BASE_2025, prototype=prototype):
        cert = V3.assert_certified(BASE_2025)
        control = V3.stage_control(BASE_2025, OUT_DIR)
        t0 = time.time()
        parent = RA.Parent(parent_file)
        # 'residue' must mean THE 2025 CHAIN's residue: recompute the landed map
        parent.landed = _landed_map_for(_c, prototype=prototype, upto="RA_2025")
        parent.residue = RA.residue_by_class(parent.doc, parent.landed)
        log(f"[RA] parent {_relp(parent_file)}: landed {len(parent.landed)}, "
            f"residue classes {len(parent.residue)} ({round(time.time()-t0, 1)}s)")
        plans = [RA.plan_subcat(parent), RA.plan_annot(parent), RA.plan_datum(parent),
                 RA.plan_pattern(parent), RA.plan_asset(parent)]
        merged = RA.merge_plans(plans)
        rung = RA.RungPlan(
            "RA_2025",
            "the residue-A round (2025): sub-categories + annotation types/fonts/arrowheads "
            "+ datum content (grids + surplus levels) + pattern surplus + appearance assets, "
            "IN PLACE, port2025-adapted",
            merged.plans, merged.residue_left, merged.notes, info=merged.info)
        plans25, dropped = adapt_obj_plans(rung.plans)
        rung = RA.RungPlan(rung.name, rung.label, plans25, rung.residue_left,
                           rung.notes + [
                               f"[port2025] {len(plans25)} objects adapted to the 2025 "
                               f"schema; {len(dropped)} dropped as 2026-only"
                               + (f": {dropped}" if dropped else "")],
                           info={**rung.info, "port2025_dropped": dropped})
        rep = RA.emit_rung(rung, parent, OUT_DIR, base_certification=cert,
                           control=control)
        rep["parent_mode"] = mode
        rep["stream"] = "y2025-views"
        rep["parent"] = _relp(parent_file)
        # residue_a's emit declares its (2026-certified) parent as 'base'; on
        # this chain the ledger-certified ancestor is B2025_K4 -- declare THAT
        rep["base"] = {"file": _relp(BASE_2025), "certification": cert,
                       "note": ("the parent Y9_2025 is a STAGED chain file "
                                "(certification pending its viewer round); the "
                                "certified ancestor is B2025_K4")}
        _write_json(os.path.join(OUT_DIR, "RA_2025.json"), rep)
        # the curtain constellation: the coherent-removal queue (computed, handed over)
        curt = RA.curtain_constellation(parent.state)
        _write_json(os.path.join(OUT_DIR, "curtain_constellation_2025.json"), curt)
        log(f"[RA] curtain constellation: {curt.get('count')} elements "
            f"(removal queue for the deletion stream)")
        return rep


# ---------------------------------------------------------------------------
# 7. RB_2025 (residue-B: the definitions + MEP catalog, charter scope)
# ---------------------------------------------------------------------------
def build_rb() -> Dict[str, dict]:
    """RB1_defs_2025 (parameter definitions at the 2025 shared-parameter GUID
    registry keys) -> RB2_mepcat_2025 (the MEP catalog) -> RB_2025 (alias of
    the deepest).  The 2026-only conductor catalog is skipped BY CONSTRUCTION
    (Missing2025 -> listed)."""
    from rvt.genesis import residue_b as RB
    V3 = _V3()
    parent_file = os.path.join(OUT_DIR, "RA_2025.rvt")
    if not os.path.exists(parent_file):
        raise SystemExit("RB_2025: RA_2025.rvt missing -- build stage ra first")
    _pp, mode, _c, prototype = deep_parent()
    reports: Dict[str, dict] = {}
    with context_y2025(BASE_2025, prototype=prototype):
        control = V3.stage_control(BASE_2025, OUT_DIR)
        # my renamed copies of the two charter rungs, builds port2025-wrapped
        my_zb: List[Any] = []
        for src_name, my_name, parent_name in (
                ("ZB1_defs", "RB1_defs_2025", "BASE"),
                ("ZB2_mepcat", "RB2_mepcat_2025", "RB1_defs_2025")):
            orig = RB.ZB_BY_NAME[src_name]
            def _wrap(orig_build):
                def build(ctx, landed):
                    return _adapt_substbuild(orig_build(ctx, landed))
                return build
            my_zb.append(RB.ZBRung(
                name=my_name, label=orig.label + " (2025, port2025-adapted)",
                build=_wrap(orig.build), parent=parent_name,
                description=orig.description, tests=orig.tests,
                if_pass=orig.if_pass, if_fail=orig.if_fail,
                seqs=orig.seqs, slot_fill=orig.slot_fill))
        for r in my_zb:
            RB.ZB_BY_NAME[r.name] = r
        try:
            landed = _landed_map_for(_c, prototype=prototype, upto="RB1_defs_2025")
            parent_path = parent_file
            for r in my_zb:
                rep = RB.zb_substitute_inplace(
                    r, parent_path, out_dir=OUT_DIR, y_dir=OUT_DIR,
                    base_path=BASE_2025, control=control, extra_landed=landed)
                rep["parent_mode"] = mode
                rep["stream"] = "y2025-views"
                _write_json(os.path.join(OUT_DIR, f"{r.name}.json"), rep)
                reports[r.name] = rep
                nxt = os.path.join(OUT_DIR, f"{r.name}.rvt")
                if rep.get("verdict") != "VALID" or not os.path.exists(nxt):
                    log(f"[RB] {r.name} verdict {rep.get('verdict')} -- chain stops")
                    break
                parent_path = nxt
        finally:
            for r in my_zb:
                RB.ZB_BY_NAME.pop(r.name, None)
        # RB_2025 = alias of the deepest built chain file (md5-recorded)
        deepest = None
        for name in ("RB2_mepcat_2025", "RB1_defs_2025"):
            if reports.get(name, {}).get("verdict") == "VALID":
                deepest = name
                break
        if deepest:
            src = os.path.join(OUT_DIR, f"{deepest}.rvt")
            dst = os.path.join(OUT_DIR, "RB_2025.rvt")
            shutil.copyfile(src, dst)
            alias = {"rung": "RB_2025", "alias_of": deepest, "md5": _md5(dst),
                     "md5_identical_to": _relp(src),
                     "parent": _relp(parent_file),
                     "verdict": reports[deepest].get("verdict"),
                     "meaning": ("RB_2025 = the residue-B round's deepest chain file "
                                 "(charter scope: parameter definitions at the 2025 "
                                 "shared-parameter GUID registry keys + the MEP wire/pipe "
                                 "catalog; the 2026-only conductor catalog does not exist "
                                 "in 2025 and is skipped by the port layer, per class)")}
            if _md5(src) != _md5(dst):                             # pragma: no cover
                raise RuntimeError("RB_2025 alias copy not byte-identical")
            _write_json(os.path.join(OUT_DIR, "RB_2025.json"), alias)
            reports["RB_2025"] = alias
    return reports


# ---------------------------------------------------------------------------
# 8. RC_2025 (residue-C: years / previews / link+area fixes + lawful deletions)
# ---------------------------------------------------------------------------
def rc_census(parent_path: str) -> dict:
    """The generic (id-free) residue-C census of the 2025 chain file: the
    external-link trio, the zero-referrer vendor DataStorage, the operating-
    year schedules, the stale type previews, the seq-101 header slots naming
    the link symbol, the drafting-view link-overrides pin, the content-
    bearing plan topologies + their room constellations, the locked-EQ
    constraint dimensions + their reference planes.  Everything derived from
    the live typed graph -- no 2026 id is assumed."""
    import rvt_reduce as RR
    st = RR.build_state_v2(parent_path)
    doc, cls_of, referrers = st["doc"], st["cls_of"], st["referrers"]

    def ids_of(c: str) -> List[int]:
        return sorted(e for e, k in cls_of.items() if k == c)

    link_symbols = ids_of("RvtLinkSymbol")
    link_instances = ids_of("RvtLinkInstance")
    copywatch = ids_of("CopyWatchProperties")
    vendor_ds = [e for e in ids_of("DataStorage") if not referrers.get(e)]
    years = ids_of("BuildingOperatingYearSchedule")
    previews, curtain_previews = [], []
    for e in ids_of("LegendComponent"):
        v = doc.value(e) or {}
        if v.get("m_oPreviewImage") is None:
            continue
        surro = int(v.get("m_previewFamilySurrogateId", -1) or -1)
        if surro > 0 and cls_of.get(surro) == "FamilySurrogate":
            curtain_previews.append(e)                # leaves WITH the curtain set
        else:
            previews.append(e)
    # header slots naming a link symbol (minus the link trio itself)
    trio = set(link_symbols) | set(link_instances) | set(copywatch)
    hdr_slots, drafting_slots = [], []
    for e in doc.et_by_id:
        e = int(e)
        if e in trio:
            continue
        h = doc.value(e, 101) or {}
        par = ((h.get("m_parents") or {}).get("value") or {})
        if any(isinstance(par.get(k), list) and any(x in set(link_symbols) for x in par[k])
               for k in ("m_deletion", "m_appearanceParents", "m_regeneration")):
            (drafting_slots if cls_of.get(e) == "DBViewDrafting" else hdr_slots).append(e)
    # the drafting view's seq-102 link-overrides pin
    link_override_slots = []
    for e in ids_of("DBViewDrafting"):
        v = doc.value(e) or {}
        m = (((v.get("m_pRvtLinkOverrides") or {}).get("value") or {})
             .get("m_displaySettingsMap") or [])
        if any(int((row or {}).get("first", -1)) in set(link_symbols) for row in m
               if isinstance(row, dict)):
            link_override_slots.append(e)
    # content-bearing plan topologies + the room constellation (closure)
    constellations: Dict[int, List[int]] = {}
    area_unwire: List[Tuple[int, int]] = []                      # (measure, topology)
    for t in ids_of("AreaSchemePlanTopologies"):
        members = {r for r in referrers.get(t, ()) if cls_of.get(r) in ROOM_CONTENT_CLASSES}
        if not members:
            continue
        seed = {t} | members
        grown = True
        while grown:
            grown = False
            for e in list(doc.et_by_id):
                e = int(e)
                if e in seed or cls_of.get(e) not in (
                        "RoomElem", "LevelRoomPlan", "CurveElem", "SketchPlane"):
                    continue
                refs = set(referrers.get(e, ()))
                if refs and refs <= seed:
                    seed.add(e)
                    grown = True
        constellations[t] = sorted(seed)
        for m in ids_of("AreaMeasureElem"):
            if int((doc.value(m) or {}).get("m_areaSchemePlanTopologyElemId", -1)) == t:
                area_unwire.append((m, t))
    # locked-EQ constraint dimensions + the planes that name them
    constraint_sets: Dict[int, List[int]] = {}
    for d in ids_of("LinearDimString"):
        planes = sorted(r for r in referrers.get(d, ()) if cls_of.get(r) == "RefPlane")
        if planes:
            constraint_sets[d] = planes
    return {
        "state": st, "doc": doc,
        "link_symbols": link_symbols, "link_instances": link_instances,
        "copywatch": copywatch, "vendor_datastorage": vendor_ds,
        "year_schedules": years, "previews": previews,
        "curtain_previews": curtain_previews,
        "header_slots": sorted(hdr_slots), "drafting_header_slots": sorted(drafting_slots),
        "link_override_slots": sorted(link_override_slots),
        "room_constellations": constellations, "area_unwire": area_unwire,
        "constraint_sets": constraint_sets,
    }


def _census_public(cen: dict) -> dict:
    return {k: v for k, v in cen.items() if k not in ("state", "doc")}


def plan_z_rc(cen: dict, gen: Callable[[str], str]) -> Any:
    """Z_RC_2025: the compose-consumable residue-C slice -- slots UNTOUCHED by
    any Y rung: OUR names on the year schedules, the stale preview caches
    nulled, the drafting view's link-overrides display map emptied + its
    header cleaned."""
    from rvt.genesis import residue_c as RC
    doc = cen["doc"]
    recs: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    ours: Dict[int, List[str]] = {}
    notes: List[str] = []
    for i, e in enumerate(sorted(cen["year_schedules"]), 1):
        v = copy.deepcopy(doc.value(e) or {})
        v["m_scheduleName"] = gen(f"Operating Year {i:02d}")
        recs[e] = {102: (doc.record(e).class_id, v)}
        ours[e] = ["m_scheduleName"]
    if cen["year_schedules"]:
        notes.append(f"{len(cen['year_schedules'])} operating-year schedules named OURS "
                     "(our own numbering vocabulary; the 2026 convention 'year name = the "
                     "wrapped OUR day-schedule name' does not apply on this chain -- the "
                     "day schedules are still Autodesk residue, no ZC_hvac equivalent in "
                     "this stream's charter)")
    for e in cen["previews"]:
        recs[e] = {102: (doc.record(e).class_id, RC.our_type_preview(doc.value(e) or {}))}
        ours[e] = ["m_oPreviewImage"]
    if cen["previews"]:
        notes.append(f"{len(cen['previews'])} type-preview LegendComponents: the "
                     "Autodesk-rendered PNG cache NULLED (corpus-normal null form; the "
                     "m_componentType wiring untouched)")
    if cen["curtain_previews"]:
        notes.append(f"{len(cen['curtain_previews'])} curtain-surrogate previews LEFT "
                     f"({cen['curtain_previews']}): they leave WITH the curtain "
                     "constellation (the deletion stream's removal queue)")
    for e in cen["link_override_slots"]:
        v = copy.deepcopy(doc.value(e) or {})
        lo = v.get("m_pRvtLinkOverrides")
        if isinstance(lo, dict) and isinstance(lo.get("value"), dict):
            lo["value"]["m_displaySettingsMap"] = []
        by: Dict[int, Tuple[int, dict]] = {102: (doc.record(e).class_id, v)}
        if e in cen["drafting_header_slots"]:
            h = RC.clean_view_header(doc.value(e, 101) or {},
                                     drop_id=cen["link_symbols"][0])
            by[101] = (doc.record(e, seq=101).class_id, h)
        recs[e] = by
        ours[e] = ["m_pRvtLinkOverrides.m_displaySettingsMap (emptied: a genesis file "
                   "links NO model)", "m_parents.m_deletion (minus the RvtLinkSymbol)"]
    if cen["link_override_slots"]:
        notes.append("the residue drafting view's RvtLinkOverrides display map EMPTIED "
                     "(the link symbol's seq-102 pin) + its seq-101 header cleaned -- "
                     "slots untouched by every Y rung, so this rung stays one-call-"
                     "composable")
    return RC.RcPlan("Z_RC_2025",
                     "residue-C compose-consumable slice (2025): year-schedule names OURS "
                     "+ stale preview caches nulled + the drafting view's link pin removed",
                     recs, ours, notes)


def plan_rc_inplace(cen: dict) -> Any:
    """RC_2025_inplace: the residue-C fixes that OVERLAP Y-rung slots (second-
    compose stage): the landed view slots' headers cleaned + the area
    measures unwired from content-bearing topologies."""
    from rvt.genesis import residue_c as RC
    doc = cen["doc"]
    ls = cen["link_symbols"][0] if cen["link_symbols"] else -1
    recs: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    ours: Dict[int, List[str]] = {}
    notes: List[str] = []
    for e in cen["header_slots"]:
        h = RC.clean_view_header(doc.value(e, 101) or {}, drop_id=ls)
        recs[e] = {101: (doc.record(e, seq=101).class_id, h)}
        ours[e] = [f"m_parents web (minus the RvtLinkSymbol {ls})"]
    if cen["header_slots"]:
        notes.append(f"{len(cen['header_slots'])} view slots' seq-101 headers re-emitted "
                     f"without the RvtLinkSymbol deletion-parent entry (slots landed by "
                     "Y2/Y9 -- NOT one-call-composable; the RC_zero-2025 second-compose "
                     "stage, 2026 precedent)")
    for m, t in cen["area_unwire"]:
        nv, nh = RC.rewired_area_measure(doc.value(m) or {}, doc.value(m, 101) or {},
                                         topology_id=t)
        recs[m] = {101: (doc.record(m, seq=101).class_id, nh),
                   102: (doc.record(m).class_id, nv)}
        ours[m] = [f"m_areaSchemePlanTopologyElemId ({t} -> -1)",
                   f"m_parents.m_deletion (minus {t})"]
    if cen["area_unwire"]:
        notes.append(f"area measures unwired from content-bearing topologies "
                     f"{cen['area_unwire']} (deletion finding 2's fix: the room "
                     "constellation becomes delete-reachable)")
    return RC.RcPlan("RC_2025_inplace",
                     "residue-C overlap slice (2025): landed view headers cleaned + area "
                     "measures unwired (enables the lawful straggler deletions)",
                     recs, ours, notes)


def emit_deletion(name: str, parent_path: str, seed_ids: Set[int], *,
                  out_dir: str = OUT_DIR, declared_base: str = BASE_2025,
                  label: str = "") -> dict:
    """The lawful deletion rung: maxgc over the typed graph + the certified
    re-blocking deleter, gated by the REDUCTION LAW (assert_edit_free), the
    validator, the structural proof, the four-registry census and stream
    identity.  Refuses to emit when maxgc pins any seed member."""
    from rvt import reduce_law as RL
    from rvt.reduce import delete_elements
    import rvt_reduce as RR
    G25, GD = _G25(), _GD()
    t0 = time.time()
    out = os.path.join(out_dir, f"{name}.rvt")
    log(f"\n== {name} :: {label or 'lawful straggler deletions (maxgc)'}")
    policy = RL.law_policy().permits("maxgc", "reduction-rung")
    if not policy.allowed:                                        # pragma: no cover
        raise RL.BannedGeneratorError(policy.reason, policy)
    st = RR.build_state_v2(parent_path)
    cls_of = st["cls_of"]
    seed = {int(i) for i in seed_ids}
    protected = RR._protect_history(st, set(seed))
    dropped_hist = sorted(seed - protected)
    delete, kept, ev = RR.maxgc(st, protected)
    report: Dict[str, Any] = {
        "rung": name, "label": label, "kind": "deletion (delete-with-content by maxgc)",
        "stream": "y2025-views",
        "mechanism": ("rvt_reduce.maxgc over the arbiter's typed reference graph + "
                      "rvt.reduce.delete_elements (the certified re-blocking deleter); "
                      "DELETION-WITH-CONTENT only; Global/Latest / ContentDocuments / "
                      "identity streams untouched; deleted ids' registry entries left "
                      "dangling and censused"),
        "law": {"statement": RL.THE_LAW,
                "policy": {"mechanism": "maxgc", "purpose": "reduction-rung",
                           "decision": "ALLOW" if policy.allowed else "REFUSE",
                           "reason": policy.reason}},
        "base": {"file": _relp(declared_base),
                 "certification": _V3().certification_of(declared_base)},
        "parent": _relp(parent_path), "out": _relp(out),
        "deletion_set": {
            "seed": sorted(seed),
            "seed_by_class": dict(collections.Counter(cls_of.get(e, "?") for e in seed)),
            "history_protected_removed": dropped_hist,
            "deleted": len(delete),
            "deleted_by_class": dict(collections.Counter(cls_of.get(e, "?") for e in delete)),
            "deleted_ids": sorted(delete),
            "kept_pinned": [{"id": k, "class": cls_of.get(k, "?")} for k in sorted(kept)],
            "pin_evidence": (ev if kept else None),
        },
    }
    log(f"   seed {len(seed)} -> maxgc delete {len(delete)}, PINNED {len(kept)}, "
        f"history-protected {len(dropped_hist)}")
    if kept or dropped_hist:
        report["FAILED_SELF_CHECK"] = (f"{len(kept)} seed member(s) PINNED / "
                                       f"{len(dropped_hist)} history-protected -- not a "
                                       "closed delete-with-content constellation")
        report["verdict"] = "NOT-BUILT"
        _write_json(os.path.join(out_dir, f"{name}.json"), report)
        log(f"   *** {name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        return report
    rrep = delete_elements(parent_path, out, delete)
    report["emit"] = rrep.to_json() if hasattr(rrep, "to_json") else repr(rrep)
    # THE LAW GUARD (assert_edit_free raises on any edited survivor / added id)
    from rvt.mutate import Document
    before_doc = Document.from_file(parent_path)
    try:
        law = G25.law_gate_reduction(before_doc, out,
                                     before_label=os.path.basename(parent_path),
                                     after_label=name)
    except Exception as ex:                                       # law violation = NOT-CLEAN
        law = {"ok": False, "verdict": f"LAW-VIOLATION: {ex!r}"[:400]}
    report["reduce_law"] = law
    # validator + structural + registries + stream identity + dangling census
    import rvt_reduce as _RR
    val = _RR._run_validator(out)
    report["validator"] = val
    from rvt.reduce import verify_reduced
    report["structural"] = verify_reduced(out, delete)
    cen = G25.four_registry_census(out)
    report["four_registry"] = {k: cen.get(k) for k in
                               ("save_units", "contentdocs_entries", "contenttable_records",
                                "familymgr_doc_guids", "four_registry_coherent")}
    report["stream_identity"] = GD.stream_identity(parent_path, out)
    # deleted ids' ADocument registry entries are LEFT DANGLING (never nulled)
    # and censused via the arbiter's own Global/Latest + ContentDocuments scan
    # (genesis_deletion.adocument_dangling_census hardwires the 2026 base --
    # not usable inside a 2025 context)
    st_out = RR.build_state_v2(out)
    ext = st_out.get("ext") or {}
    dangling = {stream: sorted(set(map(int, ids)) & delete)
                for stream, ids in ext.items()}
    report["adocument_dangling"] = {
        "meaning": ("deleted ids still referenced from the document registry "
                    "streams -- LEFT DANGLING by design (viewer-tolerated: the "
                    "R5/R9 lineage precedent), censused here"),
        "by_stream": {k: {"count": len(v), "ids": v[:40]} for k, v in dangling.items()},
    }
    problems: List[str] = []
    if not law.get("ok"):
        problems.append(f"reduce_law: {law.get('verdict')}")
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}")
    if not (report["structural"] or {}).get("ok", False):
        problems.append("structural proof failed")
    if not cen.get("four_registry_coherent"):
        problems.append("four-registry census incoherent")
    si = report["stream_identity"] or {}
    if not si.get("only_partition_and_elemtable_differ"):
        problems.append(f"streams beyond the element partition/ElemTable differ: "
                        f"{si.get('differing_streams')}")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    report["bytes"] = os.path.getsize(out) if os.path.exists(out) else None
    report["md5"] = _md5(out) if os.path.exists(out) else None
    report["seconds"] = round(time.time() - t0, 1)
    _write_json(os.path.join(out_dir, f"{name}.json"), report)
    log(f"   law {law.get('verdict')}; validator errors={val.get('errors')}; "
        f"structural {(report['structural'] or {}).get('ok')}; registries "
        f"{report['four_registry'].get('four_registry_coherent')}; -> {_relp(out)} "
        f"VERDICT {report['verdict']} ({report['seconds']}s)")
    return report


def build_rc() -> Dict[str, dict]:
    """The residue-C round: Z_RC_2025 (compose-consumable) -> RC_2025_inplace
    (overlap fixes) -> RC_2025 (the lawful straggler deletions), plus the
    composer's D_2025_*.json deletion specs (pin-free sets only)."""
    from rvt.genesis import house_standard as hs
    from rvt.genesis import residue_c as RC
    V3 = _V3()
    parent_file = os.path.join(OUT_DIR, "RB_2025.rvt")
    if not os.path.exists(parent_file):
        raise SystemExit("RC_2025: RB_2025.rvt missing -- build stage rb first")
    _pp, mode, _c, prototype = deep_parent()
    reports: Dict[str, dict] = {}
    with context_y2025(BASE_2025, prototype=prototype):
        control = V3.stage_control(BASE_2025, OUT_DIR)
        cen = rc_census(parent_file)
        _write_json(os.path.join(OUT_DIR, "rc_census_2025.json"), _census_public(cen))
        log(f"[RC] census: link trio {cen['link_symbols'] + cen['link_instances'] + cen['copywatch']}, "
            f"vendor DS {cen['vendor_datastorage']}, years {len(cen['year_schedules'])}, "
            f"previews {len(cen['previews'])} (+{len(cen['curtain_previews'])} curtain), "
            f"header slots {cen['header_slots']}, drafting pin {cen['link_override_slots']}, "
            f"room constellations { {t: len(m) for t, m in cen['room_constellations'].items()} }, "
            f"constraint sets { {d: p for d, p in cen['constraint_sets'].items()} }")
        # --- stage 1: Z_RC_2025 (compose-consumable) --------------------------
        plan = plan_z_rc(cen, hs.gen)
        rep = RC.emit_rung(plan, parent_file, OUT_DIR, doc=cen["doc"])
        rep["parent_mode"] = mode
        rep["stream"] = "y2025-views"
        rep["control_to_upload_with_batch"] = control
        rep["base"] = {"file": _relp(BASE_2025),
                       "certification": V3.certification_of(BASE_2025)}
        _write_json(os.path.join(OUT_DIR, "Z_RC_2025.json"), rep)
        reports["Z_RC_2025"] = rep
        if rep.get("verdict") != "VALID":
            log("[RC] Z_RC_2025 not clean -- stopping the round")
            return reports
        z_file = os.path.join(OUT_DIR, "Z_RC_2025.rvt")
        # --- stage 2: RC_2025_inplace (overlap fixes; parent = Z_RC_2025) -----
        cen2 = rc_census(z_file)
        plan2 = plan_rc_inplace(cen2)
        rep2 = RC.emit_rung(plan2, z_file, OUT_DIR, doc=cen2["doc"])
        rep2["parent_mode"] = mode
        rep2["stream"] = "y2025-views"
        rep2["base"] = {"file": _relp(BASE_2025),
                        "certification": V3.certification_of(BASE_2025)}
        _write_json(os.path.join(OUT_DIR, "RC_2025_inplace.json"), rep2)
        reports["RC_2025_inplace"] = rep2
        if rep2.get("verdict") != "VALID":
            log("[RC] RC_2025_inplace not clean -- stopping before the deletions")
            return reports
        inplace_file = os.path.join(OUT_DIR, "RC_2025_inplace.rvt")
        # --- stage 3: RC_2025 = the lawful straggler deletions ----------------
        seed: Set[int] = set(cen["link_symbols"]) | set(cen["link_instances"]) \
            | set(cen["copywatch"]) | set(cen["vendor_datastorage"])
        for d, planes in cen["constraint_sets"].items():
            seed |= {d} | set(planes)
        for t, members in cen["room_constellations"].items():
            seed |= set(members)
        rep3 = emit_deletion(
            "RC_2025", inplace_file, seed,
            label=("the lawful straggler deletions (2025): the external-link trio "
                   "(symbol delete-reachable after the header/link-override fixes), the "
                   "zero-referrer vendor DataStorage blob, the locked-EQ constraint "
                   "dimension + its reference planes, the room constellation atomically "
                   "with its containing plan topology"))
        rep3["parent_mode"] = mode
        _write_json(os.path.join(OUT_DIR, "RC_2025.json"), rep3)
        reports["RC_2025"] = rep3
        # --- the composer's deletion specs: PIN-FREE sets on the one-call file --
        write_deletion_specs(cen)
        # --- residue-after census (the honest remaining queue) ----------------
        if rep3.get("verdict") == "VALID":
            residue_after = residue_census_after(os.path.join(OUT_DIR, "RC_2025.rvt"),
                                                 prototype=prototype)
            _write_json(os.path.join(OUT_DIR, "residue_after_RC_2025.json"), residue_after)
            reports["residue_after"] = residue_after
    return reports


def write_deletion_specs(cen: dict) -> List[str]:
    """The composer-consumable D_2025_*.json specs -- ONLY the sets that are
    PIN-FREE on the one-call composed file (no header/area fixes there): the
    link INSTANCE pair, the vendor DataStorage, the constraint-dim content.
    The symbol + room sets need the RC fixes first (second-compose stage) --
    stated in each spec's notes, and the full-set spec is NOT D_-named so the
    one-call composer never discovers a pinned set."""
    paths: List[str] = []
    specs = [
        {"name": "D_2025_links_pair",
         "ids": sorted(set(cen["link_instances"]) | set(cen["copywatch"])),
         "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["the placed RvtLinkInstance + its CopyWatchProperties companion: a "
                   "genesis file links NO model; PIN-FREE on the one-call composed file "
                   "(maxgc-proven on this chain). The RvtLinkSymbol is NOT here: it stays "
                   "pinned by the landed view headers until the RC_2025_inplace fixes land "
                   "(second-compose stage, 2026 RC_zero precedent)."]},
        {"name": "D_2025_vendor_datastorage",
         "ids": sorted(cen["vendor_datastorage"]),
         "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["the vendor Extensible-Storage DataStorage blob: zero referrers "
                   "(leaf) -- maxgc-proven pin-free."]},
        {"name": "D_2025_constraint_dim",
         "ids": sorted({d for d in cen["constraint_sets"]}
                       | {p for ps in cen["constraint_sets"].values() for p in ps}),
         "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["the locked-EQ constraint LinearDimString + the reference planes whose "
                   "EQ constraint names it (they leave together; delete-with-content) -- "
                   "maxgc-proven pin-free on this chain."]},
    ]
    for s in specs:
        if not s["ids"]:
            continue
        p = os.path.join(OUT_DIR, f"{s['name']}.json")
        _write_json(p, s)
        paths.append(p)
        log(f"   [D-spec] {_relp(p)}: {len(s['ids'])} ids")
    # the FULL straggler set: the UNION spec.  The evolved composer
    # (genesis_compose_2025.discover_residue_specs) walks the declared parent
    # chain, consumes RC_2025_inplace (linearized last-wins) and collapses
    # subset D specs onto a discovered union -- with the fixes merged the
    # union is maxgc-pin-free (proven by RC_2025.rvt), and composing it makes
    # the final G reproduce the chain's deletion-applied proof file.  On a
    # composer run WITHOUT the fixes the union PINS (symbol held by the view
    # headers) and the compose fails RED with the pin evidence -- never a
    # silent partial deletion.
    full = {"name": "D_2025_stragglers_full",
            "ids": sorted(set().union(
                cen["link_symbols"], cen["link_instances"], cen["copywatch"],
                cen["vendor_datastorage"],
                *[[d] + list(ps) for d, ps in cen["constraint_sets"].items()],
                *cen["room_constellations"].values())),
            "policy": "maxgc", "purpose": "genesis-base",
            "requires_first": ["Z_RC_2025 (drafting link pin)",
                               "RC_2025_inplace (view headers + area unwiring)"],
            "notes": ["the COMPLETE lawful straggler set (union of the three pin-free "
                      "sets + the RvtLinkSymbol + the room constellation), "
                      "delete-reachable only after the RC in-place fixes -- proven "
                      "EDIT-FREE on this chain by RC_2025.rvt; a compose without the "
                      "fixes pins (fails red), never partially deletes"]}
    p = os.path.join(OUT_DIR, "D_2025_stragglers_full.json")
    _write_json(p, full)
    paths.append(p)
    # keep the old non-D name as a pointer for readers of the earlier record
    _write_json(os.path.join(OUT_DIR, "RC_2025_full_straggler_set.spec.json"),
                {**full, "name": "RC_2025_full_straggler_set",
                 "superseded_by": "D_2025_stragglers_full.json"})
    return paths


def residue_census_after(path: str, *, prototype: bool) -> dict:
    """What is STILL Autodesk's after the deepest rung, bucketed (the honest
    remaining queue for the next streams)."""
    from rvt.genesis import residue_a as RA
    from rvt.mutate import Document
    doc = Document.from_file(path)
    _pp, _mode, chain, _proto = deep_parent()
    landed = _landed_map_for(chain, prototype=prototype)
    residue = collections.Counter()
    for e in doc.et_by_id:
        if int(e) not in landed:
            residue[doc.class_of(int(e)) or "?"] += 1
    V3 = _V3()
    buckets: Dict[str, dict] = {}
    for cls_name, n in residue.most_common():
        b, reason = V3._residue_bucket(cls_name)
        d = buckets.setdefault(b, {"elements": 0, "classes": {}})
        d["elements"] += n
        d["classes"][cls_name] = n
    return {
        "subject": _relp(path), "elements_total": len(doc.et_by_id),
        "landed_ours": sum(1 for e in doc.et_by_id if int(e) in landed),
        "residue_elements": sum(residue.values()),
        "residue_classes": len(residue),
        "by_bucket": buckets,
        "note": ("the remaining queue: curtain constellation (removal), the ZC groups "
                 "(hvac/electrical/analysis product data -- residue_a2's 2026 territory, "
                 "not this charter), ZB3..ZB8 buckets, definitions-removal candidates"),
    }


# ---------------------------------------------------------------------------
# 9. composer handoff: the Z aliases
# ---------------------------------------------------------------------------
def write_z_aliases() -> List[str]:
    """Z_RA_2025 / Z_RB_2025 = md5-identical aliases of RA_2025 / RB_2025
    whose reports name their parents -- the one-call composer's residue-rung
    discovery (Z*.rvt + report with 'parent').  Z_RC_2025 is Z-named
    directly.  Slot-disjoint by construction: RA slots are Group-A residue,
    RB slots Group-B residue, Z_RC slots untouched content/machinery."""
    out: List[str] = []
    for src_name, alias, parent_name in (
            ("RA_2025", "Z_RA_2025", "Y9_2025.rvt"),
            ("RB_2025", "Z_RB_2025", "RA_2025.rvt")):
        src = os.path.join(OUT_DIR, f"{src_name}.rvt")
        if not os.path.exists(src):
            continue
        src_rep = _read_json(os.path.join(OUT_DIR, f"{src_name}.json")) or {}
        if src_rep.get("verdict") not in ("VALID",):
            log(f"   [Z-alias] {src_name} verdict {src_rep.get('verdict')} -- alias NOT written")
            continue
        dst = os.path.join(OUT_DIR, f"{alias}.rvt")
        shutil.copyfile(src, dst)
        if _md5(src) != _md5(dst):                                # pragma: no cover
            raise RuntimeError(f"{alias} not byte-identical to {src_name}")
        rep = {"rung": alias, "alias_of": src_name, "md5": _md5(dst),
               "parent": _relp(os.path.join(OUT_DIR, parent_name)),
               "verdict": src_rep.get("verdict"),
               "meaning": (f"md5-identical alias of {src_name}.rvt for the one-call "
                           "composer's Z*-rung discovery (tools/genesis_compose_2025.py); "
                           "the rung's delta vs its parent is slot-disjoint from every "
                           "other composed layer")}
        _write_json(os.path.join(OUT_DIR, f"{alias}.json"), rep)
        out.append(dst)
        log(f"   [Z-alias] {alias}.rvt = {src_name}.rvt (md5 {rep['md5']})")
    return out


# ---------------------------------------------------------------------------
# 10. probes.json (merge-write; the settings stream shares this directory)
# ---------------------------------------------------------------------------
def write_probes() -> str:
    """Merge THIS stream's probe entries into OUT_DIR/probes.json (keyed by
    rung name; foreign entries preserved)."""
    V3 = _V3()
    base_cert = V3.certification_of(BASE_2025)
    _pp, mode, _c, prototype = deep_parent()
    control_file = os.path.join(OUT_DIR, "CTRL_B2025_K4_base.rvt")
    control = ({"file": _relp(control_file), "md5": _md5(control_file),
                "identical_to": _relp(BASE_2025), "certification": base_cert}
               if os.path.exists(control_file) else None)
    order = ["RC_2025", "RC_2025_inplace", "Z_RC_2025", "RB_2025", "RB2_mepcat_2025",
             "RB1_defs_2025", "RA_2025", "Y9_2025", "Y8_2025"]
    tests = {
        "RC_2025": ("THE DEEPEST 2025 CHAIN FILE: every rung of this stream + the lawful "
                    "straggler deletions. PASS proves the whole Y8/Y9 + residue A/B/C "
                    "chain + the deletion layer at 2025 registrations in one verdict."),
        "RC_2025_inplace": "the overlap fixes alone (view headers + area unwiring).",
        "Z_RC_2025": "year-schedule names + preview nulls + the drafting link pin removal.",
        "RB_2025": "alias of the deepest residue-B chain file (defs + MEP catalog).",
        "RB2_mepcat_2025": "our MEP wire/pipe catalog objects at 2025 registrations.",
        "RB1_defs_2025": ("our parameter definitions at the 2025 file's own shared-"
                          "parameter GUID registry keys."),
        "RA_2025": ("ALL Group-A residue constructors at once (subcategories, annotation "
                    "types + fonts, datum content, pattern surplus, appearance assets) "
                    "on the 2025 chain."),
        "Y9_2025": ("our view layer in the 2025 LAYOUT (DBView without m_viewPositionId, "
                    "Viewport v10) at Autodesk's 2025 registrations -- the deepest Y rung."),
        "Y8_2025": "our datum + identity layer at 2025 registrations.",
    }
    entries: List[dict] = []
    for name in order:
        rep = _read_json(os.path.join(OUT_DIR, f"{name}.json"))
        if not rep:
            continue
        v = rep.get("validator") or {}
        entries.append({
            "order": len(entries) + 1, "rung": name, "stream": "y2025-views",
            "file": f"{_relp(OUT_DIR)}/{name}.rvt",
            "base": {"file": _relp(BASE_2025), "certification": base_cert},
            "parent": rep.get("parent"), "parent_mode": rep.get("parent_mode", mode),
            "the_ONE_thing_it_tests": tests.get(name, ""),
            "alias_of": rep.get("alias_of"),
            "verdict": rep.get("verdict"),
            "validator": ({"ok": v.get("ok"), "errors": v.get("errors"),
                           "warnings": v.get("warnings")} if v else None),
            "byte_delta_assertion_holds": (rep.get("byte_delta") or {}).get(
                "assertion_holds"),
            "reduce_law": (rep.get("reduce_law") or {}).get("verdict"),
            "report": f"{_relp(OUT_DIR)}/{name}.json",
            "control_to_upload_with_batch": control,
        })
    p = os.path.join(OUT_DIR, "probes.json")
    man = _read_json(p) or {}
    foreign = [e for e in (man.get("probes") or [])
               if e.get("stream") != "y2025-views"]
    man.setdefault("manifest", "experiments/genesis/subst_k4_2025 -- the certified-base "
                               "2025 substitution chain (shared by the settings stream "
                               "and the y2025-views stream; entries keyed by rung)")
    man.setdefault("base", {"file": _relp(BASE_2025), "certification": base_cert})
    man.setdefault("controls_discipline", (
        "Upload every batch with the certified control (CTRL_B2025_K4_base.rvt, "
        "md5-identical to the certified base) plus a certified-2026 control; a failing "
        "control voids the batch (tools/probe_batch.py stage enforces this)."))
    man["y2025_views_upload_order_bisection_first"] = [e["rung"] for e in entries]
    man["probes"] = foreign + entries
    man["parent_mode_now"] = mode
    _write_json(p, man)
    log(f"[probes] merged {len(entries)} y2025-views entries into {_relp(p)} "
        f"({len(foreign)} foreign entries preserved)")
    return p


# ---------------------------------------------------------------------------
# 11. driver
# ---------------------------------------------------------------------------
def clean_outputs() -> None:
    """--rebase: remove THIS stream's outputs (never the settings stream's)."""
    stems = MY_CHAIN + ["RB_2025", "RC_2025", "Z_RA_2025", "Z_RB_2025",
                        "D_2025_links_pair", "D_2025_vendor_datastorage",
                        "D_2025_constraint_dim", "RC_2025_full_straggler_set.spec",
                        "rc_census_2025", "residue_after_RC_2025",
                        "curtain_constellation_2025"]
    n = 0
    for stem in stems:
        for ext in (".rvt", ".json"):
            p = os.path.join(OUT_DIR, f"{stem}{ext}")
            if os.path.exists(p):
                os.remove(p)
                n += 1
    log(f"[rebase] removed {n} prior outputs of this stream")


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stage", default="all",
                    help="comma list: y89 | ra | rb | rc | probes | all")
    ap.add_argument("--rebase", action="store_true",
                    help="remove this stream's outputs first (after Y7_2025 lands)")
    args = ap.parse_args(argv)
    stages = [s.strip() for s in args.stage.split(",") if s.strip()]
    if "all" in stages:
        stages = ["y89", "ra", "rb", "rc", "probes"]
    if args.rebase:
        clean_outputs()
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    verdicts: Dict[str, Any] = {}
    if "y89" in stages:
        for k, v in build_y89().items():
            verdicts[k] = v.get("verdict")
    if "ra" in stages:
        verdicts["RA_2025"] = build_ra().get("verdict")
    if "rb" in stages:
        for k, v in build_rb().items():
            verdicts[k] = v.get("verdict")
    if "rc" in stages:
        for k, v in build_rc().items():
            verdicts[k] = v.get("verdict") if isinstance(v, dict) else None
    write_z_aliases()
    if "probes" in stages:
        write_probes()
    log(f"\n=== y2025-views SUMMARY ({round(time.time()-t0, 1)}s) ===")
    for k, v in verdicts.items():
        log(f"  {k:20s} {v}")
    bad = [k for k, v in verdicts.items() if v not in ("VALID", None)]
    return 0 if not bad else 2


if __name__ == "__main__":                                        # pragma: no cover
    sys.exit(main())
