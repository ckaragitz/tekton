#!/usr/bin/env python
"""genesis_compose.py -- THE COMPOSER: one certified base + several in-place
rung sets + a deletion set -> ONE composed candidate in ONE deterministic
pass, with a MANIFEST and the campaign's invariant assertions.

WHY THIS EXISTS (docs/inbox/genesis-audit.md through ORCHESTRATOR VERDICTS
#18; docs/writer/genesis-endgame.md).  The substitution ladder is rebased on
the certified family-free base K4; pure IN-PLACE substitution
(``rvt.regadd.substitute_element[s]`` -- zero registration motion, only the
seq-102 object records change) took it to Y9 and then ZA_deep, all
VIEWER-PASSED.  Two residue streams (Group A / Group B) each emit their rungs
as separate probe files derived from ONE certified parent; the deletion stream
emits a removal set; residue_a2 emits ZC rungs.  Somebody has to APPLY THEM
TOGETHER -- several independent in-place rung sets AND a deletion set onto
ONE certified base, in one deterministic pass, with every invariant asserted
and a record of exactly what was composed.  That is this module.

THE OPERATION (:func:`compose`).
  Phase I  -- IN-PLACE substitution first: the merged, DISJOINT correspondence
              sets of every rung spec are replayed onto the base in ONE
              ``regadd.substitute_elements`` call (zero registration motion;
              Global/Latest + Global/ElemTable byte-identical to the base).
              Assertions: pairwise slot-disjointness across the composed
              rung sets, slot existence + same class in the base, PARENT
              COHERENCE (the base carries the exact record state each rung
              was built against), the reduce-law IN-PLACE law
              (``reduce_law.check_substitution``: only landed slots changed,
              only in the declared seqs, nothing added or removed), registry
              PARITY (both global registry streams byte-identical => every
              registry leaf that indexed a slot still indexes it), FOUR-
              REGISTRY coherence (``famload.four_registry_census``), per-rung
              BYTE FIDELITY (the composed file carries each rung's exact
              record bytes at its slots -- no cross-rung overwrite), the
              validator (0 errors) + the structural proof, and the byte-delta
              table vs the base with every benign exception listed.
  Phase II -- reduce-law-governed DELETIONS on the substituted file, by the
              certified mechanics of the R-ladder (``rvt.reduce.delete_
              elements`` + ``rvt_reduce.maxgc`` over the validator-exact
              reference graph).  Policies: ``maxgc`` (the SANCTIONED reduction
              generator -- only ids no survivor references are deleted;
              dangling-free by construction), ``closure`` (delete-with-content:
              the seed grows with its referrers first, then maxgc), ``exact``
              (delete precisely the given ids -- may leave element-record
              danglers, which the validator counts as ERRORS: allowed only
              for a ``research-probe`` purpose, refused for genesis output).
              Assertions: ``reduce_law.assert_edit_free`` (every survivor
              BYTE-IDENTICAL, nothing added -- THE REDUCTION LAW),
              ``reduce.verify_reduced`` (CRC / ECC / walker / counts /
              sentinels / no deleted id survives), the validator, the four-
              registry census, the byte-delta table (only Partitions/N and
              Global/ElemTable may differ; Global/Latest stays byte-identical
              with its now-dangling registry entries -- tolerated per the
              certified R5 / R9 -- unless registry reconciliation is requested).
  A MANIFEST (JSON) records exactly which rung sets and deletions were
  composed, from which source files (md5), onto which base, with every
  assertion's evidence.  Nothing about a composed file is a claim without a
  manifest entry.

CORRECTNESS ANCHOR (:func:`prove_anchor`, proven by this stream): composing
Y9 + Group A's five certified single-layer rung deltas reproduces the
certified ``ZA_deep.rvt`` BYTE-IDENTICALLY (md5).  A composer that replays
five independently-emitted rungs into the exact file the residue stream
emitted in one merged call is a composer whose Phase I is exact.

THE CANDIDATES the orchestrator gates (:func:`build_candidates`):
  * ``G_A``       = compose(Y9, Group-A rungs) == the ZA_deep anchor
                    (md5-identical to the certified file; recorded).
  * ``G_AB_defs`` = ZA_deep + Group B's certified ``Z_defs`` bucket (the one
                    B bucket already viewer-PASSED), composed in.
  * ``G_endgame`` = the TEMPLATE :func:`compose_endgame`: A-rungs + the
                    named-good B buckets + residue_a2's ZC rungs + the deletion
                    stream's D_all set, in ONE call, once those streams deliver.

THE HONEST MEASURE (:func:`scoreboard`): ``rvt.provenance`` (--baseline all
--streams) + the element census on Y9, ZA_deep and every composed candidate
-> ``docs/writer/genesis-progress.md`` (elements ours / 3,342, Autodesk-
authored residue + named buckets, byte-weighted provenance split, viewer
status), reproducible with ``--recompute``.

Territory: this file, tests/test_genesis_compose.py,
docs/writer/genesis-progress.md, docs/writer/genesis-definition.md,
docs/inbox/genesis-assembly.md, experiments/genesis/subst_k4/compose/*.
Every dependency (rvt.regadd / rvt.reduce / rvt.reduce_law / rvt.famload /
rvt.provenance / rvt.mutate / rvt.validate / tools rvt_reduce / latest_map /
genesis_substitute_v3) is IMPORTED, never edited.

Usage (repo root, .venv/bin/python):
  tools/genesis_compose.py anchor                 # prove compose(Y9, Group A) == ZA_deep
  tools/genesis_compose.py candidates             # build G_A + G_AB_defs (+ probes.json)
  tools/genesis_compose.py compose --base FILE --rung name=RUNG.rvt[@PARENT.rvt] ...
                                  [--delete SET.json] --out OUT.rvt
  tools/genesis_compose.py endgame --spec endgame_inputs.json
  tools/genesis_compose.py scoreboard [--recompute] [--fast]
  tools/genesis_compose.py check FILE.rvt         # the mechanical genesis definition check
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import datetime
import glob
import hashlib
import json
import os
import struct
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import regadd                                                  # noqa: E402
from rvt import reduce as RV                                             # noqa: E402
from rvt import reduce_law as RL                                         # noqa: E402
from rvt.mutate import Document                                          # noqa: E402
from rvt.objects import ObjectDecoder                                    # noqa: E402

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
GEN = os.path.join(ROOT, "experiments", "genesis")
LADDER = os.path.join(GEN, "subst_k4")
RESIDUE_A = os.path.join(LADDER, "residue_a")
RESIDUE_B = os.path.join(LADDER, "residue_b")
OUT_DIR = os.path.join(LADDER, "compose")                     # this stream's experiment dir
Y9 = os.path.join(LADDER, "Y9.rvt")                            # certified deepest Y rung
ZA_DEEP = os.path.join(RESIDUE_A, "ZA_deep.rvt")               # certified Group-A deep file
K4 = os.path.join(GEN, "triage", "K4.rvt")                     # certified family-free base
CERTIFIED_JSON = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")
SAMPLES_DIR = os.path.join(ROOT, "samples")
PROGRESS_MD = os.path.join(ROOT, "docs", "writer", "genesis-progress.md")
PROGRESS_JSON = os.path.join(OUT_DIR, "genesis-progress.json")
DEFINITION_MD = os.path.join(ROOT, "docs", "writer", "genesis-definition.md")
ASSEMBLY_MD = os.path.join(ROOT, "docs", "inbox", "genesis-assembly.md")

#: Group A's single-layer rungs (each derives DIRECTLY from Y9); ZA_deep = all
GROUP_A_SINGLES = ["Z_subcat", "Z_annot", "Z_datum", "Z_pattern", "Z_asset"]
#: Group B's single-change probes (each Y9 + ONE bucket); ZB_deep = the 8-rung chain
GROUP_B_SINGLES = ["Z_defs", "Z_mepcat", "Z_pens", "Z_annot", "Z_palette",
                   "Z_filters", "Z_machinery", "Z_content"]
#: Group-B buckets whose single probe is viewer-CERTIFIED as of this record
GROUP_B_CERTIFIED_BUCKETS = ["Z_defs"]

SEQS = (101, 102, 103)
HOST_TOTAL = 3342                                              # K4-lineage host element count


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    try:
        return os.path.relpath(os.path.abspath(p), ROOT)
    except Exception:                                            # pragma: no cover
        return str(p)


def _abs(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hdr_len(seq: int) -> int:
    """Raw framed-record header length before the body (id[8] [+stamp[4]] +psize[4])."""
    return 12 if int(seq) == 101 else 16


def _rec_class_id(framed: bytes, seq: int) -> int:
    return struct.unpack_from("<H", framed, _hdr_len(seq))[0]


def _rec_id(framed: bytes) -> int:
    return struct.unpack_from("<q", framed, 0)[0]


_DEC: Optional[ObjectDecoder] = None


def decoder() -> ObjectDecoder:
    global _DEC
    if _DEC is None:
        _DEC = ObjectDecoder()
    return _DEC


class CompositionError(Exception):
    """A composition input violates a composition law (disjointness / parent
    coherence / class / policy).  Carries the structured detail as ``.detail``."""

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.detail = detail


# ===========================================================================
# 1. CERTIFICATION (the standing-controls discipline: what may be built on)
# ===========================================================================

def load_ledger(path: str = CERTIFIED_JSON) -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:                                            # pragma: no cover
        return {"certified": [], "failed": []}


def certification_of(rvt_path: str) -> Optional[dict]:
    """The viewer-certification entry of ``rvt_path`` (None = not certified)."""
    rel = _relp(rvt_path)
    for e in load_ledger().get("certified") or []:
        if str(e.get("file")) == rel:
            return dict(e)
    return None


def failure_of(rvt_path: str) -> Optional[dict]:
    rel = _relp(rvt_path)
    for e in load_ledger().get("failed") or []:
        if str(e.get("file")) == rel:
            return dict(e)
    return None


def viewer_status(rvt_path: str) -> dict:
    """Certified / failed / untested, plus md5-identity to a certified file
    (a byte-identical copy of a certified file is certified BY BYTES)."""
    cert = certification_of(rvt_path)
    if cert:
        return {"status": "PASS", "certification": cert.get("proves"), "how": "ledger entry"}
    fail = failure_of(rvt_path)
    if fail:
        return {"status": "FAIL", "verdict": fail.get("verdict"), "how": "ledger entry"}
    return {"status": "UNTESTED", "how": "not in docs/coverage/viewer-certified.json"}


def certified_by_identity(rvt_path: str, candidates: Sequence[str]) -> Optional[dict]:
    """If ``rvt_path`` is md5-identical to a viewer-CERTIFIED file among
    ``candidates`` (or any ledger-certified file at those paths), it carries
    that file's verdict by BYTES.  Returns the matching entry."""
    if not os.path.exists(rvt_path):
        return None
    m = md5_of(rvt_path)
    for c in candidates:
        c = _abs(c)
        if os.path.exists(c) and os.path.abspath(c) != os.path.abspath(rvt_path) \
                and md5_of(c) == m and certification_of(c):
            return {"identical_to": _relp(c), "md5": m,
                    "certification": certification_of(c).get("proves")}
    return None


def assert_certified(rvt_path: str, *, allow_uncertified: bool = False) -> dict:
    """A composition base MUST be viewer-certified before anything is built
    on it (ORCHESTRATOR VERDICT #15: the whole K1 program was built on an
    untested base that fails on its own)."""
    cert = certification_of(rvt_path)
    if cert is not None:
        return cert
    ident = certified_by_identity(rvt_path, [ZA_DEEP, Y9, K4] + sorted(
        glob.glob(os.path.join(LADDER, "**", "*.rvt"), recursive=True)))
    if ident is not None:
        return {"file": _relp(rvt_path), "proves": f"md5-identical to certified "
                f"{ident['identical_to']} ({ident['certification']})", "by_identity": ident}
    msg = (f"{_relp(rvt_path)} is NOT viewer-certified"
           f"{' (listed as FAILED)' if failure_of(rvt_path) else ''} -- a composition may "
           f"only build on a CERTIFIED base (verdict #15 / the standing-controls discipline)")
    if allow_uncertified:
        log(f"   WARNING: {msg}")
        return {"file": _relp(rvt_path), "proves": "NOT CERTIFIED (override)"}
    raise CompositionError(msg)


def stage_control(base_path: str, out_dir: str = OUT_DIR) -> dict:
    """Stage the batch's certified positive CONTROL: a byte-identical copy of
    the certified base (md5-asserted), uploaded with EVERY probe of a batch;
    a failing control voids the round (oracle health), never the composer."""
    import shutil
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(base_path))[0]
    dst = os.path.join(out_dir, f"CTRL_{stem}_base.rvt")
    shutil.copyfile(base_path, dst)
    if md5_of(dst) != md5_of(base_path):                        # pragma: no cover
        raise RuntimeError("staged control is not byte-identical to the base")
    return {"file": _relp(dst), "identical_to": _relp(base_path), "md5": md5_of(dst),
            "certification": certification_of(base_path)}


# ===========================================================================
# 2. THE RECORD INDEX (what a file's unit-0 records ARE, byte-exact)
# ===========================================================================

def record_index(rvt_path: str) -> dict:
    """Everything the composer compares, per file: ``records`` = {(seq, id):
    framed bytes}, ``order`` = per-seq id order, ``streams`` = raw stream bytes,
    the ElemTable model, the ADocument payload, embedded-unit digests, the
    exact partition logical stream.  Delegates to rvt.regadd's diff index (the
    K1 byte-diff instrument), so the composer and the substitution engine
    read files identically."""
    return regadd._unit0_index(rvt_path)


def stream_diff(parent: str, out: str) -> dict:
    """The regadd BYTE-DIFF REPORT: per-stream identity, records added /
    removed / changed (with field-level decode diffs), per-seq id order and
    block partition, ElemTable rows, ADocument leaf changes."""
    return regadd.stream_diff_report(parent, out)


def _classes_of(records: Dict[int, Dict[int, bytes]]) -> Dict[str, int]:
    dec = decoder()
    cnt: collections.Counter = collections.Counter()
    for slot, by_seq in records.items():
        fb = by_seq.get(102)
        if fb is None:
            cnt["?"] += 1
            continue
        try:
            cnt[dec.class_name(_rec_class_id(fb, 102)) or "?"] += 1
        except Exception:                                        # pragma: no cover
            cnt["?"] += 1
    return dict(cnt.most_common())


# ===========================================================================
# 3. RUNG SPECS  (an in-place substitution set: {slot: {seq: framed bytes}})
# ===========================================================================

@dataclasses.dataclass
class RungSpec:
    """ONE independent in-place rung set, ready to compose.

    ``records`` = {existing element id (slot): {seq: framed record bytes}} --
    the exact bytes the composed file must carry at those slots.  ``parent``
    = the file the rung was built AGAINST; ``parent_records`` = that parent's
    framed bytes at the same slots, so the composer can PROVE the base it is
    applying the rung to carries the state the rung was built on (parent
    coherence).  ``landed_slots`` (from the rung's certification report) is
    the superset that includes landed-but-byte-identical slots (reproduced
    machinery) -- used for the census, not for the substitution.
    """
    name: str
    group: str = ""                                   # 'A' | 'B' | 'C' | 'add' | ...
    kind: str = "file-delta"                          # 'file-delta' | 'records'
    source_file: Optional[str] = None                 # the rung .rvt (kind file-delta)
    parent_file: Optional[str] = None                 # the file it was built against
    records: Dict[int, Dict[int, bytes]] = dataclasses.field(default_factory=dict)
    parent_records: Dict[int, Dict[int, bytes]] = dataclasses.field(default_factory=dict)
    landed_slots: List[int] = dataclasses.field(default_factory=list)
    report_file: Optional[str] = None
    notes: List[str] = dataclasses.field(default_factory=list)

    # ---- derived --------------------------------------------------------------
    @property
    def slots(self) -> Set[int]:
        return {int(s) for s in self.records}

    @property
    def seqs(self) -> List[int]:
        return sorted({int(s) for by in self.records.values() for s in by})

    @property
    def classes(self) -> Dict[str, int]:
        return _classes_of(self.records)

    @property
    def reproduced_slots(self) -> List[int]:
        """Landed by the rung's builder but BYTE-IDENTICAL to the parent
        (reproduced machinery: a format constant, nothing of ours to reject)."""
        ch = self.slots
        return sorted(int(s) for s in self.landed_slots if int(s) not in ch)

    def summary(self) -> dict:
        return {
            "name": self.name, "group": self.group, "kind": self.kind,
            "source_file": _relp(self.source_file) if self.source_file else None,
            "source_md5": (md5_of(self.source_file) if self.source_file
                           and os.path.exists(self.source_file) else None),
            "source_viewer": (viewer_status(self.source_file).get("status")
                              if self.source_file else None),
            "parent_file": _relp(self.parent_file) if self.parent_file else None,
            "report_file": _relp(self.report_file) if self.report_file else None,
            "slots": len(self.slots), "seqs": self.seqs,
            "classes": self.classes,
            "landed_slots": len(self.landed_slots) if self.landed_slots else None,
            "landed_but_byte_identical": (len(self.reproduced_slots)
                                          if self.landed_slots else None),
            "notes": self.notes,
        }

    # ---- constructors -----------------------------------------------------
    @classmethod
    def from_rung_file(cls, rung_file: str, parent_file: str, *, name: Optional[str] = None,
                       group: str = "", report_file: Optional[str] = None) -> "RungSpec":
        """Extract a rung's substitution set = the BYTE DELTA of ``rung_file``
        vs the ``parent_file`` it was built against.  An in-place rung adds
        and removes NOTHING (asserted); every changed (seq, id) record becomes
        one entry of the set, its framed bytes taken verbatim from the rung
        file.  ``report_file`` (the rung's certification .json, default: the
        sibling .json) supplies the landed-slot superset for the census."""
        rung_file, parent_file = _abs(rung_file), _abs(parent_file)
        for p in (rung_file, parent_file):
            if not os.path.exists(p):
                raise FileNotFoundError(p)
        A = record_index(parent_file)
        B = record_index(rung_file)
        ra, rb = A["records"], B["records"]
        added = sorted(k for k in rb if k not in ra)
        removed = sorted(k for k in ra if k not in rb)
        if added or removed:
            raise CompositionError(
                f"{_relp(rung_file)} is NOT an in-place rung of {_relp(parent_file)}: "
                f"{len(added)} record(s) added, {len(removed)} removed (an in-place rung has "
                f"zero registration motion)",
                {"added": added[:12], "removed": removed[:12]})
        records: Dict[int, Dict[int, bytes]] = {}
        parent_records: Dict[int, Dict[int, bytes]] = {}
        for k, fb in rb.items():
            if ra[k] != fb:
                seq, eid = k
                records.setdefault(int(eid), {})[int(seq)] = bytes(fb)
                parent_records.setdefault(int(eid), {})[int(seq)] = bytes(ra[k])
        notes = []
        for s in ("Global/Latest", "Global/ElemTable"):
            if A["streams"].get(s) != B["streams"].get(s):
                notes.append(f"WARNING: {s} of the rung differs from its parent -- not a "
                             f"pure in-place rung (registration motion); the delta captures "
                             f"only record content, not the registry edit")
        rep = report_file or (os.path.splitext(rung_file)[0] + ".json")
        landed: List[int] = []
        if rep and os.path.exists(rep):
            try:
                with open(rep) as fh:
                    jr = json.load(fh)
                landed = sorted({int(r["slot"]) for r in (jr.get("landed_slots") or [])})
            except Exception:                                    # pragma: no cover
                landed = []
        if not landed:
            landed = sorted(records)
            notes.append("no certification report found: landed_slots := changed slots")
        return cls(name=name or os.path.splitext(os.path.basename(rung_file))[0],
                   group=group, kind="file-delta", source_file=rung_file,
                   parent_file=parent_file, records=records, parent_records=parent_records,
                   landed_slots=landed, report_file=(rep if os.path.exists(rep) else None),
                   notes=notes)

    @classmethod
    def from_records(cls, name: str, records_by_id: Dict[int, Any], *, group: str = "",
                     source: str = "records", notes: Sequence[str] = ()) -> "RungSpec":
        """A rung set supplied directly as records: ``{slot: TypeRecord}`` /
        ``{slot: {seq: framed bytes}}`` / ``{slot: {seq: (class_id, value)}}``
        (encoded at the slot id via rvt.regadd; the object's own m_id follows
        the slot).  For template inputs that arrive as records, not files."""
        records: Dict[int, Dict[int, bytes]] = {}
        for slot, recs in records_by_id.items():
            records[int(slot)] = regadd.framed_records_from(recs, int(slot))
        spec = cls(name=name, group=group, kind="records", source_file=None,
                   parent_file=None, records=records, parent_records={},
                   landed_slots=sorted(records), notes=[f"records source: {source}", *notes])
        return spec

    def restrict_to(self, keep: Iterable[int]) -> "RungSpec":
        """A copy carrying only the slots in ``keep`` (used when a deletion
        policy retires a slot this rung would have substituted)."""
        k = {int(x) for x in keep}
        return dataclasses.replace(
            self, records={s: v for s, v in self.records.items() if s in k},
            parent_records={s: v for s, v in self.parent_records.items() if s in k},
            landed_slots=[s for s in self.landed_slots if int(s) in k],
            notes=list(self.notes) + [f"restricted to {len(k & self.slots)} of "
                                      f"{len(self.slots)} slots"])


# ===========================================================================
# 4. DELETION SPECS  (a removal set under the REDUCTION LAW)
# ===========================================================================

#: deletion policies and the reduce-law mechanism each maps to
DELETION_POLICIES = {
    "maxgc": ("maxgc", "the SANCTIONED reduction generator: of the seed, delete only the "
                       "ids that NO surviving element references (maximal dangling-free "
                       "subset over the validator-exact reference graph); survivors are "
                       "byte-identical BY CONSTRUCTION"),
    "closure": ("maxgc", "delete-WITH-content: the seed grows with every host referrer "
                         "(the reduce-law's deletion_with_content_seed / closure_delete), "
                         "then maxgc over the grown set -- referrers leave WITH the content, "
                         "never edited"),
    "exact": (None, "delete PRECISELY the given ids: surviving referrers keep DANGLING "
                    "element-record ids (byte-identical, so the reduce law holds) which the "
                    "validator counts as reference-integrity ERRORS -- a research probe, "
                    "REFUSED for genesis output unless purpose='research-probe'"),
}


@dataclasses.dataclass
class DeletionSpec:
    """ONE deletion set (a constellation) + the policy that closes it."""
    name: str
    ids: List[int]                                   # the SEED (a constellation's ids)
    policy: str = "maxgc"                            # maxgc | closure | exact
    protected: List[int] = dataclasses.field(default_factory=list)   # never deleted
    latest_pins: bool = False                        # treat Latest/ContentDocs scan hits as pins
    purpose: str = "genesis-base"                    # reduce-law PURPOSE (exact needs research-probe)
    source_file: Optional[str] = None
    notes: List[str] = dataclasses.field(default_factory=list)

    def summary(self) -> dict:
        return {"name": self.name, "policy": self.policy, "seed": len(self.ids),
                "protected": len(self.protected), "latest_pins": self.latest_pins,
                "purpose": self.purpose, "mechanism": DELETION_POLICIES.get(self.policy, ("?", "?"))[0],
                "source_file": _relp(self.source_file) if self.source_file else None,
                "notes": self.notes}

    @classmethod
    def from_json(cls, src: Union[str, dict], *, name: Optional[str] = None) -> "DeletionSpec":
        """Load a deletion set: a JSON file / dict ``{"name", "ids" | "delete" |
        "seed", "policy", "protected", "latest_pins", "purpose"}``, or a plain
        list of ids (policy defaults to maxgc)."""
        obj: Any = src
        source = None
        if isinstance(src, str):
            source = _abs(src)
            with open(source) as fh:
                obj = json.load(fh)
        if isinstance(obj, list):
            obj = {"ids": obj}
        ids = obj.get("ids") or obj.get("delete") or obj.get("seed") or obj.get("delete_ids") or []
        if isinstance(ids, dict):
            ids = list(ids.keys())
        return cls(name=str(obj.get("name") or name or (os.path.splitext(os.path.basename(source))[0]
                                                       if source else "deletion")),
                   ids=[int(x) for x in ids], policy=str(obj.get("policy") or "maxgc"),
                   protected=[int(x) for x in (obj.get("protected") or [])],
                   latest_pins=bool(obj.get("latest_pins", False)),
                   purpose=str(obj.get("purpose") or "genesis-base"),
                   source_file=source, notes=list(obj.get("notes") or []))


# ===========================================================================
# 5. THE COMPOSITION REPORT / MANIFEST
# ===========================================================================

@dataclasses.dataclass
class ComposeReport:
    op: str
    base: dict
    out: dict
    phase_1_inplace: dict
    phase_2_deletions: Optional[dict]
    invariants: dict
    problems: List[str] = dataclasses.field(default_factory=list)
    warnings: List[str] = dataclasses.field(default_factory=list)
    verdict: str = "?"
    manifest_file: Optional[str] = None
    seconds: float = 0.0
    anchor: Optional[dict] = None

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def _run_validator(path: str) -> dict:
    from rvt.validate import validate_file
    rep = validate_file(path)
    errs = rep.errors
    return {"ok": bool(rep.ok), "errors": len(errs), "warnings": len(rep.warnings),
            "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:400] for f in errs[:6]],
            "stats": {k: v for k, v in rep.stats.items()
                      if k in ("streams", "records", "elements_decoded", "refs_checked",
                               "partition_blocks", "decode_failures")}}


def _four_registry(path: str) -> dict:
    from rvt.famload import four_registry_census
    try:
        cen = four_registry_census(path)
    except Exception as ex:                                     # pragma: no cover
        return {"error": repr(ex)[:300], "coherent": False}
    return {k: cen.get(k) for k in ("save_units", "contentdocs_entries", "contenttable_records",
                                    "familymgr_entries", "coherent", "coherent_counts",
                                    "coherent_guids", "adocument_clean")}


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1,
                  default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o))


# ===========================================================================
# 6. PHASE I -- merge the rung sets (the composition laws)
# ===========================================================================

def merge_rung_sets(base_records: Dict[Tuple[int, int], bytes], rungs: Sequence[RungSpec],
                    *, base_label: str = "base",
                    deletion_ids: Set[int] = frozenset(),
                    on_overlap: str = "refuse") -> Tuple[Dict[int, Dict[int, bytes]], dict]:
    """Union the rung specs' substitution sets under the COMPOSITION LAWS.

    Laws (each violation is a :class:`CompositionError` unless a policy
    resolves it, and every resolution is REPORTED):
      1. DISJOINTNESS -- two composed rung sets never target the same slot
         (a slot carries exactly one of our objects; a collision is a planning
         defect the atomicity rule of the endgame forbids).
      2. EXISTENCE -- every slot exists in the base (in-place = an existing id).
      3. SAME CLASS -- the seq-102 record we install has the class the base's
         slot already has (a substitution never re-types an element).
      4. PARENT COHERENCE -- for a file-delta rung, the base's records at the
         rung's slots equal the PARENT records the rung was built against
         (else the delta does not mean the same edit here).
      5. DELETION OVERLAP -- a slot both substituted and deleted is a
         contradiction; ``on_overlap='refuse'`` raises, ``'delete-wins'``
         drops the substitution for those slots (recorded).
    Returns (merged {slot: {seq: bytes}}, report).
    """
    merged: Dict[int, Dict[int, bytes]] = {}
    owner: Dict[int, str] = {}
    rep: Dict[str, Any] = {"laws": {}, "rungs": [], "resolutions": [], "base": base_label}
    collisions: List[dict] = []
    missing: List[dict] = []
    class_mismatch: List[dict] = []
    incoherent: List[dict] = []
    overlap: List[dict] = []
    dec = decoder()
    for spec in rungs:
        kept = 0
        for slot, by_seq in spec.records.items():
            slot = int(slot)
            # 5. deletion overlap
            if slot in deletion_ids:
                overlap.append({"rung": spec.name, "slot": slot})
                if on_overlap == "delete-wins":
                    continue
            # 1. disjointness
            if slot in owner:
                collisions.append({"slot": slot, "rungs": [owner[slot], spec.name]})
                continue
            # 2. existence
            base_102 = base_records.get((102, slot))
            if base_102 is None:
                missing.append({"rung": spec.name, "slot": slot})
                continue
            # 3. same class (seq-102)
            ours_102 = by_seq.get(102)
            if ours_102 is not None:
                bc, oc = _rec_class_id(base_102, 102), _rec_class_id(ours_102, 102)
                if bc != oc:
                    class_mismatch.append({"rung": spec.name, "slot": slot,
                                           "base_class": dec.class_name(bc),
                                           "our_class": dec.class_name(oc)})
                    continue
                if _rec_id(ours_102) != slot:
                    raise CompositionError(f"{spec.name}: framed record id "
                                           f"{_rec_id(ours_102)} != slot {slot}")
            # 4. parent coherence (file-delta rungs)
            if spec.parent_records:
                pr = spec.parent_records.get(slot) or {}
                bad_seqs = [s for s, pb in pr.items() if base_records.get((s, slot)) != pb]
                if bad_seqs:
                    incoherent.append({"rung": spec.name, "slot": slot, "seqs": bad_seqs})
                    continue
            owner[slot] = spec.name
            merged[slot] = {int(s): bytes(b) for s, b in by_seq.items()}
            kept += 1
        rep["rungs"].append({**spec.summary(), "merged_slots": kept})
    rep["laws"] = {
        "disjoint": not collisions, "collisions": collisions[:20],
        "all_slots_exist": not missing, "missing_slots": missing[:20],
        "same_class": not class_mismatch, "class_mismatch": class_mismatch[:20],
        "parent_coherent": not incoherent, "incoherent_slots": incoherent[:20],
        "deletion_overlap": overlap[:20], "on_overlap": on_overlap,
    }
    if overlap:
        if on_overlap == "delete-wins":
            rep["resolutions"].append(f"{len(overlap)} substituted slot(s) also in a deletion "
                                      f"set: deletion WINS (substitution dropped) -- listed")
        else:
            raise CompositionError(
                f"{len(overlap)} slot(s) are BOTH substituted and deleted (a contradiction the "
                f"atomicity rule forbids); pass on_overlap='delete-wins' to let the deletion win",
                rep["laws"])
    for law, bad, what in (("disjoint", collisions, "slot collision(s) between rung sets"),
                           ("all_slots_exist", missing, "slot(s) not present in the base"),
                           ("same_class", class_mismatch, "class mismatch(es) vs the base's slot"),
                           ("parent_coherent", incoherent,
                            "slot(s) whose base records differ from the rung's PARENT records "
                            "(the base does not carry the state this rung was built on)")):
        if bad:
            raise CompositionError(f"COMPOSITION LAW {law} violated: {len(bad)} {what}: "
                                   f"{bad[:6]}", rep["laws"])
    rep["merged_slots"] = len(merged)
    rep["merged_seqs"] = sorted({s for by in merged.values() for s in by})
    rep["merged_by_class"] = _classes_of(merged)
    return merged, rep


# ===========================================================================
# 7. PHASE I -- emission + invariant assertions (in place)
# ===========================================================================

def _byte_delta_table(diff: dict, *, slots: Set[int], seqs: Sequence[int],
                      partition_name: str, layer: str = "in-place") -> dict:
    """The BYTE-DELTA ASSERTION TABLE vs the parent: exactly which bytes
    changed, whether that is the expected set, every exception with a reason.

    In-place: ONLY the landed slots' records in the declared seqs may change;
    the two global registry streams (Global/Latest, Global/ElemTable) must be
    byte-identical; no id added / removed; the per-seq id order unchanged."""
    recs = diff["records"]
    changed_ids = set(recs.get("changed_ids") or [])
    added_ids = set(recs.get("added_ids") or [])
    removed_ids = set(recs.get("removed_ids") or [])
    expected = {int(s) for s in slots}
    unexpected_changed = sorted(changed_ids - expected)
    unchanged_slots = sorted(expected - changed_ids)
    differing = list(diff["streams"]["differing"])
    problems: List[str] = []
    exceptions: List[dict] = []
    for s in ("Global/Latest", "Global/ElemTable"):
        if s in differing:
            problems.append(f"{s} differs from the parent (in-place must not touch it)")
    other = [s for s in differing if s != partition_name]
    if other:
        problems.append(f"streams other than the element partition differ: {other}")
    if added_ids:
        problems.append(f"record ids ADDED (in-place adds nothing): {sorted(added_ids)[:8]}")
    if removed_ids:
        problems.append(f"record ids REMOVED (in-place deletes nothing): {sorted(removed_ids)[:8]}")
    if unexpected_changed:
        problems.append(f"record ids CHANGED beyond the composed slots: {unexpected_changed[:8]}")
    if not recs.get("id_order_identical", True):
        problems.append("per-seq id order changed (in-place keeps every record position)")
    if not diff["elemtable"].get("identical", False):
        problems.append("ElemTable rows differ (registrations must be untouched)")
    if not diff["latest"].get("identical", False):
        problems.append("ADocument (Global/Latest) differs (registries must be untouched)")
    if not diff.get("embedded_units_identical", True):
        problems.append("embedded save units differ (in-place edits unit 0 only)")
    changed_pairs = {(c["seq"], c["id"]) for c in recs.get("changed", [])}
    changed_seqs = collections.Counter(s for (s, _i) in changed_pairs)
    for s in changed_seqs:
        if s not in set(seqs):
            problems.append(f"seq-{s} records changed although only seqs {list(seqs)} were composed")
    for s, b in (diff.get("blocks") or {}).items():
        if not b.get("identical", True):
            exceptions.append({"what": f"seq-{s} block partition re-flowed",
                               "reason": ("our objects differ in byte length from the parent's, so "
                                          "the certified re-blocker (rvt.reduce.reblock) re-chunked "
                                          f"the unit-0 seq-{s} run; record ORDER unchanged"),
                               "blocks_parent": b.get("parent"), "blocks_out": b.get("out")})
    if unchanged_slots:
        exceptions.append({"what": f"{len(unchanged_slots)} composed slot(s) byte-identical to the parent",
                           "reason": ("the rung's constructor reproduced the parent's own object at "
                                      "these slots (reproduced machinery) -- composed, but no bytes "
                                      "to change"),
                           "slots": unchanged_slots[:40]})
    return {
        "layer": layer,
        "streams_differing": differing,
        "only_partition_differs": (set(differing) <= {partition_name}),
        "records_changed_count": recs.get("changed_count"),
        "records_changed_by_seq": {str(s): n for s, n in changed_seqs.items()},
        "expected_slots": len(expected),
        "unexpected_changed_ids": unexpected_changed,
        "records_added_ids": sorted(added_ids), "records_removed_ids": sorted(removed_ids),
        "landed_but_unchanged_slots": len(unchanged_slots),
        "id_order_identical_per_seq": recs.get("id_order_identical_per_seq"),
        "block_partition_identical_per_seq": {str(s): b.get("identical")
                                              for s, b in (diff.get("blocks") or {}).items()},
        "elemtable_identical": diff["elemtable"].get("identical"),
        "adocument_identical": diff["latest"].get("identical"),
        "embedded_units_identical": diff.get("embedded_units_identical"),
        "field_diff_examples": recs.get("changed", [])[:4],
        "exceptions": exceptions,
        "problems": problems,
        "assertion_holds": not problems,
    }


def _rung_fidelity(rungs: Sequence[RungSpec], out_records: Dict[Tuple[int, int], bytes]) -> dict:
    """Per-rung BYTE FIDELITY: the composed file carries every rung's exact
    record bytes at its slots (the merge overwrote nothing)."""
    rows = []
    all_ok = True
    for spec in rungs:
        bad = []
        for slot, by_seq in spec.records.items():
            for seq, fb in by_seq.items():
                if out_records.get((int(seq), int(slot))) != fb:
                    bad.append({"slot": int(slot), "seq": int(seq)})
        ok = not bad
        all_ok = all_ok and ok
        rows.append({"rung": spec.name, "slots": len(spec.slots), "fidelity_ok": ok,
                     "mismatches": bad[:12]})
    return {"all_ok": all_ok, "per_rung": rows}


def _inplace_law_check(base_path: str, out_path: str, landed: Set[int],
                       allow_seqs: Sequence[int]) -> dict:
    """The reduce-law IN-PLACE law (rvt.reduce_law.check_substitution) over
    the two documents: only the landed slots' records changed, only in the
    declared seqs, nothing added or removed."""
    try:
        b, a = Document.from_file(base_path), Document.from_file(out_path)
        rep = RL.check_substitution(b, a, landed, allow_seqs=tuple(allow_seqs),
                                    allow_add_remove=False, host_only=False)
        return {"ok": bool(rep.ok), "landed": rep.landed, "changed": len(rep.changed),
                "unchanged_landed": len(rep.unchanged_landed),
                "stray_changed": rep.stray_changed[:20],
                "seq_violations": {str(k): v for k, v in list(rep.seq_violations.items())[:12]},
                "added": rep.added[:20], "removed": rep.removed[:20],
                "problems": rep.problems, "law": RL.THE_LAW}
    except Exception as ex:                                     # pragma: no cover
        return {"ok": False, "error": repr(ex)[:300]}


def _apply_inplace(base_path: str, out_path: str, merged: Dict[int, Dict[int, bytes]],
                   seqs: Sequence[int], *, verify: bool) -> Any:
    """ONE regadd.substitute_elements call = one EditImage, one emission."""
    return regadd.substitute_elements(
        base_path, out_path, {int(k): {int(s): bytes(b) for s, b in v.items()}
                             for k, v in merged.items()},
        seqs=tuple(int(s) for s in seqs), keep_row=True, verify=verify, diff=True)


# ===========================================================================
# 8. PHASE II -- deletions under the reduction law
# ===========================================================================

def _load_state(path: str) -> dict:
    """The validator-exact reference-graph state of a file (rvt_reduce.build_
    state_v2 -- the same instrument the certified R-ladder is built with)."""
    import rvt_reduce as RR                                       # noqa: E402
    return RR.build_state_v2(path)


def resolve_deletion(spec: DeletionSpec, state: dict) -> Tuple[Set[int], dict]:
    """Turn a deletion SPEC into the FINAL id set its policy commands, over the
    reference-graph state of the file it will be applied to.  Returns
    (final_ids, evidence).  Consults the reduce-law policy first: the
    ``exact`` policy is a banned-shape emission for genesis output (danglers)
    and is refused unless the spec's purpose is a research probe."""
    import rvt_reduce as RR                                       # noqa: E402
    law = RL.law_policy()
    ev: Dict[str, Any] = {"policy": spec.policy, "purpose": spec.purpose,
                          "law": RL.THE_LAW}
    if spec.policy not in DELETION_POLICIES:
        raise CompositionError(f"{spec.name}: unknown deletion policy {spec.policy!r} "
                               f"(known: {sorted(DELETION_POLICIES)})")
    mech, why = DELETION_POLICIES[spec.policy]
    ev["mechanism"] = mech or "exact-id-list"
    ev["policy_meaning"] = why
    if spec.policy == "exact":
        dec = law.permits("neutralise-list-remove", spec.purpose)   # danglers ~ un-swept refs
        if not (spec.purpose in ("research-probe", "diagnostic")):
            raise CompositionError(
                f"{spec.name}: policy 'exact' can leave surviving records pointing at deleted "
                f"ids (validator reference-integrity ERRORS) -- refused for purpose "
                f"{spec.purpose!r}; use 'maxgc' / 'closure' for genesis output or declare "
                f"purpose='research-probe'", {"decision": str(dec.reason)})
        ev["law_decision"] = "exact deletion allowed as a research probe (may leave danglers)"
    else:
        dec = law.check_generator("maxgc", spec.purpose)           # raises if refused
        ev["law_decision"] = dec.reason
    universe = set(state["universe"])
    host = set(state["host"])
    seed = {int(i) for i in spec.ids if int(i) in universe}
    absent = sorted(int(i) for i in spec.ids if int(i) not in universe)
    protected = {int(i) for i in spec.protected} & universe
    # the History invariant: never delete the element carrying the newest
    # modified episode (History count == max(modified_ep)+1)
    hist_protected: Set[int] = set()
    try:
        hp = RR._protect_history(state, set(seed))
        hist_protected = seed - hp
        seed = hp
    except Exception:                                            # pragma: no cover
        pass
    seed -= protected
    ev.update({"seed_given": len(spec.ids), "seed_present": len(seed),
               "absent_ids": absent[:40], "protected_removed": sorted(protected)[:40],
               "history_protected": sorted(hist_protected)})
    if spec.policy == "exact":
        final = set(seed)
        # what dangles among the SURVIVORS
        dangling: Dict[int, List[int]] = {}
        for e, refs in state["graph"].items():
            if e in final:
                continue
            hit = sorted(t for t in refs if t in final)
            if hit:
                dangling[int(e)] = hit
        ev["surviving_referrers_left_dangling"] = len(dangling)
        ev["dangling_examples"] = dict(list(dangling.items())[:12])
        return final, ev
    grow: Set[int] = set()
    if spec.policy == "closure":
        # delete-WITH-content: the seed's host referrers join the seed (the
        # reduce law's sanctioned alternative to editing them), to a fixpoint
        try:
            grow = RV.closure_delete(state["graph"], seed, protected=set(protected)) - seed
        except Exception as ex:                                 # pragma: no cover
            raise CompositionError(f"{spec.name}: closure computation failed: {ex!r}")
        seed = seed | grow
        ev["closure_added"] = len(grow)
        ev["closure_added_by_class"] = dict(collections.Counter(
            state["cls_of"].get(int(e), "?") for e in grow).most_common(20))
        # honour history protection after growth as well
        try:
            hp = RR._protect_history(state, set(seed))
            hist_protected |= (seed - hp)
            seed = hp
            ev["history_protected"] = sorted(hist_protected)
        except Exception:                                        # pragma: no cover
            pass
    pins = set()
    if spec.latest_pins:
        pins = set().union(*state.get("ext", {}).values()) if state.get("ext") else set()
    delete, kept, pin_ev = RR.maxgc(state, seed, extra_pins=pins)
    ev.update({"maxgc_seed": len(seed), "maxgc_deleted": len(delete),
               "maxgc_kept_pinned": len(kept),
               "kept_seed_by_class": pin_ev.get("kept_seed_by_class"),
               "top_pinning_pairs": (pin_ev.get("top_pinning_pairs") or [])[:12],
               "latest_pins_used": bool(spec.latest_pins), "pin_ids": len(pins)})
    return set(delete), ev


def _deletion_layer(before_path: str, out_path: str, deletions: Sequence[DeletionSpec],
                    *, verify: bool, purge_registries: bool) -> dict:
    """Apply the deletion specs (union of their resolved sets) to
    ``before_path`` -> ``out_path`` with the CERTIFIED deletion mechanics and
    the reduce-law guard; return the deletion-layer report."""
    t0 = time.time()
    rep: Dict[str, Any] = {"specs": [], "problems": []}
    state = _load_state(before_path)
    final_all: Set[int] = set()
    per_spec = []
    for spec in deletions:
        ids, ev = resolve_deletion(spec, state)
        per_spec.append({**spec.summary(), "resolved_ids": len(ids), "evidence": ev,
                         "resolved_by_class": dict(collections.Counter(
                             state["cls_of"].get(int(e), "?") for e in ids).most_common(30))})
        final_all |= ids
    rep["specs"] = per_spec
    rep["total_deleted"] = len(final_all)
    rep["deleted_by_class"] = dict(collections.Counter(
        state["cls_of"].get(int(e), "?") for e in final_all).most_common(60))
    if not final_all:
        rep["note"] = "the deletion set resolved to EMPTY (nothing deletable under the policy)"
        rep["out"] = None
        rep["seconds"] = round(time.time() - t0, 1)
        return rep
    # dangling analysis BEFORE emission (what the deletion leaves pointing at nothing)
    try:
        an = RV.analyze_deletion(state["doc"], state["graph"], set(final_all),
                                external_refs={k: set(v) for k, v in (state.get("ext") or {}).items()})
    except Exception as ex:                                     # pragma: no cover
        an = {"error": repr(ex)[:200]}
    rep["analysis"] = an
    lat_dangling = len((state.get("ext") or {}).get("Global/Latest", set()) & final_all)
    rep["latest_registry_entries_left_dangling"] = lat_dangling
    rep["latest_dangling_note"] = ("ADocument registry entries of deleted ids are LEFT DANGLING "
                                   "-- tolerated (certified R5 / R9: thousands of dangling Latest "
                                   "refs pass); Global/Latest stays byte-identical unless registry "
                                   "reconciliation is requested")
    # the emission: the certified R-ladder deletion mechanics
    rr = RV.delete_elements(before_path, out_path, final_all)
    rep["emission"] = rr.to_json()
    latest_purged = None
    if purge_registries:
        # SANCTIONED registry-reconciliation (Revit's own deletion semantics on
        # Global/Latest): purge exactly the deleted ids from the ADocument
        try:
            import genesis_triage as GT                                # noqa: E402
            RL.guard_generator("registry-reconciliation", "genesis-base")
            tmp = out_path + ".regpurge.rvt"
            latest_purged = GT.purge_ids_from_latest(out_path, tmp, final_all)
            os.replace(tmp, out_path)
        except Exception as ex:                                 # pragma: no cover
            rep["problems"].append(f"registry reconciliation failed: {ex!r}"[:300])
    rep["registry_reconciliation"] = ({"performed": True, "report": latest_purged}
                                       if purge_registries else
                                       {"performed": False,
                                        "note": "Global/Latest byte-identical; deleted ids' "
                                                "registry entries dangling (tolerated)"})
    # ---- assertions ----------------------------------------------------------
    if verify:
        # THE REDUCTION LAW: every survivor byte-identical, nothing added
        try:
            b_doc, a_doc = Document.from_file(before_path), Document.from_file(out_path)
            law = RL.check_reduction(b_doc, a_doc, before_label=_relp(before_path),
                                     after_label=_relp(out_path))
            rep["reduce_law"] = {"verdict": law.verdict, "ok": bool(law.ok),
                                 "removed": law.removed, "added": len(law.added),
                                 "survivors_edited": len(law.survivors_edited),
                                 "clause_counts": law.clause_counts,
                                 "summary": law.summary(limit=8), "law": RL.THE_LAW}
            if not law.ok:
                rep["problems"].append(f"REDUCTION LAW VIOLATED ({law.verdict}): "
                                       f"{len(law.survivors_edited)} edited survivor(s), "
                                       f"{len(law.added)} added id(s)")
            if law.removed != len(final_all):
                rep["problems"].append(f"removed {law.removed} != resolved deletion set "
                                       f"{len(final_all)}")
        except Exception as ex:                                 # pragma: no cover
            rep["reduce_law"] = {"error": repr(ex)[:300]}
            rep["problems"].append("reduce-law check crashed")
        # structural proof (the R-ladder's own gate)
        try:
            st = RV.verify_reduced(out_path, final_all)
            rep["structural"] = {k: st.get(k) for k in
                                 ("ok", "crc_failures", "ecc_mismatches", "walker_errors",
                                  "counts_match", "seq_id_sets_equal", "stamps_bad",
                                  "isize_identity_ok", "deleted_still_present",
                                  "elemtable_ids_without_record")}
            if not st.get("ok"):
                rep["problems"].append("structural proof (verify_reduced) failed")
        except Exception as ex:                                 # pragma: no cover
            rep["structural"] = {"error": repr(ex)[:300]}
            rep["problems"].append("structural proof crashed")
        # validator
        val = _run_validator(out_path)
        rep["validator"] = val
        if not (val.get("ok") and val.get("errors") == 0):
            rep["problems"].append(f"validator errors={val.get('errors')}")
        # four-registry coherence
        four = _four_registry(out_path)
        rep["four_registry"] = four
        if four.get("coherent") is False:
            rep["problems"].append("four-registry document coherence broken after deletion")
        # the byte-delta table for the deletion layer
        d = stream_diff(before_path, out_path)
        pname = rr.partition
        differing = list(d["streams"]["differing"])
        allowed = {pname, "Global/ElemTable"} | ({"Global/Latest"} if purge_registries else set())
        strays = [s for s in differing if s not in allowed]
        exceptions = [
            {"stream": "Global/ElemTable",
             "reason": "the deleted elements' ElemTable rows are removed -- a deletion's "
                       "registration effect (the count drops; the id watermark is NOT lowered, "
                       "Revit never re-issues ids)"},
            {"stream": pname,
             "reason": "the deleted records leave unit 0; the certified re-blocker "
                       "(rvt.reduce.reblock) re-chunks the seq runs; SURVIVOR RECORD BYTES "
                       "UNCHANGED (asserted by the reduce law)"}]
        if purge_registries:
            exceptions.append({"stream": "Global/Latest",
                               "reason": "registry reconciliation was requested: the deleted ids' "
                                         "ADocument registry rows were purged (sanctioned "
                                         "generator 'registry-reconciliation')"})
        rep["byte_delta"] = {
            "layer": "deletion",
            "streams_differing": differing,
            "allowed_to_differ": sorted(allowed),
            "strays": strays,
            "records_removed_ids_count": len(d["records"]["removed_ids"]),
            "records_added_ids": d["records"]["added_ids"][:12],
            "records_changed_ids": d["records"]["changed_ids"][:12],
            "common_order_preserved": d["records"].get("common_order_preserved"),
            "adocument_identical": d["latest"].get("identical"),
            "embedded_units_identical": d.get("embedded_units_identical"),
            "exceptions": exceptions,
            "assertion_holds": (not strays and not d["records"]["added_ids"]
                                and not d["records"]["changed_ids"]
                                and (d["latest"].get("identical") or purge_registries)),
        }
        if not rep["byte_delta"]["assertion_holds"]:
            rep["problems"].append(f"deletion byte-delta: strays {strays}, added "
                                   f"{len(d['records']['added_ids'])}, changed "
                                   f"{len(d['records']['changed_ids'])}, latest identical "
                                   f"{d['latest'].get('identical')}")
    rep["out"] = _relp(out_path)
    rep["seconds"] = round(time.time() - t0, 1)
    return rep


# ===========================================================================
# 9. COMPOSE  (the one call)
# ===========================================================================

def compose(base_path: str, rungs: Sequence[RungSpec], out_path: str, *,
            deletions: Sequence[DeletionSpec] = (),
            manifest_path: Optional[str] = None,
            on_overlap: str = "refuse",
            verify: bool = True,
            purge_registries: bool = False,
            allow_uncertified_base: bool = False,
            label: str = "") -> ComposeReport:
    """COMPOSE ``rungs`` (independent in-place rung sets) AND ``deletions``
    onto ONE certified base -> ``out_path``, in a single deterministic pass:
    in-place substitutions first (one merged ``substitute_elements`` call,
    zero registration motion), then reduce-law-governed deletions, with the
    invariant assertions (registry parity, byte-delta on the in-place layer,
    the reduce law on the deletion layer, four-registry coherence, per-rung
    byte fidelity, validator, structural proof) and a MANIFEST recording
    exactly which rung sets and deletions were composed.  Deterministic:
    the same inputs produce the same bytes (no timestamps in the output).

    ``manifest_path`` defaults to ``<out stem>.manifest.json``.  Raises
    :class:`CompositionError` when a composition law is violated (nothing is
    written); a NOT-CLEAN verdict (assertion failed after emission) is
    reported, not raised, so the manifest documents the failure.
    """
    t_all = time.time()
    base_path = _abs(base_path)
    out_path = _abs(out_path)
    manifest_path = _abs(manifest_path or (os.path.splitext(out_path)[0] + ".manifest.json"))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    log(f"\n== COMPOSE {label or _relp(out_path)}")
    log(f"   base {_relp(base_path)}; rung sets {[r.name for r in rungs]}; "
        f"deletions {[d.name for d in deletions]}")
    # ---- base facts -----------------------------------------------------------
    cert = assert_certified(base_path, allow_uncertified=allow_uncertified_base)
    A = record_index(base_path)
    base_records: Dict[Tuple[int, int], bytes] = A["records"]
    base_info = {
        "file": _relp(base_path), "md5": md5_of(base_path), "sha256": sha256_of(base_path),
        "bytes": os.path.getsize(base_path), "certification": cert,
        "host_elements": len(A["elemtable"]["records"]),
        "watermark": A["elemtable"]["footer"]["last_id"],
        "partition": A["partition"],
    }
    problems: List[str] = []
    warnings: List[str] = []
    # ---- Phase I: merge + emit -----------------------------------------------
    del_ids_all: Set[int] = set()
    for d in deletions:
        del_ids_all |= {int(x) for x in d.ids}
    merged, mrep = merge_rung_sets(base_records, rungs, base_label=_relp(base_path),
                                   deletion_ids=del_ids_all, on_overlap=on_overlap)
    for r in rungs:
        for n in r.notes:
            if n.startswith("WARNING"):
                warnings.append(f"{r.name}: {n}")
    phase1: Dict[str, Any] = {"merge": mrep}
    subst_target = out_path if not deletions else (os.path.splitext(out_path)[0] + ".inplace.rvt")
    landed = set(merged)
    seqs = mrep.get("merged_seqs") or [102]
    if merged:
        log(f"   phase I: {len(merged)} merged slots over {len(rungs)} rung set(s), seqs {seqs}")
        t0 = time.time()
        srep = _apply_inplace(base_path, subst_target, merged, seqs, verify=verify)
        phase1["emit"] = {"op": srep.op, "verdict": srep.verdict, "problems": srep.problems,
                          "seqs_replaced": srep.seqs_replaced,
                          "elemtable_rewritten": (srep.emit or {}).get("elemtable_rewritten"),
                          "latest_rewritten": (srep.emit or {}).get("latest_rewritten"),
                          "streams_replaced": (srep.emit or {}).get("streams_replaced"),
                          "seconds": round(time.time() - t0, 1)}
        phase1["validator"] = srep.validator
        phase1["structural"] = srep.structural
        diff = srep.diff or {}
        pname = (srep.emit or {}).get("partition") or A["partition"]
        # invariants ---------------------------------------------------------------
        bd = _byte_delta_table(diff, slots=landed, seqs=seqs, partition_name=pname)
        law = _inplace_law_check(base_path, subst_target, landed, seqs)
        Bidx = record_index(subst_target)
        fid = _rung_fidelity(rungs, Bidx["records"])
        four = _four_registry(subst_target)
        parity = {
            "global_latest_identical": bool((diff.get("latest") or {}).get("identical")),
            "global_elemtable_identical": bool((diff.get("elemtable") or {}).get("identical")),
            "statement": ("100% by construction: Global/Latest and Global/ElemTable are byte-"
                          "identical to the base, so every registry leaf that indexed a slot "
                          "still indexes the same id (now carrying OUR object) -- ASSERTED "
                          "via the stream byte-diff, not assumed"),
        }
        phase1.update({"byte_delta": bd, "in_place_law": law, "rung_fidelity": fid,
                       "four_registry": four, "registry_parity": parity,
                       "registration_diff_sample": _registration_diff_sample(
                           base_path, subst_target, sorted(landed), limit=6)})
        if srep.verdict != "VALID":
            problems += [f"regadd: {p}" for p in (srep.problems or [])]
        val = srep.validator or {}
        if not (val.get("ok") and val.get("errors") == 0):
            problems.append(f"in-place layer: validator errors={val.get('errors')}")
        if not (srep.structural or {}).get("ok"):
            problems.append("in-place layer: structural proof failed")
        if not bd["assertion_holds"]:
            problems += [f"byte-delta: {p}" for p in bd["problems"]]
        if not law.get("ok"):
            problems.append(f"in-place law: {law.get('problems') or law.get('error')}")
        if not fid["all_ok"]:
            problems.append("rung byte fidelity: the composed file does not carry a rung's exact "
                            "record bytes at its slots")
        if not (parity["global_latest_identical"] and parity["global_elemtable_identical"]):
            problems.append("registry parity: a global registry stream is not byte-identical")
        if four.get("coherent") is False:
            problems.append("four-registry document coherence broken")
        log(f"   phase I: emit {srep.verdict}; changed {bd['records_changed_count']} of "
            f"{bd['expected_slots']} slots (byte-identical {bd['landed_but_unchanged_slots']}); "
            f"Latest identical {parity['global_latest_identical']} / ElemTable identical "
            f"{parity['global_elemtable_identical']}; validator errors {val.get('errors')}; "
            f"law ok {law.get('ok')}; fidelity {fid['all_ok']}; four-registry coherent "
            f"{four.get('coherent')}")
    else:
        phase1["emit"] = {"note": "no in-place slots to compose (rung sets empty / all "
                                  "resolved away) -- the base is carried unchanged"}
        if deletions:
            import shutil
            shutil.copyfile(base_path, subst_target)
        elif not deletions:
            import shutil
            shutil.copyfile(base_path, out_path)
    # ---- Phase II: deletions -------------------------------------------------
    phase2 = None
    if deletions:
        log(f"   phase II: {len(deletions)} deletion spec(s) "
            f"{[(d.name, d.policy, len(d.ids)) for d in deletions]}")
        phase2 = _deletion_layer(subst_target, out_path, deletions,
                                 verify=verify, purge_registries=purge_registries)
        problems += [f"deletion: {p}" for p in (phase2.get("problems") or [])]
        if phase2.get("out") is None:
            # nothing deletable -> the substituted file IS the output
            import shutil
            shutil.copyfile(subst_target, out_path)
            phase2["note_output"] = "deletion set empty after policy -> output = the in-place layer"
        # keep the intermediate for audit; record it
        phase2["intermediate_inplace_file"] = _relp(subst_target)
        log(f"   phase II: deleted {phase2.get('total_deleted')}; reduce-law "
            f"{(phase2.get('reduce_law') or {}).get('verdict')}; validator errors "
            f"{(phase2.get('validator') or {}).get('errors')}; structural ok "
            f"{(phase2.get('structural') or {}).get('ok')}")
    # ---- the record ------------------------------------------------------------
    out_info = {"file": _relp(out_path), "md5": md5_of(out_path), "sha256": sha256_of(out_path),
                "bytes": os.path.getsize(out_path)}
    invariants = {
        "in_place_first_then_deletions": True,
        "registry_parity": (phase1.get("registry_parity") if merged else
                            {"statement": "no in-place layer"}),
        "byte_delta_in_place": (phase1.get("byte_delta") if merged else None),
        "in_place_law": (phase1.get("in_place_law") if merged else None),
        "reduce_law_deletions": (phase2.get("reduce_law") if phase2 else None),
        "four_registry_final": _four_registry(out_path),
        "validator_final": (phase2.get("validator") if phase2 and phase2.get("out")
                            else phase1.get("validator")),
    }
    rep = ComposeReport(
        op="compose", base=base_info, out=out_info,
        phase_1_inplace=phase1, phase_2_deletions=phase2,
        invariants=invariants, problems=problems, warnings=warnings,
        verdict=("COMPOSED-VALID" if not problems else "NOT-CLEAN"),
        manifest_file=_relp(manifest_path), seconds=round(time.time() - t_all, 1))
    _write_json(manifest_path, rep.to_json())
    log(f"   -> {_relp(out_path)} {out_info['bytes']:,} B  VERDICT {rep.verdict} "
        f"({rep.seconds}s); manifest {_relp(manifest_path)}"
        + ("" if not problems else "\n   *** " + "\n   *** ".join(problems)))
    return rep


def _registration_diff_sample(parent: str, out: str, slots: Sequence[int], limit: int = 6) -> List[dict]:
    """rvt.regdiff registration record of a sample of composed slots: every
    NON-object registration dimension must be identical (row / positions /
    surface); only the object may differ."""
    rows: List[dict] = []
    try:
        from rvt import regdiff as RD
        da, db = RD.RegDoc(parent), RD.RegDoc(out)
        for s in list(slots)[:limit]:
            ra, rb = RD.registration_of(da, int(s)), RD.registration_of(db, int(s))
            dif = RD.diff_registrations(ra, rb)
            structural = [d for d in dif if not str(d.get("dimension", "")).startswith("OBJ.")]
            rows.append({"slot": int(s), "class": ra.class_name,
                         "registration_identical": (len(dif) == 0),
                         "non_object_differences": structural[:6],
                         "surface_paths": len(ra.registry)})
    except Exception as ex:                                        # pragma: no cover
        rows.append({"error": repr(ex)[:300]})
    return rows


# ===========================================================================
# 10. RUNG-SPEC LOADERS for the streams' outputs
# ===========================================================================

def group_a_specs(names: Sequence[str] = tuple(GROUP_A_SINGLES),
                  parent: str = Y9, directory: str = RESIDUE_A) -> List[RungSpec]:
    """Group A's certified single-layer rungs (each Y9 + ONE bucket), as
    rung specs extracted by byte delta vs their parent Y9."""
    out = []
    for n in names:
        f = os.path.join(directory, f"{n}.rvt")
        out.append(RungSpec.from_rung_file(f, parent, name=f"A:{n}", group="A"))
    return out


def group_b_specs(names: Sequence[str] = tuple(GROUP_B_CERTIFIED_BUCKETS),
                  parent: str = Y9, directory: str = RESIDUE_B) -> List[RungSpec]:
    """Group B's single-bucket probes (each Y9 + ONE bucket) as rung specs.
    Default: only the buckets whose probe is viewer-CERTIFIED."""
    out = []
    for n in names:
        f = os.path.join(directory, f"{n}.rvt")
        out.append(RungSpec.from_rung_file(f, parent, name=f"B:{n}", group="B"))
    return out


# ===========================================================================
# 11. THE CORRECTNESS ANCHOR: compose(Y9, Group A) == ZA_deep byte-identical
# ===========================================================================

def prove_anchor(out_dir: str = OUT_DIR, *, base: str = Y9, target: str = ZA_DEEP,
                 verify: bool = True) -> dict:
    """PROVE the composer: Group A's five independently-emitted single-layer
    rung deltas, merged and replayed onto Y9 in ONE substitute_elements
    call, must reproduce the certified ``ZA_deep.rvt`` BYTE-IDENTICALLY.
    Writes ``<out_dir>/G_A.rvt`` (the reproduction) + ``anchor.json``."""
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    out = os.path.join(out_dir, "G_A.rvt")
    specs = group_a_specs()
    rep = compose(base, specs, out, label="G_A (the ZA_deep anchor)", verify=verify)
    got, want = md5_of(out), md5_of(target)
    identical = (got == want)
    anchor = {
        "claim": ("compose(Y9, [A:Z_subcat, A:Z_annot, A:Z_datum, A:Z_pattern, A:Z_asset]) "
                  "reproduces the certified ZA_deep.rvt BYTE-IDENTICALLY"),
        "base": _relp(base), "target": _relp(target),
        "target_certification": (certification_of(target) or {}).get("proves"),
        "rung_sets": [s.summary() for s in specs],
        "reproduction": _relp(out), "md5_reproduction": got, "md5_target": want,
        "BYTE_IDENTICAL": identical,
        "meaning": ("the composer's Phase I is EXACT: five independently emitted in-place "
                    "rungs, merged into one call, land in precisely the file the residue "
                    "stream emitted -- so a composed candidate carries each rung's proven "
                    "content bit for bit"),
        "compose_verdict": rep.verdict, "compose_problems": rep.problems,
        "seconds": round(time.time() - t0, 1),
    }
    _write_json(os.path.join(out_dir, "anchor.json"), anchor)
    log(f"\n[anchor] reproduction md5 {got}\n[anchor] target       md5 {want}\n"
        f"[anchor] BYTE-IDENTICAL: {identical}  ({anchor['seconds']}s)")
    if not identical:
        log("[anchor] *** THE ANCHOR DOES NOT HOLD -- the composer is NOT exact ***")
    return anchor


# ===========================================================================
# 12. THE CANDIDATES the orchestrator gates
# ===========================================================================

def build_candidates(out_dir: str = OUT_DIR, *, verify: bool = True) -> dict:
    """Build the composed candidates + the batch manifest:

      * ``G_A``       -- compose(Y9, Group-A rungs): the ANCHOR (must equal the
                         certified ZA_deep.rvt bit for bit; it is certified BY
                         BYTES the moment the md5 matches).
      * ``G_AB_defs`` -- ZA_deep + Group B's certified ``Z_defs`` bucket (the
                         one Group-B bucket already viewer-PASSED), composed
                         onto the certified deep base; the FIRST cross-group
                         composition to gate.
    Plus the standing control (a byte-identical copy of the deepest
    certified base) and ``probes.json`` for the batch gate."""
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    results: Dict[str, Any] = {}
    # -- G_A = the anchor -------------------------------------------------------
    anchor = prove_anchor(out_dir, verify=verify)
    results["G_A"] = {"file": f"{_relp(out_dir)}/G_A.rvt", "anchor": anchor,
                      "viewer": ("PASS (byte-identical to the certified ZA_deep.rvt)"
                                 if anchor["BYTE_IDENTICAL"] else "UNTESTED (anchor failed)")}
    # -- G_AB_defs = ZA_deep + Z_defs ------------------------------------------
    b_specs = group_b_specs(["Z_defs"])
    out = os.path.join(out_dir, "G_AB_defs.rvt")
    rep = compose(ZA_DEEP, b_specs, out, label="G_AB_defs (ZA_deep + Group B's certified Z_defs)",
                  verify=verify)
    results["G_AB_defs"] = {"file": f"{_relp(out_dir)}/G_AB_defs.rvt", "verdict": rep.verdict,
                            "problems": rep.problems, "manifest": rep.manifest_file,
                            "landed_added": (b_specs[0].summary().get("landed_slots")
                                             if b_specs else None),
                            "viewer": "UNTESTED (staged for the gate)"}
    # -- control + probes -------------------------------------------------------
    control = stage_control(ZA_DEEP, out_dir)
    results["control"] = control
    probes = write_probes_manifest(out_dir, results, control=control)
    results["probes"] = _relp(probes)
    results["seconds"] = round(time.time() - t0, 1)
    _write_json(os.path.join(out_dir, "candidates.json"), results)
    log(f"\n[candidates] G_A anchor {anchor['BYTE_IDENTICAL']}; G_AB_defs {rep.verdict}; "
        f"control {control['file']} ({results['seconds']}s)")
    return results


def write_probes_manifest(out_dir: str, results: dict, *, control: dict) -> str:
    """probes.json for this stream's batch: G_AB_defs (the one file that
    needs a viewer verdict) + its certified control; G_A is recorded as
    certified-by-bytes (no upload needed)."""
    ga = results.get("G_A") or {}
    gab = results.get("G_AB_defs") or {}
    manifest = {
        "stream": ("genesis-assembly (THE COMPOSER: certified base + independent in-place "
                   "rung sets + a deletion set -> one composed candidate)"),
        "situation": (
            "ZA_deep (Y9 + Group A's residue layers) is viewer-CERTIFIED (VERDICTS #18); Group "
            "B's Z_defs bucket is viewer-CERTIFIED (its single probe passed; ZB_deep FAILED "
            "partially, one other B bucket carries a subtle defect the singles are naming). "
            "The composer merges independent certified rung sets onto ONE certified base in one "
            "deterministic pass; its correctness is ANCHORED: compose(Y9, Group-A rungs) "
            "reproduces the certified ZA_deep.rvt byte-identically."),
        "anchor": {"file": ga.get("file"), "BYTE_IDENTICAL_to_ZA_deep": (ga.get("anchor") or {}).get("BYTE_IDENTICAL"),
                   "md5": (ga.get("anchor") or {}).get("md5_reproduction"),
                   "viewer": ga.get("viewer"),
                   "note": "certified by BYTES (md5-identical to a viewer-PASSED file) -- no upload"},
        "standing_control": control,
        "controls_discipline": ("Upload the batch with the certified CONTROL (a byte-identical "
                                "copy of the certified deep base ZA_deep). If the CONTROL fails, "
                                "the batch is VOID (oracle / service health) and nothing about "
                                "the composition is read from it."),
        "probes": [
            {"order": 1, "rung": "G_AB_defs", "file": gab.get("file"),
             "class_layer_substituted": ("Group A's whole residue layer (already in the base "
                                         "ZA_deep) + Group B's parameter-DEFINITIONS bucket "
                                         "(ParamElemExternal / ParamBinding / ParamElemProject "
                                         "/ ParamElemElectricalLoadClassification), composed in "
                                         "place"),
             "base": {"file": _relp(ZA_DEEP),
                      "certification": certification_of(ZA_DEEP)},
             "derived_from": _relp(ZA_DEEP),
             "composed_from": [_relp(os.path.join(RESIDUE_B, "Z_defs.rvt")) + " (certified)"],
             "the_ONE_thing_it_tests": (
                 "Whether two independently CERTIFIED in-place layers (ZA_deep's Group-A "
                 "layer + Group B's Z_defs bucket, each viewer-PASSED alone on Y9) COMPOSE: "
                 "the merged file changes exactly the union of their slots, both global "
                 "registry streams byte-identical to ZA_deep."),
             "if_PASS": ("Certified in-place layers compose additively: every future certified "
                         "bucket (the named-good Group-B singles, residue_a2's ZC rungs) can be "
                         "composed onto the deep base by this tool -- the end-game is one "
                         "compose_endgame call."),
             "if_FAIL": ("The composition of two individually-passing layers fails: read the "
                         "control first (round health); if the control passes, the two layers "
                         "interact -- bisect by composing Z_defs onto Y9 vs onto ZA_deep."),
             "verdict": gab.get("verdict"), "problems": gab.get("problems"),
             "manifest": gab.get("manifest"),
             "control_to_upload_with_batch": control},
        ],
        "not_uploaded": [{"rung": "G_A", "file": ga.get("file"),
                          "why": "byte-identical to the already-certified ZA_deep.rvt "
                                 "(the anchor) -- its verdict IS ZA_deep's PASS"}],
    }
    p = os.path.join(out_dir, "probes.json")
    _write_json(p, manifest)
    log(f"[probes] wrote {_relp(p)}")
    return p


# ===========================================================================
# 13. THE G_endgame TEMPLATE (one call, once the streams deliver)
# ===========================================================================

def compose_endgame(*, base: str = ZA_DEEP,
                    a_rungs: Sequence[Union[RungSpec, str]] = (),
                    b_buckets: Sequence[Union[RungSpec, str]] = (),
                    zc_rungs: Sequence[Union[RungSpec, str]] = (),
                    add_records: Optional[Dict[int, Any]] = None,
                    deletions: Sequence[Union[DeletionSpec, str, dict]] = (),
                    default_parent: str = Y9,
                    zc_parent: Optional[str] = None,
                    out_path: str = os.path.join(OUT_DIR, "G_endgame.rvt"),
                    on_overlap: str = "refuse",
                    purge_registries: bool = False,
                    verify: bool = True) -> ComposeReport:
    """THE END-GAME TEMPLATE: {Group-A rungs, the named-good Group-B
    buckets, residue_a2's ZC rungs, the deletion stream's D_all set} onto the
    certified deep base -> the final G_endgame candidate, in ONE call.

    Inputs may be :class:`RungSpec` objects or rung ``.rvt`` paths (a path
    ``FILE.rvt@PARENT.rvt`` names its own parent; else ``default_parent`` /
    ``zc_parent`` apply).  ``deletions`` may be :class:`DeletionSpec`
    objects, JSON paths, or dicts (D_all).  ``base`` defaults to the deepest
    certified file (ZA_deep) -- when the base already CONTAINS a rung set
    (Group A is inside ZA_deep) pass only the NEW rung sets: a rung already
    in the base would be re-applied identically (its records match), but the
    honest call composes only what the base lacks.  ``add_records`` = the
    ADD queue (records with NO in-place slot) -- NOT composable by this
    machinery (a registration variable, Phase II of the endgame): they are
    rejected here with the reason, so nothing silently disappears.
    """
    def _spec(x, group: str, parent_default: str) -> RungSpec:
        if isinstance(x, RungSpec):
            return x
        s = str(x)
        parent = parent_default
        if "@" in s:
            s, parent = s.split("@", 1)
        return RungSpec.from_rung_file(_abs(s), _abs(parent), group=group,
                                       name=f"{group}:{os.path.splitext(os.path.basename(s))[0]}")

    def _dspec(x) -> DeletionSpec:
        if isinstance(x, DeletionSpec):
            return x
        return DeletionSpec.from_json(x)

    if add_records:
        raise CompositionError(
            f"{len(add_records)} ADD-queue record(s) supplied: the ADD path (new elements with "
            f"NEW registrations) is NOT an in-place composition -- it is the endgame's Phase II "
            f"(regadd.add_element_like_original, one registration variable per rung, its own "
            f"controls); the composer refuses to fold it in silently")
    specs: List[RungSpec] = []
    specs += [_spec(x, "A", default_parent) for x in a_rungs]
    specs += [_spec(x, "B", default_parent) for x in b_buckets]
    specs += [_spec(x, "C", zc_parent or default_parent) for x in zc_rungs]
    dels = [_dspec(x) for x in deletions]
    return compose(base, specs, out_path, deletions=dels, on_overlap=on_overlap,
                   purge_registries=purge_registries, verify=verify,
                   label="G_endgame (A-rungs + named-good B buckets + ZC rungs + D_all)")


def endgame_from_spec(spec_path: str) -> ComposeReport:
    """Run :func:`compose_endgame` from a JSON inputs file:
    ``{"base", "a_rungs": [...], "b_buckets": [...], "zc_rungs": [...],
      "zc_parent", "default_parent", "deletions": [json paths | dicts],
      "out", "on_overlap", "purge_registries"}``."""
    with open(_abs(spec_path)) as fh:
        s = json.load(fh)
    return compose_endgame(
        base=_abs(s.get("base") or ZA_DEEP),
        a_rungs=s.get("a_rungs") or [], b_buckets=s.get("b_buckets") or [],
        zc_rungs=s.get("zc_rungs") or [],
        deletions=s.get("deletions") or [],
        default_parent=_abs(s.get("default_parent") or Y9),
        zc_parent=(_abs(s["zc_parent"]) if s.get("zc_parent") else None),
        out_path=_abs(s.get("out") or os.path.join(OUT_DIR, "G_endgame.rvt")),
        on_overlap=s.get("on_overlap") or "refuse",
        purge_registries=bool(s.get("purge_registries", False)),
        verify=bool(s.get("verify", True)))


# ===========================================================================
# 14. THE HONEST MEASURE -- provenance ledger + element census + scoreboard
# ===========================================================================

#: which host elements are OURS in the two certified deep files (by their
#: streams' certification reports): the Y-ladder's landed slots for Y9,
#: plus Group A's landed slots for ZA_deep.
Y_RUNGS = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7", "Y8", "Y9"]


def _report_landed(paths: Sequence[str]) -> Set[int]:
    out: Set[int] = set()
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            out.add(int(row["slot"]))
    return out


def landed_set_for(name: str) -> Tuple[Set[int], List[str]]:
    """The set of host element ids whose seq-102 OBJECT is OUR constructors'
    output (LANDED), for a known scoreboard subject, + the report sources."""
    y_reports = [os.path.join(LADDER, f"{n}.json") for n in Y_RUNGS]
    if name == "Y9":
        return _report_landed(y_reports), [_relp(p) for p in y_reports]
    if name in ("ZA_deep", "G_A"):
        srcs = y_reports + [os.path.join(RESIDUE_A, "ZA_deep.json")]
        return _report_landed(srcs), [_relp(p) for p in srcs]
    if name == "G_AB_defs":
        srcs = (y_reports + [os.path.join(RESIDUE_A, "ZA_deep.json"),
                            os.path.join(RESIDUE_B, "Z_defs.json")])
        return _report_landed(srcs), [_relp(p) for p in srcs]
    return set(), []


def _forge_corpus_bytes(latest_payload: bytes) -> dict:
    """Measure the two Forge / ESSchema unit-schema JSON corpus tables inside a
    Global/Latest payload (counsel C4 item): their byte span + doc count."""
    try:
        import latest_map as LM                                       # noqa: E402
        tables = LM.find_json_tables(latest_payload)
    except Exception as ex:                                            # pragma: no cover
        return {"error": repr(ex)[:200], "bytes": 0, "tables": []}
    total = 0
    rows = []
    for t in tables:
        span = int(t["end"]) - int(t["header_start"])
        total += max(0, span)
        rows.append({"docs": t["count"], "bytes": span, "sha256_16": t["sha256_16"],
                     "namespaces_top": dict(list((t.get("namespaces") or {}).items())[:4])})
    return {"bytes": total, "tables": rows, "table_count": len(rows)}


def element_census(rvt_path: str, landed: Set[int]) -> dict:
    """Elements OURS / total + the Autodesk-authored RESIDUE by class,
    bucketed with the substitution stream's residue vocabulary (Yn's own
    buckets), + the byte-weighted split of the host unit."""
    import genesis_substitute_v3 as V3                                 # noqa: E402
    doc = Document.from_file(rvt_path)
    host = sorted(doc.et_by_id)
    ours = [e for e in host if int(e) in landed]
    residue = [e for e in host if int(e) not in landed]
    res_by_class: collections.Counter = collections.Counter(doc.class_of(e) or "?" for e in residue)
    buckets: Dict[str, dict] = {}
    for c, n in res_by_class.most_common():
        b, why = V3._residue_bucket(c)
        e = buckets.setdefault(b, {"elements": 0, "classes": {}, "reason": why})
        e["elements"] += n
        e["classes"][c] = n
    # byte-weighted element split over the host unit's framed records
    ours_obj = ours_env = residue_bytes = 0
    for e in host:
        for seq in SEQS:
            r = doc.idx[seq].get(int(e))
            if r is None:
                continue
            n = len(r.payload) + _hdr_len(seq) + 6           # framed size approx (hdr+body+repeat)
            if int(e) in landed:
                if seq == 102:
                    ours_obj += n
                else:
                    ours_env += n
            else:
                residue_bytes += n
    return {
        "host_elements": len(host), "ours_landed": len(ours), "residue": len(residue),
        "ours_pct": round(100.0 * len(ours) / max(1, len(host)), 2),
        "residue_by_bucket": {b: {"elements": v["elements"], "classes": len(v["classes"]),
                                   "top": dict(sorted(v["classes"].items(), key=lambda kv: -kv[1])[:5]),
                                   "reason": v["reason"]}
                              for b, v in sorted(buckets.items(), key=lambda kv: -kv[1]["elements"])},
        "residue_classes": len(res_by_class),
        "element_bytes": {"our_objects_seq102": ours_obj,
                          "landed_envelopes_seq101_103": ours_env,
                          "autodesk_residue_records": residue_bytes,
                          "note": ("record-framed bytes in the host unit: our constructed = the "
                                   "seq-102 objects of landed slots; the seq-101/103 envelopes of "
                                   "landed slots and every record of a residue element are "
                                   "Autodesk-authored element bytes")},
    }


def run_ledger(rvt_path: str, *, cache_json: Optional[str] = None,
               force: bool = False) -> dict:
    """The provenance ledger v2 (rvt.provenance --baseline all --streams
    --strings --identity), cached as JSON next to the file."""
    if cache_json and os.path.exists(cache_json) and not force:
        with open(cache_json) as fh:
            return json.load(fh)
    from rvt.provenance import provenance
    bases = sorted(glob.glob(os.path.join(SAMPLES_DIR, "*.rvt")))
    doc = Document.from_file(rvt_path)
    baselines = [Document.from_file(b) for b in bases
                 if os.path.abspath(b) != os.path.abspath(rvt_path)]
    t0 = time.time()
    rep = provenance(doc, baselines[0] if baselines else None, baselines=baselines or None,
                     examples=2, with_units=True, streams=True, strings=True, identity=True,
                     cache_dir=os.path.join(GEN, "provenance", ".cache"), verbose=False)
    rep["elapsed_s"] = round(time.time() - t0, 1)
    if cache_json:
        _write_json(cache_json, rep)
    return rep


def byte_weighted_split(rvt_path: str, landed: Set[int], ledger: Optional[dict] = None) -> dict:
    """The byte-weighted provenance split of a file:
    {our constructed / Autodesk element residue / the two product corpora
    (Formats/Latest + the ESSchema unit-schema corpus, counsel C4) / format &
    document machinery / lineage & identity streams}, summing to the total
    inflated bytes the ledger counts."""
    from rvt.provenance import content_units
    from rvt.container import open_rvt
    units = content_units(rvt_path)
    by_name = {u.name: u for u in units}
    total = sum(len(u.data) for u in units)
    # element census over the host unit
    census = element_census(rvt_path, landed)
    eb = census["element_bytes"]
    # the two product corpora
    schema_b = len(by_name["Formats/Latest"].data) if "Formats/Latest" in by_name else 0
    latest_b = len(by_name["Global/Latest"].data) if "Global/Latest" in by_name else 0
    corpus = _forge_corpus_bytes(by_name["Global/Latest"].data) if "Global/Latest" in by_name \
        else {"bytes": 0, "tables": []}
    # lineage / identity streams
    LINEAGE = ["BasicFileInfo", "Global/History", "Global/DocumentIncrementTable", "Contents",
               "Global/PartitionTable", "TransmissionData", "ProjectInformation",
               "PartAtom", "RevitPreview4.0"]
    lineage_b = sum(len(by_name[n].data) for n in LINEAGE if n in by_name)
    host_unit = next((u for u in units if u.kind == "host-unit"), None)
    host_unit_b = len(host_unit.data) if host_unit else 0
    save_units_b = sum(len(u.data) for u in units if u.kind == "save-unit")
    elem_records_b = eb["our_objects_seq102"] + eb["landed_envelopes_seq101_103"] + \
        eb["autodesk_residue_records"]
    unit0_framing = max(0, host_unit_b - elem_records_b)
    machinery = (latest_b - corpus.get("bytes", 0)) + \
        (len(by_name["Global/ElemTable"].data) if "Global/ElemTable" in by_name else 0) + \
        (len(by_name["Global/ContentDocuments"].data) if "Global/ContentDocuments" in by_name else 0) + \
        unit0_framing
    rows = {
        "our_constructed_element_objects": eb["our_objects_seq102"],
        "autodesk_element_residue": eb["autodesk_residue_records"] + eb["landed_envelopes_seq101_103"],
        "product_corpora_counsel_C4": schema_b + corpus.get("bytes", 0),
        "format_and_document_machinery": machinery,
        "lineage_and_identity_streams": lineage_b,
        "embedded_family_documents": save_units_b,
    }
    accounted = sum(rows.values())
    def pct(x: int) -> float:
        return round(100.0 * x / max(1, total), 2)
    out = {
        "total_inflated_bytes": total,
        "split_bytes": rows,
        "split_pct": {k: pct(v) for k, v in rows.items()},
        "product_corpora_detail": {"formats_latest_schema": schema_b,
                                   "forge_unit_schema_corpus": corpus.get("bytes", 0),
                                   "corpus_tables": corpus.get("tables")},
        "accounting_closes": (accounted == total),
        "accounting_delta": accounted - total,
        "note": ("element bytes are the FRAMED records of the host unit split by the landed "
                 "set; 'format_and_document_machinery' = the ADocument minus the two corpus "
                 "tables + ElemTable + ContentDocuments + unit-0 framing; the lineage / "
                 "identity streams are the own-save item; the product corpora are counsel C4"),
        "element_census": census,
    }
    if ledger:
        sl = ledger.get("stream_ledger") or {}
        tot = sl.get("totals") or {}
        tot_ex = sl.get("totals_excluding_schema") or {}
        latest = next((u for u in sl.get("units", []) if u.get("name") == "Global/Latest"), None)
        out["ledger"] = {
            "gate_G1": (ledger.get("gate_G1") or {}).get("verdict"),
            "identical_to_baseline_pct": tot.get("identical_pct"),
            "excluding_schema_identical_pct": tot_ex.get("identical_pct"),
            "ours_pct": tot.get("ours_pct"),
            "global_latest": ({"inflated": latest.get("inflated"), "class": latest.get("class"),
                               "identical_pct": latest.get("identical_pct"),
                               "best_baseline": latest.get("best_baseline")} if latest else None),
            "element_provenance": ledger.get("provenance_totals"),
            "resource_refs": ((ledger.get("resource_refs") or {}).get("total_refs")),
            "identity_ok": ((ledger.get("identity") or {}).get("ok")),
            "identity_violations": len((ledger.get("identity") or {}).get("violations") or []),
        }
    return out


def measure_file(name: str, rvt_path: str, *, landed: Optional[Set[int]] = None,
                 landed_sources: Sequence[str] = (), with_ledger: bool = True,
                 force_ledger: bool = False, viewer: Optional[str] = None) -> dict:
    """ONE scoreboard row for ``rvt_path``: element census + byte-weighted
    split + provenance ledger + viewer status."""
    rvt_path = _abs(rvt_path)
    t0 = time.time()
    if landed is None:
        landed, srcs = landed_set_for(name)
        landed_sources = srcs
    ledger = None
    if with_ledger:
        cache = os.path.join(OUT_DIR, f"{name}_provenance.json")
        try:
            ledger = run_ledger(rvt_path, cache_json=cache, force=force_ledger)
        except Exception as ex:                                     # pragma: no cover
            ledger = {"error": repr(ex)[:300]}
    split = byte_weighted_split(rvt_path, set(landed), ledger)
    row = {
        "name": name, "file": _relp(rvt_path), "md5": md5_of(rvt_path),
        "bytes_stored": os.path.getsize(rvt_path),
        "landed_sources": list(landed_sources),
        "viewer": viewer or viewer_status(rvt_path),
        "measure": split,
        "seconds": round(time.time() - t0, 1),
    }
    return row


def scoreboard(out_json: str = PROGRESS_JSON, out_md: str = PROGRESS_MD, *,
               with_ledger: bool = True, force_ledger: bool = False,
               extra: Sequence[Tuple[str, str]] = ()) -> dict:
    """THE HONEST MEASURE, RE-RUN: Y9, ZA_deep and every composed candidate.
    Writes ``docs/writer/genesis-progress.md`` (the campaign's scoreboard)
    + its JSON companion (``--recompute`` regenerates both)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    subjects: List[Tuple[str, str, Optional[str]]] = [
        ("Y9", Y9, None),
        ("ZA_deep", ZA_DEEP, None),
    ]
    ga = os.path.join(OUT_DIR, "G_A.rvt")
    if os.path.exists(ga):
        anchor_note = None
        aj = os.path.join(OUT_DIR, "anchor.json")
        if os.path.exists(aj):
            try:
                with open(aj) as fh:
                    a = json.load(fh)
                anchor_note = ("PASS -- byte-identical (md5) to the certified ZA_deep.rvt"
                               if a.get("BYTE_IDENTICAL") else "anchor FAILED")
            except Exception:
                pass
        subjects.append(("G_A", ga, anchor_note))
    gab = os.path.join(OUT_DIR, "G_AB_defs.rvt")
    if os.path.exists(gab):
        subjects.append(("G_AB_defs", gab, None))
    for n, p in extra:
        subjects.append((n, _abs(p), None))
    rows = []
    for name, path, viewer in subjects:
        if not os.path.exists(path):
            log(f"[scoreboard] {name}: {path} missing -- skipped")
            continue
        log(f"[scoreboard] measuring {name} ({_relp(path)}) ...")
        rows.append(measure_file(name, path, with_ledger=with_ledger,
                                 force_ledger=force_ledger, viewer=viewer))
    board = {"host_element_total": HOST_TOTAL, "subjects": rows,
             "generated_by": "tools/genesis_compose.py scoreboard --recompute",
             "with_ledger": with_ledger}
    _write_json(out_json, board)
    write_progress_md(board, out_md)
    log(f"[scoreboard] wrote {_relp(out_json)} + {_relp(out_md)}")
    return board


def _fmt_int(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def write_progress_md(board: dict, out_md: str = PROGRESS_MD) -> str:
    """Render ``docs/writer/genesis-progress.md`` from the scoreboard JSON."""
    rows = board.get("subjects") or []
    L: List[str] = []
    L.append("# GENESIS PROGRESS -- the campaign's scoreboard (the honest measure, re-run)")
    L.append("")
    L.append("Author: the genesis-assembly stream (`tools/genesis_compose.py`).  Regenerate: "
             "`.venv/bin/python tools/genesis_compose.py scoreboard --recompute` (the JSON "
             "companion is `experiments/genesis/subst_k4/compose/genesis-progress.json`).  Every "
             "number below is MEASURED by `rvt.provenance` (`--baseline all --streams`) plus the "
             "element census of this stream; nothing is inherited.  Definitions of the columns and "
             "of 'genesis achieved' live in `docs/writer/genesis-definition.md`.")
    L.append("")
    L.append("## 1. The element scoreboard")
    L.append("")
    L.append("| file | elements OURS / total | Autodesk-authored residue | residue buckets (named) "
             "| viewer status |")
    L.append("|---|--:|--:|---|---|")
    for r in rows:
        m = r["measure"]
        c = m["element_census"]
        buckets = ", ".join(f"{b} {v['elements']}" for b, v in list(c["residue_by_bucket"].items())[:5])
        v = r.get("viewer")
        vs = v if isinstance(v, str) else f"{v.get('status')}" + (
            f" ({str(v.get('certification'))[:60]})" if v.get("certification") else "")
        L.append(f"| **{r['name']}** `{r['file']}` | **{_fmt_int(c['ours_landed'])} / "
                 f"{_fmt_int(c['host_elements'])}** ({c['ours_pct']}%) | "
                 f"{_fmt_int(c['residue'])} ({c['residue_classes']} classes) | {buckets or '(none)'} "
                 f"| {vs} |")
    L.append("")
    L.append("'elements OURS' = LANDED slots: the element's seq-102 OBJECT record is one of OUR "
             "constructors' output at Autodesk's own registration (in-place substitution).  Residue = "
             "K4-inherited Autodesk-authored elements never landed; the named buckets are the "
             "substitution stream's own residue vocabulary (Yn), each with a recorded disposition "
             "(in-place / delete-with-content / add / product data / counsel).")
    L.append("")
    L.append("## 2. Byte-weighted provenance split (of the file's total inflated bytes)")
    L.append("")
    L.append("| file | total inflated | our constructed (element objects) | Autodesk element "
             "residue (+ landed envelopes) | product corpora (Formats/Latest + ESSchema corpus, "
             "counsel C4) | format & document machinery | lineage & identity streams |")
    L.append("|---|--:|--:|--:|--:|--:|--:|")
    for r in rows:
        m = r["measure"]
        sb, sp = m["split_bytes"], m["split_pct"]
        L.append(f"| **{r['name']}** | {_fmt_int(m['total_inflated_bytes'])} B | "
                 f"{_fmt_int(sb['our_constructed_element_objects'])} B "
                 f"({sp['our_constructed_element_objects']}%) | "
                 f"{_fmt_int(sb['autodesk_element_residue'])} B ({sp['autodesk_element_residue']}%) | "
                 f"{_fmt_int(sb['product_corpora_counsel_C4'])} B "
                 f"({sp['product_corpora_counsel_C4']}%) | "
                 f"{_fmt_int(sb['format_and_document_machinery'])} B "
                 f"({sp['format_and_document_machinery']}%) | "
                 f"{_fmt_int(sb['lineage_and_identity_streams'])} B "
                 f"({sp['lineage_and_identity_streams']}%) |")
    L.append("")
    L.append("Columns partition the inflated byte total (the accounting is asserted to close; the "
             "corpus detail is in the JSON): **our constructed** = the seq-102 object records of the "
             "landed slots; **Autodesk element residue** = every record of a never-landed element "
             "plus the seq-101/103 envelopes the in-place ladder keeps at landed slots; **product "
             "corpora** = Autodesk's `Formats/Latest` class model + the ESSchemaStorage / Forge "
             "unit-schema JSON corpus inside `Global/Latest` (byte-identical in every Revit file -- "
             "counsel item C4, not element authorship); **format & document machinery** = the "
             "ADocument minus those corpus tables + `Global/ElemTable` + `Global/ContentDocuments` "
             "+ unit-0 framing (the constructor-authored / own-save layer); **lineage & identity** "
             "= History / DocumentIncrementTable / BasicFileInfo / Contents / PartitionTable / "
             "TransmissionData / ProjectInformation (the own-save item).")
    L.append("")
    if board.get("with_ledger"):
        L.append("## 3. Provenance ledger v2 (rvt.provenance --baseline all --streams --strings "
                 "--identity)")
        L.append("")
        L.append("| file | ledger gate | bytes identical-to-baseline (excl. schema) | "
                 "Global/Latest identical | element provenance (baseline-relative) | resource "
                 "refs | identity ok |")
        L.append("|---|---|--:|--:|---|--:|---|")
        for r in rows:
            g = (r["measure"].get("ledger") or {})
            if not g:
                L.append(f"| **{r['name']}** | (ledger not run) | | | | | |")
                continue
            gl = g.get("global_latest") or {}
            ep = g.get("element_provenance") or {}
            eps = ", ".join(f"{k} {v}" for k, v in ep.items())
            L.append(f"| **{r['name']}** | {str(g.get('gate_G1') or '')[:70]} | "
                     f"{g.get('identical_to_baseline_pct')}% (excl. schema "
                     f"{g.get('excluding_schema_identical_pct')}%) | "
                     f"{gl.get('identical_pct')}% ({gl.get('best_baseline')}) | {eps} | "
                     f"{g.get('resource_refs')} | {g.get('identity_ok')} "
                     f"({g.get('identity_violations')} violations) |")
        L.append("")
        L.append("The ledger's element classifier is BASELINE-RELATIVE (it reads an in-place slot as "
                 "'ours-modified' only when its record bytes differ from every sample; a landed slot "
                 "whose constructor reproduced Autodesk's own object bytes reads 'autodesk-sample').  "
                 "For this programme the LANDED accounting of table 1 is the authority; the ledger is "
                 "the cross-check that the bytes really moved.  The container-layer columns "
                 "(Global/Latest identical %, resource refs, identity) are the OWN-SAVE + counsel "
                 "items and are UNCHANGED by any element rung by design (the in-place ladder keeps "
                 "every global stream byte-identical).")
        L.append("")
    L.append("## 4. Reproduction")
    L.append("")
    L.append("```")
    L.append(".venv/bin/python tools/genesis_compose.py scoreboard --recompute   # this document")
    L.append(".venv/bin/python tools/genesis_compose.py anchor                   # the correctness anchor")
    L.append(".venv/bin/python tools/genesis_compose.py candidates               # G_A + G_AB_defs")
    L.append(".venv/bin/python tools/genesis_compose.py check FILE.rvt            # the genesis definition check")
    L.append("```")
    L.append("")
    text = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as fh:
        fh.write(text)
    return text


# ===========================================================================
# 15. THE GENESIS DEFINITION, MECHANICAL (docs/writer/genesis-definition.md)
# ===========================================================================

def genesis_check(rvt_path: str, *, landed: Optional[Set[int]] = None,
                  reproduced_ok: Sequence[str] = (), with_ledger: bool = False) -> dict:
    """Verify a file against the per-stream accounting the ZERO-Autodesk-
    authored-elements definition demands (docs/writer/genesis-definition.md).
    Returns a clause table {clause: {ok, evidence}} + the overall verdict.

    ``landed`` = the ids whose objects are our constructors' output (the
    manifest / ladder accounting); ``reproduced_ok`` = the class names the
    definition accepts as REPRODUCED FORMAT MACHINERY (byte-identical to the
    sample's own object, no free value -- e.g. NumberingSchema, SunAnnotation
    Elem, SlaveSymbolTrackerElem, ParamBinding).  An element counts as
    accounted-for iff it is landed, reproduced machinery, or an add-path
    record (ids above the sample watermark)."""
    rvt_path = _abs(rvt_path)
    doc = Document.from_file(rvt_path)
    host = sorted(doc.et_by_id)
    landed = set(int(x) for x in (landed or set()))
    machinery = set(reproduced_ok)
    residue = []
    for e in host:
        if int(e) in landed:
            continue
        cls_name = doc.class_of(e) or "?"
        if cls_name in machinery:
            continue
        residue.append((int(e), cls_name))
    res_by_class = dict(collections.Counter(c for _e, c in residue).most_common())
    clauses: Dict[str, dict] = {}
    val = _run_validator(rvt_path)
    clauses["V0_validator_zero_errors"] = {
        "ok": bool(val.get("ok") and val.get("errors") == 0),
        "evidence": {"errors": val.get("errors"), "warnings": val.get("warnings")},
        "rule": "tools/rvt_validate.py reports VALID with 0 errors"}
    four = _four_registry(rvt_path)
    clauses["V1_four_registry_coherent"] = {
        "ok": bool(four.get("coherent")),
        "evidence": {k: four.get(k) for k in ("save_units", "contentdocs_entries",
                                               "contenttable_records", "coherent")},
        "rule": ("save_units - 1 == ContentDocuments entries == ContentTable records == "
                 "FamilyMgr entries, and the four GUID sets are equal")}
    clauses["E1_zero_autodesk_authored_elements"] = {
        "ok": not residue,
        "evidence": {"host_elements": len(host), "landed_ours": len(landed & set(host)),
                     "reproduced_machinery_classes": sorted(machinery),
                     "residue_elements": len(residue), "residue_by_class": res_by_class},
        "rule": ("EVERY host element is (a) LANDED (its seq-102 object = OUR constructor's "
                 "output at Autodesk's registration), (b) REPRODUCED FORMAT MACHINERY (a class "
                 "with no free value, byte-identical to what any Revit writes: listed by name), "
                 "or (c) OUR add-path record -- residue count MUST be 0")}
    # ADocument decodes clean (the machinery frame is well-formed)
    try:
        from rvt import adocument as adoc
        from rvt.container import open_rvt
        with open_rvt(rvt_path) as f:
            a = adoc.decode_latest(f.inflate("Global/Latest", 0))
        clauses["D1_adocument_clean"] = {"ok": bool(a.clean),
                                         "evidence": {"clean": bool(a.clean),
                                                      "errors": (a.errors or [])[:3]},
                                         "rule": "Global/Latest decodes as a clean ADocument"}
    except Exception as ex:                                        # pragma: no cover
        clauses["D1_adocument_clean"] = {"ok": False, "evidence": {"error": repr(ex)[:200]},
                                         "rule": "Global/Latest decodes as a clean ADocument"}
    if with_ledger:
        led = run_ledger(rvt_path, cache_json=None)
        sl = led.get("stream_ledger") or {}
        ident = led.get("identity") or {}
        rr = led.get("resource_refs") or {}
        expr_ident = sl.get("expression_streams_identical_bytes") or {}
        clauses["S1_no_expression_stream_bytes_identical_to_a_sample"] = {
            "ok": not expr_ident,
            "evidence": {"expression_streams_identical_bytes": expr_ident},
            "rule": ("Global/Latest / Global/ContentDocuments / embedded save units carry ZERO "
                     "bytes byte-identical to any Autodesk sample (the sample's expression is out) "
                     "-- the two product corpora inside Latest are the counsel-C4 exception, "
                     "disclosed separately")}
        clauses["I1_identity_ours"] = {
            "ok": bool(ident.get("ok")),
            "evidence": {"violations": ident.get("violations")},
            "rule": ("BasicFileInfo + DocumentIncrementTable + History carry OUR identity: our "
                     "author / client / GUIDs / usernames / save path; no Autodesk-employee "
                     "usernames; no template GUIDs (the own-save step)")}
        clauses["R1_resource_refs_disclosed"] = {
            "ok": True,  # a disclosure, gated by counsel not by count
            "evidence": {"total_refs_outside_schema": rr.get("total_refs"),
                         "by_pattern": rr.get("by_pattern")},
            "rule": ("every Autodesk resource identifier in our bytes (Forge typeIds, %1!s! "
                     "tokens, ADSK) is COUNTED and listed for counsel (interface tokens); "
                     "target: only the tokens the UnitsElem registry needs")}
    overall = all(v.get("ok") for v in clauses.values())
    return {"file": _relp(rvt_path), "clauses": clauses, "genesis_zero": overall,
            "verdict": ("GENESIS-ZERO ACHIEVED (mechanically verified)" if overall
                        else "NOT GENESIS-ZERO (see failing clauses)")}


# ===========================================================================
# 16. THE ASSEMBLY RECORD (docs/inbox/genesis-assembly.md is written by hand)
# ===========================================================================
# (the record document is authored, not generated; the JSON artefacts this
#  module writes -- anchor.json, candidates.json, *.manifest.json, probes.json,
#  genesis-progress.json -- are its evidence)


# ===========================================================================
# 17. CLI
# ===========================================================================

def _cli_compose(args) -> int:
    specs: List[RungSpec] = []
    for r in args.rung or []:
        # name=FILE.rvt[@PARENT.rvt]
        if "=" in r:
            name, spec = r.split("=", 1)
        else:
            name, spec = os.path.splitext(os.path.basename(r))[0], r
        parent = args.parent or Y9
        if "@" in spec:
            spec, parent = spec.split("@", 1)
        specs.append(RungSpec.from_rung_file(_abs(spec), _abs(parent), name=name))
    dels: List[DeletionSpec] = []
    for d in args.delete or []:
        dels.append(DeletionSpec.from_json(d))
    rep = compose(args.base, specs, args.out, deletions=dels,
                  on_overlap=args.on_overlap, purge_registries=args.purge_registries,
                  allow_uncertified_base=args.allow_uncertified)
    print(json.dumps({"verdict": rep.verdict, "problems": rep.problems,
                      "manifest": rep.manifest_file, "out": rep.out}, indent=1))
    return 0 if rep.verdict == "COMPOSED-VALID" else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("anchor", help="prove compose(Y9, Group-A rungs) == certified ZA_deep (md5)")
    sub.add_parser("candidates", help="build G_A + G_AB_defs + probes.json (the gate batch)")
    pc = sub.add_parser("compose", help="compose rung sets (+ deletions) onto a certified base")
    pc.add_argument("--base", required=True, help="the certified base .rvt")
    pc.add_argument("--rung", action="append", default=[],
                    help="name=RUNG.rvt[@PARENT.rvt] (repeatable); the delta vs its parent")
    pc.add_argument("--parent", default=None, help="default parent for --rung (default: Y9)")
    pc.add_argument("--delete", action="append", default=[],
                    help="deletion set JSON {name, ids, policy: maxgc|closure|exact} (repeatable)")
    pc.add_argument("--out", required=True, help="output .rvt")
    pc.add_argument("--on-overlap", default="refuse", choices=["refuse", "delete-wins"])
    pc.add_argument("--purge-registries", action="store_true",
                    help="also reconcile the ADocument registries (sanctioned "
                         "registry-reconciliation) after deletion")
    pc.add_argument("--allow-uncertified", action="store_true",
                    help="build on a base NOT viewer-certified (never for a real candidate)")
    pe = sub.add_parser("endgame", help="run the G_endgame template from a JSON inputs file")
    pe.add_argument("--spec", required=True, help="endgame_inputs.json")
    ps = sub.add_parser("scoreboard", help="write docs/writer/genesis-progress.md (the measure)")
    ps.add_argument("--recompute", action="store_true", help="re-run the provenance ledgers")
    ps.add_argument("--fast", action="store_true",
                    help="skip the provenance ledgers (element census + byte split only)")
    pk = sub.add_parser("check", help="the mechanical genesis-zero definition check of a file")
    pk.add_argument("file")
    pk.add_argument("--landed-from", default=None,
                    help="a compose manifest or rung report supplying the landed slots")
    pk.add_argument("--ledger", action="store_true", help="also run the identity/ledger clauses")
    args = ap.parse_args(argv)
    if args.cmd == "anchor":
        a = prove_anchor()
        return 0 if a["BYTE_IDENTICAL"] else 2
    if args.cmd == "candidates":
        r = build_candidates()
        return 0 if r["G_A"]["anchor"]["BYTE_IDENTICAL"] and \
            r["G_AB_defs"]["verdict"] == "COMPOSED-VALID" else 2
    if args.cmd == "compose":
        return _cli_compose(args)
    if args.cmd == "endgame":
        rep = endgame_from_spec(args.spec)
        print(json.dumps({"verdict": rep.verdict, "problems": rep.problems,
                          "manifest": rep.manifest_file}, indent=1))
        return 0 if rep.verdict == "COMPOSED-VALID" else 2
    if args.cmd == "scoreboard":
        scoreboard(with_ledger=not args.fast, force_ledger=args.recompute)
        return 0
    if args.cmd == "check":
        landed: Set[int] = set()
        if args.landed_from:
            with open(_abs(args.landed_from)) as fh:
                j = json.load(fh)
            for row in (j.get("landed_slots") or []):
                landed.add(int(row["slot"]))
            for r in ((j.get("phase_1_inplace") or {}).get("merge") or {}).get("rungs") or []:
                pass  # (manifest carries counts, not ids; use the rung reports for ids)
        rep = genesis_check(args.file, landed=landed, with_ledger=args.ledger)
        print(json.dumps(rep, indent=1, default=str))
        return 0 if rep["genesis_zero"] else 3
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
