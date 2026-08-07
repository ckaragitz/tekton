#!/usr/bin/env python
"""genesis_compose_2025.py -- THE 2025 COMPOSER: tools/genesis_compose.py
run under the Revit-2025 emit context, against the CERTIFIED 2025 family-free
base B2025_K4 (docs/inbox/genesis-audit.md VERDICTS #28).

WHY A WRAPPER (and not an edit).  ``tools/genesis_compose.py`` is the proven
composer (anchor: compose(Y9, Group-A rungs) == certified ZA_deep,
md5-identical).  Its mechanics are release-agnostic BY NAME, but the process
defaults are 2026-baked in exactly the places the 2025 campaign has already
mapped (docs/inbox/genesis-2025-reduce.md section 4, genesis-2025-port.md
section 4): the partition-framing ordinals kept as module-local copies on the
emit path, the ADocument/record codec singletons, and the lazy report
decoders in rvt.regadd / rvt.regdiff.  This wrapper enters
``tools/genesis_2025.py::context_2025`` (the seven framing patches +
versions.reading + the ADocument decoder) PLUS the codec swaps the Y2025
ladder runner proved out (run_ladder2025.py), then DELEGATES every operation
to genesis_compose unchanged.  Nothing leaks: all swaps restore on exit.

THE CORRECTNESS ANCHOR (:func:`prove_anchor_2025`), the 2026 proof re-run on
2025: the NINE cumulative Y2025 rung deltas (Y1 vs B2025_K4, Y2 vs Y1, ...,
Y9 vs Y8 -- pairwise DISJOINT, seq-102 only), merged and replayed onto
B2025_K4 in ONE ``regadd.substitute_elements`` call, must reproduce the
ladder's deepest cumulative rung ``Y9.rvt`` BYTE-IDENTICALLY (md5).

THE CANDIDATE (:func:`compose_g`): G_ABPD_2025 = B2025_K4 + all Y2025 rungs
+ every landed 2025 residue rung + the lawful 2025 deletion set ->
``experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt`` (the EXACT
relpath the front-door registry's 2025 slot reserves --
src/rvt/frontdoor/assets/genesis_base.json releases.2025).  Residue rungs
and deletion sets are DISCOVERED from the sibling streams' output trees
(each rung must carry its .json report naming its parent; each deletion set
is a JSON spec with ids+policy).  Until BOTH exist the composition is the
DEEPEST AVAILABLE PREFIX, honestly named ``G_partial_2025.rvt`` -- the
registry path is never occupied by a partial file.  When the siblings land,
ONE command completes the campaign step:

    .venv/bin/python tools/genesis_compose_2025.py all

(it re-discovers, composes the full G_ABPD_2025, and re-stages the batch.)

THE BATCH (:func:`stage`): probes.json + tools/probe_batch.py stage --
control = a byte-identical copy of the CERTIFIED base
experiments/genesis2025/reduce/B2025_K4.rvt, candidate-base = the composed G
file.  Nothing is uploaded here; the orchestrator uploads.

THE FINISH LINE (:func:`finishline`): the dry run of
tests/test_target2025.py::test_END_STATE_author_2025_produces_a_2025_file --
the G25-5 flip applied IN MEMORY ONLY (KNOWN_RELEASES[2025].creation_
certified + the genesis_base.json 2025 slot pin), then the real front door
``author --prompt ... --target-version 2025`` against the composed base.
NOTHING on disk is flipped; the result (pass or the exact failure) is
reported for the record.

Usage (repo root):
  .venv/bin/python tools/genesis_compose_2025.py anchor      # the md5 proof
  .venv/bin/python tools/genesis_compose_2025.py compose     # G file (partial or full)
  .venv/bin/python tools/genesis_compose_2025.py stage       # probes.json + batch
  .venv/bin/python tools/genesis_compose_2025.py finishline [--full]
  .venv/bin/python tools/genesis_compose_2025.py all [--full]

Territory: this file, tests/test_compose_2025.py,
experiments/genesis/subst_k4_2025/compose/**, docs/inbox/compose-2025.md.
Everything else (genesis_compose, genesis_2025, port2025, probe_batch,
regadd, versions, frontdoor) is IMPORTED, never edited.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import functools
import glob
import hashlib
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import genesis_compose as GC                                        # noqa: E402
import genesis_2025 as G25                                          # noqa: E402

# ---------------------------------------------------------------------------
# paths (the 2025 campaign's geography)
# ---------------------------------------------------------------------------
#: the CERTIFIED 2025 family-free base (docs/coverage/viewer-certified.json
#: entry 'experiments/genesis2025/reduce/B2025_K4.rvt'; VERDICTS #28)
BASE_2025 = os.path.join(ROOT, "experiments", "genesis2025", "reduce", "B2025_K4.rvt")
#: the CANONICAL Y2025 ladder dir (the y2025-settings stream and its
#: successors emit cumulative Y<n>_2025 rungs here, on the certified base)
LADDER_2025 = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025")
#: the FIRST Y2025 ladder (genesis-2025-port stream, cumulative Y1..Y9 on a
#: byte-identical pre-certification copy of the base) -- the fallback chain
SUBST_2025 = os.path.join(ROOT, "experiments", "genesis2025", "subst")
#: this stream's experiment dir == the registry slot's parent directory
OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025", "compose")
#: the EXACT relpath genesis_base.json releases.2025 reserves
G_FINAL = os.path.join(OUT_DIR, "G_ABPD_2025.rvt")
G_PARTIAL = os.path.join(OUT_DIR, "G_partial_2025.rvt")
ANCHOR_OUT = os.path.join(OUT_DIR, "G_Y2025_anchor.rvt")
ANCHOR_JSON = os.path.join(OUT_DIR, "anchor_2025.json")

#: where sibling streams' 2025 deletion sets are discovered (residue rungs
#: are discovered by walking the declared parent chain, not by glob)
DELETION_GLOBS = [
    os.path.join(ROOT, "experiments", "genesis2025", "**", "D_*.json"),
    os.path.join(ROOT, "experiments", "genesis2025", "**", "*deletion*.json"),
    os.path.join(ROOT, "experiments", "genesis2025", "**", "*.spec.json"),
    os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025", "**", "D_*.json"),
    os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025", "**", "*deletion*.json"),
    os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025", "**", "*.spec.json"),
]

log = GC.log
_relp = GC._relp
md5_of = GC.md5_of
sha256_of = GC.sha256_of


# ---------------------------------------------------------------------------
# the 2025 compose context
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def context_compose_2025(base: str = BASE_2025):
    """genesis_2025.context_2025 (versions.reading + the SEVEN module-local
    framing-tag patches + rvt.adocument._DECODER) PLUS the per-release codec
    swaps the Y2025 ladder proved out: rvt.encode._DEFAULT_ENCODER, the lazy
    ObjectDecoder factories in rvt.regadd / rvt.regdiff, and
    genesis_compose's own report decoder.  Restores everything on exit."""
    from rvt import encode as ENC
    from rvt import regadd, regdiff
    from rvt.genesis import port2025 as P25
    from rvt.objects import ObjectDecoder

    dec25, enc25, schema25 = P25._S25()
    with G25.context_2025(base) as ords:
        saved: List[Tuple[Any, str, Any]] = []

        def swap(mod, name, value):
            saved.append((mod, name, getattr(mod, name)))
            setattr(mod, name, value)

        swap(ENC, "_DEFAULT_ENCODER", enc25)
        swap(regadd, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(regdiff, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(GC, "_DEC", dec25)
        try:
            yield ords
        finally:
            for mod, name, val in reversed(saved):
                setattr(mod, name, val)


# ---------------------------------------------------------------------------
# rung + deletion discovery
# ---------------------------------------------------------------------------
def discover_y_chain(base: str = BASE_2025) -> List[str]:
    """The CANONICAL cumulative Y2025 chain, ordered base -> deepest, by the
    rungs' OWN parent declarations (each report's ``parent``/``base.file``).

    Candidates: ``Y<n>_2025.rvt`` in the canonical ladder dir (single-change
    probes ``Y<n>s_2025`` excluded -- their content is contained in the
    cumulative chain).  Fallback when the canonical dir carries no chain yet:
    the port stream's ``Y1..Y9`` in experiments/genesis2025/subst.  The walk
    follows parent links from the base, so deeper rungs (Y8_2025 / Y9_2025,
    another stream's next step) join the chain the moment they land."""
    def chain_from(directory: str, pattern: str) -> List[str]:
        # nodes are keyed by MD5, not path: a rung may declare its parent via
        # any byte-identical copy of it (the port ladder named the staged
        # pre-certification copy of the base, not the certified reduce/ path)
        cands: List[str] = []
        for f in sorted(glob.glob(os.path.join(directory, "*.rvt"))):
            stem = os.path.splitext(os.path.basename(f))[0]
            if re.fullmatch(pattern, stem):
                cands.append(f)
        by_parent: Dict[str, List[str]] = {}
        for f in cands:
            p = _report_parent(f)
            if p is not None:
                by_parent.setdefault(md5_of(p), []).append(f)
        chain: List[str] = []
        cur = md5_of(base)
        seen = set()
        while cur in by_parent and cur not in seen:
            seen.add(cur)
            kids = sorted(by_parent[cur])
            if len(kids) > 1:
                raise SystemExit(
                    f"the cumulative chain forks after {chain[-1] if chain else _relp(base)}: "
                    f"{[_relp(k) for k in kids]} -- two rungs declare the same "
                    "parent; the ladder must be linear")
            chain.append(kids[0])
            cur = md5_of(kids[0])
        return chain
    chain = chain_from(LADDER_2025, r"Y\d+_2025")
    if chain:
        return chain
    return chain_from(SUBST_2025, r"Y\d")


def y2025_specs(base: str = BASE_2025,
                chain: Optional[List[str]] = None) -> List[GC.RungSpec]:
    """The cumulative Y2025 rung deltas, each vs its own parent (Y1 vs the
    base, Yn vs Yn-1) -- must be called INSIDE the context."""
    chain = chain if chain is not None else discover_y_chain(base)
    if not chain:
        raise SystemExit("no Y2025 ladder found (neither the canonical "
                         f"{_relp(LADDER_2025)} chain nor the fallback "
                         f"{_relp(SUBST_2025)})")
    specs: List[GC.RungSpec] = []
    parent = base
    for f in chain:
        stem = os.path.splitext(os.path.basename(f))[0]
        specs.append(GC.RungSpec.from_rung_file(f, parent, name=f"Y2025:{stem}",
                                                group="Y"))
        parent = f
    return specs


def _report_parent(rvt_path: str) -> Optional[str]:
    """The parent file a sibling rung's .json report declares."""
    rep = os.path.splitext(rvt_path)[0] + ".json"
    if not os.path.exists(rep):
        return None
    try:
        with open(rep) as fh:
            j = json.load(fh)
    except Exception:
        return None
    for k in ("parent", "derived_from"):
        v = j.get(k)
        if isinstance(v, str) and v:
            p = v if os.path.isabs(v) else os.path.join(ROOT, v)
            if os.path.exists(p):
                return p
    b = j.get("base")
    if isinstance(b, dict) and b.get("file"):
        p = os.path.join(ROOT, str(b["file"]))
        if os.path.exists(p):
            return p
    return None


def discover_residue_specs(y_chain: List[str]) -> Tuple[List[GC.RungSpec], Optional[str]]:
    """Sibling 2025 residue rungs, discovered by WALKING THE DECLARED PARENT
    CHAIN from the deepest Y rung -- must be called INSIDE the context.

    The residue stream emits cumulative in-place files (some twice: an
    ``R*`` name and a byte-identical ``Z_*`` compose-consumable alias) plus
    single-change LEAF probes; a deletion layer arrives as a file whose step
    is NOT in-place.  The walk: nodes are keyed by md5 (aliases collapse);
    from the deepest Y rung, follow children (files whose reports declare
    the current node as parent); at a fork prefer the TRUNK (the child whose
    descendant chain is deepest -- single-change probes are leaves); STOP at
    the first non-in-place step (that is the deletion layer, composable only
    via its D_*.json spec).  Each consumed step becomes one RungSpec (the
    delta vs its parent file).

    Returns ``(specs, deletion_proof_file)`` -- the latter is the non-in-place
    child the walk stopped at (the sibling's deletion-applied PROOF file, e.g.
    RC_2025.rvt), if any: the FINAL composition must reproduce it."""
    if not y_chain:
        return [], None
    # ---- candidate files (both campaign trees), keyed by md5 ---------------
    cands: List[str] = []
    for d in (LADDER_2025, SUBST_2025):
        for f in sorted(glob.glob(os.path.join(d, "*.rvt"))):
            stem = os.path.splitext(os.path.basename(f))[0]
            if stem.startswith("CTRL") or re.fullmatch(r"Y\d+s?(_2025)?", stem) \
                    or stem == "Y_cat":
                continue
            cands.append(f)
    y_md5 = {md5_of(p) for p in y_chain} | {md5_of(BASE_2025)}
    by_md5: Dict[str, List[str]] = {}
    parent_md5: Dict[str, str] = {}
    for f in cands:
        m = md5_of(f)
        if m in y_md5:
            continue                                   # an alias of a Y rung / base
        by_md5.setdefault(m, []).append(f)
        p = _report_parent(f)
        if p is not None:
            parent_md5[m] = md5_of(p)
    children: Dict[str, List[str]] = {}
    for m, pm in parent_md5.items():
        children.setdefault(pm, []).append(m)

    def depth(m: str, seen: frozenset) -> int:
        if m in seen:
            return 0
        return 1 + max((depth(k, seen | {m}) for k in children.get(m, [])), default=0)

    def pick_file(m: str) -> str:
        files = sorted(by_md5[m])
        for f in files:                                 # prefer the Z_* alias name
            if os.path.basename(f).startswith("Z_"):
                return f
        return files[0]

    specs: List[GC.RungSpec] = []
    deletion_proof: Optional[str] = None
    cur_file = y_chain[-1]
    cur = md5_of(cur_file)
    seen: set = set()
    while cur in children and cur not in seen:
        seen.add(cur)
        kids = children[cur]
        if len(kids) > 1:
            ranked = sorted(kids, key=lambda k: (-depth(k, frozenset()), pick_file(k)))
            if depth(ranked[0], frozenset()) == depth(ranked[1], frozenset()):
                log(f"   [discover] residue chain FORKS after {_relp(cur_file)} with "
                    f"equal-depth branches {[ _relp(pick_file(k)) for k in ranked[:2] ]} "
                    f"-- stopping the walk here (linearity unresolvable)")
                break
            kids = [ranked[0]]
        nxt = pick_file(kids[0])
        stem = os.path.splitext(os.path.basename(nxt))[0]
        try:
            specs.append(GC.RungSpec.from_rung_file(nxt, cur_file,
                                                    name=f"R2025:{stem}",
                                                    group="residue"))
        except GC.CompositionError as ex:
            deletion_proof = nxt
            log(f"   [discover] {_relp(nxt)} is NOT an in-place step of "
                f"{_relp(cur_file)} ({str(ex)[:120]}) -- the walk stops here "
                f"(the deletion layer composes via its spec; this file is the "
                f"sibling's deletion PROOF the final composition must equal)")
            break
        cur_file = nxt
        cur = kids[0]
    return specs, deletion_proof


def discover_deletion_specs() -> List[GC.DeletionSpec]:
    """Sibling 2025 deletion sets (JSON with ids + a lawful policy).  A spec
    whose id set is a strict subset of another discovered spec's is DROPPED
    (the residue stream publishes constituent singles beside their union --
    e.g. D_2025_* beside RC_2025_full_straggler_set -- exactly the 2026
    D_curtain/D_links-vs-D_all shape); composing the union once is the same
    deletion without double bookkeeping."""
    cands: List[GC.DeletionSpec] = []
    seen = set()
    for pat in DELETION_GLOBS:
        for f in sorted(glob.glob(pat, recursive=True)):
            if os.path.basename(f) in seen:
                continue
            try:
                with open(f) as fh:
                    j = json.load(fh)
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            ids = j.get("ids") or j.get("delete") or j.get("seed") or j.get("delete_ids")
            if not ids or not isinstance(ids, (list, dict)):
                continue
            if str(j.get("purpose") or "genesis-base") not in ("genesis-base",):
                continue                        # research probes never compose
            seen.add(os.path.basename(f))
            cands.append(GC.DeletionSpec.from_json(f))
    out: List[GC.DeletionSpec] = []
    for i, sp in enumerate(cands):
        s = set(sp.ids)
        if any(j != i and s < set(o.ids) for j, o in enumerate(cands)):
            log(f"   [discover] deletion set {sp.name} is a strict subset of a "
                f"discovered union set -- composing the union only")
            continue
        if any(j < i and s == set(cands[j].ids) for j in range(i)):
            continue                            # exact duplicate
        out.append(sp)
    return out


def linearize_chain_specs(specs: List[GC.RungSpec]) -> List[GC.RungSpec]:
    """Resolve CUMULATIVE-CHAIN overlaps so the composer's laws hold when the
    whole chain is replayed onto the chain's ROOT in one pass.

    A deeper cumulative rung may RE-substitute a slot an earlier rung landed
    (the residue chain's RC_2025_inplace re-emits view/navigator slots the Y
    layer owns, with cleaned headers).  Composed onto the root, the honest
    semantics is LAST-WINS: the deepest rung's bytes are the chain's final
    state.  For every such slot this helper (a) verifies CHAIN CONTINUITY --
    the deeper delta's 'before' bytes equal the earlier owner's bytes, so
    the two really are steps of one chain; (b) drops the slot from the
    earlier spec (recorded in its notes); (c) rewrites the deeper spec's
    parent_records at the slot to the FIRST owner's parent bytes (= the
    root's state), so the composer's parent-coherence law checks the right
    thing.  The end-to-end proof stays the anchor: the composed file must
    equal the chain's deepest in-place file BYTE-IDENTICALLY."""
    final: Dict[int, Dict[int, bytes]] = {}       # slot -> seq -> LAST written bytes
    firstp: Dict[int, Dict[int, bytes]] = {}      # slot -> seq -> ROOT-state bytes
    last_owner: Dict[int, int] = {}               # slot -> deepest touching spec
    touched_by: Dict[int, set] = {}
    for i, sp in enumerate(specs):
        for slot, by_seq in sp.records.items():
            slot = int(slot)
            cur = final.setdefault(slot, {})
            for seq, b in by_seq.items():
                seq = int(seq)
                pb = (sp.parent_records.get(slot) or {}).get(seq)
                if seq in cur:
                    # continuity: this delta's 'before' must be the last
                    # writer's bytes, or these are not steps of one chain
                    if pb is not None and bytes(pb) != cur[seq]:
                        raise GC.CompositionError(
                            f"chain continuity broken at slot {slot} seq {seq}: "
                            f"{sp.name}'s parent bytes are not the previous chain "
                            f"rung's emitted bytes")
                elif pb is not None:
                    firstp.setdefault(slot, {})[seq] = bytes(pb)
                cur[seq] = bytes(b)
            last_owner[slot] = i
            touched_by.setdefault(slot, set()).add(i)
    multi = {s for s, who in touched_by.items() if len(who) > 1}
    out: List[GC.RungSpec] = []
    for i, sp in enumerate(specs):
        mine = {int(s) for s in sp.records}
        if not (mine & multi):
            out.append(sp)
            continue
        own = sorted(s for s in mine if last_owner[s] == i)
        dropped = sorted(mine - set(own))
        merged_in: List[int] = []
        records: Dict[int, Dict[int, bytes]] = {}
        parent_records: Dict[int, Dict[int, bytes]] = {}
        for s in own:
            # the slot's FINAL per-seq bytes (may merge seqs written by
            # earlier rungs: e.g. the Y layer's seq-102 object + this rung's
            # cleaned seq-101 attributes), against the ROOT's parent bytes
            records[s] = dict(final[s])
            if set(final[s]) - set(sp.records.get(s) or {}):
                merged_in.append(s)
            pr = {seq: firstp.get(s, {}).get(seq) for seq in final[s]}
            pr = {seq: b for seq, b in pr.items() if b is not None}
            if pr:
                parent_records[s] = pr
        r = dataclasses.replace(
            sp, records=records, parent_records=parent_records,
            landed_slots=sorted(own), notes=list(sp.notes))
        if dropped:
            r.notes.append(
                f"{len(dropped)} slot(s) SUPERSEDED by a deeper cumulative rung "
                f"(last-wins; chain continuity asserted): {dropped[:10]}")
        if merged_in:
            r.notes.append(
                f"{len(merged_in)} slot(s) carry per-seq records MERGED from "
                f"earlier chain rungs (this rung re-emitted only some seqs of "
                f"the slot; the final state is the union, parent-coherence "
                f"baseline = the chain ROOT): {merged_in[:10]}")
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# 1. THE ANCHOR: compose(B2025_K4, Y1..Y9 deltas) == Y9 byte-identical
# ---------------------------------------------------------------------------
def prove_anchor_2025(*, verify: bool = True) -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    with context_compose_2025(BASE_2025):
        specs = linearize_chain_specs(y2025_specs())
        rep = GC.compose(BASE_2025, specs, ANCHOR_OUT,
                         label="G_Y2025_anchor (the 2025 composer anchor)",
                         verify=verify)
    target = discover_y_chain()[-1]                  # the deepest cumulative rung
    got, want = md5_of(ANCHOR_OUT), md5_of(target)
    identical = (got == want)
    anchor = {
        "claim": (f"compose(B2025_K4, [the {len(specs)} cumulative Y2025 rung "
                  f"deltas]) reproduces the ladder's deepest cumulative rung "
                  f"{os.path.basename(target)} BYTE-IDENTICALLY under the 2025 "
                  "emit context"),
        "base": _relp(BASE_2025), "base_md5": md5_of(BASE_2025),
        "base_certification": (GC.certification_of(BASE_2025) or {}).get("proves"),
        "target": _relp(target),
        "rung_sets": [s.summary() for s in specs],
        "merged_slots": (rep.phase_1_inplace.get("merge") or {}).get("merged_slots"),
        "reproduction": _relp(ANCHOR_OUT),
        "md5_reproduction": got, "md5_target": want,
        "BYTE_IDENTICAL": identical,
        "meaning": ("the composer's Phase I is EXACT on Revit 2025: the "
                    "independently-emitted in-place rungs, merged into one "
                    "substitute_elements call under context_compose_2025, land in "
                    "precisely the file the Y2025 ladder emitted -- the 2026 "
                    "anchor proof (compose(Y9, Group A) == ZA_deep) transfers"),
        "compose_verdict": rep.verdict, "compose_problems": rep.problems,
        "seconds": round(time.time() - t0, 1),
    }
    GC._write_json(ANCHOR_JSON, anchor)
    log(f"\n[anchor-2025] reproduction md5 {got}\n[anchor-2025] target       md5 {want}\n"
        f"[anchor-2025] BYTE-IDENTICAL: {identical}  ({anchor['seconds']}s)")
    if not identical:
        log("[anchor-2025] *** THE ANCHOR DOES NOT HOLD ***")
    return anchor


# ---------------------------------------------------------------------------
# 2. THE CANDIDATE: G_ABPD_2025 (full) or G_partial_2025 (deepest prefix)
# ---------------------------------------------------------------------------
def compose_g(*, verify: bool = True, on_overlap: str = "delete-wins") -> dict:
    """Compose the deepest available 2025 candidate.  FULL (all three layers
    present: Y rungs + residue rungs + a deletion set) -> G_ABPD_2025.rvt at
    the registry relpath.  Anything less -> G_partial_2025.rvt + the
    completion instructions.  ``delete-wins`` mirrors the certified 2026
    G_ABPD call (19 substitute/delete overlaps resolved delete-wins there)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    with context_compose_2025(BASE_2025):
        chain = discover_y_chain()
        y = y2025_specs(chain=chain)
        residue, deletion_proof = discover_residue_specs(chain)
        deletions = discover_deletion_specs()
        complete = bool(residue) and bool(deletions)
        out = G_FINAL if complete else G_PARTIAL
        label = ("G_ABPD_2025 (B2025_K4 + Y2025 + residue + lawful deletions)"
                 if complete else
                 "G_partial_2025 (DEEPEST AVAILABLE 2025 prefix: B2025_K4 + Y2025"
                 + (" + residue" if residue else "")
                 + (" + deletions" if deletions else "") + ")")
        log(f"[compose-2025] layers: Y rungs {len(y)}; residue rungs "
            f"{len(residue)}; deletion sets {len(deletions)} -> "
            f"{'FULL G_ABPD_2025' if complete else 'PARTIAL (deepest prefix)'}")
        specs = linearize_chain_specs(y + residue)
        deepest_chain_file = (residue[-1].source_file if residue else
                              (chain[-1] if chain else None))
        # CHAIN-FAITHFUL deletion semantics: in the sibling chain a slot may
        # be SUBSTITUTED first and DELETED later (the straggler set is
        # delete-reachable only AFTER the RC in-place header fixes -- dropping
        # the substitution changes the reference graph and maxgc pins the
        # link symbol).  The composer's single pass refuses that overlap, so
        # when it exists the composition runs as TWO compose calls:
        # Phase 1 = every in-place layer (must equal the chain's deepest
        # in-place file), Phase 2 = the lawful deletion set on that output
        # (must equal the sibling's deletion-proof file).  Every assertion
        # battery runs in both calls.
        del_ids = {int(x) for d in deletions for x in d.ids}
        sub_slots = {int(s) for sp in specs for s in sp.records}
        overlap = sorted(del_ids & sub_slots)
        if overlap:
            phase1_out = os.path.splitext(out)[0] + ".phase1.rvt"
            log(f"[compose-2025] {len(overlap)} slot(s) are substituted AND in "
                f"the deletion seed {overlap[:8]}: composing chain-faithfully "
                f"(substitute THEN delete) as two compose calls")
            rep1 = GC.compose(BASE_2025, specs, phase1_out, verify=verify,
                              label=label + " [phase 1: every in-place layer]")
            rep = GC.compose(phase1_out, [], out, deletions=deletions,
                             verify=verify, allow_uncertified_base=True,
                             label=label + " [phase 2: the lawful deletion set "
                                   "on the phase-1 output]")
            rep.problems = list(rep1.problems) + list(rep.problems)
            if rep1.verdict != "COMPOSED-VALID":
                rep.verdict = "NOT-CLEAN"
        else:
            rep = GC.compose(BASE_2025, specs, out, deletions=deletions,
                             on_overlap=(on_overlap if deletions else "refuse"),
                             verify=verify, label=label)
    # the end-to-end chain proofs: (a) the IN-PLACE layer of the composition
    # must equal the chain's deepest in-place file byte-for-byte MODULO the
    # delete-wins slots (a substitution dropped because its slot is in the
    # deletion set leaves the base's bytes there, pending Phase II removal);
    # (b) when the sibling published a deletion-applied PROOF file, the FINAL
    # output must equal it byte-for-byte, delete-wins and all.
    inplace_file = (os.path.splitext(out)[0] + ".inplace.rvt") if deletions else out
    chain_ok = None
    if deepest_chain_file and os.path.exists(inplace_file):
        chain_ok = (md5_of(inplace_file) == md5_of(deepest_chain_file))
    proof_ok = None
    if deletion_proof and os.path.exists(out) and deletions:
        proof_ok = (md5_of(out) == md5_of(deletion_proof))
    result = {
        "complete": complete,
        "out": _relp(out), "md5": md5_of(out), "sha256": sha256_of(out),
        "bytes": os.path.getsize(out),
        "verdict": rep.verdict, "problems": rep.problems,
        "manifest": rep.manifest_file,
        "phase1_manifest": (_relp(os.path.splitext(out)[0] + ".phase1.manifest.json")
                            if overlap else None),
        "substitute_then_delete_overlap_slots": overlap,
        "layers": {"y_rungs": [s.name for s in y],
                   "residue_rungs": [s.name for s in residue],
                   "deletion_sets": [d.name for d in deletions]},
        "inplace_layer_byte_identical_to_deepest_chain_file": {
            "file": _relp(inplace_file),
            "deepest_chain_file": (_relp(deepest_chain_file)
                                   if deepest_chain_file else None),
            "identical": chain_ok,
            "note": ("expected identical when the deletion set overlaps no "
                     "substituted slot; delete-wins slots legitimately differ "
                     "at this layer -- the FINAL proof below is the binding one")},
        "final_byte_identical_to_sibling_deletion_proof": {
            "file": _relp(out),
            "deletion_proof_file": (_relp(deletion_proof) if deletion_proof
                                    else None),
            "identical": proof_ok},
        "registry_relpath": _relp(G_FINAL),
        "seconds": round(time.time() - t0, 1),
    }
    if complete:
        # a stale PARTIAL from an earlier (pre-completion) run must not
        # linger beside the full candidate (it was never uploaded)
        for stale in (G_PARTIAL, os.path.splitext(G_PARTIAL)[0] + ".manifest.json",
                      os.path.splitext(G_PARTIAL)[0] + ".inplace.rvt"):
            if os.path.exists(stale):
                os.remove(stale)
                log(f"[compose-2025] removed stale partial artifact {_relp(stale)}")
    if proof_ok is False:
        result["problems"] = list(result["problems"]) + [
            "FINAL output does NOT equal the sibling's deletion-proof file "
            "byte-for-byte"]
        log("[compose-2025] *** the final output does not match the sibling's "
            "deletion-proof file -- the full-chain replay is NOT exact ***")
    elif proof_ok:
        log("[compose-2025] FINAL == the sibling's deletion-proof file "
            "byte-for-byte (the full-chain replay is exact)")
    if not complete:
        result["completion"] = {
            "missing": ([] if residue else ["the 2025 residue rungs (in-place "
                                            "files whose .json reports name their "
                                            "parents, chained off the deepest Y rung)"])
                       + ([] if deletions else ["the lawful 2025 deletion set "
                                                "(D_*.json with ids + policy)"]),
            "watched_locations": [_relp(LADDER_2025), _relp(SUBST_2025)]
                                 + [_relp(p) for p in DELETION_GLOBS],
            "one_command": ".venv/bin/python tools/genesis_compose_2025.py all",
            "note": ("re-running discovers the landed layers, composes the FULL "
                     "G_ABPD_2025.rvt at the registry relpath, and re-stages the "
                     "batch; nothing needs editing"),
        }
        log(f"[compose-2025] PARTIAL: missing {result['completion']['missing']}")
        log(f"[compose-2025] completion is ONE command: "
            f"{result['completion']['one_command']}")
    GC._write_json(os.path.join(OUT_DIR, "compose_2025.json"), result)
    return result


# ---------------------------------------------------------------------------
# 3. THE STAGED BATCH (probe_batch gate; the orchestrator uploads)
# ---------------------------------------------------------------------------
def stage() -> dict:
    import probe_batch as PB
    g = G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL
    if not os.path.exists(g):
        raise SystemExit("no composed G file -- run compose first")
    # idempotence: if the newest staged batch already carries EXACTLY this
    # candidate (same bytes) with a control of the certified base, keep it --
    # a re-run must not mint a new batch number for identical content
    existing = sorted(glob.glob(os.path.join(OUT_DIR, "batch_*.json")))
    if existing:
        with open(existing[-1]) as fh:
            man = json.load(fh)
        entries = {e.get("kind"): e for e in man.get("entries", [])}
        cand, ctrl = entries.get("candidate-base"), entries.get("control")
        if cand and ctrl and cand.get("md5") == md5_of(g) \
                and os.path.basename(str(cand.get("file", ""))) == os.path.basename(g) \
                and ctrl.get("md5") == md5_of(BASE_2025):
            log(f"[stage] batch {man['batch']} already stages this exact candidate "
                f"(md5 {cand['md5']}) with the certified control -- kept")
            return man
    name = os.path.splitext(os.path.basename(g))[0]
    is_full = (g == G_FINAL)
    cj = os.path.join(OUT_DIR, "compose_2025.json")
    comp = {}
    if os.path.exists(cj):
        with open(cj) as fh:
            comp = json.load(fh)
    manifest = {
        "stream": "compose-2025 (THE 2025 COMPOSER: tools/genesis_compose_2025.py)",
        "release": 2025,
        "situation": (
            "B2025_K4 (experiments/genesis2025/reduce/B2025_K4.rvt) is viewer-"
            "CERTIFIED (VERDICTS #28: the whole 2025 reduction lineage passed in "
            "one round).  The Y2025 substitution ladder (Y1..Y9, genesis-2025-"
            "port) is BUILT on it; the composer's 2025 anchor holds (compose of "
            "the nine rung deltas == Y9 byte-identical, see anchor_2025.json).  "
            + ("This batch stages the FULL composed candidate G_ABPD_2025."
               if is_full else
               "Residue rungs / the deletion set are NOT landed yet, so this "
               "batch stages the DEEPEST AVAILABLE composed prefix "
               "G_partial_2025 (= B2025_K4 + all nine Y2025 rungs, composed in "
               "one pass -- byte-identical to the ladder's Y9.rvt by the anchor).")),
        "base": _relp(BASE_2025),
        "probes": [{
            "name": name,
            "file": _relp(g),
            "kind": "candidate-base",
            "base": _relp(BASE_2025),
            "composed_from": (comp.get("layers") or {}),
            "the_ONE_thing_it_tests": (
                "Whether the COMPOSED 2025 candidate (every substituted layer "
                "merged onto the certified 2025 family-free base in one "
                "deterministic pass) LOADS in Autodesk's reader -- the 2025 "
                "equivalent of the G_ABPD candidacy (2026 verdict #24)."),
            "if_PASS": (
                ("certify + pin: fill genesis_base.json releases.2025 (sha256/"
                 "bytes/status certified) + flip KNOWN_RELEASES[2025]."
                 "creation_certified + bundle the asset (the ready-to-apply "
                 "diff is in docs/inbox/compose-2025.md); the front door's "
                 "--target-version 2025 then resolves this file."
                 if is_full else
                 "certify (it is byte-identical to Y9.rvt, so Y9 certifies by "
                 "bytes too); the ladder's ported constructors are viewer-"
                 "proven at 2025 registrations; on the residue + deletion "
                 "layers landing, re-compose the FULL G_ABPD_2025 and stage "
                 "it -- do NOT flip the registry on a partial file.")),
            "if_FAIL": (
                "with the control passing, bisect the composed layers the 2026 "
                "way: the sibling Y-ladder batch (experiments/genesis2025/"
                "subst/probes.json, bisection-first order Y9 -> Y6 -> Y1) "
                "isolates which rung's content the 2025 reader rejects."),
            "viewer_status": "PENDING (nothing uploaded by this stream)",
        }],
        "flip_gate": (
            "The G25-5 data flip (registry pin + version-model flag + plugin "
            "asset) is GATED on this batch's viewer verdict AND on the file "
            "being the FULL composition; the exact diff is in "
            "docs/inbox/compose-2025.md and is NOT applied."),
    }
    GC._write_json(os.path.join(OUT_DIR, "probes.json"), manifest)
    log(f"[stage] wrote {_relp(os.path.join(OUT_DIR, 'probes.json'))}")
    # GLOBAL numbering: scan every batch_N.json in the repo's experiments tree
    # (parallel campaign streams stage into their own dirs -- the 2024 stream
    # staged batch_28 while this stream ran), so the label never reuses a
    # number another batch already carries.
    n = PB.HISTORICAL_ROUNDS
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "batch_*.json"),
                       recursive=True):
        m = re.match(r"batch_(\d+)\.json$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    n += 1
    batch = PB.stage_batch(
        [], candidate_bases=[g], control_from=_relp(BASE_2025),
        out_dir=OUT_DIR, batch_n=n,
        note=("2025 compose round: control = byte-identical copy of the "
              "CERTIFIED 2025 family-free base B2025_K4; candidate-base = "
              f"{name} (the {'full' if is_full else 'deepest-available'} "
              "composed 2025 candidate).  Batch number = 1 + the highest "
              "batch_N.json anywhere under experiments/ (parallel campaign "
              "streams stage into their own dirs).  Read with "
              "probe_batch.read_batch_verdicts; control FAIL voids the round."))
    log(f"[stage] batch {batch['batch']} staged into {_relp(OUT_DIR)}: "
        + ", ".join(batch["reading_order"]))
    return batch


# ---------------------------------------------------------------------------
# 4. THE FINISH LINE, DRY-RUN (tests/test_target2025.py's skipped test body)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _inmemory_flip(g_path: str):
    """Apply the G25-5 flip IN MEMORY ONLY: KNOWN_RELEASES[2025] gains
    creation_certified + genesis_base; the genesis_base.json 2025 slot (the
    already-loaded PIN object) gains sha256/bytes/status.  Restores on exit;
    the on-disk registry and version model are UNTOUCHED."""
    import rvt.versions as V
    from rvt.frontdoor import base as B
    rel = _relp(g_path)
    old_release = V.KNOWN_RELEASES[2025]
    old_supported = V.SUPPORTED_CREATION_RELEASES
    slot = B.PIN.raw["releases"]["2025"]
    old_slot = dict(slot)
    try:
        V.KNOWN_RELEASES[2025] = dataclasses.replace(
            old_release, creation_certified=True, genesis_base=rel)
        V.SUPPORTED_CREATION_RELEASES = frozenset(
            y for y, r in V.KNOWN_RELEASES.items() if r.creation_certified)
        slot["relpath"] = rel
        slot["sha256"] = sha256_of(g_path)
        slot["bytes"] = os.path.getsize(g_path)
        slot["status"] = "certified"
        yield
    finally:
        V.KNOWN_RELEASES[2025] = old_release
        V.SUPPORTED_CREATION_RELEASES = old_supported
        slot.clear()
        slot.update(old_slot)


def finishline(*, full: bool = False, out_dir: Optional[str] = None,
               simulate_allow_fix: bool = False,
               in_context: bool = False) -> dict:
    """DRY-RUN of test_END_STATE_author_2025_produces_a_2025_file against the
    composed G file, with the flip applied in memory only.  ``full=False``
    runs the fast handoff-only author (resolution + manifest honesty);
    ``full=True`` runs the whole build (the test's actual body).  The result
    is REPORTED (finishline_2025.json), never asserted -- a failure here is
    the finding, not a crash.

    ``simulate_allow_fix``: the first full-build gap found by this dry run is
    the standalone research-input tripwire -- its allow list carries only the
    DEFAULT slot's base (standalone.bundled_base_path -> the 2026 pin), so a
    resolved 2025 base under experiments/ trips it.  This flag simulates the
    one-line front-door fix (allow the RESOLVED base, which resolve_base has
    already pin-verified) in memory, to expose whatever layer fails next."""
    import tempfile
    import rvt.versions as V
    g = G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL
    if not os.path.exists(g):
        raise SystemExit("no composed G file -- run compose first")
    rep: Dict[str, Any] = {
        "test": "tests/test_target2025.py::test_END_STATE_author_2025_produces_a_2025_file",
        "mode": ("FULL build (no_handoff) -- the test's actual body" if full
                 else "handoff-only (resolution + manifest honesty; pass --full "
                      "for the whole build)"),
        "g_file": _relp(g), "g_sha256": sha256_of(g),
        "flip": "IN MEMORY ONLY (nothing on disk changed)",
        "checks": {},
    }
    out_dir = out_dir or tempfile.mkdtemp(prefix="finishline2025_")
    t0 = time.time()
    restore_sa: List[Tuple[Any, str, Any]] = []
    if simulate_allow_fix:
        from rvt.frontdoor import standalone as SA
        orig_forbid = SA.forbid_research_inputs

        def _forbid_with_base(*, allow=()):
            return orig_forbid(allow=list(allow) + [g])

        restore_sa.append((SA, "forbid_research_inputs", orig_forbid))
        SA.forbid_research_inputs = _forbid_with_base
        rep["simulated_fix"] = (
            "standalone.forbid_research_inputs wrapped to ALSO allow the "
            "resolved 2025 base (the proposed one-line build.py fix: "
            "allow=[opts.specimen_src, opts.base.path])")
    if in_context:
        rep["in_context"] = (
            "the WHOLE author call runs inside context_compose_2025 (the 2025 "
            "emit context: versions.reading + the seven framing patches + the "
            "2025 codecs) -- probing whether the ladder's context is the "
            "missing versions.creating(2025) the build path needs")
    ctx = context_compose_2025(g) if in_context else contextlib.nullcontext()
    with ctx, _inmemory_flip(g):
        import rvt.frontdoor as FD
        from rvt.frontdoor import base as B
        # the guard + registry now agree (the three-source rule)
        st = V.creation_status(2025)
        rs = B.release_status(2025)
        rep["checks"]["creation_status_supported"] = bool(st.get("supported"))
        rep["checks"]["release_status_certified"] = bool(rs.get("certified"))
        try:
            rb = B.resolve_base(target_release=2025)
            rep["checks"]["resolve_base"] = {
                "path": _relp(rb.path), "certified": rb.certified,
                "pinned": rb.pinned,
                "detected_release": V.detect_release(rb.path)}
        except Exception as ex:
            rep["checks"]["resolve_base"] = {"error": repr(ex)[:300]}
        try:
            r = FD.author(prompt="a 400 A distribution panel", target_version=2025,
                          **({"no_handoff": True} if full else {"handoff_only": True}),
                          out=out_dir)
            tv = (r.manifest.get("target_version") or {})
            rep["author"] = {
                "ok": bool(r.ok), "errors": list(getattr(r, "errors", []) or [])[:8],
                "target_version": {k: tv.get(k) for k in
                                   ("status", "requested", "output_release", "line")},
                "files": {k: _relp(v) for k, v in (r.files or {}).items()
                          if isinstance(v, str)},
            }
            out = (r.files or {}).get("combined") or (r.files or {}).get("equipment") \
                or (r.files or {}).get("shell")
            if out and os.path.isfile(out):
                rep["checks"]["detect_release_of_output"] = V.detect_release(out)
                try:
                    from rvt.container import open_rvt
                    from rvt import stream_encoders as SE
                    doc = open_rvt(out)
                    try:
                        bfi = SE.decode_basic_file_info(doc.raw("BasicFileInfo"))
                    finally:
                        doc.close()
                    rep["checks"]["bfi_format"] = str(bfi.get("format"))
                    rep["checks"]["bfi_build_present"] = bool(bfi.get("build"))
                    s = V.schema_of(out)
                    rep["checks"]["schema_sha256_is_2025_pin"] = (
                        s.stats()["sha256"] == V.KNOWN_RELEASES[2025].schema_sha256)
                except Exception as ex:
                    rep["checks"]["output_decode_error"] = repr(ex)[:300]
            elif full:
                rep["checks"]["output_file"] = "MISSING (build produced no rvt)"
            rep["assertion_status_match"] = (tv.get("status") == "match"
                                             and not tv.get("line"))
        except Exception as ex:
            rep["author"] = {"exception": repr(ex)[:500]}
    for mod, name, val in reversed(restore_sa):
        setattr(mod, name, val)
    rep["seconds"] = round(time.time() - t0, 1)
    passed = (rep.get("assertion_status_match") and
              (not full or (rep["checks"].get("detect_release_of_output") == 2025
                            and rep["checks"].get("schema_sha256_is_2025_pin")
                            and rep.get("author", {}).get("ok"))))
    rep["verdict"] = ("WOULD PASS post-flip" if passed else
                      "WOULD FAIL post-flip -- see checks/author for the exact gap")
    fn = ("finishline_2025_incontext.json" if in_context
          else "finishline_2025_simfix.json" if simulate_allow_fix
          else "finishline_2025.json")
    GC._write_json(os.path.join(OUT_DIR, fn), rep)
    log(f"[finishline] {rep['verdict']} ({rep['mode']}); "
        f"report {_relp(os.path.join(OUT_DIR, fn))}")
    return rep


# ---------------------------------------------------------------------------
# 5. THE FLIP DIFF (printed, NEVER applied -- gated on the viewer verdict)
# ---------------------------------------------------------------------------
def flipdiff() -> str:
    """Print the G25-5 data flip as a ready-to-apply diff over the three
    files target-2025's record names (genesis_base.json, rvt/versions,
    sync_plugin), with the composed file's LIVE sha256/bytes filled in.
    GATE (do not apply until BOTH hold): (1) the composition is FULL
    (G_ABPD_2025.rvt exists = Y rungs + residue + lawful deletions), and
    (2) the viewer PASSED it (ledger entry in viewer-certified.json)."""
    g = G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL
    full = (g == G_FINAL)
    cert = GC.certification_of(g) if os.path.exists(g) else None
    sha = sha256_of(g) if os.path.exists(g) else "<sha256 of G_ABPD_2025.rvt>"
    nbytes = os.path.getsize(g) if os.path.exists(g) else "<bytes>"
    md5v = md5_of(g) if os.path.exists(g) else "<md5>"
    rel = _relp(G_FINAL)
    gate = []
    if not full:
        gate.append("composition is PARTIAL (G_partial_2025) -- values below are "
                    "TODAY'S partial file, shown as the worked example; re-run "
                    "`tools/genesis_compose_2025.py all` after the residue + "
                    "deletion layers land, then regenerate this diff")
    if cert is None:
        gate.append("the composed file is NOT in viewer-certified.json -- the "
                    "flip is GATED on its viewer PASS")
    L: List[str] = []
    A = L.append
    A("### THE G25-5 DATA FLIP -- ready to apply, NOT applied")
    A("")
    A(f"gate status: {'CLEAR' if not gate else 'BLOCKED: ' + '; '.join(gate)}")
    A(f"values from: {_relp(g)}  sha256 {sha}  md5 {md5v}  bytes {nbytes:,}"
      if isinstance(nbytes, int) else f"values from: {_relp(g)}")
    A("")
    A("--- 1. src/rvt/frontdoor/assets/genesis_base.json (releases.2025) ---")
    A('     "relpath": "experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt",')
    A(f'-    "sha256": null,')
    A(f'+    "sha256": "{sha}",')
    A(f'-    "bytes": null,')
    A(f'+    "bytes": {nbytes},')
    A(f'-    "status": "pending certification",')
    A(f'+    "status": "certified",')
    A("   (pending_reason may be deleted or left; release_status reads only "
      "status + sha256 + the version-model flag)")
    A("")
    A("--- 2. src/rvt/versions/__init__.py (KNOWN_RELEASES[2025]) ---")
    A('-        samples_dir="samples/2025", creation_certified=False),')
    A('+        samples_dir="samples/2025", creation_certified=True,')
    A(f'+        genesis_base="{rel}"),')
    A("")
    A("--- 3. tools/sync_plugin.py (bundle the 2025 base beside the 2026 one) ---")
    A("after GENESIS_MANIFEST_SRC (~line 70):")
    A('+GENESIS_BASE_2025_SRC = os.path.join(ROOT, "experiments", "genesis",')
    A('+                                     "subst_k4_2025", "compose", "G_ABPD_2025.rvt")')
    A('+GENESIS_MANIFEST_2025_SRC = os.path.join(ROOT, "experiments", "genesis",')
    A('+                                         "subst_k4_2025", "compose",')
    A('+                                         "G_ABPD_2025.manifest.json")')
    A("in asset_mappings() (~line 196):")
    A('     (GENESIS_BASE_SRC, f"{GENESIS_DST_DIR}/G_ABPD.rvt", True),')
    A('     (GENESIS_MANIFEST_SRC, f"{GENESIS_DST_DIR}/G_ABPD.compose.json", False),')
    A('+    (GENESIS_BASE_2025_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2025.rvt", True),')
    A('+    (GENESIS_MANIFEST_2025_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2025.compose.json", False),')
    A("in verify_assets(), after the default-pin cross-check (~line 305):")
    A('+    base25_dst = os.path.join(PLUGIN, GENESIS_DST_DIR, "G_ABPD_2025.rvt")')
    A('+    if os.path.exists(base25_dst) and os.path.exists(FRONTDOOR_PIN):')
    A('+        try:')
    A('+            with open(FRONTDOOR_PIN) as fh:')
    A('+                pin = json.load(fh)')
    A('+            want = str((pin.get("releases", {}).get("2025") or {}).get("sha256") or "").lower()')
    A('+            got = _hash(base25_dst)')
    A('+            if want and got != want:')
    A('+                problems.append(')
    A('+                    f"2025 genesis base asset sha256 {got[:16]}.. != releases.2025 pin "')
    A('+                    f"{want[:16]}.. — the front door would REFUSE the bundled 2025 base")')
    A('+        except (KeyError, ValueError, OSError) as e:')
    A('+            problems.append(f"cannot read frontdoor pin {FRONTDOOR_PIN}: {e}")')
    A("")
    A("then: tools/sync_plugin.py (re-sync + re-zip); tests/test_target2025.py's")
    A("finish line arms itself; the TODAY-tests flip to their certified branches.")
    A("NOTE the finish-line dry run (finishline_2025*.json): the FULL build has")
    A("three further gaps (standalone allow-list; versions.creating on the build")
    A("path; famgen constructors need the port2025 adaptation) -- the flip makes")
    A("resolution + manifest honest, it does not yet make the full 2025 build pass.")
    txt = "\n".join(L)
    print(txt)
    return txt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["anchor", "compose", "stage", "finishline",
                                    "flipdiff", "all"])
    ap.add_argument("--full", action="store_true",
                    help="finishline: run the FULL build (the test's actual body)")
    ap.add_argument("--simulate-allow-fix", action="store_true",
                    help="finishline: also simulate the one-line standalone "
                         "allow-list fix in memory (expose the next layer)")
    ap.add_argument("--in-context", action="store_true",
                    help="finishline: run the author call inside the 2025 emit "
                         "context (probe the versions.creating(2025) shape)")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the per-layer assertion battery (never for a real candidate)")
    args = ap.parse_args(argv)
    rc = 0
    if args.cmd in ("anchor", "all"):
        a = prove_anchor_2025(verify=not args.no_verify)
        rc = 0 if a["BYTE_IDENTICAL"] else 2
        if rc:
            return rc
    if args.cmd in ("compose", "all"):
        c = compose_g(verify=not args.no_verify)
        if c["verdict"] != "COMPOSED-VALID":
            rc = 2
    if args.cmd in ("stage", "all"):
        stage()
    if args.cmd in ("finishline", "all"):
        finishline(full=args.full, simulate_allow_fix=args.simulate_allow_fix,
                   in_context=args.in_context)
    if args.cmd == "flipdiff":
        flipdiff()
    return rc


if __name__ == "__main__":
    sys.exit(main())
