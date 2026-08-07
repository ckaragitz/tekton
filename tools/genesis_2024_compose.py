#!/usr/bin/env python
"""genesis_2024_compose.py -- THE 2024 COMPOSER: tools/genesis_compose.py
run under the Revit-2024 emit context, against the CERTIFIED 2024 family-free
base B2024_K4 (docs/inbox/genesis-audit.md VERDICTS #32: b28 ALL PASS).

THE PATTERN is the just-proven 2025 composer (tools/genesis_compose_2025.py,
whose G_ABPD_2025 is viewer-CERTIFIED and registry-pinned -- verdicts #31):
enter the per-release emit context (``tools/genesis_2024.py::context_2024``
= versions.reading + the seven module-local framing patches + the ADocument
decoder, PLUS the per-release codec swaps), then DELEGATE every operation to
``tools/genesis_compose.py`` unchanged.  The chain-linearization and
parent-report helpers are IMPORTED from genesis_compose_2025 (they are
release-agnostic pure functions); nothing outside this file's territory is
edited.

THE CORRECTNESS ANCHOR (:func:`prove_anchor_2024`): the NINE cumulative
Y2024 rung deltas (Y1 vs B2024_K4, Y2 vs Y1, ..., Y9 vs Y8 -- linearized,
seq-restricted), merged and replayed onto B2024_K4 in ONE
``regadd.substitute_elements`` call, must reproduce the ladder's deepest
cumulative rung ``Y9_2024.rvt`` BYTE-IDENTICALLY (md5).

THE CANDIDATE (:func:`compose_g`): G_ABPD_2024 = B2024_K4 + all Y2024 rungs
+ every landed 2024 residue rung + the lawful 2024 deletion set ->
``experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt`` (the EXACT
relpath the front-door registry's 2024 slot reserves --
src/rvt/frontdoor/assets/genesis_base.json releases.2024).  Residue rungs
and deletion sets are DISCOVERED from the chain's output tree (each rung
must carry its .json report naming its parent; each deletion set is a JSON
spec with ids+policy; a spec whose ids are a strict subset of another's is
collapsed onto the union).  When a slot is substituted AND in the deletion
seed, the composition runs chain-faithfully as TWO compose calls
(substitute THEN delete), and the FINAL output must equal the sibling
chain's deletion-proof file ``RC_2024.rvt`` byte-for-byte.

THE BATCH (:func:`stage`): the charter's four-file bisection round --
control (byte-identical copy of the CERTIFIED B2024_K4) + G_ABPD_2024 (the
deepest: settings + views + residue + deletions) + Y9_2024 (the deepest
views rung: settings + views, no residue) + Y7_2024 (the deepest settings
rung), bisection-first in probes.json.  Nothing is uploaded here; the
orchestrator uploads.

THE FLIP DIFF (:func:`flipdiff`): the 2024 data flip (genesis_base.json
releases.2024 pin + KNOWN_RELEASES[2024].creation_certified + the
sync_plugin bundle lines -- the exact shape APPLIED for 2025 at verdicts
#31), printed with the composed file's LIVE sha256/bytes, NEVER applied:
gated on the viewer PASS.

Usage (repo root):
  .venv/bin/python tools/genesis_2024_compose.py anchor      # the md5 proof
  .venv/bin/python tools/genesis_2024_compose.py compose     # G file (partial or full)
  .venv/bin/python tools/genesis_2024_compose.py stage       # probes.json + batch
  .venv/bin/python tools/genesis_2024_compose.py finishline
  .venv/bin/python tools/genesis_2024_compose.py flipdiff
  .venv/bin/python tools/genesis_2024_compose.py all

Territory: this file, tests/test_y2024.py,
experiments/genesis/subst_k4_2024/compose/**, docs/inbox/y2024-compose.md.
Everything else (genesis_compose, genesis_compose_2025, genesis_2024,
port2024, probe_batch, regadd, versions, frontdoor) is IMPORTED, never
edited.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import functools
import glob
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
import genesis_compose_2025 as GC25                                 # noqa: E402
import genesis_2024 as G24                                          # noqa: E402

# ---------------------------------------------------------------------------
# paths (the 2024 campaign's geography)
# ---------------------------------------------------------------------------
#: the CERTIFIED 2024 family-free base (docs/coverage/viewer-certified.json
#: entry 'experiments/genesis2024/reduce/B2024_K4.rvt'; VERDICTS #32)
BASE_2024 = os.path.join(ROOT, "experiments", "genesis2024", "reduce", "B2024_K4.rvt")
#: the CANONICAL Y2024 chain dir (y2024_a settings + y2024_b views/residue)
LADDER_2024 = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2024")
#: this stream's experiment dir == the registry slot's parent directory
OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2024", "compose")
#: the EXACT relpath genesis_base.json releases.2024 reserves
G_FINAL = os.path.join(OUT_DIR, "G_ABPD_2024.rvt")
G_PARTIAL = os.path.join(OUT_DIR, "G_partial_2024.rvt")
ANCHOR_OUT = os.path.join(OUT_DIR, "G_Y2024_anchor.rvt")
ANCHOR_JSON = os.path.join(OUT_DIR, "anchor_2024.json")

#: where the chain's 2024 deletion sets are discovered
DELETION_GLOBS = [
    os.path.join(ROOT, "experiments", "genesis", "subst_k4_2024", "**", "D_*.json"),
    os.path.join(ROOT, "experiments", "genesis", "subst_k4_2024", "**", "*deletion*.json"),
    os.path.join(ROOT, "experiments", "genesis", "subst_k4_2024", "**", "*.spec.json"),
]

log = GC.log
_relp = GC._relp
md5_of = GC.md5_of
sha256_of = GC.sha256_of
#: release-agnostic helpers reused from the proven 2025 composer
linearize_chain_specs = GC25.linearize_chain_specs
_report_parent = GC25._report_parent


# ---------------------------------------------------------------------------
# the 2024 compose context
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def context_compose_2024(base: str = BASE_2024):
    """genesis_2024.context_2024 (versions.reading + the SEVEN module-local
    framing-tag patches + rvt.adocument._DECODER, with the 2024 release
    assertion) PLUS the per-release codec swaps the Y2024 ladder proved out:
    rvt.encode._DEFAULT_ENCODER, the lazy ObjectDecoder factories in
    rvt.regadd / rvt.regdiff, and genesis_compose's own report decoder.
    Restores everything on exit."""
    from rvt import encode as ENC
    from rvt import regadd, regdiff
    from rvt.genesis import port2024 as P24
    from rvt.objects import ObjectDecoder

    dec24, enc24, schema24 = P24._S24()
    with G24.context_2024(base) as ords:
        saved: List[Tuple[Any, str, Any]] = []

        def swap(mod, name, value):
            saved.append((mod, name, getattr(mod, name)))
            setattr(mod, name, value)

        swap(ENC, "_DEFAULT_ENCODER", enc24)
        swap(regadd, "ObjectDecoder", functools.partial(ObjectDecoder, schema24))
        swap(regdiff, "ObjectDecoder", functools.partial(ObjectDecoder, schema24))
        swap(GC, "_DEC", dec24)
        try:
            yield ords
        finally:
            for mod, name, val in reversed(saved):
                setattr(mod, name, val)


# ---------------------------------------------------------------------------
# rung + deletion discovery
# ---------------------------------------------------------------------------
def discover_y_chain(base: str = BASE_2024) -> List[str]:
    """The CANONICAL cumulative Y2024 chain, ordered base -> deepest, by the
    rungs' OWN parent declarations (each report's ``parent``/``base.file``).
    Candidates: ``Y<n>_2024.rvt`` in the chain dir (single-change probes
    ``Y<n>s_2024`` excluded by the pattern)."""
    cands: List[str] = []
    for f in sorted(glob.glob(os.path.join(LADDER_2024, "*.rvt"))):
        stem = os.path.splitext(os.path.basename(f))[0]
        if re.fullmatch(r"Y\d+_2024", stem):
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


def y2024_specs(base: str = BASE_2024,
                chain: Optional[List[str]] = None) -> List[GC.RungSpec]:
    """The cumulative Y2024 rung deltas, each vs its own parent (Y1 vs the
    base, Yn vs Yn-1) -- must be called INSIDE the context."""
    chain = chain if chain is not None else discover_y_chain(base)
    if not chain:
        raise SystemExit(f"no Y2024 ladder found in {_relp(LADDER_2024)} -- run "
                         "rvt.genesis.y2024_a + y2024_b first")
    specs: List[GC.RungSpec] = []
    parent = base
    for f in chain:
        stem = os.path.splitext(os.path.basename(f))[0]
        specs.append(GC.RungSpec.from_rung_file(f, parent, name=f"Y2024:{stem}",
                                                group="Y"))
        parent = f
    return specs


def discover_residue_specs(y_chain: List[str]) -> Tuple[List[GC.RungSpec], Optional[str]]:
    """The chain's 2024 residue rungs, discovered by WALKING THE DECLARED
    PARENT CHAIN from the deepest Y rung -- must be called INSIDE the
    context.  Nodes are keyed by md5 (Z aliases collapse); at a fork the
    TRUNK (deepest descendant chain) wins; the walk STOPS at the first
    non-in-place step (the deletion layer, composable only via its D_*.json
    spec -- that file is the sibling's deletion PROOF the final composition
    must equal)."""
    if not y_chain:
        return [], None
    cands: List[str] = []
    for f in sorted(glob.glob(os.path.join(LADDER_2024, "*.rvt"))):
        stem = os.path.splitext(os.path.basename(f))[0]
        if stem.startswith("CTRL") or re.fullmatch(r"Y\d+s?(_2024)?", stem):
            continue
        cands.append(f)
    y_md5 = {md5_of(p) for p in y_chain} | {md5_of(BASE_2024)}
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
                                                    name=f"R2024:{stem}",
                                                    group="residue"))
        except GC.CompositionError as ex:
            deletion_proof = nxt
            log(f"   [discover] {_relp(nxt)} is NOT an in-place step of "
                f"{_relp(cur_file)} ({str(ex)[:120]}) -- the walk stops here "
                f"(the deletion layer composes via its spec; this file is the "
                f"chain's deletion PROOF the final composition must equal)")
            break
        cur_file = nxt
        cur = kids[0]
    return specs, deletion_proof


def discover_deletion_specs() -> List[GC.DeletionSpec]:
    """The chain's 2024 deletion sets (JSON with ids + a lawful policy).  A
    spec whose id set is a strict subset of another discovered spec's is
    DROPPED (the chain publishes constituent singles beside their union --
    D_2024_* beside D_2024_stragglers_full); composing the union once is the
    same deletion without double bookkeeping."""
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


# ---------------------------------------------------------------------------
# 1. THE ANCHOR: compose(B2024_K4, Y1..Y9 deltas) == Y9_2024 byte-identical
# ---------------------------------------------------------------------------
def prove_anchor_2024(*, verify: bool = True) -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    with context_compose_2024(BASE_2024):
        specs = linearize_chain_specs(y2024_specs())
        rep = GC.compose(BASE_2024, specs, ANCHOR_OUT,
                         label="G_Y2024_anchor (the 2024 composer anchor)",
                         verify=verify)
    target = discover_y_chain()[-1]                  # the deepest cumulative rung
    got, want = md5_of(ANCHOR_OUT), md5_of(target)
    identical = (got == want)
    anchor = {
        "claim": (f"compose(B2024_K4, [the {len(specs)} cumulative Y2024 rung "
                  f"deltas]) reproduces the ladder's deepest cumulative rung "
                  f"{os.path.basename(target)} BYTE-IDENTICALLY under the 2024 "
                  "emit context"),
        "base": _relp(BASE_2024), "base_md5": md5_of(BASE_2024),
        "base_certification": (GC.certification_of(BASE_2024) or {}).get("proves"),
        "target": _relp(target),
        "rung_sets": [s.summary() for s in specs],
        "merged_slots": (rep.phase_1_inplace.get("merge") or {}).get("merged_slots"),
        "reproduction": _relp(ANCHOR_OUT),
        "md5_reproduction": got, "md5_target": want,
        "BYTE_IDENTICAL": identical,
        "meaning": ("the composer's Phase I is EXACT on Revit 2024: the "
                    "independently-emitted in-place rungs, merged into one "
                    "substitute_elements call under context_compose_2024, land in "
                    "precisely the file the Y2024 ladder emitted -- the 2026 "
                    "anchor proof (and its 2025 transfer) transfers to 2024"),
        "compose_verdict": rep.verdict, "compose_problems": rep.problems,
        "seconds": round(time.time() - t0, 1),
    }
    GC._write_json(ANCHOR_JSON, anchor)
    log(f"\n[anchor-2024] reproduction md5 {got}\n[anchor-2024] target       md5 {want}\n"
        f"[anchor-2024] BYTE-IDENTICAL: {identical}  ({anchor['seconds']}s)")
    if not identical:
        log("[anchor-2024] *** THE ANCHOR DOES NOT HOLD ***")
    return anchor


# ---------------------------------------------------------------------------
# 2. THE CANDIDATE: G_ABPD_2024 (full) or G_partial_2024 (deepest prefix)
# ---------------------------------------------------------------------------
def compose_g(*, verify: bool = True, on_overlap: str = "delete-wins") -> dict:
    """Compose the deepest available 2024 candidate.  FULL (all three layers
    present: Y rungs + residue rungs + a deletion set) -> G_ABPD_2024.rvt at
    the registry relpath.  Anything less -> G_partial_2024.rvt + the
    completion instructions."""
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    with context_compose_2024(BASE_2024):
        chain = discover_y_chain()
        y = y2024_specs(chain=chain)
        residue, deletion_proof = discover_residue_specs(chain)
        deletions = discover_deletion_specs()
        complete = bool(residue) and bool(deletions)
        out = G_FINAL if complete else G_PARTIAL
        label = ("G_ABPD_2024 (B2024_K4 + Y2024 + residue + lawful deletions)"
                 if complete else
                 "G_partial_2024 (DEEPEST AVAILABLE 2024 prefix: B2024_K4 + Y2024"
                 + (" + residue" if residue else "")
                 + (" + deletions" if deletions else "") + ")")
        log(f"[compose-2024] layers: Y rungs {len(y)}; residue rungs "
            f"{len(residue)}; deletion sets {len(deletions)} -> "
            f"{'FULL G_ABPD_2024' if complete else 'PARTIAL (deepest prefix)'}")
        specs = linearize_chain_specs(y + residue)
        deepest_chain_file = (residue[-1].source_file if residue else
                              (chain[-1] if chain else None))
        # CHAIN-FAITHFUL deletion semantics (the 2025 composer's lesson): a
        # slot may be SUBSTITUTED first and DELETED later -- the composer's
        # single pass refuses that overlap, so when it exists the composition
        # runs as TWO compose calls (substitute THEN delete); every assertion
        # battery runs in both.
        del_ids = {int(x) for d in deletions for x in d.ids}
        sub_slots = {int(s) for sp in specs for s in sp.records}
        overlap = sorted(del_ids & sub_slots)
        if overlap:
            phase1_out = os.path.splitext(out)[0] + ".phase1.rvt"
            log(f"[compose-2024] {len(overlap)} slot(s) are substituted AND in "
                f"the deletion seed {overlap[:8]}: composing chain-faithfully "
                f"(substitute THEN delete) as two compose calls")
            rep1 = GC.compose(BASE_2024, specs, phase1_out, verify=verify,
                              label=label + " [phase 1: every in-place layer]")
            rep = GC.compose(phase1_out, [], out, deletions=deletions,
                             verify=verify, allow_uncertified_base=True,
                             label=label + " [phase 2: the lawful deletion set "
                                   "on the phase-1 output]")
            rep.problems = list(rep1.problems) + list(rep.problems)
            if rep1.verdict != "COMPOSED-VALID":
                rep.verdict = "NOT-CLEAN"
        else:
            rep = GC.compose(BASE_2024, specs, out, deletions=deletions,
                             on_overlap=(on_overlap if deletions else "refuse"),
                             verify=verify, label=label)
    # the end-to-end chain proofs (the 2025 composer's, verbatim)
    inplace_file = (os.path.splitext(out)[0] + ".inplace.rvt") if deletions else out
    chain_ok = None
    if deepest_chain_file and os.path.exists(inplace_file):
        chain_ok = (md5_of(inplace_file) == md5_of(deepest_chain_file))
    proof_ok = None
    if deletion_proof and os.path.exists(out) and deletions:
        proof_ok = (md5_of(out) == md5_of(deletion_proof))
    # the release gate on the composed candidate (detect==2024, tags {0x0e7c})
    release = G24.release_gate(out) if os.path.exists(out) else None
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
        "final_byte_identical_to_chain_deletion_proof": {
            "file": _relp(out),
            "deletion_proof_file": (_relp(deletion_proof) if deletion_proof
                                    else None),
            "identical": proof_ok},
        "release_gate": release,
        "registry_relpath": _relp(G_FINAL),
        "seconds": round(time.time() - t0, 1),
    }
    if complete:
        for stale in (G_PARTIAL, os.path.splitext(G_PARTIAL)[0] + ".manifest.json",
                      os.path.splitext(G_PARTIAL)[0] + ".inplace.rvt"):
            if os.path.exists(stale):
                os.remove(stale)
                log(f"[compose-2024] removed stale partial artifact {_relp(stale)}")
    if proof_ok is False:
        result["problems"] = list(result["problems"]) + [
            "FINAL output does NOT equal the chain's deletion-proof file "
            "byte-for-byte"]
        log("[compose-2024] *** the final output does not match the chain's "
            "deletion-proof file -- the full-chain replay is NOT exact ***")
    elif proof_ok:
        log("[compose-2024] FINAL == the chain's deletion-proof file "
            "byte-for-byte (the full-chain replay is exact)")
    if not complete:
        result["completion"] = {
            "missing": ([] if residue else ["the 2024 residue rungs"])
                       + ([] if deletions else ["the lawful 2024 deletion set "
                                                "(D_*.json with ids + policy)"]),
            "watched_locations": [_relp(LADDER_2024)]
                                 + [_relp(p) for p in DELETION_GLOBS],
            "one_command": ".venv/bin/python tools/genesis_2024_compose.py all",
        }
        log(f"[compose-2024] PARTIAL: missing {result['completion']['missing']}")
    GC._write_json(os.path.join(OUT_DIR, "compose_2024.json"), result)
    return result


# ---------------------------------------------------------------------------
# 3. THE STAGED BATCH (the charter's four-file bisection round)
# ---------------------------------------------------------------------------
def stage() -> dict:
    """CTRL (byte-identical B2024_K4 copy) + G_ABPD_2024 + Y9_2024 (deepest
    views rung) + Y7_2024 (deepest settings rung), bisection-first.  The
    probe_batch gate resolves every entry to the certified base; the
    orchestrator uploads."""
    import probe_batch as PB
    g = G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL
    if not os.path.exists(g):
        raise SystemExit("no composed G file -- run compose first")
    y9 = os.path.join(LADDER_2024, "Y9_2024.rvt")
    y7 = os.path.join(LADDER_2024, "Y7_2024.rvt")
    for f in (y9, y7):
        if not os.path.exists(f):
            raise SystemExit(f"missing {_relp(f)} -- the chain must be built first")
    cands = [g, y9, y7]
    # idempotence: if the newest staged batch already carries EXACTLY these
    # candidates (same bytes) with a control of the certified base, keep it
    existing = sorted(glob.glob(os.path.join(OUT_DIR, "batch_*.json")))
    if existing:
        with open(existing[-1]) as fh:
            man = json.load(fh)
        got = {os.path.basename(str(e.get("file", ""))): e.get("md5")
               for e in man.get("entries", []) if e.get("kind") == "candidate-base"}
        ctrl = next((e for e in man.get("entries", []) if e.get("kind") == "control"), None)
        if (ctrl and ctrl.get("md5") == md5_of(BASE_2024)
                and got == {os.path.basename(f): md5_of(f) for f in cands}):
            log(f"[stage] batch {man['batch']} already stages these exact candidates "
                f"with the certified control -- kept")
            return man
    name = os.path.splitext(os.path.basename(g))[0]
    is_full = (g == G_FINAL)
    cj = os.path.join(OUT_DIR, "compose_2024.json")
    comp = {}
    if os.path.exists(cj):
        with open(cj) as fh:
            comp = json.load(fh)
    base_cert = GC.certification_of(BASE_2024)
    entries = [
        {
            "order": 1, "name": name, "file": _relp(g), "kind": "candidate-base",
            "base": _relp(BASE_2024),
            "composed_from": (comp.get("layers") or {}),
            "the_ONE_thing_it_tests": (
                "Whether the COMPOSED 2024 candidate (every substituted layer + the "
                "residue rounds + the lawful deletion set, merged onto the certified "
                "2024 family-free base deterministically) LOADS in Autodesk's reader "
                "-- the 2024 equivalent of the G_ABPD / G_ABPD_2025 candidacies "
                "(verdicts #24 / #31)."),
            "if_PASS": ("certify + pin: fill genesis_base.json releases.2024 (sha256/"
                        "bytes/status certified) + flip KNOWN_RELEASES[2024]."
                        "creation_certified + bundle the asset -- the ready-to-apply "
                        "diff is `tools/genesis_2024_compose.py flipdiff` (recorded in "
                        "docs/inbox/y2024-compose.md); the front door's "
                        "--target-version 2024 then resolves this file."
                        if is_full else
                        "certify the prefix; do NOT flip the registry on a partial file."),
            "if_FAIL": ("with the control passing, read Y9_2024 / Y7_2024 below: "
                        "G FAIL + Y9 PASS convicts the residue/deletion layers; "
                        "Y9 FAIL + Y7 PASS convicts the datum/view layer; Y7 FAIL "
                        "convicts settings/catalog/palette -- then the per-half "
                        "probes.json ladders (experiments/genesis/subst_k4_2024) "
                        "bisect inside the guilty half."),
        },
        {
            "order": 2, "name": "Y9_2024", "file": _relp(y9), "kind": "candidate-base",
            "base": _relp(BASE_2024),
            "the_ONE_thing_it_tests": (
                "the deepest VIEWS rung: settings + catalog + palette + datum + view "
                "layers at 2024 registrations, WITHOUT the residue rounds or "
                "deletions -- the bisection midpoint between Y7_2024 and G."),
            "if_PASS": "the Y chain is clean; a G FAIL indicts residue/deletions.",
            "if_FAIL": "with Y7_2024 passing, the datum/view layer (Y8/Y9) is indicted.",
        },
        {
            "order": 3, "name": "Y7_2024", "file": _relp(y7), "kind": "candidate-base",
            "base": _relp(BASE_2024),
            "the_ONE_thing_it_tests": (
                "the deepest SETTINGS rung: every settings + catalog + palette "
                "constructor at 2024 registrations -- the shallow bracket of the "
                "bisection."),
            "if_PASS": "the settings half is clean.",
            "if_FAIL": ("even the settings half fails on 2024 -- read the per-half "
                        "probes.json ladder (Y1s_2024 isolates a single object)."),
        },
    ]
    manifest = {
        "stream": "y2024-compose (THE 2024 COMPOSER: tools/genesis_2024_compose.py)",
        "release": 2024,
        "situation": (
            "B2024_K4 (experiments/genesis2024/reduce/B2024_K4.rvt) is viewer-"
            "CERTIFIED (VERDICTS #32: b28 all PASS).  The Y2024 substitution chain "
            "(Y1..Y9 + residue A/B/C + lawful deletions -- rvt.genesis.y2024_a/"
            "y2024_b) is BUILT on it; the composer's 2024 anchor holds (compose of "
            "the nine rung deltas == Y9_2024 byte-identical, see anchor_2024.json). "
            + ("This batch stages the FULL composed candidate G_ABPD_2024 plus the "
               "two chain brackets (Y9_2024, Y7_2024) for one-round bisection."
               if is_full else
               "This batch stages the DEEPEST AVAILABLE composed prefix plus the "
               "two chain brackets.")),
        "base": {"file": _relp(BASE_2024), "certification": base_cert},
        "controls_discipline": (
            "control = byte-identical copy of the CERTIFIED B2024_K4 (probe_batch "
            "mints CTRL_..._b<n>); if the control FAILS the round is VOID and "
            "nothing about the chain is read from it."),
        "upload_order_bisection_first": [e["name"] for e in entries],
        "flip_gate": (
            "The 2024 data flip (registry pin + version-model flag + plugin asset) "
            "is GATED on this batch's viewer verdict AND on the file being the FULL "
            "composition; the exact diff is `tools/genesis_2024_compose.py flipdiff` "
            "and is NOT applied."),
        "probes": entries,
    }
    GC._write_json(os.path.join(OUT_DIR, "probes.json"), manifest)
    log(f"[stage] wrote {_relp(os.path.join(OUT_DIR, 'probes.json'))}")
    # GLOBAL numbering: never reuse a batch number any experiments/ dir carries
    n = PB.HISTORICAL_ROUNDS
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "batch_*.json"),
                       recursive=True):
        m = re.match(r"batch_(\d+)\.json$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    n += 1
    batch = PB.stage_batch(
        [], candidate_bases=cands, control_from=_relp(BASE_2024),
        out_dir=OUT_DIR, batch_n=n,
        note=("2024 compose round (the charter's four-file bisection): control = "
              "byte-identical copy of the CERTIFIED 2024 family-free base B2024_K4; "
              f"candidate-bases = {name} (the "
              f"{'full' if is_full else 'deepest-available'} composed 2024 "
              "candidate), Y9_2024 (deepest views rung) and Y7_2024 (deepest "
              "settings rung), bisection-first.  Batch number = 1 + the highest "
              "batch_N.json anywhere under experiments/.  Read with "
              "probe_batch.read_batch_verdicts; control FAIL voids the round."))
    log(f"[stage] batch {batch['batch']} staged into {_relp(OUT_DIR)}: "
        + ", ".join(batch["reading_order"]))
    return batch


# ---------------------------------------------------------------------------
# 4. THE FINISH LINE, DRY-RUN (the 2025 finishline re-pointed at 2024)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _inmemory_flip(g_path: str):
    """Apply the 2024 flip IN MEMORY ONLY: KNOWN_RELEASES[2024] gains
    creation_certified + genesis_base; the genesis_base.json 2024 slot (the
    already-loaded PIN object) gains sha256/bytes/status.  Restores on exit;
    the on-disk registry and version model are UNTOUCHED."""
    import rvt.versions as V
    from rvt.frontdoor import base as B
    rel = _relp(g_path)
    old_release = V.KNOWN_RELEASES[2024]
    old_supported = V.SUPPORTED_CREATION_RELEASES
    slot = B.PIN.raw["releases"]["2024"]
    old_slot = dict(slot)
    try:
        V.KNOWN_RELEASES[2024] = dataclasses.replace(
            old_release, creation_certified=True, genesis_base=rel)
        V.SUPPORTED_CREATION_RELEASES = frozenset(
            y for y, r in V.KNOWN_RELEASES.items() if r.creation_certified)
        slot["relpath"] = rel
        slot["sha256"] = sha256_of(g_path)
        slot["bytes"] = os.path.getsize(g_path)
        slot["status"] = "certified"
        yield
    finally:
        V.KNOWN_RELEASES[2024] = old_release
        V.SUPPORTED_CREATION_RELEASES = old_supported
        slot.clear()
        slot.update(old_slot)


def finishline(*, full: bool = False, out_dir: Optional[str] = None) -> dict:
    """DRY-RUN of the post-flip front door against the composed G file, with
    the flip applied in memory only: creation_status(2024) / release_status
    (2024) / resolve_base(2024) + an ``author --target-version 2024``
    handoff (``full=True`` runs the whole build).  The result is REPORTED
    (finishline_2024.json), never asserted -- a failure here is the finding,
    not a crash."""
    import tempfile
    import rvt.versions as V
    g = G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL
    if not os.path.exists(g):
        raise SystemExit("no composed G file -- run compose first")
    rep: Dict[str, Any] = {
        "test": ("the 2024 twin of tests/test_target2025.py's END-STATE dry run "
                 "(author --target-version 2024 post-flip)"),
        "mode": ("FULL build (no_handoff)" if full
                 else "handoff-only (resolution + manifest honesty; pass --full "
                      "for the whole build)"),
        "g_file": _relp(g), "g_sha256": sha256_of(g),
        "flip": "IN MEMORY ONLY (nothing on disk changed)",
        "checks": {},
    }
    out_dir = out_dir or tempfile.mkdtemp(prefix="finishline2024_")
    t0 = time.time()
    with _inmemory_flip(g):
        import rvt.frontdoor as FD
        from rvt.frontdoor import base as B
        st = V.creation_status(2024)
        rs = B.release_status(2024)
        rep["checks"]["creation_status_supported"] = bool(st.get("supported"))
        rep["checks"]["release_status_certified"] = bool(rs.get("certified"))
        try:
            rb = B.resolve_base(target_release=2024)
            rep["checks"]["resolve_base"] = {
                "path": _relp(rb.path), "certified": rb.certified,
                "pinned": rb.pinned,
                "detected_release": V.detect_release(rb.path)}
        except Exception as ex:
            rep["checks"]["resolve_base"] = {"error": repr(ex)[:300]}
        try:
            r = FD.author(prompt="a 400 A distribution panel", target_version=2024,
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
            elif full:
                rep["checks"]["output_file"] = "MISSING (build produced no rvt)"
            rep["assertion_status_match"] = (tv.get("status") == "match"
                                             and not tv.get("line"))
        except Exception as ex:
            rep["author"] = {"exception": repr(ex)[:500]}
    rep["seconds"] = round(time.time() - t0, 1)
    passed = (rep.get("assertion_status_match") and
              (not full or (rep["checks"].get("detect_release_of_output") == 2024
                            and rep.get("author", {}).get("ok"))))
    rep["verdict"] = ("WOULD PASS post-flip" if passed else
                      "WOULD FAIL post-flip -- see checks/author for the exact gap")
    GC._write_json(os.path.join(OUT_DIR, "finishline_2024.json"), rep)
    log(f"[finishline] {rep['verdict']} ({rep['mode']}); "
        f"report {_relp(os.path.join(OUT_DIR, 'finishline_2024.json'))}")
    return rep


# ---------------------------------------------------------------------------
# 5. THE FLIP DIFF (printed, NEVER applied -- gated on the viewer verdict)
# ---------------------------------------------------------------------------
def flipdiff() -> str:
    """Print the 2024 data flip as a ready-to-apply diff over the three
    files -- genesis_base.json, rvt/versions, sync_plugin -- with the
    composed file's LIVE sha256/bytes filled in.  The shape is EXACTLY the
    flip applied for 2025 at verdicts #31.  GATE (do not apply until BOTH
    hold): (1) the composition is FULL (G_ABPD_2024.rvt exists), and
    (2) the viewer PASSED it (ledger entry in viewer-certified.json)."""
    g = G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL
    full = (g == G_FINAL)
    cert = GC.certification_of(g) if os.path.exists(g) else None
    sha = sha256_of(g) if os.path.exists(g) else "<sha256 of G_ABPD_2024.rvt>"
    nbytes = os.path.getsize(g) if os.path.exists(g) else "<bytes>"
    md5v = md5_of(g) if os.path.exists(g) else "<md5>"
    rel = _relp(G_FINAL)
    gate = []
    if not full:
        gate.append("composition is PARTIAL (G_partial_2024) -- re-run "
                    "`tools/genesis_2024_compose.py all` after the missing layers "
                    "land, then regenerate this diff")
    if cert is None:
        gate.append("the composed file is NOT in viewer-certified.json -- the "
                    "flip is GATED on its viewer PASS")
    L: List[str] = []
    A = L.append
    A("### THE 2024 DATA FLIP -- ready to apply, NOT applied")
    A("")
    A(f"gate status: {'CLEAR' if not gate else 'BLOCKED: ' + '; '.join(gate)}")
    A(f"values from: {_relp(g)}  sha256 {sha}  md5 {md5v}  bytes {nbytes:,}"
      if isinstance(nbytes, int) else f"values from: {_relp(g)}")
    A("")
    A("--- 1. src/rvt/frontdoor/assets/genesis_base.json (releases.2024) ---")
    A('     "relpath": "experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt",')
    A('-    "sha256": null,')
    A(f'+    "sha256": "{sha}",')
    A('-    "bytes": null,')
    A(f'+    "bytes": {nbytes},')
    A('-    "status": "pending certification",')
    A('+    "status": "certified",')
    A("   (delete the pending_reason line or leave it; release_status reads only "
      "status + sha256 + the version-model flag)")
    A("")
    A("--- 2. src/rvt/versions/__init__.py (KNOWN_RELEASES[2024]) ---")
    A('-        samples_dir="samples/2024", creation_certified=False),')
    A('+        samples_dir="samples/2024", creation_certified=True,')
    A(f'+        genesis_base="{rel}"),')
    A("")
    A("--- 3. tools/sync_plugin.py (bundle the 2024 base beside the 2026/2025 ones;")
    A("       the exact shape of the APPLIED 2025 flip) ---")
    A("after GENESIS_MANIFEST_2025_SRC (~line 76):")
    A('+GENESIS_BASE_2024_SRC = os.path.join(ROOT, "experiments", "genesis",')
    A('+                                     "subst_k4_2024", "compose", "G_ABPD_2024.rvt")')
    A('+GENESIS_MANIFEST_2024_SRC = os.path.join(ROOT, "experiments", "genesis",')
    A('+                                         "subst_k4_2024", "compose",')
    A('+                                         "G_ABPD_2024.manifest.json")')
    A("in asset_mappings(), after the 2025 pair (~line 205):")
    A('+    (GENESIS_BASE_2024_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2024.rvt", True),')
    A('+    (GENESIS_MANIFEST_2024_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2024.compose.json", False),')
    A("")
    A("then: tools/sync_plugin.py (re-sync + re-zip); the front door's")
    A("--target-version 2024 resolves the pinned base (three agreeing sources).")
    A("NOTE (the 2025 finish-line lesson, expected to apply verbatim): the flip")
    A("makes resolution + manifest honest; the FULL 2024 build additionally needs")
    A("whatever build-path work the build2025 stream generalizes (standalone")
    A("allow-list, versions.creating on the build path, famgen port adaptation).")
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
                    help="finishline: run the FULL build (not just the handoff)")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the per-layer assertion battery (never for a real candidate)")
    args = ap.parse_args(argv)
    rc = 0
    if args.cmd in ("anchor", "all"):
        a = prove_anchor_2024(verify=not args.no_verify)
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
        finishline(full=args.full)
    if args.cmd == "flipdiff":
        flipdiff()
    return rc


if __name__ == "__main__":
    sys.exit(main())
