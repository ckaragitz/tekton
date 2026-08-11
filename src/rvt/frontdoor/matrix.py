"""rvt.frontdoor.matrix -- THE PERMUTATION MATRIX (machine-readable truth).

THE MANDATE (the user, verbatim intent): "we should be able to create rvt
and rfa files from a prompt alone OR take an ifc file and turn into rvt OR
take a prompt and turn into ifc and then turn into rvt OR ... think of any
permutation. the goal is to be able to handle any and all situations."

So the front door is not three hard-coded routes -- it is a ROUTING MATRIX
over COMPOSABLE STAGES:

    inputs  = any subset of {prompt, ifc, rvt, rfa, spec}   (spec = the
              building/room spec JSON, spec/building.schema.json dialect;
              rfa = a family REQUEST: a famspec JSON {"kind": ...} -- the
              written contract is spec/famspec.schema.json -- or a .rfa
              path; see the rfa cells for the honest input contract)
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
  :func:`audit` classifies the result (hard problems vs certified probe
  binaries that are merely absent on a fresh clone -- the ledger, not the
  git-ignored ``experiments/`` binaries, is the certification authority);
  :func:`render_text` is the one printer both ``tools/route.py matrix`` and
  ``tools/frontdoor.py matrix`` use.

The user-facing rendering of this table is
``docs/product/PERMUTATION-MATRIX.md``; ``tools/route.py matrix`` prints
the live version.  Territory: perm-matrix stream (new module; imports
existing stages, edits none of them).  2026-08-09 (issue #5): the
``rvt.convert`` implementations registered (rvt->ifc, rvt->rfa extract,
prompt+rfa family edits, prompt+rvt add-into-project, ifc+rvt merge, the
extracted-.rfa reload lane) and the certified any-.rfa-load (T2a) /
extract->place (TB0g) depths cited on the rfa cells.  Issue #162: the
famspec contract written down (spec/famspec.schema.json), rfa -> rfa
flipped to WORKS (famspec -> our .rfa for all four kinds) and the famspec
lane of rfa[+rvt] -> rvt widened from downlight-only to every kind.
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "INPUT_KINDS", "OUTPUT_KINDS", "STATUS_WORKS", "STATUS_PARTIAL",
    "STATUS_MISSING", "Stage", "Cell", "STAGES", "CELLS", "CHAINS",
    "key_for", "cell_for", "all_cells", "closest_supported", "describe_cell",
    "unsupported_line", "verify_evidence", "audit", "matrix_rows",
    "status_counts", "render_text", "LEDGER_RELPATH", "ABSENT_BINARY_MARK",
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
          "open-cell degrade (placed instances: stamp / --strict split)",
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
    Stage("prompt->archetype", "rvt.famgen.archetypes:resolve_prompt",
          "a prompt naming a product the ARCHETYPE registry GENERATES (cable "
          "tray, strut channel, wireway, junction box, conduit) -> the LOD-400 "
          "part list at standard NOMINAL sizes for that product class, every "
          "dimension reported nominal (generated) or given (the prompt stated "
          "it); no manufacturer identity is ever attached, so a named "
          "manufacturer's part is still refused",
          ("test:tests/test_famgen_archetypes.py",
           "record:docs/inbox/prompt-archetypes.md")),
    Stage("rvt-edit", "rvt.frontdoor.edit:run_edit",
          "the certified edit pipeline (tools/rvt_job.py edit via "
          "rvt.manipulate + rvt.mutate): modify / move / retype / delete / "
          "cascade / add-instance / add-circuit, NL or ops.json",
          ("test:tests/test_manipulate.py",
           "certified:experiments/manipulate/M3_modify.rvt",
           "certified:experiments/manipulate/M4_move_retype.rvt",
           "certified:experiments/manipulate/M2_delete_cascade.rvt",
           "certified:experiments/manipulate/M2_delete_cascade_rac.rvt")),
    Stage("famspec->rfa", "rvt.frontdoor.famspec:build (rvt.famgen.factory:make_panelboard "
                          "| make_transformer | make_luminaire | make_device; "
                          "rvt.ifc.famfrom_ifc:make_downlight)",
          "a famspec JSON ({'kind': ..., <the constructor's kwargs>} -- the "
          "written contract spec/famspec.schema.json, validated stdlib-only, "
          "typos answered in one clear line) -> OUR standalone .rfa through the "
          "kind's constructor + FamilyProduct.write (family-mode validator, "
          "provenance scan, --target-version release context); zero donors",
          ("test:tests/test_router.py", "test:tests/test_famgen_factory.py",
           "worked:spec/famspec.schema.json", "worked:spec/examples/famspec-panelboard.json",
           "record:docs/inbox/famspec-contract.md")),
    Stage("ifc->facts", "rvt.ifc.product_facts:extract_product_facts",
          "measure a PRODUCT IFC into ProductFacts (dims, parts, psets)",
          ("test:tests/test_ifc_family.py",)),
    Stage("ifc->parts", "rvt.ifc.assembly_parts:read_assembly",
          "measure EVERY tessellated product of an arbitrary-geometry IFC "
          "(no catalog identity, no archetype) into prismatic solids -- the "
          "plan hull fitted to a cylinder / box / N-gon, extruded over the "
          "mesh's Z extent, placement chain applied, per-part 'fill' "
          "(mesh volume / prism volume) reported so the massing's fidelity "
          "is a number; feeds make_generic_model(parts=...)",
          ("test:tests/test_ifc_assembly.py",
           "record:docs/inbox/ifc-assembly-rfa.md")),
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
    # ---- the rvt.convert stages (convert-a: export/extract; convert-b:
    #      creating INTO existing files) -- registered 2026-08-09, issue #5 --
    Stage("rvt->intent", "rvt.convert.rvt_to_ifc:extract_intent",
          "read a project's CONTENT back out of the .rvt into the intent "
          "shape (levels; straight walls; electrical equipment with position + "
          "frame + the tagging-contract values from its family document; "
          "feeder edges) -- rvt.mutate + rvt.inventory + rvt.families, no "
          "Revit involved",
          ("test:tests/test_convert.py",
           "worked:experiments/convert/rvt-to-ifc/electrical_room_prompt.manifest.json",
           "record:docs/inbox/convert-a.md")),
    Stage("rvt->rfa", "rvt.convert.extract_family:extract_family",
          "lift ONE embedded family document out of a project into a "
          "standalone .rfa: the unit's records carried VERBATIM, the "
          "container scaffolding re-authored by our writers "
          "(rvt.convert.rfa_assemble), family-mode validator gate; nested "
          "family documents refused by name",
          ("test:tests/test_convert.py",
           "worked:experiments/convert/extract-family/DP1_reextracted.manifest.json",
           "record:docs/inbox/convert-a.md")),
    Stage("rfa-reload", "rvt.convert.extract_family:reload_family",
          "a standalone .rfa ON DISK -> RfaFamilyDoc -> the four-registry "
          "COMPONENT loader (rvt.famgen.loader, the stage_L8 mechanism) into a "
          "copy of the host; the family's element ids must clear the host's "
          "id watermark (a tekton-EXTRACTED family does by construction)",
          ("test:tests/test_convert.py",
           "worked:experiments/convert/extract-family/DP1_reextracted.reloaded.rvt.load.json",
           "certified:experiments/ifc_room/stage_L8_lp4.rvt")),
    # ---- issue #99: the standalone-born .rfa lane (T2a product-wired) ----
    Stage("rfa-classify", "rvt.convert.rfa_load:is_standalone_born",
          "the id law that picks the .rfa lane: family id floor vs host "
          "ElemTable watermark (above -> verbatim reload; at/below -> "
          "standalone-born id-remap load); two ElemTable reads, no partition walk",
          ("test:tests/test_rfa_load.py",)),
    Stage("rfa-born-load", "rvt.convert.rfa_load:load_rfa_into_project",
          "any STANDALONE-BORN .rfa (our own start_id=1000 deliverables, a "
          "Revit-saved family) -> RfaSource (owners from Global/ElemTable, the "
          "file's own schema + release) -> schema-TYPED decode-time id remap "
          "into the free block above the host watermark -> rvt.famload "
          "four-registry load; the mechanism viewer-certified as T2a, this "
          "lane's own artifacts pending a batch (needs-viewer)",
          ("test:tests/test_rfa_load.py",
           "certified:experiments/rftprobe/T2a.rvt",
           "record:docs/inbox/rfa-load-product.md")),
    Stage("add-into-rvt", "rvt.convert.add_to_project:add_to_project",
          "the prompt's intent RETARGETED INTO the user's file -- its release "
          "(preserved: the output is a splice of the input), its own schema, "
          "its levels, free floor space beside its content -- families "
          "generated zero-donor, four-registry loaded, instances placed with "
          "specimens CONSTRUCTED against the target (never cloned from it)",
          ("test:tests/test_convert_combo.py",
           "worked:experiments/convert_combo/A1_add_own/manifest.json",
           "record:docs/inbox/convert-b.md")),
    Stage("merge-into-rvt", "rvt.convert.merge_ifc:merge_ifc",
          "the IFC's resolved intent translated by a deterministic DISJOINT "
          "offset (recorded; --offset overrides) and built INTO the target by "
          "the same engine: walls appended, families loaded + placed",
          ("test:tests/test_convert_combo.py",
           "worked:experiments/convert_combo/B1_merge_ifc_into_own/out/manifest.json",
           "record:docs/inbox/convert-b.md")),
    Stage("rfa-edit", "rvt.convert.modify_family:modify_family",
          "family EDITS -- rename type / rename family / set parameters, given "
          "as an edit sentence, inline JSON ops or an ops.json path "
          "(rvt.convert.edit_family is the structured-ops surface over the "
          "same engine) -- through rvt.manipulate's certified modify path on "
          "the family's self-Family record; PartAtom kept in step; family-mode "
          "validator + release-preservation + semantic re-read gates",
          ("test:tests/test_convert_combo.py", "test:tests/test_convert.py",
           "worked:experiments/convert_combo/C1_modify_own/manifest.json",
           "worked:experiments/convert/edit-family/manifest.json",
           "record:docs/inbox/convert-b.md")),
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
_OPEN_BUG = ("PLACED INSTANCES of our generated families on our composed "
             "genesis base are THE OPEN CELL (docs/inbox/genesis-audit.md "
             "#48, issue #16; walls, loaded families and walls + loaded "
             "families in one file are certified -- WF_fix / WF_nofix): a "
             "job that places instances is DELIVERED and STAMPED 'PROOF-ONLY: "
             "generated-family INSTANCES on a composed genesis base (open "
             "cell, docs/inbox/genesis-audit.md #48, issue #16)'; --strict "
             "emits two coordinated files instead, both delivered -- 'shell' "
             "(walls + loaded families, the certified shape) + 'equipment' "
             "(the placed instances, the open cell isolated)")
_CIRCUITS = ("feeder CIRCUITS are AUTHORED natively on the genesis base "
             "(2026/2025/2024): one constructed RbsElectricalSystem per "
             "non-service feeder edge, wired panel slot <-> load supply in the "
             "equipment commit and read back (count == edges, both-side "
             "connector links, validator CIRCUITS rule 0 errors) -- PROOF-ONLY: "
             "validator-green is necessary, NOT certification; no viewer "
             "verdict exists for the circuit layer yet (issue #146), and it "
             "rides the open instance cell above; a shortfall is named in the "
             "manifest with the resolved plan, never faked")
_CATALOG = ("family generation covers the catalog-backed kinds (panelboard / "
            "transformer / luminaire / wiring device / the honest house switchboard); "
            "anything without facts is REFUSED by name, never invented -- EXCEPT kind='generic_model', where the caller SUPPLIES the geometry and every dimension is reported as GIVEN with its source")
# --- caveats shared by the rvt.convert cells (issue #5) --------------------
_INTO_GATES = ("INTO-AN-EXISTING-FILE gates: validator 0 errors required to "
               "claim, four-registry census coherent, the target's release "
               "PRESERVED by construction (the output is a splice of the input) "
               "and re-verified per output; a target whose release has no "
               "certified creation support is refused with "
               "rvt.versions.creation_status's own reason -- never a silent "
               "newer-release file")
_INTO_VIEWER = ("no add-into / merge-into artifact has been through Autodesk's "
                "reader yet: the gates are necessary, NOT sufficient (rule 4). "
                "Our generated family documents under a placed instance are "
                "the OPEN CELL (docs/inbox/genesis-audit.md) -- expect the "
                "audit to reject the added equipment until it closes; every "
                "output is stamped PROOF-ONLY and delivered regardless")
_FOREIGN_SOURCE = ("a source/target that tekton did not author is DELIVERED "
                   "with the FOREIGN DESIGN CONTENT stamp (its walls, families "
                   "and parameter values are that owner's content: an interop "
                   "artifact for the file's owner, never shipped as tekton "
                   "content); research-corpus samples add the QUARANTINED "
                   "dev-only stamp")
_RFA_INPUT = ("rfa INPUT CONTRACT: (a) a famspec JSON ({'kind': 'panelboard' | "
              "'transformer' | 'luminaire' | 'device' | 'downlight' | 'generic_model' (an ARBITRARY 3D body: vertices+height, geometry GIVEN by the caller, never a catalog claim), <the "
              "constructor's kwargs>} -- the written contract is spec/famspec.schema.json, "
              "worked examples spec/examples/famspec-*.json) -- the family is "
              "GENERATED by its constructor (rvt.famgen.factory.make_* / "
              "famfrom_ifc.make_downlight) as OUR standalone .rfa and, for rvt "
              "output, REBUILT above the host watermark and loaded through the "
              "certified four-registry loader (rvt.famload); "
              "(b) a .rfa PATH that tekton EXTRACTED from a loaded project "
              "(rvt->rfa) -- reloaded as-is through the component loader "
              "(rvt.famgen.loader; full cycle proven, project validator 0 "
              "errors) when its ids sit ABOVE the host's id watermark (the "
              "pinned genesis base always qualifies); "
              "(c) a STANDALONE-BORN .rfa (our own start_id=1000 .rfa "
              "deliverables, any Revit-saved 2024-2026 family whose ElemTable "
              "our codec parses, or an extracted .rfa going into a host that has "
              "grown past its ids) LOADS through rvt.convert.rfa_load: the "
              "schema-typed decode-time id remap into the free block above the "
              "watermark + the four-registry famload (project validator 0 "
              "errors, census coherent). That MECHANISM is viewer-CERTIFIED "
              "(T2a: a Revit-born 1,992-element .rfa famloaded onto our composed "
              "base with a placed instance PASSES); this lane's own artifacts are "
              "pending their viewer batch (needs-viewer) -- delivered + labelled, "
              "never claimed 'loads in Revit'. Refused by name, one clear line: a "
              "GraveyardRec ElemTable footer (codec gap #13), nested family "
              "documents, seq-103 classes beyond GElement/SerializedDummy")
_RFA_HOST = ("default host = the pinned certified genesis base (G_ABPD, "
             "hash-verified, bundled with the plugin); pass rvt to load into "
             "YOUR project. Load depth certified by the ledger: our families "
             "onto the rst host (L1a, L_downlight_loaded) and the genesis "
             "lineage (stage_L8_lp4), a Revit-born standalone .rfa (T2a) and "
             "an embedded-born family document (TB0g) onto the composed base "
             "with instances")
_RFA_RELEASE = ("PER RELEASE (--target-version, or 'target_version' in the famspec): "
                "with no rvt the host is THAT year's pinned certified base and the "
                "family is emitted AND loaded under its release -- 2026 / 2025 / 2024: "
                "the .rfa and the loaded project both ARE that release, project "
                "validator 0 errors, four-registry census coherent (every catalog "
                "famspec kind and the standalone-born .rfa lane, fresh clone, "
                "tests/test_router_load_release.py); an uncertified (2023) or unknown "
                "(2027+) year is never refused and never silent -- loaded onto the "
                "default Revit 2026 base + THE one line, as on every create route; "
                "a family that cannot be emitted at a certified year degrades "
                "ONCE (block, .rfa and host all name the default release). A given "
                "rvt keeps ITS release (a load cannot transmute the host): stated "
                "every time as detected / match / match-older, or THE line when the "
                "stated year is older than that host; the .rfa beside it is emitted at "
                "the flag's year and says so in its own block. The load "
                "certifications above are 2026-era files: 2025 / 2024 loads are "
                "VALIDATED under their own release, not viewer-certified")
_RFA_FAMSPEC_ENV = ("the catalog famspec kinds (panelboard / transformer / "
                    "luminaire / device) emit on the plugin-bundled base and run anywhere "
                    "(fresh clone, cloud session, bare plugin unzip); the "
                    "downlight famspec kind (the MEASURED product archetype) emits "
                    "on the family container archetype of the git-ignored research "
                    "corpus -- owner machine only until rvt.ifc.famfrom_ifc emits on "
                    "the bundled base, one clear line elsewhere; the .rfa-path lanes "
                    "run anywhere")
_FAMSPEC_GATES = ("a famspec-generated .rfa is family-mode-validator + provenance "
                  "gated (0 errors, zero donor bytes, assumed/user-given fact fields "
                  "surfaced in its report) and stamped PROOF-ONLY: no famspec artifact "
                  "is in the certified ledger as a standalone .rfa (rule 4: no .rfa "
                  "of ours is) -- what the ledger certifies is the same constructors' "
                  "families LOADED into projects (stage_L8_lp4 on the genesis lineage, "
                  "L1a on the rst host); the standalone file is delivered regardless, "
                  "the label rides with it")

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
         ("prompt->intent", "intent->rfa", "prompt->archetype"),
         ("worked:experiments/frontdoor/prompt-electrical-room/families",
          "test:tests/test_famgen_factory.py", "test:tests/test_frontdoor.py",
          "test:tests/test_famgen_archetypes.py"),
         (_CATALOG, _PROOF_ONLY,
          "a prompt naming a product the ARCHETYPE registry generates (cable "
          "tray, strut channel, wireway, junction box, conduit) is built at "
          "standard NOMINAL sizes for that product class when no catalog "
          "record applies: every dimension is reported nominal (generated) or "
          "given (you stated it), and no manufacturer / model / part number is "
          "ever claimed. A prompt that names a SPECIFIC manufacturer's item "
          "still gets a family (output is never withheld), and the status line "
          "and report say in the first line that the named item is NOT what was "
          "delivered (rvt.famgen.archetypes:manufacturer_claim, issue #591)"),
         hint=("catalog facts win when the prompt names a catalog product; the "
               "archetype lane is the fallback, not the first choice")),
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
         ("ifc->intent", "intent->rfa", "ifc->facts", "facts->rfa", "ifc->parts"),
         ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
          "test:tests/test_ifc_family.py", "test:tests/test_ifc_intent.py",
          "test:tests/test_ifc_assembly.py",
          "record:docs/inbox/ifc-assembly-rfa.md"),
         ("THREE lanes, tried in that order: ROOM IFCs yield catalog families "
          "for their tagged equipment (intent->rfa); a single PRODUCT IFC is "
          "measured into facts and composed as the downlight archetype (the one "
          "facts->rfa archetype wired); ANY OTHER geometry IFC -- several "
          "untagged products, a fabrication assembly, a Claude Design body -- "
          "goes to the ASSEMBLY lane (ifc->parts), which measures every "
          "tessellated body and authors ONE donor-free multi-part "
          "generic_model .rfa instead of refusing",
          "the ASSEMBLY lane authors the PRISMATIC MASSING of each mesh (plan "
          "footprint extruded over its Z extent), not a faceted copy: a "
          "cross-section that varies with height becomes its envelope, and "
          "assembly-parts.json reports each part's 'fill' (mesh volume / "
          "authored prism volume) so that approximation is measured per part, "
          "never described. Rotation is not expressible in the part contract, "
          "so a body whose axis is not Z is massed by its bounding prism",
          "the assembly lane needs TESSELLATED bodies (IfcTriangulatedFaceSet / "
          "IfcPolygonalFaceSet); a product carrying only swept/CSG solids is "
          "skipped BY NAME in the record, never given a guessed size",
          _CATALOG)),
    # ---------------- singles: rvt ----------------
    Cell(("rvt",), "rvt", STATUS_MISSING, None, (),
         (), (),
         missing_reason=("an .rvt alone with .rvt output is a no-op copy: an "
                         "EDIT needs instructions"),
         closest=(("prompt", "rvt"), "rvt"),
         hint="add a prompt (edit sentence or ops.json): prompt+rvt -> rvt"),
    Cell(("rvt",), "ifc", STATUS_WORKS, "rvt_to_ifc",
         ("rvt-read", "rvt->intent", "intent->ifc"),
         ("test:tests/test_convert.py",
          "worked:experiments/convert/rvt-to-ifc/electrical_room_prompt.ifc",
          "worked:experiments/convert/rvt-to-ifc/electrical_room_prompt.manifest.json",
          "record:docs/inbox/convert-a.md"),
         ("the ROUND TRIP IS THE ACCEPTANCE: the emitted IFC re-resolves "
          "through our own rvt.ifc.intent resolver and the manifest carries "
          "the survival table (equipment tag/kind/position/front, walls, "
          "feeder edges) -- full survival proven on the acceptance output "
          "(equipment 7/7 then 4/4 incl. a transformer, walls 4/4) and on a "
          "quarantined MEP sample (equipment 29/29, feeder edges 28/28, walls "
          "131/133: two runs regrouped by the room-scale resolver, honest "
          "partial in the table)",
          "extraction scope: levels, straight (GLine-driven) walls, "
          "OST_ElectricalEquipment instances + their tagging-contract values, "
          "equipment-to-equipment feeder edges; non-electrical categories, "
          "curved/curtain walls and circuits to non-equipment loads are "
          "COUNTED as not-extracted in the manifest, never faked",
          _FOREIGN_SOURCE),
         hint="an IFC has no Autodesk arbiter: the survival table is the verdict"),
    Cell(("rvt",), "rfa", STATUS_WORKS, "extract_family",
         ("rvt-read", "rvt->rfa"),
         ("test:tests/test_convert.py",
          "worked:experiments/convert/extract-family/DP1_reextracted.manifest.json",
          "worked:experiments/convert/extract-family/DP1_reextracted.reloaded.rvt.load.json",
          "certified:experiments/species/TB0g.rvt",
          "record:docs/inbox/convert-a.md"),
         ("select the family with opts['family'] (route.py --family: name "
          "fragment | host family id | unit index); a project embedding "
          "exactly one family needs no selector; otherwise the route lists "
          "the embedded families in one clear line (families.json delivered)",
          "our own loaded-project outputs extract CLEAN (family-mode validator "
          "0 errors) and complete the FULL CYCLE generate -> load -> extract "
          "-> re-load (rfa+rvt -> rvt, extracted-.rfa lane); a Revit-authored "
          "PROJECT-HOSTED family is delivered + labelled PARTIAL (dangling "
          "references to host-side categories/styles/materials with no "
          "embedded twin: host-resource repatriation is a named follow-up); "
          "a family embedding NESTED family documents is refused by name",
          "extract->place has BASE-LEVEL viewer evidence: TB0g (an "
          "embedded-born family document transplanted byte-identically onto "
          "our composed base with a placed instance) PASSES; the product "
          "lane's own extract->reload artifact is validator/census-gated, "
          "not separately viewer-certified",
          _FOREIGN_SOURCE),
         hint="then reload it: route --output rvt --rfa <extracted.rfa> [--rvt host.rvt]"),
    # ---------------- singles: rfa ----------------
    Cell(("rfa",), "rvt", STATUS_WORKS, "rfa_load",
         ("famspec->rfa", "rfa-load", "rfa-classify", "rfa-reload", "rfa-born-load"),
         ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
          "certified:experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt",
          "certified:experiments/ifc_room/stage_L8_lp4.rvt",
          "certified:experiments/rftprobe/T2a.rvt",
          "certified:experiments/species/TB0g.rvt",
          "worked:experiments/rftprobe/probes.json",
          "worked:experiments/convert/extract-family/DP1_reextracted.reloaded.rvt.load.json",
          "worked:spec/famspec.schema.json",
          "test:tests/test_ifc_family.py", "test:tests/test_famload.py",
          "test:tests/test_convert.py", "test:tests/test_router.py",
          "test:tests/test_rfa_load.py", "test:tests/test_router_load_release.py",
          "record:docs/inbox/rfa-load-product.md",
          "record:docs/inbox/famspec-contract.md", "record:docs/inbox/router-rfa-release.md"),
         (_RFA_INPUT,
          "famspec lane (form a): every famspec kind LOADS onto the pinned base with "
          "project validator 0 errors and a coherent four-registry census (the "
          "device kind lands UNPLACED as an Electrical Fixtures host family, "
          "category -2001060, like the others); the "
          "generated .rfa rides beside the loaded project; a famspec that fails "
          "spec/famspec.schema.json (unknown kind, misspelt field, wrong type) or "
          "whose facts the catalog lacks is answered in ONE clear line naming the "
          "field -- never a traceback, never an invented dimension",
          _RFA_HOST, _RFA_RELEASE, _RFA_FAMSPEC_ENV, _FAMSPEC_GATES, _PROOF_ONLY)),
    Cell(("rfa",), "ifc", STATUS_MISSING, None, (),
         (), (),
         missing_reason="no family->IFC product emitter exists yet",
         closest=(("prompt",), "ifc"),
         hint=("author the product IFC from its facts: prompt->ifc / spec->ifc; "
               "or load the family into a project and export that: rfa->rvt "
               "then rvt->ifc")),
    Cell(("rfa",), "rfa", STATUS_WORKS, "rfa_generate",
         ("famspec->rfa",),
         ("test:tests/test_router.py", "test:tests/test_famgen_factory.py",
          "worked:spec/famspec.schema.json",
          "worked:spec/examples/famspec-panelboard.json",
          "worked:spec/examples/famspec-transformer.json",
          "worked:spec/examples/famspec-luminaire.json",
          "worked:spec/examples/famspec-device.json",
          "record:docs/inbox/famspec-contract.md"),
         ("the rfa input here is a famspec JSON -- THE STRUCTURED REQUEST for one "
          "family: {'kind': 'panelboard' | 'transformer' | 'luminaire' | 'device' | "
          "'downlight' | 'generic_model' (an ARBITRARY 3D body: vertices+height, geometry GIVEN by the caller), <fields mirroring the constructor's keyword arguments>, "
          "optional 'target_version'} per spec/famspec.schema.json (JSON Schema "
          "draft-07, our own text; validated stdlib-only, so a misspelt field or a "
          "wrong type is ONE clear line naming it); the output is OUR standalone "
          ".rfa (+ its report: family-mode validator verdict, provenance ledger, "
          "assumed/user-given fact fields) -- measured on a fresh clone (with the "
          "shared family view constellation): panelboard 87 / transformer 75 / "
          "luminaire 81 / device 73 elements (the device = an Electrical Fixtures "
          "family, category -2001060 read back from the written file), VALID 0 "
          "errors, provenance ok",
          "an existing .rfa PATH alone is a no-op for .rfa output (nothing to "
          "generate, nothing to edit): answered with the clear line pointing at "
          "prompt+rfa -> rfa (edit it) and rfa -> rvt (load it)",
          _CATALOG, _RFA_FAMSPEC_ENV, _FAMSPEC_GATES,
          "PER RELEASE exactly as prompt -> rfa: 'target_version' in the famspec or "
          "--target-version on the CLI (the flag wins) emits the .rfa AS Revit "
          "2026 / 2025 / 2024 in that year's certified release context; an "
          "uncertified or unknown year is delivered at the default release with THE "
          "one line saying which Revit opens it -- and, unlike the room routes, NO "
          "IFC beside it (a family request resolves no room intent to emit; the line "
          "says so); no year -> the default release and the route JSON says to ask "
          "the recipient's year",
          _PROOF_ONLY),
         hint=("edit an existing .rfa with prompt+rfa -> rfa; load a famspec or .rfa "
               "into a project with rfa -> rvt")),
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
         ("rvt-read", "rvt-edit", "prompt->intent", "add-into-rvt"),
         ("certified:experiments/manipulate/M3_modify.rvt",
          "certified:experiments/manipulate/M4_move_retype.rvt",
          "certified:experiments/manipulate/M2_delete_cascade.rvt",
          "certified:experiments/manipulate/M2_delete_cascade_rac.rvt",
          "worked:experiments/frontdoor/rvt-edit-room/manifest.json",
          "worked:experiments/convert_combo/A1_add_own/manifest.json",
          "worked:experiments/convert_combo/A2_add_rme_devonly/manifest.json",
          "test:tests/test_manipulate.py", "test:tests/test_frontdoor.py",
          "test:tests/test_convert_combo.py", "test:tests/test_router.py",
          "test:tests/test_edit_own_release.py",
          "record:docs/inbox/convert-b.md", "record:docs/inbox/edit-own-release.md"),
         ("an EDIT-shaped prompt (an edit sentence, ops.json path, or inline "
          "JSON: modify / move / retype / delete / cascade / add-instance / "
          "add-circuit) runs the certified edit pipeline -- certified "
          "including on a FOREIGN file (M2_rac); known blocker: rename / "
          "set-mark on OUR created instances (no instance param rows yet)",
          "PER RELEASE: the edit runs under the INPUT file's own release and "
          "the output keeps it -- Revit 2026 / 2025 / 2024 projects open, "
          "edit, re-emit and validate 0 errors through the front door, "
          "tools/rvt_edit.py and tools/rvt_job.py edit "
          "(tests/test_edit_own_release.py); the edit certifications above "
          "are 2026-era files -- 2025/2024 edit outputs are VALIDATED, not yet "
          "viewer-certified; a release we cannot author into (2023 and older) "
          "is named and refused, never guessed",
          "an AUTHORING-shaped prompt ('add a 100 A lighting panel and a 75 "
          "kVA transformer to my project') runs rvt.convert.add_to_project: "
          "the new equipment is generated, loaded and placed INTO your file "
          "in free floor space beside its content (--at X Y / --level "
          "override); proven on our acceptance output (A1: VALID 0 errors) "
          "and dev-only on a 32.6 MB quarantined MEP sample (A2: VALID 0 "
          "errors, census coherent 308 units, release preserved)",
          _INTO_GATES, _INTO_VIEWER, _FOREIGN_SOURCE, _PROOF_ONLY)),
    Cell(("ifc", "rvt"), "rvt", STATUS_WORKS, "ifc_merge_into_rvt",
         ("ifc->intent", "merge-into-rvt"),
         ("worked:experiments/convert_combo/B1_merge_ifc_into_own/out/manifest.json",
          "worked:experiments/convert_combo/B2_merge_rst_devonly/manifest.json",
          "test:tests/test_convert_combo.py", "test:tests/test_ifc_intent.py",
          "test:tests/test_router.py", "record:docs/inbox/convert-b.md"),
         ("MERGE = the IFC's resolved intent is appended INTO your .rvt at a "
          "deterministic DISJOINT offset east of your content (recorded pre/"
          "post; --offset DX DY overrides, --offset 0 0 merges in the IFC's "
          "own world frame): walls appended, families generated + loaded, "
          "instances placed; proven on a copy of our acceptance output (B1: "
          "28 created ids, VALID 0 errors) and dev-only on the quarantined "
          "rst sample (B2: VALID 0 errors, 61 save units, two independent "
          "runs converge on identical created ids)",
          _INTO_GATES, _INTO_VIEWER, _OPEN_BUG, _FOREIGN_SOURCE, _PROOF_ONLY),
         hint="drop the rvt to build the IFC on the certified genesis base instead"),
    Cell(("prompt", "rfa"), "rfa", STATUS_WORKS, "rfa_modify",
         ("rfa-edit",),
         ("worked:experiments/convert_combo/C1_modify_own/manifest.json",
          "worked:experiments/convert_combo/C2_rename_family/manifest.json",
          "worked:experiments/convert/edit-family/manifest.json",
          "test:tests/test_convert_combo.py", "test:tests/test_convert.py",
          "test:tests/test_router.py", "record:docs/inbox/convert-b.md",
          "record:docs/inbox/convert-a.md"),
         ("the prompt is the FAMILY EDIT of an EXISTING .rfa: text ('rename "
          "the type to 225A MCB 42ckt; set BusRating 225; set PanelName "
          "DP-7; set Width of type \"X\" 600 mm'), inline JSON ops or an "
          "ops.json path -- one vocabulary (rename-type | rename-family | "
          "set-param, optionally type-scoped); the value carrier follows the "
          "parameter's STORAGE CLASS first (ParamDefString = text, "
          "ParamDefInt = integer -- neither carries a spec), the m_specTypeId "
          "of a ParamDefValue second, which also drives unit conversion (amps "
          "as-is, volts, kVA; lengths REQUIRE an explicit unit, never guessed)",
          "proven on our generated families: family-mode validator VALID 0 "
          "errors, release preserved, every edit echoed back by a semantic "
          "RE-READ, PartAtom title/type kept in step (C1/C2/C4, edit-family)",
          "PARTIAL on FOREIGN Revit-authored .rfa files: inventory + parse "
          "work, the COMMIT is blocked by the ElemTable GraveyardRec codec "
          "gap (rvt.stream_encoders) -- refused by name, nothing corrupted",
          "a DIMENSION edit changes the type-table value only (generated "
          "families carry no constraint graph): the geometry-true path is "
          "regeneration from the facts (prompt->rfa) -- recorded on every "
          "length edit",
          "the edited .rfa is validator-gated, not viewer-certified (no .rfa "
          "of ours has been through the family editor's audit yet)",
          _PROOF_ONLY),
         hint="a famspec is not editable -- generate it first (prompt->rfa), then edit the .rfa"),
    Cell(("rfa", "rvt"), "rvt", STATUS_WORKS, "rfa_load",
         ("famspec->rfa", "rfa-load", "rfa-classify", "rfa-reload", "rfa-born-load"),
         ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
          "certified:experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt",
          "certified:experiments/ifc_room/stage_L8_lp4.rvt",
          "certified:experiments/rftprobe/T2a.rvt",
          "certified:experiments/species/TB0g.rvt",
          "worked:experiments/convert/extract-family/DP1_reextracted.reloaded.rvt.load.json",
          "test:tests/test_famload.py", "test:tests/test_convert.py",
          "test:tests/test_router.py", "test:tests/test_rfa_load.py",
          "test:tests/test_router_load_release.py",
          "record:docs/inbox/rfa-load-product.md",
          "record:docs/inbox/router-rfa-release.md"),
         ("LOAD the family into YOUR project (the rvt): the famspec lane and "
          "the standalone-born .rfa lane through the certified four-registry "
          "loader (rvt.famload), the extracted-.rfa lane through the component "
          "loader (rvt.famgen.loader); no instance is placed by this cell (place "
          "with prompt+rvt: 'add ...', or edit ops add-instance)",
          _RFA_INPUT, _RFA_HOST,
          "on YOUR host the same mechanisms + census/validator gates run; "
          "the viewer evidence is on the rst sample host and our genesis/"
          "composed bases (both Revit-lineage 2026 projects) -- a host of "
          "another release loads only where that release's creation support "
          "is certified",
          _RFA_RELEASE, _RFA_FAMSPEC_ENV, _PROOF_ONLY)),
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
                 "L_downlight_loaded pipeline; per release exactly as rfa->rvt "
                 "(the product .rfa is emitted in the --target-version year's "
                 "context and the default host is that year's certified base, one "
                 "resolver, one stated block); the measured archetype itself still "
                 "needs the family container archetype on disk (owner machine, #94)"),
        "evidence": ("certified:experiments/families/ifc/L_downlight_loaded.rvt",
                     "test:tests/test_ifc_family.py",
                     "test:tests/test_router_load_release.py"),
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
    "rvt->rfa->loaded-rvt": {
        "via": None, "cell": key_for(("rfa", "rvt"), "rvt"),
        "route": "rfa_load",
        "stages": ("rvt->rfa", "rfa-reload"),
        "status": STATUS_WORKS,
        "note": ("EXTRACT -> PLACE INTO OUR PROJECTS in two hops: rvt->rfa "
                 "(--family X) lifts the family out of project A, then "
                 "rfa+rvt->rvt reloads that .rfa into project B (default: "
                 "the pinned genesis base). TB0g certifies the cell at base "
                 "level (an embedded-born family document moved onto our "
                 "composed base with a placed instance PASSES); the product "
                 "lane's own artifact (DP1_reextracted.reloaded) is "
                 "validator/census-gated"),
        "evidence": ("certified:experiments/species/TB0g.rvt",
                     "worked:experiments/convert/extract-family/DP1_reextracted.reloaded.rvt.load.json",
                     "test:tests/test_convert.py", "test:tests/test_router.py"),
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

#: the certification ledger (rule 4: the ONLY authority for a certified claim)
LEDGER_RELPATH = os.path.join("docs", "coverage", "viewer-certified.json")
#: the prefix of the one audit-problem class a fresh clone legitimately shows:
#: a ``certified:`` probe binary that IS in the ledger but lives in the
#: git-ignored ``experiments/**/*.rvt|rfa`` tree and is absent on this disk
ABSENT_BINARY_MARK = "certified file missing on disk: "


def _ledger_path() -> str:
    return os.path.join(_root(), LEDGER_RELPATH)


def _ledger() -> Dict[str, Any]:
    with open(_ledger_path()) as fh:
        return json.load(fh)


def verify_evidence() -> List[str]:
    """Audit every citation in STAGES/CELLS/CHAINS.  Returns problems (empty
    = every cited test/worked path exists and every certified citation is in
    the viewer ledger's CERTIFIED list).  tests/test_router.py asserts the
    HARD subset is empty everywhere (see :func:`audit`)."""
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
                problems.append(f"{where}: {ABSENT_BINARY_MARK}{path}")
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
        elif CELLS[ch["cell"]].status == STATUS_MISSING:
            problems.append(f"chain {name}: cell {ch['cell']} is MISSING")
        if ch.get("status") not in (STATUS_WORKS, STATUS_PARTIAL):
            problems.append(f"chain {name}: status {ch.get('status')!r} is not works/partial")
        for sid in ch["stages"]:
            if sid not in STAGES:
                problems.append(f"chain {name}: unknown stage {sid!r}")
        for ref in ch.get("evidence", ()):
            check(ref, f"chain {name}")
    return problems


def _experiment_binaries_present() -> bool:
    """True when this checkout carries ANY certified-round probe binary
    (``experiments/acceptance/*.rvt`` -- every viewer round stages there).
    False = the fresh-clone signature: the git-ignored binaries were never
    here, so an absent ``certified:`` file says nothing about the claim."""
    return bool(glob.glob(os.path.join(_root(), "experiments", "acceptance", "*.rvt")))


def audit() -> Dict[str, Any]:
    """Classify :func:`verify_evidence` for humans and tests.

    * ``problems``        -- HARD problems that are wrong on ANY checkout: a
      ``certified:`` citation not in the ledger, a cited test/worked/record
      path that does not exist, a malformed ref, an unknown stage, a claimed
      cell without evidence.  On a checkout that carries the probe binaries
      (the owner machine) an absent certified binary is ALSO hard -- the
      byte-identical control of the next viewer round needs it on disk.
    * ``absent_binaries`` -- ``certified:`` files that ARE in the ledger but
      are not on this disk.  Informational on a fresh clone (the ledger is
      the certification authority, rule 4; the binaries are git-ignored).
    * ``ledger_present``  -- False inside a bare plugin bundle (no docs/):
      the audit cannot run there and says so instead of pretending.
    """
    ledger_present = os.path.isfile(_ledger_path())
    raw = verify_evidence() if ledger_present else []
    absent = [p for p in raw if ABSENT_BINARY_MARK in p]
    hard = [p for p in raw if ABSENT_BINARY_MARK not in p]
    binaries_here = _experiment_binaries_present() if ledger_present else False
    if binaries_here:
        hard = hard + absent
    return {
        "ledger_present": ledger_present,
        "ledger": LEDGER_RELPATH,
        "fresh_clone": bool(ledger_present and not binaries_here),
        "problems": hard,
        "absent_binaries": [] if binaries_here else absent,
        "n_cells": len(CELLS), "n_stages": len(STAGES), "n_chains": len(CHAINS),
        "ok": bool(ledger_present and not hard),
    }


# ===========================================================================
# rendering (tools/route.py matrix; the .md is the committed rendering)
# ===========================================================================

def matrix_rows() -> List[Dict[str, Any]]:
    """Rows for the truth table: singles first, then combinations."""
    def order(c: Cell) -> Tuple[int, int, str, str]:
        return (len(c.inputs), INPUT_KINDS.index(c.inputs[0]) if c.inputs else 9,
                "+".join(c.inputs), c.output)
    return [c.as_json() for c in sorted(_CELL_LIST, key=order)]


def status_counts() -> Dict[str, int]:
    out = {STATUS_WORKS: 0, STATUS_PARTIAL: 0, STATUS_MISSING: 0}
    for c in _CELL_LIST:
        out[c.status] = out.get(c.status, 0) + 1
    return out


def render_text(*, with_audit: bool = True) -> Tuple[str, Dict[str, Any]]:
    """The plain-text table ``tools/route.py matrix`` and ``tools/frontdoor.py
    matrix`` print, plus the :func:`audit` record (empty when
    ``with_audit`` is False).  One renderer for every CLI so the two front
    doors can never disagree about the table."""
    lines: List[str] = []
    lines.append("")
    lines.append("tekton PERMUTATION MATRIX -- inputs {prompt, ifc, rvt, rfa, "
                 "spec} -> outputs {rvt, rfa, ifc}")
    lines.append("(machine truth: src/rvt/frontdoor/matrix.py; rendered doc: "
                 "docs/product/PERMUTATION-MATRIX.md)")
    lines.append("")
    for row in matrix_rows():
        ins = "+".join(row["inputs"])
        status = row["status"].upper()
        if row["status"] == STATUS_MISSING:
            lines.append(f"  {ins:14s} -> {row['output']:3s}  {status:8s} "
                         f"{row['missing_reason']}")
        else:
            lines.append(f"  {ins:14s} -> {row['output']:3s}  {status:8s} "
                         f"route={row['route']}  stages: {' -> '.join(row['stages'])}")
    cnt = status_counts()
    lines.append("")
    lines.append(f"  {len(_CELL_LIST)} cells: {cnt[STATUS_WORKS]} works / "
                 f"{cnt[STATUS_PARTIAL]} partial / {cnt[STATUS_MISSING]} missing")
    lines.append("")
    lines.append("chains (opts --via, or implicit):")
    for name, ch in CHAINS.items():
        lines.append(f"  {name:24s} [{ch['status']}] {' -> '.join(ch['stages'])}")
    lines.append("")
    lines.append("any other (inputs, output) combination is answered with the "
                 "matrix row + the closest supported route in one clear line.")
    rep: Dict[str, Any] = {}
    if with_audit:
        rep = audit()
        lines.append("")
        if not rep["ledger_present"]:
            lines.append(f"evidence self-audit: SKIPPED -- {LEDGER_RELPATH} is not "
                         "part of this bundle (the audit runs in the source "
                         "repo: tools/route.py matrix / tests/test_router.py); "
                         "the statuses above are the audited table as shipped.")
        elif rep["problems"]:
            lines.append(f"WARNING: {len(rep['problems'])} evidence citation(s) "
                         "FAILED the self-audit (tests/test_router.py fails too):")
            for p in rep["problems"][:12]:
                lines.append(f"  ! {p}")
        else:
            lines.append("evidence self-audit: every citation checks out against "
                         f"the ledger and the tree ({rep['n_cells']} cells, "
                         f"{rep['n_stages']} stages, {rep['n_chains']} chains).")
            if rep["absent_binaries"]:
                lines.append(f"  note: {len(rep['absent_binaries'])} certified probe "
                             "binaries are not on this disk (git-ignored "
                             "experiments/**/*.rvt -- a fresh clone); their "
                             f"ledger entries in {LEDGER_RELPATH} are what "
                             "certifies them, and those all check out.")
    return "\n".join(lines) + "\n", rep


def as_json() -> Dict[str, Any]:
    return {
        "inputs": list(INPUT_KINDS), "outputs": list(OUTPUT_KINDS),
        "stages": {k: {"impl": s.impl, "does": s.does, "evidence": list(s.evidence)}
                   for k, s in STAGES.items()},
        "cells": matrix_rows(),
        "counts": status_counts(),
        "chains": {k: {kk: (list(vv) if isinstance(vv, tuple) else vv)
                       for kk, vv in ch.items()} for k, ch in CHAINS.items()},
        "fallback": ("any (inputs, output) not in `cells` is answered with "
                     "the matrix row + the closest supported route in ONE "
                     "clear line -- never a traceback"),
    }
