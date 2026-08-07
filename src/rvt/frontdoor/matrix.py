"""rvt.frontdoor.matrix -- THE PERMUTATION MATRIX (machine-readable truth).

THE MANDATE (the user, verbatim intent): "we should be able to create rvt
and rfa files from a prompt alone OR take an ifc file and turn into rvt OR
take a prompt and turn into ifc and then turn into rvt OR ... think of any
permutation. the goal is to be able to handle any and all situations."

So the front door is not three hard-coded routes -- it is a ROUTING MATRIX
over COMPOSABLE STAGES:

    inputs  = any subset of {prompt, ifc, rvt, rfa, spec}   (spec = the
              building/room spec JSON, spec/building.schema.json dialect;
              rfa = a family REQUEST: a famspec JSON {"kind": ...} or a
              .rfa path -- see the rfa cells for the honest input contract)
    outputs = one of {rvt, rfa, ifc}

This module is the machine-readable CAPABILITY TRUTH TABLE:

* :data:`STAGES`   -- every composable stage, its implementation (dotted
  ``module:callable``, resolved lazily -- importing this module stays
  cheap) and its runnable evidence;
* :data:`CELLS`    -- every meaningful (inputs, output) cell with an HONEST
  status (``works`` / ``partial`` / ``missing`` -- never a claimed cell
  without runnable evidence), the stage chain that composes it, the
  evidence cited, and the caveats that ride every delivery;
* :data:`CHAINS`   -- the named multi-hop routes (prompt->ifc->rvt, ...)
  selectable via ``opts['via']``;
* :func:`cell_for` / :func:`closest_supported` / :func:`describe_cell` --
  the lookups the router (:mod:`rvt.frontdoor.router`) uses, including the
  one-clear-line answer for unsupported cells;
* :func:`verify_evidence` -- the self-audit: every cited test file /
  worked-example path exists and every ``certified:`` citation is really
  in ``docs/coverage/viewer-certified.json``.  ``tests/test_router.py``
  runs it, so a stale claim FAILS the suite instead of surviving in prose.

The user-facing rendering of this table is
``docs/product/PERMUTATION-MATRIX.md``; ``tools/route.py matrix`` prints
the live version.  Territory: perm-matrix stream (new module; imports
existing stages, edits none of them).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "INPUT_KINDS", "OUTPUT_KINDS", "STATUS_WORKS", "STATUS_PARTIAL",
    "STATUS_MISSING", "Stage", "Cell", "STAGES", "CELLS", "CHAINS",
    "key_for", "cell_for", "all_cells", "closest_supported", "describe_cell",
    "unsupported_line", "verify_evidence", "matrix_rows",
]

INPUT_KINDS = ("prompt", "ifc", "rvt", "rfa", "spec")
OUTPUT_KINDS = ("rvt", "rfa", "ifc")

STATUS_WORKS = "works"        # runnable end to end today; evidence cited
STATUS_PARTIAL = "partial"    # mechanism runs with a NAMED caveat/scope gap
STATUS_MISSING = "missing"    # not implemented; clear message + closest route


def _root() -> str:
    from .base import repo_root
    return repo_root()


# ===========================================================================
# STAGES -- the composable pieces (implementations resolved lazily)
# ===========================================================================

@dataclass(frozen=True)
class Stage:
    """One composable stage: what it does, where it lives, what proves it."""
    id: str
    impl: str                  # dotted "module:callable" or "tool:path" note
    does: str
    evidence: Tuple[str, ...] = ()


STAGES: Dict[str, Stage] = {s.id: s for s in [
    Stage("prompt->intent", "rvt.frontdoor.prompt_intent:prompt_to_intent",
          "rules-first deterministic prompt parser -> the ONE IntentModel "
          "(no external model call, no API key); coverage reported honestly",
          ("test:tests/test_frontdoor.py",
           "worked:experiments/frontdoor/prompt-electrical-room/manifest.json")),
    Stage("prompt->handoff", "rvt.frontdoor.prompt_intent:write_handoff",
          "the PRIMARY AI-surface path: scene-brief.json + HANDOFF.md + "
          "PROMPT_TO_IFC.md (any surface executes with Three.js -> IFC4 -> "
          "back through the ifc input)",
          ("test:tests/test_frontdoor.py",
           "worked:experiments/frontdoor/prompt-electrical-room/scene-brief.json")),
    Stage("ifc->intent", "rvt.frontdoor.intent:intent_from_ifc",
          "rvt.ifc.intent resolver: placement chains + world geometry + the "
          "tagging-contract Pset join key -> IntentModel",
          ("test:tests/test_ifc_intent.py",
           "certified:experiments/acceptance/V25_room_from_ifc.rvt")),
    Stage("intent->rvt", "rvt.frontdoor:author",
          "the build step on the CERTIFIED GENESIS BASE (families F, load L, "
          "walls W, equipment E, circuits C plan, gates V) with the honest "
          "walls+families degrade (stamp / --strict split)",
          ("test:tests/test_frontdoor.py",
           "certified:experiments/ifc_room/electrical_room_2500a_walls_only.rvt",
           "certified:experiments/ifc_room/stage_L8_lp4.rvt",
           "certified:experiments/render/RSOLID_walls_A_solid.rvt")),
    Stage("intent->ifc", "rvt.frontdoor.ifc_out:write_intent_ifc",
          "deterministic IFC4 emitter of the SAME intent (version-agnostic; "
          "round-trips through our own ifc->intent resolver)",
          ("test:tests/test_target2025.py",)),
    Stage("intent->rfa", "rvt.frontdoor.build:load_ifc_room_module",
          "stage_families: the intent's family plans -> OUR generated .rfa "
          "files (rvt.famgen.factory catalog products + the honest house "
          "switchboard; zero donors)",
          ("test:tests/test_famgen_factory.py",
           "worked:experiments/frontdoor/prompt-electrical-room/families")),
    Stage("rvt-edit", "rvt.frontdoor.edit:run_edit",
          "the certified edit pipeline (tools/rvt_job.py edit via "
          "rvt.manipulate + rvt.mutate): modify / move / retype / delete / "
          "cascade / add-instance / add-circuit, NL or ops.json",
          ("test:tests/test_manipulate.py",
           "certified:experiments/manipulate/M3_modify.rvt",
           "certified:experiments/manipulate/M4_move_retype.rvt",
           "certified:experiments/manipulate/M2_delete_cascade.rvt",
           "certified:experiments/manipulate/M2_delete_cascade_rac.rvt")),
    Stage("ifc->facts", "rvt.ifc.product_facts:extract_product_facts",
          "measure a PRODUCT IFC into ProductFacts (dims, parts, psets)",
          ("test:tests/test_ifc_family.py",)),
    Stage("facts->rfa", "rvt.ifc.famfrom_ifc:make_downlight",
          "compose OUR family from measured facts (the recessed-downlight "
          "archetype; assay-clean emit_family_rfa_v2)",
          ("test:tests/test_ifc_family.py",
           "certified:experiments/families/ifc/L_downlight_loaded.rvt")),
    Stage("rfa-load", "rvt.ifc.famfrom_ifc:load_into_project",
          "the certified FOUR-REGISTRY loader (rvt.famload, L1a mechanism): "
          "our family document becomes an embedded save unit + "
          "ContentDocuments + ContentTable + FamilyMgr entries + host "
          "Family/Symbol/surrogates/twins",
          ("test:tests/test_famload.py",
           "certified:experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt",
           "certified:experiments/families/ifc/L_downlight_loaded.rvt")),
    Stage("spec->ifc", "tool:skills/tekton-ifc/scripts/generate_ifc.py",
          "deterministic building-spec JSON -> IFC4 (levels, walls, "
          "openings, equipment with the tagging-contract psets)",
          ("worked:usecases/chicago-plenum-electrical-room/generated.ifc",
           "worked:skills/tekton-ifc/tests")),
    Stage("spec->rvt-legacy", "tool:tools/rvt_job.py",
          "rvt_job.py create --spec: the job runner's gated spec build on a "
          "template/seed project (seed audit; hard gates; manifest)",
          ("test:tests/test_job.py",
           "certified:experiments/acceptance/V23_electrical_room.rvt")),
    Stage("rvt-read", "rvt.frontdoor.edit:editables",
          "open any .rvt file-driven (rvt.mutate.Document.from_file) and "
          "inventory the editable surface (instances/walls/levels/circuits)",
          ("test:tests/test_inventory.py", "test:tests/test_manipulate.py")),
    Stage("release-detect", "rvt.versions:detect_release",
          "detect the Revit release of any .rvt/.rfa; version fallbacks are "
          "honest, never silent",
          ("test:tests/test_versions.py",)),
]}


# ===========================================================================
# CELLS -- the truth table
# ===========================================================================

@dataclass(frozen=True)
class Cell:
    """One (inputs, output) capability cell."""
    inputs: Tuple[str, ...]              # sorted input kinds
    output: str
    status: str                          # works | partial | missing
    route: Optional[str]                 # router route-id (None when missing)
    stages: Tuple[str, ...] = ()         # STAGES ids, in execution order
    evidence: Tuple[str, ...] = ()       # test:/certified:/worked:/record: refs
    caveats: Tuple[str, ...] = ()        # honest caveats that ride the delivery
    missing_reason: Optional[str] = None
    closest: Optional[Tuple[Tuple[str, ...], str]] = None   # nearest supported cell
    hint: Optional[str] = None           # one-line human hint for closest/missing

    def key(self) -> Tuple[Tuple[str, ...], str]:
        return (self.inputs, self.output)

    def as_json(self) -> Dict[str, Any]:
        return {
            "inputs": list(self.inputs), "output": self.output,
            "status": self.status, "route": self.route,
            "stages": list(self.stages), "evidence": list(self.evidence),
            "caveats": list(self.caveats), "missing_reason": self.missing_reason,
            "closest": (None if self.closest is None
                        else {"inputs": list(self.closest[0]), "output": self.closest[1]}),
            "hint": self.hint,
        }


def key_for(inputs: Sequence[str], output: str) -> Tuple[Tuple[str, ...], str]:
    return (tuple(sorted(set(inputs))), str(output))


_PROOF_ONLY = ("every output is PROOF-ONLY, NOT-DELIVERABLE until TRACKER "
               "gates G2/G3 clear (docs/product/content-strategy.md); the "
               "manifest says so explicitly")
_OPEN_BUG = ("walls + loaded families in ONE file is the OPEN BUG (r2): the "
             "combined file is STAMPED 'PROOF-ONLY: walls+families "
             "combination unverified'; --strict emits two coordinated "
             "certified-shape files instead")
_CIRCUITS = ("feeder CIRCUITS are a NAMED BLOCKER on the genesis base: the "
             "resolved circuit plan rides in the manifest, never faked")
_CATALOG = ("family generation covers the catalog-backed kinds (panelboard / "
            "transformer / luminaire / the honest house switchboard); "
            "anything without facts is REFUSED by name, never invented")

_CELL_LIST: List[Cell] = [
    # ---------------- singles: prompt ----------------
    Cell(("prompt",), "rvt", STATUS_WORKS, "prompt_to_rvt",
         ("prompt->intent", "prompt->handoff", "intent->rvt"),
         ("worked:experiments/frontdoor/prompt-electrical-room/manifest.json",
          "test:tests/test_frontdoor.py",
          "certified:experiments/ifc_room/electrical_room_2500a_walls_only.rvt",
          "certified:experiments/ifc_room/stage_L8_lp4.rvt"),
         (_OPEN_BUG, _CIRCUITS, _PROOF_ONLY),
         hint="alternate chain: via='ifc' runs prompt->ifc->rvt (the handoff round trip)"),
    Cell(("prompt",), "ifc", STATUS_WORKS, "prompt_to_ifc",
         ("prompt->intent", "intent->ifc"),
         ("test:tests/test_target2025.py", "test:tests/test_frontdoor.py"),
         ("the IFC is version-agnostic and re-enters via the ifc input "
          "(round-trip proven by tests/test_target2025.py)",)),
    Cell(("prompt",), "rfa", STATUS_WORKS, "prompt_to_rfa",
         ("prompt->intent", "intent->rfa"),
         ("worked:experiments/frontdoor/prompt-electrical-room/families",
          "test:tests/test_famgen_factory.py", "test:tests/test_frontdoor.py"),
         (_CATALOG, _PROOF_ONLY)),
    # ---------------- singles: ifc ----------------
    Cell(("ifc",), "rvt", STATUS_WORKS, "ifc_to_rvt",
         ("ifc->intent", "intent->rvt"),
         ("certified:experiments/acceptance/V25_room_from_ifc.rvt",
          "certified:experiments/acceptance/V26_room_from_ifc_with_walls.rvt",
          "worked:experiments/frontdoor/ifc-electrical-room-2500a/manifest.json",
          "test:tests/test_ifc_intent.py"),
         (_OPEN_BUG, _CIRCUITS, _PROOF_ONLY),
         hint=("a PRODUCT IFC (one measured product, no room) auto-falls back "
               "to the family chain: ifc->facts->rfa->loaded rvt")),
    Cell(("ifc",), "ifc", STATUS_WORKS, "ifc_normalize",
         ("ifc->intent", "intent->ifc"),
         ("test:tests/test_target2025.py", "test:tests/test_ifc_intent.py"),
         ("normalisation into OUR tagging-contract IFC dialect; content "
          "outside the resolved intent (finishes, annotations, non-contract "
          "psets) does not survive the round trip",)),
    Cell(("ifc",), "rfa", STATUS_WORKS, "ifc_to_rfa",
         ("ifc->intent", "intent->rfa", "ifc->facts", "facts->rfa"),
         ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
          "test:tests/test_ifc_family.py", "test:tests/test_ifc_intent.py"),
         ("ROOM IFCs yield catalog families for their tagged equipment "
          "(intent->rfa); PRODUCT IFCs are measured into facts and composed "
          "as the downlight archetype (the one facts->rfa archetype wired)",
          _CATALOG)),
    # ---------------- singles: rvt ----------------
    Cell(("rvt",), "rvt", STATUS_MISSING, None, (),
         (), (),
         missing_reason=("an .rvt alone with .rvt output is a no-op copy: an "
                         "EDIT needs instructions"),
         closest=(("prompt", "rvt"), "rvt"),
         hint="add a prompt (edit sentence or ops.json): prompt+rvt -> rvt"),
    Cell(("rvt",), "ifc", STATUS_MISSING, None, (),
         ("test:tests/test_inventory.py",), (),
         missing_reason=("no RVT->intent resolver exists yet: tekton READS "
                         ".rvt (inventory / editables / families) but does "
                         "not lift project geometry back into the intent "
                         "model, so nothing feeds the IFC emitter"),
         closest=(("prompt",), "ifc"),
         hint=("inspect the file with tools/rvt_edit.py info; author the IFC "
               "from the source prompt/spec instead")),
    Cell(("rvt",), "rfa", STATUS_MISSING, None, (),
         (), (),
         missing_reason=("family EXTRACTION from a project is not implemented "
                         "-- and extracting a third-party family would "
                         "redistribute vendor bytes, which the content rule "
                         "(docs/product/content-strategy.md) forbids; OUR "
                         "families are regenerable from their plans instead"),
         closest=(("prompt",), "rfa"),
         hint="regenerate the family from its facts: prompt->rfa / spec->rfa"),
    # ---------------- singles: rfa ----------------
    Cell(("rfa",), "rvt", STATUS_WORKS, "famspec_load",
         ("facts->rfa", "rfa-load"),
         ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
          "certified:experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt",
          "test:tests/test_ifc_family.py", "test:tests/test_famload.py"),
         ("INPUT CONTRACT: a famspec JSON ({'kind': 'downlight', ...}) -- "
          "the family is REBUILT by its constructor and loaded through the "
          "certified four-registry loader; a bare foreign .rfa path is "
          "REFUSED with this row (no .rfa-from-disk reload exists yet)",
          "kind='downlight' is the certified load archetype; catalog kinds "
          "(panelboard/transformer/luminaire) load through the room "
          "pipeline (prompt/ifc -> rvt), not this cell yet",
          "default host = the loader-certified rst sample host; pass rvt to "
          "load into your own project (see the rfa+rvt cell)",
          _PROOF_ONLY)),
    Cell(("rfa",), "ifc", STATUS_MISSING, None, (),
         (), (),
         missing_reason="no family->IFC product emitter exists yet",
         closest=(("prompt",), "ifc"),
         hint="author the product IFC from its facts: prompt->ifc / spec->ifc"),
    Cell(("rfa",), "rfa", STATUS_MISSING, None, (),
         (), (),
         missing_reason=("an .rfa alone with .rfa output is a no-op; family "
                         "MODIFICATION needs instructions and the family-edit "
                         "pipeline is not built (see prompt+rfa)"),
         closest=(("prompt",), "rfa"),
         hint="regenerate from changed facts: prompt->rfa"),
    # ---------------- singles: spec ----------------
    Cell(("spec",), "rvt", STATUS_WORKS, "spec_to_rvt",
         ("spec->ifc", "ifc->intent", "intent->rvt"),
         ("worked:usecases/chicago-plenum-electrical-room/generated.ifc",
          "certified:experiments/acceptance/V23_electrical_room.rvt",
          "test:tests/test_job.py", "test:tests/test_ifc_intent.py"),
         ("canonical route = the chain spec->ifc->rvt on the certified "
          "genesis base; the LEGACY direct build (tools/rvt_job.py create "
          "--spec, V23-certified) authors on a template/seed project and "
          "remains available as spec+rvt",
          _OPEN_BUG, _PROOF_ONLY)),
    Cell(("spec",), "ifc", STATUS_WORKS, "spec_to_ifc",
         ("spec->ifc",),
         ("worked:usecases/chicago-plenum-electrical-room/generated.ifc",
          "worked:skills/tekton-ifc/tests"),
         ("deterministic: identical spec -> byte-identical IFC",)),
    Cell(("spec",), "rfa", STATUS_WORKS, "spec_to_rfa",
         ("spec->ifc", "ifc->intent", "intent->rfa"),
         ("worked:experiments/frontdoor/prompt-electrical-room/families",
          "test:tests/test_famgen_factory.py", "test:tests/test_ifc_intent.py"),
         ("the spec's tagged equipment maps to catalog family plans through "
          "the tagging contract; " + _CATALOG,)),
    # ---------------- combinations ----------------
    Cell(("prompt", "rvt"), "rvt", STATUS_WORKS, "rvt_edit",
         ("rvt-read", "rvt-edit"),
         ("certified:experiments/manipulate/M3_modify.rvt",
          "certified:experiments/manipulate/M4_move_retype.rvt",
          "certified:experiments/manipulate/M2_delete_cascade.rvt",
          "certified:experiments/manipulate/M2_delete_cascade_rac.rvt",
          "worked:experiments/frontdoor/rvt-edit-room/manifest.json",
          "test:tests/test_manipulate.py", "test:tests/test_frontdoor.py"),
         ("the prompt is the EDIT (an edit sentence, ops.json path, or "
          "inline JSON); certified including on a FOREIGN file (M2_rac)",
          "a prompt that is NOT edit-shaped but IS authoring-shaped falls "
          "back to building the new content with your .rvt as the BASE -- "
          "that branch is PARTIAL: the certified stage code + gates run, "
          "but no viewer certification exists on arbitrary bases")),
    Cell(("ifc", "rvt"), "rvt", STATUS_PARTIAL, "ifc_onto_rvt",
         ("ifc->intent", "intent->rvt"),
         ("test:tests/test_frontdoor.py", "test:tests/test_ifc_intent.py"),
         ("MERGE = the IFC intent is built with YOUR .rvt as the base "
          "(Autodesk samples refused); the certified stage code + all gates "
          "run, but no viewer certification exists on foreign bases -- the "
          "genesis base is the certified base",
          _OPEN_BUG, _PROOF_ONLY),
         hint="drop the rvt to build on the certified genesis base instead"),
    Cell(("prompt", "rfa"), "rfa", STATUS_MISSING, None, (),
         (), (),
         missing_reason=("FAMILY MODIFICATION (open an .rfa, apply a prompt, "
                         "re-emit) is not built: no family-edit pipeline "
                         "exists (families are generated, not edited)"),
         closest=(("prompt",), "rfa"),
         hint=("regenerate the family from its facts with the change in the "
               "prompt: prompt->rfa")),
    Cell(("rfa", "rvt"), "rvt", STATUS_PARTIAL, "famspec_load",
         ("facts->rfa", "rfa-load"),
         ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
          "certified:experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt",
          "certified:experiments/ifc_room/stage_L8_lp4.rvt",
          "test:tests/test_famload.py"),
         ("LOAD the famspec-rebuilt family into YOUR project through the "
          "certified four-registry loader; the loader is viewer-certified "
          "on the rst host and the genesis lineage -- on an arbitrary host "
          "the same mechanism + census/validator gates run without viewer "
          "evidence, hence PARTIAL",
          "famspec contract as in the rfa->rvt cell (kind='downlight' "
          "wired; bare foreign .rfa refused with this row)",
          _PROOF_ONLY)),
    Cell(("ifc", "prompt"), "rvt", STATUS_PARTIAL, "ifc_build_then_edit",
         ("ifc->intent", "intent->rvt", "rvt-read", "rvt-edit"),
         ("test:tests/test_ifc_intent.py", "test:tests/test_manipulate.py"),
         ("the IFC is built first (ifc->rvt), then the prompt is applied as "
          "an EDIT to the result -- a composition of two proven stages with "
          "no single-artifact certification of its own, hence PARTIAL",
          "a prompt that is NOT edit-shaped cannot merge into the IFC's "
          "intent yet (intent-level merge is not built) -- the route fails "
          "with the edit grammar rather than guessing")),
    Cell(("rvt", "spec"), "rvt", STATUS_WORKS, "spec_on_rvt_seed",
         ("spec->rvt-legacy",),
         ("certified:experiments/acceptance/V23_electrical_room.rvt",
          "test:tests/test_job.py"),
         ("the job runner's CREATE mode: your .rvt is the SEED/TEMPLATE "
          "(seed audit reports gaps; hard gates structural/validation/"
          "identity run; manifest written beside the output)",
          "authored content clones the seed's loaded types -- the output is "
          "ledgered against that seed: PROOF-ONLY vs whatever you supply")),
]

CELLS: Dict[Tuple[Tuple[str, ...], str], Cell] = {c.key(): c for c in _CELL_LIST}

#: named multi-hop routes, selectable via opts['via'] on the router
CHAINS: Dict[str, Dict[str, Any]] = {
    "prompt->ifc->rvt": {
        "via": "ifc", "cell": key_for(("prompt",), "rvt"),
        "route": "prompt_via_ifc_to_rvt",
        "stages": ("prompt->intent", "intent->ifc", "ifc->intent", "intent->rvt"),
        "status": STATUS_WORKS,
        "note": ("the handoff round trip run in-process: the prompt's intent "
                 "is emitted as IFC, then that IFC re-enters the ifc route; "
                 "proves the two legs compose (tests/test_target2025.py "
                 "round-trips the emitter against the resolver)"),
        "evidence": ("test:tests/test_target2025.py",
                     "test:tests/test_frontdoor.py"),
    },
    "spec->ifc->rvt": {
        "via": None, "cell": key_for(("spec",), "rvt"),
        "route": "spec_to_rvt",
        "stages": ("spec->ifc", "ifc->intent", "intent->rvt"),
        "status": STATUS_WORKS,
        "note": "the canonical spec route (see the spec->rvt cell)",
        "evidence": ("worked:usecases/chicago-plenum-electrical-room/generated.ifc",),
    },
    "ifc->rfa->loaded-rvt": {
        "via": "family", "cell": key_for(("ifc",), "rvt"),
        "route": "ifc_family_load",
        "stages": ("ifc->facts", "facts->rfa", "rfa-load"),
        "status": STATUS_WORKS,
        "note": ("a PRODUCT IFC measured into facts, composed as our family, "
                 "loaded four-registry into the certified host -- the "
                 "L_downlight_loaded pipeline"),
        "evidence": ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
                     "test:tests/test_ifc_family.py"),
    },
    "prompt->rfa->loaded-rvt": {
        "via": None, "cell": key_for(("prompt",), "rvt"),
        "route": "prompt_to_rvt",
        "stages": ("prompt->intent", "intent->rfa", "rfa-load", "intent->rvt"),
        "status": STATUS_WORKS,
        "note": ("this chain IS the F/L stages inside prompt->rvt: the "
                 "families are generated, loaded onto the base, then placed"),
        "evidence": ("certified:experiments/ifc_room/stage_L8_lp4.rvt",),
    },
}


# ===========================================================================
# lookups
# ===========================================================================

def cell_for(inputs: Sequence[str], output: str) -> Optional[Cell]:
    """The exact cell, or None (the router then answers with
    :func:`unsupported_line` -- never a traceback)."""
    return CELLS.get(key_for(inputs, output))


def all_cells() -> List[Cell]:
    return list(_CELL_LIST)


def closest_supported(inputs: Sequence[str], output: str) -> Optional[Cell]:
    """The nearest works/partial cell: same output preferred, maximal input
    overlap, minimal extra inputs; deterministic tie-break."""
    want = set(inputs)
    best: Optional[Tuple[Tuple[int, int, int, int], Cell]] = None
    for c in _CELL_LIST:
        if c.status == STATUS_MISSING:
            continue
        have = set(c.inputs)
        score = (0 if c.output == output else 1,          # same output first
                 -len(want & have),                        # overlap (more = better)
                 len(have - want),                         # fewer new inputs
                 0 if c.status == STATUS_WORKS else 1)     # works over partial
        k = (score, tuple(c.inputs), c.output)
        if best is None or k < (best[0], tuple(best[1].inputs), best[1].output):
            best = (score, c)
    return best[1] if best else None


def describe_cell(c: Cell) -> str:
    """One line: '<inputs> -> <output>: <status> (<route|reason>)'."""
    ins = "+".join(c.inputs)
    if c.status == STATUS_MISSING:
        return f"{ins} -> {c.output}: MISSING -- {c.missing_reason}"
    tag = "" if c.status == STATUS_WORKS else " [PARTIAL]"
    return f"{ins} -> {c.output}: {c.status}{tag} via {c.route} ({' -> '.join(c.stages)})"


def unsupported_line(inputs: Sequence[str], output: str) -> str:
    """THE one clear line for an unsupported/missing cell: the matrix row +
    the closest supported route."""
    ins = "+".join(sorted(set(inputs))) or "(no input)"
    c = cell_for(inputs, output)
    near = None
    if c is not None and c.closest is not None:
        near = CELLS.get(c.closest)
    if near is None:
        near = closest_supported(inputs, output)
    if c is not None and c.status == STATUS_MISSING:
        head = f"{ins} -> {output} is not supported yet: {c.missing_reason}."
        hint = f" {c.hint}." if c.hint else ""
    else:
        head = (f"{ins} -> {output} is not a cell of the permutation matrix "
                f"(inputs {', '.join(INPUT_KINDS)}; outputs {', '.join(OUTPUT_KINDS)}).")
        hint = ""
    if near is not None:
        head += (f" Closest supported route: {'+'.join(near.inputs)} -> "
                 f"{near.output} ({near.status}, route '{near.route}').")
    return head + hint


# ===========================================================================
# the honest-evidence self-audit
# ===========================================================================

def _ledger() -> Dict[str, Any]:
    p = os.path.join(_root(), "docs", "coverage", "viewer-certified.json")
    with open(p) as fh:
        return json.load(fh)


def verify_evidence() -> List[str]:
    """Audit every citation in STAGES/CELLS/CHAINS.  Returns problems (empty
    = every cited test/worked path exists and every certified citation is in
    the viewer ledger's CERTIFIED list).  tests/test_router.py asserts []."""
    problems: List[str] = []
    root = _root()
    try:
        certified = {e.get("file") for e in _ledger().get("certified", [])}
    except Exception as e:                                       # noqa: BLE001
        return [f"cannot read viewer-certified.json: {type(e).__name__}: {e}"]

    def check(ref: str, where: str) -> None:
        if ":" not in ref:
            problems.append(f"{where}: malformed evidence ref {ref!r}")
            return
        kind, path = ref.split(":", 1)
        if kind == "certified":
            if path not in certified:
                problems.append(f"{where}: {path} is NOT in the certified ledger")
            if not os.path.exists(os.path.join(root, path)):
                problems.append(f"{where}: certified file missing on disk: {path}")
        elif kind in ("test", "worked", "record"):
            if not os.path.exists(os.path.join(root, path)):
                problems.append(f"{where}: cited path does not exist: {path}")
        else:
            problems.append(f"{where}: unknown evidence kind {kind!r} in {ref!r}")

    for s in STAGES.values():
        for ref in s.evidence:
            check(ref, f"stage {s.id}")
    for c in _CELL_LIST:
        if c.status in (STATUS_WORKS, STATUS_PARTIAL) and not c.evidence:
            problems.append(f"cell {c.key()}: status {c.status} with NO evidence")
        for ref in c.evidence:
            check(ref, f"cell {'+'.join(c.inputs)}->{c.output}")
        for sid in c.stages:
            if sid not in STAGES:
                problems.append(f"cell {c.key()}: unknown stage {sid!r}")
        if c.status == STATUS_MISSING:
            if not c.missing_reason:
                problems.append(f"cell {c.key()}: missing without a reason")
            if c.closest is not None and c.closest not in CELLS:
                problems.append(f"cell {c.key()}: closest {c.closest} not a cell")
            elif c.closest is not None and CELLS[c.closest].status == STATUS_MISSING:
                problems.append(f"cell {c.key()}: closest {c.closest} is itself missing")
    for name, ch in CHAINS.items():
        if ch["cell"] not in CELLS:
            problems.append(f"chain {name}: cell {ch['cell']} not in CELLS")
        for sid in ch["stages"]:
            if sid not in STAGES:
                problems.append(f"chain {name}: unknown stage {sid!r}")
        for ref in ch.get("evidence", ()):
            check(ref, f"chain {name}")
    return problems


# ===========================================================================
# rendering (tools/route.py matrix; the .md is the committed rendering)
# ===========================================================================

def matrix_rows() -> List[Dict[str, Any]]:
    """Rows for the truth table: singles first, then combinations."""
    def order(c: Cell) -> Tuple[int, int, str, str]:
        return (len(c.inputs), INPUT_KINDS.index(c.inputs[0]) if c.inputs else 9,
                "+".join(c.inputs), c.output)
    return [c.as_json() for c in sorted(_CELL_LIST, key=order)]


def as_json() -> Dict[str, Any]:
    return {
        "inputs": list(INPUT_KINDS), "outputs": list(OUTPUT_KINDS),
        "stages": {k: {"impl": s.impl, "does": s.does, "evidence": list(s.evidence)}
                   for k, s in STAGES.items()},
        "cells": matrix_rows(),
        "chains": {k: {kk: (list(vv) if isinstance(vv, tuple) else vv)
                       for kk, vv in ch.items()} for k, ch in CHAINS.items()},
        "fallback": ("any (inputs, output) not in `cells` is answered with "
                     "the matrix row + the closest supported route in ONE "
                     "clear line -- never a traceback"),
    }
