"""rvt.genesis.y2024_b -- THE Y2024 DATUM/VIEWS + RESIDUE RUNGS (stream
y2024-compose): Y8_2024 / Y9_2024 + the residue rounds RA_2024 / RB_2024 /
RC_2024 on the CERTIFIED 2024 base, emitted into
``experiments/genesis/subst_k4_2024/``.

SITUATION (2026-08-05, verdicts #32 of docs/inbox/genesis-audit.md): batch
b28 ALL PASS -- the untouched 2024 sample (control), R9_2024, K3_2024 and
**B2024_K4** (``experiments/genesis2024/reduce/B2024_K4.rvt``) ALL LOAD.
B2024_K4 is in ``docs/coverage/viewer-certified.json`` ``certified`` -- the
substitution engine's gate accepts it WITHOUT any override.  The goal of the
campaign is G_ABPD_2024 (the composed 2024 genesis base) at
``experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt`` -- the slot
``src/rvt/frontdoor/assets/genesis_base.json`` releases.2024 reserves.

THIS MODULE mirrors the certified 2025 chain (rvt.genesis.y2025_b, whose
composed G_ABPD_2025 is viewer-certified -- verdicts #31) onto 2024, every
rung the certified v3 IN-PLACE mechanism (``rvt.regadd.substitute_elements``,
``Global/Latest`` + ``Global/ElemTable`` byte-identical, nothing added /
nothing deleted) with every record passed through the
``rvt.genesis.port2024`` field maps (2024 class ordinals, 2024-shaped
bodies -- the confirmed three-way table; the 2024 layout deltas: DBView
``m_viewPositionId`` ABSENT, DBViewDrafting additionally lacks
``m_sheetCollectionId`` and carries the 2024-only ``m_scheduleInstanceIds``
(corpus blank), Viewport v13->10, GeomStep has NO extra-data field at all):

  Y8_2024   identity / site / project info + the level & phase layer
  Y9_2024   the project view types + the view constellations + document sun
            (the 2024 layout, proven per record by the in-emit 2024
            encode->decode->re-encode self-check)
  RA_2024   the residue-A round in ONE cumulative rung: sub-categories,
            annotation types + fonts + arrowheads, datum content, the
            pattern surplus, the appearance assets (2024 asset profile,
            mined from the three quarantined 2024 samples)
  RB_2024   residue-B: RB1 = the parameter DEFINITIONS layer (OUR
            definitions at the 2024 file's own shared-parameter GUID
            registry keys) and RB2 = the MEP catalog.  The 2026-only
            conductor catalog does not exist in the 2024 class map (same
            refusal as 2025); the port layer's drop channel is armed.
  Z_RC_2024 the compose-consumable residue-C slice: the stale type preview
            caches nulled + the residue drafting view's RvtLinkOverrides
            display map EMPTIED (+ its header cleaned).  NOTE the 2026/2025
            year-schedule renaming has NO 2024 equivalent BY SCHEMA:
            ``BuildingOperatingYearSchedule`` does not exist in 2024
            (port2024 MISSING_2024_CONSTRUCTED) -- the census returns zero
            such elements, honestly.
  RC_2024_inplace  the residue-C fixes that OVERLAP Y-rung slots: the
            landed view slots' seq-101 headers re-emitted without the
            RvtLinkSymbol deletion-parent entry, and the AreaMeasureElem
            unwired from the content-bearing plan topology.
  RC_2024   the lawful straggler deletions per the reduction law (maxgc +
            rvt.reduce.delete_elements + reduce_law.assert_edit_free): the
            external-link trio, the zero-referrer vendor DataStorage blob,
            the locked-EQ constraint dimension + its reference planes, and
            the room constellation atomically with its plan topology.

COMPOSER HANDOFF (tools/genesis_2024_compose.py watches
``experiments/genesis/subst_k4_2024/**/Z*.rvt`` + ``**/D_*.json``): RA_2024 /
RB_2024 are aliased as ``Z_RA_2024.rvt`` / ``Z_RB_2024.rvt`` (md5-identical
copies whose reports name their parents), ``Z_RC_2024`` is Z-named directly,
and the deletion sets are written as ``D_2024_*.json`` specs -- the three
pin-free singles PLUS the ``D_2024_stragglers_full`` union (pin-free only
after the RC in-place fixes; a compose without them pins and fails RED).

BASE + PARENT RESOLUTION.  The BASE of every rung is the certified
``experiments/genesis2024/reduce/B2024_K4.rvt`` (no --allow-uncertified
anywhere).  The settings half of this stream (rvt.genesis.y2024_a) owns
Y1_2024..Y7_2024 in the same directory and builds FIRST; Y8_2024 derives
from ``Y7_2024.rvt`` and this module REFUSES to build without it (single
stream, no prototype-parent mode needed -- the 2025 fallback machinery is
deliberately not carried).

Every emission runs inside :func:`context_y2024` -- ``tools/genesis_2024.py
context_2024`` (versions.reading + the SEVEN 2026-baked framing constants +
the ADocument decoder) PLUS the per-release default codecs, the 2024 catalog
constants, v3's class-id resolution and the port2024 build adaptation (with
SOURCE-AWARE hooks: a hook never clobbers a field the source already
carries in its 2024 form -- the y2025_b lesson for parent-copied subtrees).
Everything is restored on exit; nothing leaks into the 2026 creation path.

Territory: this module, ``tests/test_y2024.py``,
``experiments/genesis/subst_k4_2024/**``, ``docs/inbox/y2024-compose.md``.
Everything else IMPORTED, never edited.

Reproduce (repo root)::

    .venv/bin/python -m rvt.genesis.y2024_b            # the whole chain
    .venv/bin/python -m rvt.genesis.y2024_b --stage y89
    .venv/bin/python -m rvt.genesis.y2024_b --stage ra,rb,rc
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

OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2024")
BASE_2024 = os.path.join(ROOT, "experiments", "genesis2024", "reduce", "B2024_K4.rvt")
SETTINGS_CHAIN = ["Y1_2024", "Y2_2024", "Y3_2024", "Y4_2024", "Y5_2024",
                  "Y6_2024", "Y7_2024"]
SAMPLES_2024_DIR = os.path.join(ROOT, "samples", "2024")
ASSET_PROFILE_2024 = os.path.join(OUT_DIR, "generic_asset_profile_2024.json")

#: my chain, base-side first (after the settings chain)
MY_CHAIN = ["Y8_2024", "Y9_2024", "RA_2024", "RB1_defs_2024", "RB2_mepcat_2024",
            "Z_RC_2024", "RC_2024_inplace"]

#: classes that make a plan-topology CONTENT-BEARING (the room constellation)
ROOM_CONTENT_CLASSES = ("CurveElem", "LevelRoomPlan", "RoomElem")

STREAM = "y2024-views"


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


def _G24():
    import genesis_2024 as G24                                     # noqa: E402
    return G24


def _GD():
    import genesis_deletion as GD                                  # noqa: E402
    return GD


# ---------------------------------------------------------------------------
# 1. parent resolution: the settings half's Y7_2024 (required, no fallback)
# ---------------------------------------------------------------------------
def deep_parent() -> Tuple[str, str, List[str]]:
    """(path, mode, protection_chain_names_nearest_first) of the file
    Y8_2024 derives from.  The settings half of THIS stream must have landed
    Y7_2024 first -- there is no prototype-parent mode on 2024."""
    settled = os.path.join(OUT_DIR, "Y7_2024.rvt")
    if os.path.exists(settled):
        return settled, "settings-chain (Y7_2024 landed by rvt.genesis.y2024_a)", \
            list(reversed(SETTINGS_CHAIN))
    raise SystemExit("Y7_2024.rvt missing -- run `python -m rvt.genesis.y2024_a` "
                     "first (the settings half of this stream builds the chain "
                     "Y8_2024 derives from)")


# ---------------------------------------------------------------------------
# 2. the 2024 run context
# ---------------------------------------------------------------------------
#: fixed namespace for the DETERMINISTIC shared-coordinate GUIDs of this
#: chain's two GeoSite records (skeleton.new_geo_site mints uuid4 per call
#: when none is supplied -- the ONE nondeterminism of the in-place chain,
#: found by a full byte-determinism re-run; pinning it makes every rebuild
#: byte-identical.  Any valid GUID is lawful content here: it is OUR
#: project's shared-coordinates identity, same as the frozen random one in
#: the certified 2026/2025 bases).
_GEO_GUID_NS = "6b2eec21-6a30-4e1a-9d0b-2024a0b2024b"


def _pinned_geo_site(orig):
    import uuid
    counter = {"n": 0}

    def new_geo_site(*a, **k):
        if not k.get("shared_coord_guid"):
            counter["n"] += 1
            k["shared_coord_guid"] = str(uuid.uuid5(
                uuid.UUID(_GEO_GUID_NS), f"tekton-y2024-geo-site-{counter['n']}"))
        return orig(*a, **k)
    return new_geo_site


def _source_aware_hooks(P24) -> Dict[Tuple[str, str], Callable]:
    """port2024's HOOKS_2024 exist to SYNTHESIZE a 2024 field from 2026 data.
    When the source object ALREADY CARRIES the 2024 field (a subtree copied
    from a decoded 2024 parent -- residue planners do this), the hook must
    not clobber it: carry the source value instead (the y2025_b lesson)."""
    def wrap(field: str, orig: Callable) -> Callable:
        def hook(src, ctx, _f=field, _o=orig):
            if isinstance(src, dict) and _f in src:
                return copy.deepcopy(src[_f])
            return _o(src, ctx)
        return hook
    return {k: wrap(k[1], fn) for k, fn in P24.HOOKS_2024.items()}


@contextlib.contextmanager
def context_y2024(base_path: str = BASE_2024):
    """genesis_2024.context_2024 (the seven framing-constant patches + the
    ADocument decoder) PLUS the per-release default codecs, the 2024 catalog
    constants, v3's class-id resolution, the port2024 build adaptation and
    the 2024 residue-A bindings.  Restores everything on exit."""
    from rvt import encode as ENC
    from rvt import regadd, regdiff
    from rvt.genesis import catalog as CAT
    from rvt.genesis import port2024 as P24
    from rvt.genesis import residue_a as RA
    from rvt.objects import ObjectDecoder
    G24 = _G24()
    V3 = _V3()

    dec24, _enc24, schema24 = P24._S24()
    saved: List[Tuple[Any, str, Any]] = []

    def swap(mod, name, value):
        saved.append((mod, name, getattr(mod, name)))
        setattr(mod, name, value)

    with G24.context_2024(base_path) as ords:
        swap(ENC, "_DEFAULT_ENCODER", ENC.ObjectEncoder(decoder=dec24))
        swap(regadd, "ObjectDecoder", functools.partial(ObjectDecoder, schema24))
        swap(regdiff, "ObjectDecoder", functools.partial(ObjectDecoder, schema24))
        swap(V3, "_class_id", P24.class_id_2024)
        enum24, prof24 = P24.load_2024_catalog_constants()
        swap(CAT, "load_builtin_category_enum", lambda *a, **k: enum24)
        swap(CAT, "load_builtin_style_profile", lambda *a, **k: prof24)
        swap(P24, "HOOKS_2024", _source_aware_hooks(P24))
        from rvt.genesis import skeleton as SK
        swap(SK, "new_geo_site", _pinned_geo_site(SK.new_geo_site))
        orig_build_for = V3.build_for
        swap(V3, "build_for", _make_adapted_build_for(orig_build_for))
        # v3 rung table: append the 2024-named rung descriptors (chain names)
        added = my_rungs()
        V3.RUNGS.extend(added)
        # residue-A: the self-check + asset profile must be 2024-bound
        swap(RA, "check_object", _check_object_2024)
        prof = load_asset_profile_2024()
        swap(RA, "load_generic_asset_profile", lambda *a, **k: prof)
        # base lineage banner for reports
        V3.BASE_LINEAGE.setdefault(_relp(base_path), (
            "B2024_K4 = the certified 2024 family-free base (viewer round b28 of "
            "2026-08-05, verdicts #32): samples/2024/rstbasicsampleproject -> "
            "R5..R9_2024 (maxgc, EDIT-FREE, release gate {0x0e7c}) -> K3_2024 "
            "(usage nulls) -> B2024_K4 (all embedded documents removed, "
            "four-registry coherent 1/0/0/0). docs/inbox/genesis-2024-reduce.md"))
        try:
            yield ords
        finally:
            for r in added:
                V3.RUNGS.remove(r)
            for mod, name, val in reversed(saved):
                setattr(mod, name, val)


def _check_object_2024(class_name: str, value: dict) -> dict:
    """residue_a.check_object under the pinned 2024 codec (the per-object
    honesty gate of every residue plan)."""
    from rvt.genesis import port2024 as P24
    dec, enc, _s = P24._S24()
    cid = P24.class_id_2024(class_name)
    body = enc.encode_object(cid, value)
    got = dec.decode_record(cid, body)
    re = enc.encode_object(cid, got.value) if got.clean else b""
    return {"class": class_name, "bytes": len(body), "clean": bool(got.clean),
            "byte_exact": (re == body), "errors": (got.errors or [])[:3],
            "ok": bool(got.clean and re == body)}


# ---------------------------------------------------------------------------
# 3. port2024 adaptation of builds (v3 SubstBuilds + residue-A Obj plans)
# ---------------------------------------------------------------------------
def _adapt_substbuild(sb):
    """Every record of a ``genesis_substitute.SubstBuild`` through
    ``port2024.adapt_record``; classes 2024 lacks dropped LOUDLY."""
    from rvt.genesis import port2024 as P24
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
                out.append(P24.adapt_record(r, resolve_name=resolve))
            except P24.Missing2024 as ex:
                dropped.append({"ours": int(r.elem_id), "class": r.class_name,
                                "name": names.get(int(r.elem_id), ""),
                                "reason": str(ex)})
        return out

    kept = port(sb.records)
    kept_new = port(sb.new_only or [])
    kept_ids = {int(r.elem_id) for r in kept}
    corr = {int(k): int(v) for k, v in sb.corr.items() if int(v) in kept_ids}
    notes = list(sb.notes) + [
        f"[port2024] {len(kept) + len(kept_new)} records adapted to the Revit-2024 "
        f"schema (2024 class ordinals, confirmed field maps); {len(dropped)} "
        f"record(s) of classes 2024 lacks emit nothing on 2024"
        + (": " + ", ".join(sorted({d["class"] for d in dropped})) if dropped else "")]
    adapted = GS.SubstBuild(
        old_ids=list(sb.old_ids), records=kept, corr=corr, new_only=kept_new,
        notes=notes, residue=dict(sb.residue or {}),
        info={**dict(sb.info or {}),
              "port2024": {"adapted": len(kept) + len(kept_new),
                           "dropped_missing_2024": dropped}})
    extra = getattr(sb, "extra_records_for_resolution", None)
    if extra is not None:
        adapted.extra_records_for_resolution = extra
    return adapted


def _make_adapted_build_for(orig_build_for):
    def adapted_build_for(rung, ctx):
        return _adapt_substbuild(orig_build_for(rung, ctx))
    return adapted_build_for


def adapt_obj_plans(plans: Dict[int, Any]) -> Tuple[Dict[int, Any], List[dict]]:
    """residue-A ``Obj`` plans -> 2024 shape: value through ``port2024.adapt``
    (source-aware hooks active), class id -> the 2024 ordinal."""
    from rvt.genesis import port2024 as P24
    out: Dict[int, Any] = {}
    dropped: List[dict] = []
    for slot, o in plans.items():
        try:
            v24 = P24.adapt(o.class_name, o.value)
            out[int(slot)] = dataclasses.replace(
                o, class_id=P24.class_id_2024(o.class_name), value=v24)
        except P24.Missing2024 as ex:
            dropped.append({"slot": int(slot), "class": o.class_name, "reason": str(ex)})
    return out, dropped


# ---------------------------------------------------------------------------
# 4. the 2024 generic appearance-asset profile (mined from the 2024 corpus)
# ---------------------------------------------------------------------------
def derive_asset_profile_2024(*, verbose: bool = True) -> dict:
    """The Protein GenericSchema appearance-asset PROPERTY SKELETON mined
    over the quarantined 2024 samples (the 2024 twin of residue_a's 2026
    profile).  Must run inside :func:`context_y2024` (2024 framing)."""
    from rvt.genesis.residue_a import GENERIC_ASSET_OURS
    from rvt.mutate import Document
    samples = sorted(_glob.glob(os.path.join(SAMPLES_2024_DIR, "*.rvt")))
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
            log(f"   [asset-profile-2024] {os.path.basename(s)}: cumulative "
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
        "generator": "rvt.genesis.y2024_b.derive_asset_profile_2024",
        "derived_from": [_relp(s) for s in samples], "generic_specimens": n,
        "note": ("The 2024 Protein GenericSchema appearance-asset property "
                 "skeleton (per-release library constant, mined from the "
                 "quarantined 2024 samples). Free properties (name / colour / "
                 "gloss / description / ...) carry no value: OURS at "
                 "construction time."),
        "properties": props,
    }
    _write_json(ASSET_PROFILE_2024, prof)
    if verbose:
        log(f"   [asset-profile-2024] wrote {_relp(ASSET_PROFILE_2024)} "
            f"({n} specimens, {len(props)} properties)")
    return prof


def load_asset_profile_2024() -> dict:
    prof = _read_json(ASSET_PROFILE_2024)
    if prof is not None:
        return prof
    return derive_asset_profile_2024()


# ---------------------------------------------------------------------------
# 5. Y8_2024 / Y9_2024 (v3's Y8/Y9 builders, 2024-named rung descriptors)
# ---------------------------------------------------------------------------
def my_rungs() -> List[Any]:
    """The 2024-named v3 rung descriptors this module appends to V3.RUNGS
    (name = report/file stem; the parent NAME drives derivation_chain /
    slot protection; the settings chain is stubbed for derivation)."""
    V3 = _V3()
    rungs: List[Any] = []
    parent = "BASE"
    for k, name in enumerate(SETTINGS_CHAIN):
        b = ["X1", "X2", "X3", "X4", "X5", "X6a", "X7"][k]
        rungs.append(V3.Rung3(
            name=name, label=f"(settings half) 2024 twin of the v3 {b} rung",
            parent=parent, build=b,
            description="settings-half rung (chain stub for derivation)",
            tests="(settings half, rvt.genesis.y2024_a)", if_pass="", if_fail=""))
        parent = name
    rungs.append(V3.Rung3(
        name="Y8_2024",
        label="levels + phases (+ set/filter) + units / site / base points / project info -> ours, IN PLACE (2024)",
        parent="Y7_2024", build="Y8",
        description=("The 2024 twin of the certified v3 Y8 (via the certified 2025 chain): "
                     "the datum + identity layer's objects replaced in place on the 2024 "
                     "chain -- our L1/L2 levels at the plan-bearing level slots, level type, "
                     "phases + phase set + filter, units, true north, geo sites / locations, "
                     "base points, ProjectInfo.  Every record port2024-adapted (this layer is "
                     "LAYOUT-IDENTICAL 2026==2024 per the confirmed table, GeomStep/GeomTable "
                     "deltas hooked)."),
        tests=("Whether the 2024 reader accepts our datum + identity objects at Autodesk's "
               "own 2024 registrations."),
        if_pass="Our datum/identity constructors load at 2024 registrations.",
        if_fail="Bisect levels+phases vs units vs site/base-points vs project info."))
    rungs.append(V3.Rung3(
        name="Y9_2024",
        label="the project view types + every view constellation (+ document sun) -> ours, IN PLACE (2024)",
        parent="Y8_2024", build="Y9",
        description=("The 2024 twin of the certified v3 Y9: the view layer in place. The "
                     "port layer emits the 2024 layout -- DBView has NO m_viewPositionId, "
                     "DBViewDrafting no m_sheetCollectionId and the 2024-only "
                     "m_scheduleInstanceIds (corpus blank []), Viewport v13->10 "
                     "(m_viewPosition/m_viewAnchor dropped), GeomStep has NO extra-data "
                     "field -- proven per record by the in-emit 2024 "
                     "encode->decode->re-encode self-check."),
        tests=("Whether the 2024 reader accepts our view/view-type/sun objects (2024 layout) "
               "at Autodesk's own registrations -- the deepest cumulative Y rung."),
        if_pass="Every constructor of the Y chain loads at 2024 registrations.",
        if_fail="Bisect view types vs the 3D constellation vs the plans."))
    return rungs


def build_y89(*, only: Sequence[str] = ("Y8_2024", "Y9_2024")) -> Dict[str, dict]:
    """Emit Y8_2024 / Y9_2024 into OUT_DIR from the settings chain's Y7."""
    V3 = _V3()
    parent_path, mode, _chain = deep_parent()
    os.makedirs(OUT_DIR, exist_ok=True)
    reports: Dict[str, dict] = {}
    with context_y2024(BASE_2024):
        cert = V3.assert_certified(BASE_2024)
        log(f"[base] {_relp(BASE_2024)} -- CERTIFIED: {cert.get('proves', '')[:100]}")
        log(f"[parent] {_relp(parent_path)} -- {mode}")
        control = V3.stage_control(BASE_2024, OUT_DIR)
        for name in ("Y8_2024", "Y9_2024"):
            if name not in only:
                continue
            rung = V3.rung_by_name(name)
            p = parent_path if name == "Y8_2024" else os.path.join(OUT_DIR, "Y8_2024.rvt")
            if not os.path.exists(p):
                log(f"== {name}: parent {_relp(p)} missing -- SKIPPED")
                continue
            rep = V3.substitute_inplace(rung, p, BASE_2024, OUT_DIR, control=control)
            rep["parent_mode"] = mode
            rep["stream"] = STREAM
            V3._write_report(OUT_DIR, name, rep)
            reports[name] = rep
    return reports


# ---------------------------------------------------------------------------
# 6. RA_2024 (the residue-A round, one cumulative rung)
# ---------------------------------------------------------------------------
def _landed_map_for(parent_names_nearest_first: Sequence[str], *,
                    upto: Optional[str] = None) -> Dict[int, str]:
    """{slot: rung} landed by every rung STRICTLY BEFORE ``upto`` on this
    chain (``upto=None`` = the whole chain -- for the final census)."""
    from rvt.genesis import residue_a as RA
    chain = [n for n in MY_CHAIN]
    if upto is not None and upto in chain:
        chain = chain[:chain.index(upto)]
    return RA.ladder_landed(OUT_DIR, tuple(chain + list(parent_names_nearest_first)))


def build_ra() -> dict:
    """RA_2024 = the Group-A residue layers in ONE cumulative in-place rung on
    Y9_2024, every object port2024-adapted and 2024-round-trip-gated."""
    from rvt.genesis import residue_a as RA
    V3 = _V3()
    parent_file = os.path.join(OUT_DIR, "Y9_2024.rvt")
    if not os.path.exists(parent_file):
        raise SystemExit("RA_2024: Y9_2024.rvt missing -- build stage y89 first")
    _pp, mode, chain_names = deep_parent()
    with context_y2024(BASE_2024):
        cert = V3.assert_certified(BASE_2024)
        control = V3.stage_control(BASE_2024, OUT_DIR)
        t0 = time.time()
        parent = RA.Parent(parent_file)
        # 'residue' must mean THE 2024 CHAIN's residue: recompute the landed map
        parent.landed = _landed_map_for(chain_names, upto="RA_2024")
        parent.residue = RA.residue_by_class(parent.doc, parent.landed)
        log(f"[RA] parent {_relp(parent_file)}: landed {len(parent.landed)}, "
            f"residue classes {len(parent.residue)} ({round(time.time()-t0, 1)}s)")
        plans = [RA.plan_subcat(parent), RA.plan_annot(parent), RA.plan_datum(parent),
                 RA.plan_pattern(parent), RA.plan_asset(parent)]
        merged = RA.merge_plans(plans)
        rung = RA.RungPlan(
            "RA_2024",
            "the residue-A round (2024): sub-categories + annotation types/fonts/arrowheads "
            "+ datum content (grids + surplus levels) + pattern surplus + appearance assets, "
            "IN PLACE, port2024-adapted",
            merged.plans, merged.residue_left, merged.notes, info=merged.info)
        plans24, dropped = adapt_obj_plans(rung.plans)
        rung = RA.RungPlan(rung.name, rung.label, plans24, rung.residue_left,
                           rung.notes + [
                               f"[port2024] {len(plans24)} objects adapted to the 2024 "
                               f"schema; {len(dropped)} dropped as missing-2024"
                               + (f": {dropped}" if dropped else "")],
                           info={**rung.info, "port2024_dropped": dropped})
        rep = RA.emit_rung(rung, parent, OUT_DIR, base_certification=cert,
                           control=control)
        rep["parent_mode"] = mode
        rep["stream"] = STREAM
        rep["parent"] = _relp(parent_file)
        # residue_a's emit declares its (2026-certified) parent as 'base'; on
        # this chain the ledger-certified ancestor is B2024_K4 -- declare THAT
        rep["base"] = {"file": _relp(BASE_2024), "certification": cert,
                       "note": ("the parent Y9_2024 is a STAGED chain file "
                                "(certification pending its viewer round); the "
                                "certified ancestor is B2024_K4")}
        _write_json(os.path.join(OUT_DIR, "RA_2024.json"), rep)
        # the curtain constellation: the coherent-removal queue (computed, handed over)
        curt = RA.curtain_constellation(parent.state)
        _write_json(os.path.join(OUT_DIR, "curtain_constellation_2024.json"), curt)
        log(f"[RA] curtain constellation: {curt.get('count')} elements "
            f"(removal queue for a future deletion stream)")
        return rep


# ---------------------------------------------------------------------------
# 7. RB_2024 (residue-B: the definitions + MEP catalog)
# ---------------------------------------------------------------------------
def build_rb() -> Dict[str, dict]:
    """RB1_defs_2024 (parameter definitions at the 2024 shared-parameter GUID
    registry keys) -> RB2_mepcat_2024 (the MEP catalog) -> RB_2024 (alias of
    the deepest).  The 2026-only conductor catalog is skipped BY CONSTRUCTION
    (Missing2024 -> listed)."""
    from rvt.genesis import residue_b as RB
    V3 = _V3()
    parent_file = os.path.join(OUT_DIR, "RA_2024.rvt")
    if not os.path.exists(parent_file):
        raise SystemExit("RB_2024: RA_2024.rvt missing -- build stage ra first")
    _pp, mode, chain_names = deep_parent()
    reports: Dict[str, dict] = {}
    with context_y2024(BASE_2024):
        control = V3.stage_control(BASE_2024, OUT_DIR)
        # my renamed copies of the two charter rungs, builds port2024-wrapped
        my_zb: List[Any] = []
        for src_name, my_name, parent_name in (
                ("ZB1_defs", "RB1_defs_2024", "BASE"),
                ("ZB2_mepcat", "RB2_mepcat_2024", "RB1_defs_2024")):
            orig = RB.ZB_BY_NAME[src_name]
            def _wrap(orig_build):
                def build(ctx, landed):
                    return _adapt_substbuild(orig_build(ctx, landed))
                return build
            my_zb.append(RB.ZBRung(
                name=my_name, label=orig.label + " (2024, port2024-adapted)",
                build=_wrap(orig.build), parent=parent_name,
                description=orig.description, tests=orig.tests,
                if_pass=orig.if_pass, if_fail=orig.if_fail,
                seqs=orig.seqs, slot_fill=orig.slot_fill))
        for r in my_zb:
            RB.ZB_BY_NAME[r.name] = r
        try:
            landed = _landed_map_for(chain_names, upto="RB1_defs_2024")
            parent_path = parent_file
            for r in my_zb:
                rep = RB.zb_substitute_inplace(
                    r, parent_path, out_dir=OUT_DIR, y_dir=OUT_DIR,
                    base_path=BASE_2024, control=control, extra_landed=landed)
                rep["parent_mode"] = mode
                rep["stream"] = STREAM
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
        # RB_2024 = alias of the deepest built chain file (md5-recorded)
        deepest = None
        for name in ("RB2_mepcat_2024", "RB1_defs_2024"):
            if reports.get(name, {}).get("verdict") == "VALID":
                deepest = name
                break
        if deepest:
            src = os.path.join(OUT_DIR, f"{deepest}.rvt")
            dst = os.path.join(OUT_DIR, "RB_2024.rvt")
            shutil.copyfile(src, dst)
            alias = {"rung": "RB_2024", "alias_of": deepest, "md5": _md5(dst),
                     "md5_identical_to": _relp(src),
                     "parent": _relp(parent_file),
                     "verdict": reports[deepest].get("verdict"),
                     "stream": STREAM,
                     "meaning": ("RB_2024 = the residue-B round's deepest chain file "
                                 "(parameter definitions at the 2024 shared-parameter "
                                 "GUID registry keys + the MEP wire/pipe catalog; the "
                                 "2026-only conductor catalog does not exist in 2024 "
                                 "and is skipped by the port layer, per class)")}
            if _md5(src) != _md5(dst):                             # pragma: no cover
                raise RuntimeError("RB_2024 alias copy not byte-identical")
            _write_json(os.path.join(OUT_DIR, "RB_2024.json"), alias)
            reports["RB_2024"] = alias
    return reports


# ---------------------------------------------------------------------------
# 8. RC_2024 (residue-C: previews / link+area fixes + lawful deletions)
# ---------------------------------------------------------------------------
def rc_census(parent_path: str) -> dict:
    """The generic (id-free) residue-C census of the 2024 chain file --
    everything derived from the live typed graph, no prior-release id is
    assumed.  NB ``BuildingOperatingYearSchedule`` does not exist in the
    2024 schema, so ``year_schedules`` is empty BY CONSTRUCTION (the class
    cannot appear in a 2024 document)."""
    import rvt_reduce as RR
    st = RR.build_state_v2(parent_path)
    doc, cls_of, referrers = st["doc"], st["cls_of"], st["referrers"]

    def ids_of(c: str) -> List[int]:
        return sorted(e for e, k in cls_of.items() if k == c)

    link_symbols = ids_of("RvtLinkSymbol")
    link_instances = ids_of("RvtLinkInstance")
    copywatch = ids_of("CopyWatchProperties")
    vendor_ds = [e for e in ids_of("DataStorage") if not referrers.get(e)]
    years = ids_of("BuildingOperatingYearSchedule")            # [] on 2024, by schema
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
    """Z_RC_2024: the compose-consumable residue-C slice -- slots UNTOUCHED by
    any Y rung: the stale preview caches nulled, the drafting view's
    link-overrides display map emptied + its header cleaned.  (No 2024
    year-schedule layer: the class does not exist in the 2024 schema.)"""
    from rvt.genesis import residue_c as RC
    doc = cen["doc"]
    recs: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    ours: Dict[int, List[str]] = {}
    notes: List[str] = []
    for i, e in enumerate(sorted(cen["year_schedules"]), 1):        # empty on 2024
        v = copy.deepcopy(doc.value(e) or {})
        v["m_scheduleName"] = gen(f"Operating Year {i:02d}")
        recs[e] = {102: (doc.record(e).class_id, v)}
        ours[e] = ["m_scheduleName"]
    notes.append("0 operating-year schedules: BuildingOperatingYearSchedule does not "
                 "exist in the 2024 schema (port2024 MISSING_2024_CONSTRUCTED) -- the "
                 "2026/2025 year-naming layer has no 2024 equivalent, by schema")
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
                     "constellation (a future deletion stream's removal queue)")
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
    return RC.RcPlan("Z_RC_2024",
                     "residue-C compose-consumable slice (2024): stale preview caches "
                     "nulled + the drafting view's link pin removed (no year-schedule "
                     "layer: the class is absent from the 2024 schema)",
                     recs, ours, notes)


def plan_rc_inplace(cen: dict) -> Any:
    """RC_2024_inplace: the residue-C fixes that OVERLAP Y-rung slots (second-
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
                     "Y2/Y9 -- NOT one-call-composable; the second-compose stage, "
                     "2026/2025 precedent)")
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
    return RC.RcPlan("RC_2024_inplace",
                     "residue-C overlap slice (2024): landed view headers cleaned + area "
                     "measures unwired (enables the lawful straggler deletions)",
                     recs, ours, notes)


def emit_deletion(name: str, parent_path: str, seed_ids: Set[int], *,
                  out_dir: str = OUT_DIR, declared_base: str = BASE_2024,
                  label: str = "") -> dict:
    """The lawful deletion rung: maxgc over the typed graph + the certified
    re-blocking deleter, gated by the REDUCTION LAW (assert_edit_free), the
    validator, the structural proof, the four-registry census, stream
    identity AND the 2024 release gate (detect_release == 2024, on-disk
    block-header tag set exactly {0x0e7c}).  Refuses to emit when maxgc pins
    any seed member."""
    from rvt import reduce_law as RL
    from rvt.reduce import delete_elements
    import rvt_reduce as RR
    G24, GD = _G24(), _GD()
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
        "stream": STREAM,
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
        law = G24.law_gate_reduction(before_doc, out,
                                     before_label=os.path.basename(parent_path),
                                     after_label=name)
    except Exception as ex:                                       # law violation = NOT-CLEAN
        law = {"ok": False, "verdict": f"LAW-VIOLATION: {ex!r}"[:400]}
    report["reduce_law"] = law
    # validator + structural + registries + stream identity + release gate
    import rvt_reduce as _RR
    val = _RR._run_validator(out)
    report["validator"] = val
    from rvt.reduce import verify_reduced
    report["structural"] = verify_reduced(out, delete)
    cen = G24.four_registry_census(out)
    report["four_registry"] = {k: cen.get(k) for k in
                               ("save_units", "contentdocs_entries", "contenttable_records",
                                "familymgr_doc_guids", "four_registry_coherent")}
    report["stream_identity"] = GD.stream_identity(parent_path, out)
    report["release_gate"] = G24.release_gate(out)
    # deleted ids' ADocument registry entries are LEFT DANGLING (never nulled)
    # and censused via the arbiter's own Global/Latest + ContentDocuments scan
    # (genesis_deletion.adocument_dangling_census hardwires the 2026 base --
    # not usable inside a 2024 context; the y2025_b finding applies verbatim)
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
    if not (report["release_gate"] or {}).get("ok"):
        problems.append(f"release gate failed: {report['release_gate']}")
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
        f"{report['four_registry'].get('four_registry_coherent')}; release "
        f"{(report['release_gate'] or {}).get('ok')}; -> {_relp(out)} "
        f"VERDICT {report['verdict']} ({report['seconds']}s)")
    return report


def build_rc() -> Dict[str, dict]:
    """The residue-C round: Z_RC_2024 (compose-consumable) -> RC_2024_inplace
    (overlap fixes) -> RC_2024 (the lawful straggler deletions), plus the
    composer's D_2024_*.json deletion specs (pin-free sets + the union)."""
    from rvt.genesis import house_standard as hs
    from rvt.genesis import residue_c as RC
    V3 = _V3()
    parent_file = os.path.join(OUT_DIR, "RB_2024.rvt")
    if not os.path.exists(parent_file):
        raise SystemExit("RC_2024: RB_2024.rvt missing -- build stage rb first")
    _pp, mode, _chain = deep_parent()
    reports: Dict[str, dict] = {}
    with context_y2024(BASE_2024):
        control = V3.stage_control(BASE_2024, OUT_DIR)
        cen = rc_census(parent_file)
        _write_json(os.path.join(OUT_DIR, "rc_census_2024.json"), _census_public(cen))
        log(f"[RC] census: link trio {cen['link_symbols'] + cen['link_instances'] + cen['copywatch']}, "
            f"vendor DS {cen['vendor_datastorage']}, years {len(cen['year_schedules'])}, "
            f"previews {len(cen['previews'])} (+{len(cen['curtain_previews'])} curtain), "
            f"header slots {cen['header_slots']}, drafting pin {cen['link_override_slots']}, "
            f"room constellations { {t: len(m) for t, m in cen['room_constellations'].items()} }, "
            f"constraint sets { {d: p for d, p in cen['constraint_sets'].items()} }")
        # --- stage 1: Z_RC_2024 (compose-consumable) --------------------------
        plan = plan_z_rc(cen, hs.gen)
        rep = RC.emit_rung(plan, parent_file, OUT_DIR, doc=cen["doc"])
        rep["parent_mode"] = mode
        rep["stream"] = STREAM
        rep["control_to_upload_with_batch"] = control
        rep["base"] = {"file": _relp(BASE_2024),
                       "certification": V3.certification_of(BASE_2024)}
        _write_json(os.path.join(OUT_DIR, "Z_RC_2024.json"), rep)
        reports["Z_RC_2024"] = rep
        if rep.get("verdict") != "VALID":
            log("[RC] Z_RC_2024 not clean -- stopping the round")
            return reports
        z_file = os.path.join(OUT_DIR, "Z_RC_2024.rvt")
        # --- stage 2: RC_2024_inplace (overlap fixes; parent = Z_RC_2024) -----
        cen2 = rc_census(z_file)
        plan2 = plan_rc_inplace(cen2)
        rep2 = RC.emit_rung(plan2, z_file, OUT_DIR, doc=cen2["doc"])
        rep2["parent_mode"] = mode
        rep2["stream"] = STREAM
        rep2["base"] = {"file": _relp(BASE_2024),
                        "certification": V3.certification_of(BASE_2024)}
        _write_json(os.path.join(OUT_DIR, "RC_2024_inplace.json"), rep2)
        reports["RC_2024_inplace"] = rep2
        if rep2.get("verdict") != "VALID":
            log("[RC] RC_2024_inplace not clean -- stopping before the deletions")
            return reports
        inplace_file = os.path.join(OUT_DIR, "RC_2024_inplace.rvt")
        # --- stage 3: RC_2024 = the lawful straggler deletions ----------------
        seed: Set[int] = set(cen["link_symbols"]) | set(cen["link_instances"]) \
            | set(cen["copywatch"]) | set(cen["vendor_datastorage"])
        for d, planes in cen["constraint_sets"].items():
            seed |= {d} | set(planes)
        for t, members in cen["room_constellations"].items():
            seed |= set(members)
        rep3 = emit_deletion(
            "RC_2024", inplace_file, seed,
            label=("the lawful straggler deletions (2024): the external-link trio "
                   "(symbol delete-reachable after the header/link-override fixes), the "
                   "zero-referrer vendor DataStorage blob, the locked-EQ constraint "
                   "dimension + its reference planes, the room constellation atomically "
                   "with its containing plan topology"))
        rep3["parent_mode"] = mode
        _write_json(os.path.join(OUT_DIR, "RC_2024.json"), rep3)
        reports["RC_2024"] = rep3
        # --- the composer's deletion specs: PIN-FREE sets on the one-call file --
        write_deletion_specs(cen)
        # --- residue-after census (the honest remaining queue) ----------------
        if rep3.get("verdict") == "VALID":
            residue_after = residue_census_after(os.path.join(OUT_DIR, "RC_2024.rvt"))
            _write_json(os.path.join(OUT_DIR, "residue_after_RC_2024.json"), residue_after)
            reports["residue_after"] = residue_after
    return reports


def write_deletion_specs(cen: dict) -> List[str]:
    """The composer-consumable D_2024_*.json specs -- the three sets that are
    PIN-FREE on the one-call composed file, PLUS the full straggler UNION
    (pin-free only after the RC in-place fixes; the evolved composer walks
    the declared parent chain, consumes RC_2024_inplace and collapses subset
    specs onto the union -- on a compose WITHOUT the fixes the union PINS
    and the compose fails RED, never a silent partial deletion)."""
    paths: List[str] = []
    specs = [
        {"name": "D_2024_links_pair",
         "ids": sorted(set(cen["link_instances"]) | set(cen["copywatch"])),
         "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["the placed RvtLinkInstance + its CopyWatchProperties companion: a "
                   "genesis file links NO model; PIN-FREE on the one-call composed file "
                   "(maxgc-proven on this chain). The RvtLinkSymbol is NOT here: it stays "
                   "pinned by the landed view headers until the RC_2024_inplace fixes land "
                   "(second-compose stage, 2026/2025 precedent)."]},
        {"name": "D_2024_vendor_datastorage",
         "ids": sorted(cen["vendor_datastorage"]),
         "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["the vendor Extensible-Storage DataStorage blob: zero referrers "
                   "(leaf) -- maxgc-proven pin-free."]},
        {"name": "D_2024_constraint_dim",
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
    full = {"name": "D_2024_stragglers_full",
            "ids": sorted(set().union(
                cen["link_symbols"], cen["link_instances"], cen["copywatch"],
                cen["vendor_datastorage"],
                *[[d] + list(ps) for d, ps in cen["constraint_sets"].items()],
                *cen["room_constellations"].values())),
            "policy": "maxgc", "purpose": "genesis-base",
            "requires_first": ["Z_RC_2024 (drafting link pin)",
                               "RC_2024_inplace (view headers + area unwiring)"],
            "notes": ["the COMPLETE lawful straggler set (union of the three pin-free "
                      "sets + the RvtLinkSymbol + the room constellation), "
                      "delete-reachable only after the RC in-place fixes -- proven "
                      "EDIT-FREE on this chain by RC_2024.rvt; a compose without the "
                      "fixes pins (fails red), never partially deletes"]}
    p = os.path.join(OUT_DIR, "D_2024_stragglers_full.json")
    _write_json(p, full)
    paths.append(p)
    return paths


def residue_census_after(path: str) -> dict:
    """What is STILL Autodesk's after the deepest rung, bucketed (the honest
    remaining queue for the next streams)."""
    from rvt.mutate import Document
    doc = Document.from_file(path)
    _pp, _mode, chain = deep_parent()
    landed = _landed_map_for(chain)
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
                 "(hvac/electrical/analysis product data), ZB3..ZB8 buckets, "
                 "definitions-removal candidates -- outside this stream's charter"),
    }


# ---------------------------------------------------------------------------
# 9. composer handoff: the Z aliases
# ---------------------------------------------------------------------------
def write_z_aliases() -> List[str]:
    """Z_RA_2024 / Z_RB_2024 = md5-identical aliases of RA_2024 / RB_2024
    whose reports name their parents -- the one-call composer's residue-rung
    discovery (Z*.rvt + report with 'parent').  Z_RC_2024 is Z-named
    directly."""
    out: List[str] = []
    for src_name, alias, parent_name in (
            ("RA_2024", "Z_RA_2024", "Y9_2024.rvt"),
            ("RB_2024", "Z_RB_2024", "RA_2024.rvt")):
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
               "stream": STREAM,
               "meaning": (f"md5-identical alias of {src_name}.rvt for the one-call "
                           "composer's Z*-rung discovery (tools/genesis_2024_compose.py); "
                           "the rung's delta vs its parent is slot-disjoint from every "
                           "other composed layer")}
        _write_json(os.path.join(OUT_DIR, f"{alias}.json"), rep)
        out.append(dst)
        log(f"   [Z-alias] {alias}.rvt = {src_name}.rvt (md5 {rep['md5']})")
    return out


# ---------------------------------------------------------------------------
# 10. probes.json (merge-write; the settings half shares this directory)
# ---------------------------------------------------------------------------
def write_probes() -> str:
    """Merge THIS half's probe entries into OUT_DIR/probes.json (keyed by
    stream; the settings half's entries preserved)."""
    V3 = _V3()
    base_cert = V3.certification_of(BASE_2024)
    _pp, mode, _c = deep_parent()
    control_file = os.path.join(OUT_DIR, "CTRL_B2024_K4_base.rvt")
    control = ({"file": _relp(control_file), "md5": _md5(control_file),
                "identical_to": _relp(BASE_2024), "certification": base_cert}
               if os.path.exists(control_file) else None)
    order = ["RC_2024", "RC_2024_inplace", "Z_RC_2024", "RB_2024", "RB2_mepcat_2024",
             "RB1_defs_2024", "RA_2024", "Y9_2024", "Y8_2024"]
    tests = {
        "RC_2024": ("THE DEEPEST 2024 CHAIN FILE: every rung of this stream + the lawful "
                    "straggler deletions. PASS proves the whole Y8/Y9 + residue A/B/C "
                    "chain + the deletion layer at 2024 registrations in one verdict."),
        "RC_2024_inplace": "the overlap fixes alone (view headers + area unwiring).",
        "Z_RC_2024": "preview nulls + the drafting link pin removal (no 2024 year layer).",
        "RB_2024": "alias of the deepest residue-B chain file (defs + MEP catalog).",
        "RB2_mepcat_2024": "our MEP wire/pipe catalog objects at 2024 registrations.",
        "RB1_defs_2024": ("our parameter definitions at the 2024 file's own shared-"
                          "parameter GUID registry keys."),
        "RA_2024": ("ALL Group-A residue constructors at once (subcategories, annotation "
                    "types + fonts, datum content, pattern surplus, appearance assets) "
                    "on the 2024 chain."),
        "Y9_2024": ("our view layer in the 2024 LAYOUT (DBView without m_viewPositionId, "
                    "Viewport v10, DBViewDrafting with m_scheduleInstanceIds []) at "
                    "Autodesk's 2024 registrations -- the deepest Y rung."),
        "Y8_2024": "our datum + identity layer at 2024 registrations.",
    }
    entries: List[dict] = []
    for name in order:
        rep = _read_json(os.path.join(OUT_DIR, f"{name}.json"))
        if not rep:
            continue
        v = rep.get("validator") or {}
        entries.append({
            "order": len(entries) + 1, "rung": name, "stream": STREAM,
            "file": f"{_relp(OUT_DIR)}/{name}.rvt",
            "release": 2024,
            "base": {"file": _relp(BASE_2024), "certification": base_cert},
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
               if e.get("stream") != STREAM]
    man.setdefault("manifest", "experiments/genesis/subst_k4_2024 -- the certified-base "
                               "2024 substitution chain (settings half y2024_a + views/"
                               "residue half y2024_b of stream y2024-compose; entries "
                               "keyed by rung)")
    man.setdefault("base", {"file": _relp(BASE_2024), "certification": base_cert})
    man.setdefault("controls_discipline", (
        "Upload every batch with the certified control (CTRL_B2024_K4_base.rvt, "
        "md5-identical to the certified base) plus a certified-2026 control; a failing "
        "control voids the batch (tools/probe_batch.py stage enforces this)."))
    man["y2024_views_upload_order_bisection_first"] = [e["rung"] for e in entries]
    man["probes"] = foreign + entries
    man["parent_mode_now"] = mode
    _write_json(p, man)
    log(f"[probes] merged {len(entries)} {STREAM} entries into {_relp(p)} "
        f"({len(foreign)} foreign entries preserved)")
    return p


# ---------------------------------------------------------------------------
# 11. driver
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stage", default="all",
                    help="comma list: y89 | ra | rb | rc | probes | all")
    args = ap.parse_args(argv)
    stages = [s.strip() for s in args.stage.split(",") if s.strip()]
    if "all" in stages:
        stages = ["y89", "ra", "rb", "rc", "probes"]
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    verdicts: Dict[str, Any] = {}
    if "y89" in stages:
        for k, v in build_y89().items():
            verdicts[k] = v.get("verdict")
    if "ra" in stages:
        verdicts["RA_2024"] = build_ra().get("verdict")
    if "rb" in stages:
        for k, v in build_rb().items():
            verdicts[k] = v.get("verdict")
    if "rc" in stages:
        for k, v in build_rc().items():
            verdicts[k] = v.get("verdict") if isinstance(v, dict) else None
    write_z_aliases()
    if "probes" in stages:
        write_probes()
    log(f"\n=== {STREAM} SUMMARY ({round(time.time()-t0, 1)}s) ===")
    for k, v in verdicts.items():
        log(f"  {k:20s} {v}")
    bad = [k for k, v in verdicts.items() if v not in ("VALID", None)]
    return 0 if not bad else 2


if __name__ == "__main__":                                        # pragma: no cover
    sys.exit(main())
