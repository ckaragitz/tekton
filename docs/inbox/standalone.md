# inbox — standalone (STANDALONE CREATION FROM BUNDLED ASSETS ONLY; kills field problem A)

Stream: STANDALONE-CREATION (2026-08-04). Charter: the first real user session
(Cowork sandbox, prompt "create an eaton panel for me with 6 switches") failed
native `.rvt` creation with `FileNotFoundError:
…/extracted/racbasicsampleproject/Formats__Latest.gz/000.bin` and degraded to
IFC + a proof-only explanation. Trace every research-machine input of the
front door's build path, reproduce in a clean environment, and make creation
work from bundled assets alone — ZERO donor files. Territory:
`src/rvt/frontdoor/standalone.py`, `tests/test_frontdoor_standalone.py`, this
record. All other files: exact patches below, **not applied**.

## Verdict in one screen

* **Creation works from bundled assets alone, ZERO donor files.** In a clean
  environment containing ONLY the plugin (no `extracted/`, no `samples/`, no
  `vendor/`, no `experiments/`, no user-supplied file, no `--family-donor`),
  BOTH worked examples build native `.rvt` end to end through the unchanged
  build code with `rvt.frontdoor.standalone` active:
  - **"create an eaton panel for me with 6 switches"** (prompt route):
    1 family `.rfa` generated (family-mode validator **VALID 0 errors
    0 warnings**, `provenance_scan_v2` **all checks TRUE**), loaded, 1
    instance placed; combined `.rvt` **VALID 0 errors**, identity PASS,
    four-registry coherent.
  - **electrical-room-2500a.ifc** (the flagship IFC): **8 families**
    generated (each VALID 0 errors + provenance-clean), **8 loaded, 8
    instances placed, 4 walls built** — the walls from a **CONSTRUCTED
    SWall template**, no R5; combined `.rvt` **VALID 0 errors**, identity
    PASS, census coherent. Degradations = only the pre-existing intent-level
    refusals (ground bus / conduit runs / service entrance / hangers) and
    the known circuits blocker — identical to the research-machine run.
  - The research-input **tripwire was armed during both builds** (any read
    of `extracted/` | `samples/` | `vendor/` | `experiments/genesis/` | an
    Autodesk install dir raises): zero hits.
* **The field failure is reproduced exactly** by the same clean env without
  the resolvers (test 1), and the base-resolution sub-failure too (the stock
  resolver never probes the plugin's real bundle path — test 2).
* **The schema question is settled with hashes**: the inflated
  `Formats/Latest` is **byte-identical** (sha256
  `6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2`,
  496,597 B) across the corpus `000.bin`, the bundled `G_ABPD.rvt`, `R5.rvt`,
  **all six Autodesk sample projects AND the family archetype `.rfa`** — so
  (a) rerouting the corpus-schema default to the base's embedded stream is
  lossless (class-for-class diff: **4,690/4,690 classes identical**, 0
  mismatches — `standalone.schema_identity_report`), and (b) the prior
  report's claim "the format constant is identical either way"
  (project vs family container) is **CONFIRMED** — one carried stream serves
  both container kinds.
* **The zero-donor family container is proven, not asserted**:
  `famdoc_adoc.emit_family_rfa_v2(doc, path, donor=<bundled G_ABPD.rvt>)`
  works as-is — `Formats/Latest` = the base's copy of the format constant,
  `Global/Latest` = **OUR AUTHORED family ADocument**
  (`author_family_adocument` seeded from the base's decoded tree, purged,
  repopulated over OUR inventory — **no borrowed project ADocument**: the
  emitted stream is the authored payload, round-tripped, 0 dangling ids,
  0 base-id byte hits), element records / PartAtom / footer / container OURS.
  Family-mode validator **VALID 0 errors 0 warnings**; `provenance_scan_v2`
  verdict **PROVENANCE-CLEAN**. Also proven with the clean-env registry-maps
  fallback (no `G1_registry_maps.json`).
* **10/10 stream tests pass** (`tests/test_frontdoor_standalone.py`, ~42 s
  including both clean-env E2E builds). Full suite: see BRANCH STATE.

## 1. The dependency trace (reproduced first, then measured)

Reproduction (clean env = temp dir with ONLY `plugin/` copied in;
`TEKTON_ROOT=<cleanroot>`; engine = `plugin/lib/src`):

* Without `$RVT_GENESIS_BASE`: `FAILED (the pinned genesis base G_ABPD was
  not found (tried: <cleanroot>/plugin/lib/experiments/genesis/subst_k4/
  compose/G_ABPD.rvt))` — the resolver's pinned candidates are the repo
  relpath and `<plugin>/lib/genesis/`; the actual bundle location
  `<plugin>/assets/genesis/G_ABPD.rvt` is never probed (patch P2).
* With `$RVT_GENESIS_BASE=<cleanroot>/plugin/assets/genesis/G_ABPD.rvt`: the
  build starts and stage F dies per family with **the field error**:
  `FileNotFoundError: <cleanroot>/extracted/racbasicsampleproject/
  Formats__Latest.gz/000.bin` → no family loadable → `FAILED (no family
  could be loaded and there are no walls to build)` → the front door
  degrades exactly as the field session reported.

Then both prompts were run on the research machine under an `open()` audit
hook. The complete set of non-bundled inputs the build path reads is FOUR
files (everything else it opened — famgen catalog facts JSON, the frontdoor
pin JSON — ships inside `src/rvt`, which the plugin mirrors):

| # | input read by the old path | read by | bundled? |
|---|---------------------------|---------|----------|
| 1 | `extracted/racbasicsampleproject/Formats__Latest.gz/000.bin` | `rvt.schema.load_schema()` default → every no-arg `ObjectDecoder()` / `ObjectEncoder()` (famgen `build_unit_segments`, `rvt.commit`, `rvt.regadd`, …) and `rvt.adocument.get_decoder()` | NO → the field FileNotFoundError |
| 2 | `experiments/genesis/R5.rvt` | `ifc_intent.SpecimenSet` (wall + instance clone templates; needed by stage W **and** stage E — even the wall-less eaton prompt reads it) | NO |
| 3 | `experiments/genesis/subst_k4/compose/G_ABPD.rvt` | `frontdoor.base.resolve_base` (repo pin path) | YES at `plugin/assets/genesis/G_ABPD.rvt` — but the resolver never looks there |
| 4 | `vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa` | `famgen.skeleton.emit_family_rfa` (v1 donor: `Formats/Latest` + `Global/Latest` + footer) / `famdoc_adoc.TEMPLATE_DONOR` (v2 archetype tree + `Formats/Latest`) | NO (deliberately — Autodesk sample family) |

Plus two of OUR OWN engine scripts loaded by path and missing from the
plugin mirror (packaging gap, not a donor dependency): famdoc_adoc's
`_ga()` loads `tools/genesis_assemble.py`, which loads `tools/rvt_reduce.py`
— neither is in `LIB_TOOLS_SHIM` (patch P6).

## 2. The resolution table {creation feature: source-before → source-now}

(`standalone.dependency_table()` returns the same table as data.)

| creation feature | source BEFORE | source NOW (bundled) |
|---|---|---|
| project-side schema (all codec defaults) | corpus `000.bin` | parsed from the bundled base's own `Formats/Latest` (byte-identical constant; proof above) |
| genesis base | repo path only | `<plugin>/assets/genesis/G_ABPD.rvt`, sha256-pinned (env/`--base` still first) |
| wall clone template (stage W) | R5 `SWall` specimen (Autodesk-lineage joined wall, cloned + cleaned) | **CONSTRUCTED** `SWall` template: schema-default object + the generic box topology tables, unjoined by construction, centerline key ref, faces at the base wall type's own compound-structure offsets |
| instance clone template (stage E) | R5 `FamilyInstance` specimen (a door) | **CONSTRUCTED** free-standing `FamilyInstance` template (schema defaults; every placement-bearing field is overwritten by the unchanged `add_family_instance` + `_scrub_instance`) |
| family container `Formats/Latest` | donor `.rfa` raw stream | the bundled base's raw stream (project-vs-family byte-identity CONFIRMED) |
| family container `Global/Latest` | donor ADocument (v1: byte-carried; v2: archetype tree) | **OUR AUTHORED family ADocument** — `author_family_adocument` seeded from the bundled base's decoded tree (same 239-slot AppInfo shape — `docs/inbox/family-genesis.md`), purged to 0 dangling/0 donor-id bytes, repopulated over OUR inventory |
| family container footer / end record | donor opaque bytes (v1) | already OURS in v2 (`build_footer` + the decoded 10-byte constant) — unchanged |
| family registry maps (UET fill) | `experiments/genesis/G1_registry_maps.json` (optional) | same file when present; built-in fallback otherwise — **proven sufficient** (VALID 0 errors without it) |
| feeder circuits (stage C) | no circuit specimen anywhere | **still-needs**: unchanged NAMED BLOCKER (an `RbsElectricalSystem` constructor is electrical-stream territory); the resolved circuit plan rides in the manifest |

Per-class template verdict for “drawn from the bundled base itself”: G_ABPD
carries **no `SWall` and no `FamilyInstance`** (verified by class census — it
does carry the `BasicWallType` 600634, levels, and no `Phase`), so both
template classes route to the **constructor path**, implemented in
`standalone.py` (`swall_template`, `family_instance_template`, on the
schema-directed `default_object` substrate). Constructed templates encode →
decode clean against the base schema before injection, and the templates set
`m_createdPhaseId=-1` (the base has no Phase element; the old R5 templates
named phase 86961, which does not exist in G_ABPD — the constructed ones are
*more* reference-coherent).

## 3. What `src/rvt/frontdoor/standalone.py` provides

* `bundled_base_path()` — env → repo pin path → `<plugin>/assets/genesis` →
  `<plugin>/lib/genesis`, sha256-pinned; plugin root discovered relative to
  the package itself (works wherever Cowork mounts the plugin).
* `bundled_schema()` / `install_schema()` — parse the base's embedded
  `Formats/Latest`; reroute `rvt.schema.load_schema` (and the from-imported
  copies in `rvt.objects` / `rvt.encode` / `rvt.adocument`), point
  `rvt.schema.DEFAULT_PATH` at a materialised cache file, seed
  `rvt.genesis.skeleton._SCHEMA_CACHE`, `rvt.encode._DEFAULT_ENCODER`,
  `rvt.adocument._DECODER`.
* `schema_identity_report()` — the byte + class-for-class proof (above).
* `default_object(schema, class)` — a complete, schema-conformant value dict
  with every field at its type default; the constructor substrate.
* `swall_template` / `family_instance_template` / `ConstructedSpecimens` —
  the SpecimenSet replacement; encoded records injected into each build
  `Document` exactly like the old specimen records (`inject_into` contract
  preserved, report says `constructed: true`).
* `standalone_family_write(product, path, family_donor=None)` — stage F
  emission via `emit_family_rfa_v2` with the bundled base (or a
  user-supplied donor) as container source; family-mode validation +
  `provenance_scan_v2`; returns the report shape `stage_families` consumes.
  `--family-donor` / `$RVT_FAMILY_DONOR` is the **hidden escape hatch**:
  never required, never advertised.
* `forbid_research_inputs()` / `allow_research_inputs()` — the tripwire:
  reads of `extracted/` | `samples/` | `vendor/` | `experiments/genesis/`
  raise `StandaloneError`; **any Autodesk installation path raises
  unconditionally** (ProgramData/Autodesk, Program Files/Autodesk,
  /Applications/Autodesk, "Family Templates").
* `activate()` / `author_standalone()` — one call wires all of the above
  into the UNCHANGED build path at runtime (the same wiring the patches
  below land permanently). `author_standalone` also passes the resolved
  bundled base as `--base` so `resolve_base`'s pin check runs (sha256 match
  ⇒ certified).
* `dependency_table()` — §2 as data.

Interim invocation (until P1–P6 land), for the skills / any surface:

```bash
python - <<'EOF'
from rvt.frontdoor.standalone import author_standalone
r = author_standalone(prompt="create an eaton panel for me with 6 switches",
                      out="out/job1", guard=True)     # or ifc="design.ifc"
print(r.status); print(r.files)
EOF
```

## 4. Autodesk-install-path sweep (HARD RULE)

`grep -rniE "programdata|program files.?/autodesk|/applications/autodesk|family templates|\.rft|winreg|HKEY_"`
over `src/`, `plugin/`, `tools/`:

* **ZERO functional code reads, probes, lists, or requests an Autodesk
  installation directory. Nothing to delete.** Every hit is either (a) the
  ban stated as policy (`plugin/skills/_shared/tekton_env.py` HARD RULE
  docstring, `plugin/skills/tekton-author/SKILL.md`,
  `plugin/skills/tekton-native/SKILL.md`, `plugin/commands/tekton-doctor.md`
  — all "NEVER read/probe/list/request"), (b) an analysis docstring in
  `famgen/skeleton.py:1428` about what family templates *contain* (prose, no
  path), or (c) this stream's own tripwire constants.
* `tests/test_bootstrap.py` already enforces the ban with a source scan;
  `standalone.forbid_research_inputs` now also enforces it **at runtime**
  (an attempted open raises).

## 5. THE DELIVERABLE RULE — audit of the build path

Mandate: convert every site that withholds/deletes/declines an output
because a gate said PROOF-ONLY. Audit result, site by site:

| site | verdict |
|---|---|
| `src/rvt/frontdoor/build.py` | **no withhold logic.** Degrade modes write files and record stamps; on a failed E stage the deepest good file is still copied to `combined` (lines 351–357); `files` only lacks entries when a stage produced nothing. Already write-and-stamp. |
| `src/rvt/frontdoor/manifest.py` | **no withhold logic.** `_rollup_status` labels (`PROOF-ONLY (…)` is a status string over files already written); `honesty.proof_only_stamps` are labels; CRUD affordances emitted regardless. |
| `tools/rvt_job.py` | **no withhold logic.** The output is written BEFORE the gates run; `PROOF-ONLY, NOT-DELIVERABLE` is a manifest status; exit 6 only under the opt-in `--require-deliverable`; the only `os.remove` is a temp staging file. |
| `tools/frontdoor.py` / `rvt.frontdoor.__init__` | **no withhold logic.** `--json` always lists `files`; exit 0 on PROOF-ONLY. |
| the FIELD refusal | came from (a) the build being genuinely impossible off the research machine (**fixed by this stream**) and (b) skill-text steering. `plugin/skills/tekton-author/SKILL.md` has since been rewritten with THE DELIVERABLE RULE (“build it, write it, hand it — always … stamps are labels, never refusal logic”). Two residual text nits for the skills stream, listed as P7 — including SKILL.md's “Honest caveats” item 1, which still tells users the family build “needs a family format donor” and walls/equipment “a specimen ancestor”: obsolete once the patches land. |

Zero code sites required conversion; the deliverable rule is enforced going
forward by `tests/test_frontdoor_standalone.py::_assert_built`, which asserts
the combined file EXISTS on disk while the status says PROOF-ONLY.

## 6. Counsel-C4 note — data needed for zero-user-input family creation

**Nothing beyond what the plugin already ships.** A generated `.rfa` needs
exactly one Autodesk-authored stream: the per-release `Formats/Latest`
class-schema corpus — C4 product-corpus #1 — and the bundled genesis base
`G_ABPD.rvt` already carries it (byte-identical in every Revit-2026 file,
project or family; hash proof in §1). The family document object
(`Global/Latest`) is AUTHORED at runtime by `famdoc_adoc` (purged to zero
donor bytes / zero donor ids — the family-genesis stream's audited
machinery); element records, PartAtom, footer, container are constructed.
The ESSchemaStorage unit-schema corpus — C4 product-corpus #2 — likewise
already rides inside the bundled base. So standalone family creation
**changes the C4 posture by nothing**: the two corpora counsel is already
evaluating, carried once inside the one bundled `.rvt`, are the only
Autodesk-authored data involved; no additional Autodesk data (no template
`.rft`/`.rfa`, no install-dir reads) needs bundling, ever. The base's own
residue disclosure (~260 Autodesk-authored elements + 4 stragglers, per
verdict #24) is unchanged and stays in every manifest.

## 7. Patches (exact diffs — NOT applied; territory rule)

P1+P2+P4+P6 together make the STOCK entrypoints (`tools/frontdoor.py`, the
skills' `_bootstrap` path, `rvt.frontdoor.author`) standalone with **no
change to the CLI itself**: P2 lets `resolve_base` find the bundle, P1
installs the base-embedded schema + constructed specimens inside
`build_intent`, P4 reroutes stage-F emission, P6 completes the plugin
mirror. Until they land, `standalone.activate()` / `author_standalone()`
provides identical behaviour at runtime (what the tests exercise).

### P1 — `src/rvt/frontdoor/build.py`: activate the resolvers in the build step

```diff
@@ from . import intent as FI
-from .base import ResolvedBase, repo_root, resolve_specimen_source
+from .base import ResolvedBase, repo_root, resolve_specimen_source
+from . import standalone as SA
@@ def build_intent(model: FI.IntentModel, opts: BuildOptions) -> BuildResult:
     try:
         R = load_ifc_room_module()
     except BuildError as e:
         res.errors.append(str(e))
         res.seconds = round(time.time() - t0, 1)
         return res
+
+    # STANDALONE RESOLUTION (docs/inbox/standalone.md): the schema comes from
+    # the base's own Formats/Latest, and the build may never read the
+    # research corpus — a stray read fails RED, not silently.
+    try:
+        SA.install_schema(opts.base.path)
+    except Exception as e:                                   # noqa: BLE001
+        res.errors.append(f"schema install from base failed: {type(e).__name__}: {e}")
+        res.seconds = round(time.time() - t0, 1)
+        return res
+    SA.forbid_research_inputs(allow=[p for p in (opts.specimen_src,) if p])
@@ def _run(model, opts: BuildOptions, R, res: BuildResult, verdict, plans,
     specimens = None
     if want_walls or (loaded and "E" in opts.stages):
-        spec_src = opts.specimen_src or resolve_specimen_source()
-        specimens = R.SpecimenSet(spec_src)
+        spec_src = opts.specimen_src or SA.CONSTRUCTED
+        specimens = (R.SpecimenSet(spec_src) if spec_src != SA.CONSTRUCTED
+                     else SA.ConstructedSpecimens(base_path=opts.base.path))
         res.stages.append({"stage": "specimens", "source": _relp(spec_src),
```

(`resolve_specimen_source` keeps serving an explicit `--specimens`; the R5
default is retired everywhere.)

### P2 — `src/rvt/frontdoor/base.py`: find the plugin's real bundle location

```diff
@@ class GenesisPin:
     def candidate_paths(self, plugin_root: Optional[str] = None) -> List[str]:
         """Where the pinned default may live, in resolution order (after
         ``--base`` and ``$RVT_GENESIS_BASE``)."""
-        out = [os.path.join(repo_root(), self.base_relpath)]
-        for pr in (plugin_root, os.environ.get("RVT_PLUGIN_ROOT")):
-            if pr:
-                out.append(os.path.join(pr, "lib", "genesis", os.path.basename(self.base_relpath)))
-        return out
+        name = os.path.basename(self.base_relpath)
+        out = [os.path.join(repo_root(), self.base_relpath)]
+        # the plugin mounts the engine at <plugin>/lib/src/rvt/** and the ONE
+        # bundled .rvt at <plugin>/assets/genesis/ — discover the bundle
+        # relative to THIS package, then honour explicit roots
+        pkg_plugin = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
+        for pr in (plugin_root, os.environ.get("RVT_PLUGIN_ROOT"), pkg_plugin):
+            if pr:
+                out.append(os.path.join(pr, "assets", "genesis", name))
+                out.append(os.path.join(pr, "lib", "genesis", name))
+        return out
```

### P3 — `tools/ifc_intent.py`: constructed specimens for the CLI path + the clean message

```diff
@@ def build_room(ifc_path: str, out_dir: str, *, base_rvt: str = DEFAULT_BASE,
     specimens = None
     if "W" in stages or "E" in stages:
         try:
-            specimens = SpecimenSet(specimen_src)
+            if specimen_src and os.path.isfile(specimen_src):
+                specimens = SpecimenSet(specimen_src)
+            else:
+                from rvt.frontdoor.standalone import ConstructedSpecimens
+                specimens = ConstructedSpecimens(base_path=base_rvt)
             record["specimens"] = {"source": _relp(specimen_src),
```

### P4 — `src/rvt/famgen/factory.py`: stage-F emission from bundled assets

```diff
@@ class FamilyProduct:
     def write(self, path: str, *, validate: bool = True, provenance: bool = True,
               timestamp: Optional[int] = 0, report_path: Optional[str] = None
               ) -> Dict[str, Any]:
-        """Emit the standalone ``.rfa`` at ``path``; verify + validate +
-        provenance-scan it; write a JSON report beside it (``<stem>.json``)."""
-        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
-        rep: Dict[str, Any] = {"path": path, "family": self.summary(),
-                               "facts": self.facts.as_json()}
-        emit = self.doc.to_rfa(path, product_name=PRODUCT_NAME,
-                               username=PRODUCT_NAME, timestamp=timestamp)
-        [... v1 body through rep["report_path"] = rp ...]
-        return rep
+        """Emit the standalone ``.rfa`` at ``path`` from BUNDLED assets
+        (container source = the certified genesis base; a user-supplied
+        ``$RVT_FAMILY_DONOR`` .rfa is the hidden escape hatch), then verify,
+        family-mode-validate and provenance-scan it."""
+        from rvt.frontdoor.standalone import standalone_family_write
+        return standalone_family_write(
+            self, path, validate=validate, provenance=provenance,
+            timestamp=timestamp, report_path=report_path,
+            family_donor=os.environ.get("RVT_FAMILY_DONOR"))
```

### P5 — `src/rvt/famgen/skeleton.py` + `famdoc_adoc.py`: no silent vendor-path default

```diff
--- a/src/rvt/famgen/skeleton.py
@@ def emit_family_rfa(doc: FamilyDoc, path: str, *, donor: Optional[str] = None,
     donor = donor or DEFAULT_DONOR
+    if not os.path.isfile(donor):
+        raise FileNotFoundError(
+            "family container source not found -- the default path (v2, "
+            "rvt.frontdoor.standalone) builds it from the bundled genesis "
+            "base; to use THIS v1 emitter supply donor= (an .rfa of yours). "
+            f"(looked for: {donor})")
--- a/src/rvt/famgen/famdoc_adoc.py
@@ def emit_family_rfa_v2(doc, path: str, *, mode: str = "candidate",
     t0 = time.time()
+    if not os.path.isfile(donor):
+        raise FileNotFoundError(
+            "family container source not found: pass donor=<the bundled "
+            "genesis base> (rvt.frontdoor.standalone.bundled_base_path()) or "
+            f"a user-supplied .rfa. (looked for: {donor})")
     if not doc.finalized:
```

(One clear line naming the single missing input; never a traceback into the
vendor path, never a request for any directory.)

### P6 — `tools/sync_plugin.py`: bundle the two path-loaded engine scripts

```diff
@@
 LIB_TOOLS_SHIM = ("frontdoor.py", "ifc_intent.py", "rvt_job.py", "probe_batch.py",
                   "spec_to_rvt.py", "ifc_to_spec.py", "seed_audit.py",
-                  "panel_schedule.py", "genesis_compose.py", "rvt_validate.py",
-                  "rvt_edit.py")
+                  "panel_schedule.py", "genesis_compose.py", "rvt_validate.py",
+                  "rvt_edit.py",
+                  # loaded by path from rvt.famgen.famdoc_adoc._ga(): the
+                  # audited ADocument purge machinery + its reducer import.
+                  # OUR OWN engine code — without them stage F dies in the
+                  # field with FileNotFoundError (docs/inbox/standalone.md §1)
+                  "genesis_assemble.py", "rvt_reduce.py")
```

Then run `python tools/sync_plugin.py` once: the tree mirror also picks up
`src/rvt/frontdoor/standalone.py` automatically.

### P7 — coordination notes for the skills / plugin stream (text, their territory)

* `plugin/skills/tekton-author/SKILL.md` “Honest caveats” item 1 still says
  the family build "needs a family format donor" and walls/equipment "a
  specimen ancestor", "the fix is one file from the user" — after P1–P6 that
  caveat is FALSE; replace with: "all build inputs ship in the plugin; a
  user file is only ever needed for a non-2026 target release
  (`$RVT_FAMILY_DONOR` / `--specimens` remain as expert overrides)".
* Exit-code text "4 = self-checks failed (do not deliver that file; deliver
  the report)": per THE DELIVERABLE RULE the file is still written and still
  the user's; suggest "deliver the file WITH the failed-self-check report
  and say plainly it failed our own validator".
* `plugin/skills/_shared/tekton_env.py` doctor: `family donor: missing`
  should become `family container: bundled (genesis base)` once P4 lands.

## 8. Proof artefacts (scratchpad, this session)

* clean-env reproduction + both E2E builds: pytest
  `tests/test_frontdoor_standalone.py` (10 passed) — the fixture rebuilds
  the clean env from `plugin/` on every run; nothing depends on ad-hoc state.
* hash table (§1): corpus `000.bin`, `G_ABPD.rvt`, `R5.rvt`, the vendor
  archetype `.rfa`, and all six `samples/*.rvt` → one sha256.
* zero-donor family probe: `emit_family_rfa_v2(prod.doc, out,
  donor=G_ABPD.rvt)` with the registry-maps fallback forced → verify ok,
  family-mode VALID 0/0, provenance PROVENANCE-CLEAN.
* clean-env room build: combined `.rvt` re-opened with
  `Document.from_file`: 4 `SWall` (type 600634, level 311, correct 30×20 ft
  ring), 8 `FamilyInstance`.

## 9. Still-needs / follow-ups (honest)

1. **Viewer certification of the constructed-template outputs.** The
   constructed SWall / FamilyInstance templates are validator-proven
   (0 errors, reference-coherent, commit round-trip) but NOT yet
   Autodesk-viewer-certified — the R5-clone path they replace had viewer
   PASSes (V22/V26 lineage). Next upload round should include the two
   clean-env outputs (`out-eaton/prompt_room.rvt`,
   `out-room/electrical-room-2500a.rvt`) with the standing certified
   control, per the certify-the-base rule.
2. **Circuits** stay a named blocker (unchanged; electrical stream).
3. **Instance seq-103**: constructed instances ride `SerializedDummy` (like
   walls); loaded SYMBOLS carry real solids. If the viewer round shows blank
   instances, the follow-up is a constructed `GElement` rep (the shape is
   documented in this stream's notes; deliberately not shipped unproven).
4. The prompt parser maps "6 switches" to a 225 A/42-space panelboard and
   does not model a switch count — prompt-coverage stream, observed here
   only.
5. Pre-existing suite breakage found while running the full suite — all
   proven independent of this stream (they reproduce identically in a fresh
   interpreter that never imports `standalone`):
   - `tests/test_engine.py` fails COLLECTION (`No module named 'bridge_lib'`)
     — still points at `skills/revit-bridge/scripts`, renamed to
     `skills/tekton-ifc/scripts`;
   - `tests/test_genesis_types.py::test_no_cloned_payload_source` —
     **hardcoded** `ROOT = "/Users/ck/dev/things/rev-revit"` at line 25
     (rename debris; FileNotFoundError);
   - `tests/test_provenance.py::test_G0_resource_refs_are_counted`
     (`asset-library-fbx` count 0 ≥ 1 expectation) and
     `::test_G0_identity_dit_usernames_still_leak`, plus
     `tests/test_electrical.py::test_committed_room_schedules_exist` —
     expectation drift against current artefacts/`src` (other streams'
     churn today; `src/rvt/provenance.py`-adjacent files were modified at
     17:5x by a concurrent session).
   One-line fixes for whoever owns the rename sweep / those streams.

## BRANCH STATE

* Repo is not a git repo (no branch). Files ADDED (my territory only):
  `src/rvt/frontdoor/standalone.py`, `tests/test_frontdoor_standalone.py`,
  `docs/inbox/standalone.md`. NO existing file edited; NO patches applied;
  plugin/ untouched (the tests simulate P6 + the sync mirror inside their
  temp env only).
* Tests: stream file **10/10 PASS** (in isolation and inside the suite).
  Full suite (`pytest tests --ignore=tests/test_engine.py`; the ignore is
  the pre-existing collection break in §9.5): **1302 passed, 4 failed,
  5 skipped in 29:25** — all 4 failures pre-existing and proven independent
  of this stream (§9.5: hardcoded `rev-revit` path + expectation drift;
  each reproduces identically in a fresh interpreter that never imports
  `standalone`).
* DONE criterion met: dependency table (§2), clean-env reproduction test,
  the resolver (`standalone.py`), the patches (§7) — and the honest line,
  earned in a clean environment with the tripwire armed:
  **creation works from bundled assets alone, ZERO donor files** — both
  worked examples, families generated / loaded / placed, walls built,
  validator 0 errors, `--family-donor` reduced to a hidden escape hatch.

## 10. INTEGRATION (2026-08-04, integrator session): P1-P7 APPLIED

Patches P1-P6 landed in source, P7 in the plugin skill texts; plugin synced,
zip rebuilt, checks + acceptance below. Applied exactly as specified except
the adaptations listed.

**Applied**: P1 `src/rvt/frontdoor/build.py` (install_schema + tripwire +
constructed-specimens default); P2 `src/rvt/frontdoor/base.py`
(package-relative `<plugin>/assets/genesis` probe); P3 `tools/ifc_intent.py`
(ConstructedSpecimens fallback); P4 `src/rvt/famgen/factory.py`
(`FamilyProduct.write` -> `standalone_family_write`); P5 skeleton/famdoc
one-line donor FileNotFoundError messages; P6 `tools/sync_plugin.py`
(+`genesis_assemble.py`, +`rvt_reduce.py` in LIB_TOOLS_SHIM); P7
tekton-author SKILL.md caveat 1 + exit-4 text, tekton_env doctor now prints
`family container: bundled (genesis base)`, plus the same stale-donor text
in tekton-native SKILL.md and tekton-doctor.md.

**Adaptations (all noted, none change the patch intent):**

1. **Tripwire lifecycle (P1)**: `forbid_research_inputs` is a process-wide
   audit hook; armed permanently it broke every later research-machine test
   in the same pytest process (31 collateral failures). `build_intent` now
   arms it and disarms in a `finally:` -- the guarantee (no research read
   DURING the build) is unchanged; the field CLI process exits right after
   anyway.
2. **provenance_scan_v2 dangling census** (`famgen/famdoc_adoc.py`): the
   scan's `zero_dangling_element_refs` used the naive Id-key collector,
   which counts non-element counters -- the genesis base's archetype tree
   carries numbering-registry DESCRIPTION ids (e.g.
   `m_oMatchRegistry.m_lastDescriptionId` = 1397) that flagged false
   positives on small families (house switchboard, 43 elements). The scan
   now uses the SAME schema-typed graph-editor census as the author gate
   (the stream's own documented authority); the naive figure stays in the
   report as `naive_id_leaves_not_ours_gt99`.
3. **Report shape**: `standalone_family_write` now also carries the full
   scan `checks` dict in `rep["provenance"]` (stage_families shape
   unchanged); `tests/test_famgen_factory.py`'s panelboard write test was
   updated from the obsolete v1 donor-carried expectations
   (`carried_format_constants`, `part_atom_ours`) to the v2 checks.
4. **Stream tests flipped to post-patch reality**
   (`tests/test_frontdoor_standalone.py`): the two pre-patch reproduction
   tests (field failure comes back without the resolvers; stock resolver
   misses the bundle) now assert the FIX on the stock path -- clean-env
   stock `author()` builds end to end with no env var, and `resolve_base`
   resolves `pinned-bundled` + certified from the plugin bundle.
5. **Autodesk-path prose reworded** (`standalone.py` docstring,
   `tekton_env.py`, both SKILL.mds, tekton-doctor.md): the ban is restated
   without the literal Windows-path spellings so the plugin zip is free of
   those byte strings (the packaging check below); the tripwire match
   constants (lowercase) are untouched and `tests/test_bootstrap.py`'s
   path-literal scan still passes.

**Rename debris fixed**: `tests/test_genesis_types.py` ROOT now resolved
from the test file's own path (was a baked `/Users/ck/dev/things/rev-revit`);
`tests/test_engine.py` -> `skills/tekton-ifc/scripts` (was
`skills/revit-bridge`); `tests/test_electrical.py` kind string ->
`tekton.electrical-summary`.

**NOT fixed (real drift, not rename debris -- provenance stream to
refresh)**: `tests/test_provenance.py::test_G0_resource_refs_are_counted`
and `::test_G0_identity_dit_usernames_still_leak`. The current
`experiments/genesis/G0.rvt` (Aug 3 17:15) reports DIT usernames
`{'rvt-writer': 23}` and ZERO `asset-library-fbx` refs -- i.e. the artifact
now carries the V32 identity scrub and purged FBX refs; both tests document
the OLD G0's leaks ("the writer's V32 scrub post-dates G0.rvt" -- no longer
true). Flipping them is a re-audit decision that belongs to the
provenance/genesis stream (also logged in docs/inbox/versions.md item 4+5).

**Full suite** (`.venv/bin/python -m pytest tests -q`, no ignores):
**1338 passed, 2 failed, 3 warnings in 22:43** -- the 2 = the G0 pair above.
`test_engine.py` collects and passes; stream file 10/10.

**Packaging**: `tools/sync_plugin.py` -> deny-audit clean, assets verified,
`tekton-plugin.zip` rebuilt (292 entries). Raw-byte scan INSIDE the zip:
0 hits for `rev-revit` / `revit-bridge` / `rvt-native` / `ProgramData` /
`Family Templates` in any entry; all 5 SKILL.md frontmatters free of
angle brackets, descriptions 518-984 chars (<=1024); plugin.json
description 366 chars (<=500).

**ACCEPTANCE (the field scenario)**: fresh temp dir containing ONLY the
unzipped `tekton-plugin.zip`, cwd there, `TEKTON_ROOT` set, RVT_*/PYTHONPATH
cleared, the plugin's own path:
`python <tmp>/skills/tekton-author/scripts/_bootstrap.py run frontdoor.py
author --prompt "create an eaton panel for me with 6 switches" --json --out
<tmp>/out` -> **exit 0, ok true, 4.3 s**:
`prompt_room.rvt` (593,920 B, combined validator **VALID 0 errors**,
identity PASS) + `families/pp1_eaton_prl2x_225a_42sp_480y_277.rfa`
(299,008 B, family-mode **VALID**, provenance clean,
`container_mode: bundled-base`), `manifest.json`/`MANIFEST.md`,
intent + handoff package, degradations [], status
`PROOF-ONLY (self-checks PASS; ...)` stamped ON the delivered file
(THE DELIVERABLE RULE upheld). An audited rerun (process-wide open/socket
hook): **0 network events, 0 reads outside the temp dir + the python
installation** (single benign OS-tempdir staging file, the tool's own
mkstemp). Base resolved to `<tmp>/assets/genesis/G_ABPD.rvt`, sha256
pin-verified; re-opened output carries 1 Family + 1 FamilyInstance.

## BRANCH STATE (integration)

* Files EDITED: `src/rvt/frontdoor/build.py`, `src/rvt/frontdoor/base.py`,
  `src/rvt/frontdoor/standalone.py` (docstring + provenance checks field),
  `src/rvt/famgen/factory.py`, `src/rvt/famgen/skeleton.py`,
  `src/rvt/famgen/famdoc_adoc.py` (P5 + census fix), `tools/ifc_intent.py`,
  `tools/sync_plugin.py`, `plugin/skills/tekton-author/SKILL.md`,
  `plugin/skills/tekton-native/SKILL.md`, `plugin/skills/_shared/tekton_env.py`,
  `plugin/commands/tekton-doctor.md`, `tests/test_frontdoor_standalone.py`,
  `tests/test_genesis_types.py`, `tests/test_engine.py`,
  `tests/test_electrical.py`, `tests/test_famgen_factory.py`; plugin mirror
  + `tekton-plugin.zip` regenerated via `tools/sync_plugin.py`.
* Suite: **1338 passed / 2 failed** (the pre-existing G0 artifact-drift
  pair, provenance stream's call). Zip checks PASS. Acceptance PASS.
* DONE: the stock entrypoints are standalone -- zero donor, zero research
  reads, the field scenario builds native `.rvt` + `.rfa` from the plugin
  alone with validator 0 errors.

### 10.1 Post-integration addendum (same session)

* **Tripwire allow-list hardening** (`build.py`): the RESOLVED base is now
  explicitly in the tripwire's allow list (`opts.base.path`), matching the
  documented contract -- an explicit `--base`/`$RVT_GENESIS_BASE` living
  under `experiments/genesis/**` (the 2025-composer shape flagged by the
  y2025-views stream) builds clean instead of tripping the guard mid-build.
  Probe: explicit base under a synthetic `experiments/genesis/` path ->
  PROOF-ONLY, errors [], family ok, combined written. Covering tests
  (`test_frontdoor.py` + `test_frontdoor_standalone.py` + `test_ifc_intent.py`)
  66/66 green after the change.
* **Final bundle**: `tekton-plugin.zip` rebuilt again after concurrent
  streams landed `src/rvt/convert/**` (mirror sweep; 2714 -> 3240 KB).
  Zip checks ALL PASS on the final artifact; the acceptance scenario rerun
  against this exact zip: exit 0, ok true, errors [], `prompt_room.rvt` +
  the `.rfa` delivered.
* **Freshness pass after convert-a landed** (same session, later): mirror
  re-synced (5 files: convert extract_family/edit_family/rfa_assemble,
  versions/records32, genesis/port2024), zip rebuilt (3241 KB), zip checks
  ALL PASS, acceptance rerun on that zip green (exit 0, errors [],
  prompt_room.rvt + .rfa), test_plugin_sync 7/7. Bundle-snapshot timing
  stays the orchestrator's call -- this was the last freshness pass by this
  session.
* **Two further teammate-requested packaging passes** (supersede the "last
  freshness pass" line above): (a) genesis-2023's request -- already
  satisfied by the prior sweep; verified their 2023 modules shipped, zero
  sample binaries in the zip, test_genesis_2023 + test_plugin_sync +
  test_versions 68/68. (b) convert-a's 00:59 rvt_to_ifc.py tag-fallback fix
  -- one-file sync. Bundle is now 4088 KB: concurrent streams landed a
  second schema-cache blob (00:37) and assets/genesis/G_ABPD_2025.rvt
  (the y2025 base) between passes; zip checks ALL PASS, test_plugin_sync
  7/7, acceptance scenario green on this exact zip. Other sessions also run
  tools/sync_plugin.py -- `--check` is the shared invariant, not this
  session's ledger.

## eng #425 — 2026-08-10 (fresh cloud clone, no `samples/`, `origin/main` @ af15f6c): the job's `--out` is an OUTPUT, never a "research input"

Issue #425 (Refs #373 / #374). On `main` a stranger whose `--out` merely lived under a directory *named* `samples/`
(`vendor/`, `extracted/`, `experiments/genesis/`) — `~/samples/jobs/x` on their own laptop — got rc 3, ONE JSON
`NO-OUTPUT (see build.degradations / errors)`, `files == {families_dir}` (empty), and six degradations, five of them
`StandaloneError … touched a research-machine input: <out>/build.log | _stages/stage_P_identity.rvt |
_stages/stage_L_loaded.rvt.load.json | prompt_room.rvt` — the tripwire of §7 calling the job's own **outputs**
"inputs" (reproduced here first, uid nobody, 2.5 s). Nothing forbidden was read, nothing was delivered: rule 1 in
spirit, PG3 for the stranger.

### Decision: (a), with (b)'s one line for the only `--out` that (a) must not exempt — and why not (c)

* **(c) is not sufficient on its own.** Policing only *read* opens sounds closest to the documented law, but the build
  *re-reads its own outputs*: stage D opens `_stages/stage_P_identity.rvt`, stage L reads back `stage_L_loaded.rvt`
  and its `.load.json`, the loader opens the `.rfa` files stage F just wrote, stage V validates the written `.rvt`.
  Every one of those is a READ of a path carrying `/samples/`, so a mode-aware hook still ends in NO-OUTPUT (later,
  with fewer notes) unless the out dir is *also* exempted — i.e. (c) needs (a) anyway, and then adds `r+`/`os.open`
  flag parsing for no remaining benefit. Rejected.
* **(b) alone withholds a deliverable from someone who did nothing wrong** (their disk, their directory name); the
  deliverable rule prefers delivery whenever nothing forbidden is read. Rejected as the general answer.
* **(a) — implemented:** `forbid_research_inputs(*, allow=…, outputs=[out_dir])`. Files under an `outputs` prefix are
  the job's own outputs and are exempt from the *corpus* law (the `/samples/ | /vendor/ | /extracted/ |
  /experiments/genesis/` segment match) — **never** from the Autodesk-install ban (the hook checks `allow` → Autodesk
  markers → `outputs` → corpus markers, in that order, so `<out>/…/Family Templates/x.rft` still raises BANNED), and an
  `outputs` entry that *equals, lies inside, or contains* a quarantine root of THIS checkout (`quarantine_roots()` =
  `<repo>/{extracted,samples,vendor,experiments/genesis}`, abspath **and** realpath compared) is silently dropped, so
  the corpus stays exactly as guarded no matter what a caller passes (`--out <repo>`, `--out <repo>/samples`,
  `--out <repo>/samples/x` exempt nothing). Prefixes end in `os.sep`: `…/samples/jobs/x` does not exempt
  `…/samples/jobs/xy/`.
* **…plus (b)'s ONE line for `--out` INSIDE a real quarantine root** (or inside an Autodesk installation directory):
  `out_dir_refusal(out_dir)` at the top of `build_intent`, before `makedirs`, before `install_schema`, before stage P:
  `--out refused (nothing built): it lies inside this checkout's quarantined samples/ directory, whose files the build
  may never read -- choose another --out than <abs out>` (reason first, path last, so `status`'s 160-char truncation
  keeps the reason). Why refuse rather than "deliver without reading a sample": (i) exempting exactly the job's files
  under `<repo>/samples/x` is not expressible as a prefix without also exempting `--out <repo>/samples` itself;
  (ii) anything written under `<repo>/samples/` **is an Autodesk sample to `is_autodesk_sample()` ever after** —
  measured: the edit route happily wrote `samples/e425/G_ABPD_2025.edited.rvt`, and `--base` on that file is then
  refused as "an Autodesk sample project"; (iii) it is the git-ignored third-party quarantine — our outputs do not
  belong among counsel-C4 material. Ancestors of a quarantine root (`--out <repo>`, `--out <repo>/experiments`) are
  *not* refused (legal today, no marker on the path) and not exempted either.
* **rc is 3, not 2, and that is deliberate for this PR.** The rc-2 mapping lives in `tools/frontdoor.py::cmd_author`
  (hot, not this territory), and its only rc-2 path (`FrontDoorError`) prints the line on **stderr with no JSON** —
  raising from `build.py` would have cost every surface the ONE JSON it parses (`go` would report `result: null`).
  Returned as `BuildResult.errors == [line]` instead: ONE JSON, `status == "FAILED (<line>…)"`, `errors == [line]`,
  `build.stages == []`, no `_stages`/`families`/`.rvt`/`build.log` created, rc 3 (`EX_INCOMPLETE`). If rc 2 is wanted,
  the hot-file patch is one line in `cmd_author` after `_print_summary`/`json.dumps`:
  `if r.errors and str(r.errors[0]).startswith("--out refused"): return EX_USAGE`.

### Evidence (uid nobody unless noted; `--json`; this VM; every run ONE JSON on stdout, 0 B stderr, no traceback)

| case | `main` @ af15f6c | this head |
|---|---|---|
| prompt `"…1 panel" --out <tmp>/samples/xN`, 3 runs | rc 3 · `NO-OUTPUT (…)` · files `{families_dir}` · manifest `json, md` · 6 degradations (5× `StandaloneError` on its own outputs) · 2.5 s | **rc 0** · `PROOF-ONLY (self-checks PASS; …)` · files `combined, families_dir` · manifest `build.log, json, md` · `errors []` · `degradations []` · 2.5 / 2.9 / 2.6 s |
| same prompt `--out <tmp>/plain/c1` (control) | — | rc 0 · same status/files/stamps · 3.0 s · `prompt_room.rvt` 606,208 B **== the samples/x1 output byte count**; `rvt_validate` `ok: true` on both (1 known DataStorage decode warning each) |
| ifc `usecases/chicago-plenum…/generated.ifc --out <tmp>/samples/i1` vs `--out <tmp>/plain/ci` | (NO-OUTPUT shape, not re-measured) | rc 0 both · identical status, files, stage list and all 11 degradations (plan refusals + census label, none guard-induced) · `combined` 749,568 B both |
| prompt `--out <repo>/samples/x425` (root: nobody cannot mkdir in the checkout — `run()`'s `makedirs`, #209's envelope) | (NO-OUTPUT shape) | **rc 3** · status `FAILED (--out refused (nothing built): it lies inside this checkout's quarantined samples/ directory, whose files the build may never read -- choose another --out than )` (160-char cut) · `errors == [the full line]` · files `{}` · manifest `json, md` · `build.stages []`, `degradations []`, `log null` · on disk only the ROUTE's pre-build files (`intent.json`, handoff, manifest) — no `_stages`, no `families`, no `.rvt` |
| ifc `--out <repo>/samples/i425` (root) | — | rc 3 · same one line · `stages []` · degradations = the IFC census label only (manifest-level, not a stage) · on disk `intent.json`, manifest |
| edit `--rvt G_ABPD_2025.rvt --edit "set level 311 elevation to 5 ft" --out <tmp>/samples/e1` | rc 0 (arms no tripwire) | rc 0, unchanged |
| edit `… --out <repo>/samples/e425` (root) | rc 0 | rc 0, **delivered into the quarantine dir**; that output `is_autodesk_sample() -> True` and is refused as a `--base` afterwards → follow-up below |
| `route.py run --prompt … --output rvt --out <tmp>/samples/r2` | rc 3 NO-OUTPUT (same `build_intent`) | **rc 0** PROOF-ONLY, `combined` + handoff files (the router's prompt/ifc→rvt cells call `FD.author`, so they inherit both the exemption and the refusal) |
| `route.py run --prompt "a 225 A panelboard …" --output rfa --out <tmp>/samples/r1` | rc 0 (no tripwire) | rc 0, unchanged |

Guard strictness, proven in `tests/test_out_dir_guard.py` (25 tests, 0.1 s, sharded): armed with
`outputs=[<tmp>/samples/jobs/x]` → its own `build.log` write + `_stages/*.rvt` write **and re-read** pass;
`<tmp>/samples/jobs/other.rvt`, `<tmp>/samples/jobs/xy/a.rvt`, `<repo>/samples/rstbasicsampleproject.rvt`,
`<repo>/vendor/…`, `<repo>/extracted/…/000.bin`, `<repo>/experiments/genesis/R5.rvt` all STILL raise;
`<out>/ProgramData/Autodesk/RVT 2026/x.rft` and `<out>/Family Templates/x.rft` raise BANNED. Armed with
`outputs=[<repo>/samples/x | <repo>/samples | <repo>/experiments/genesis/job | <repo> | <repo>/experiments]` →
`open(<repo>/samples/some.rvt)`, `open(<repo>/samples/x/prompt_room.rvt)`, `open(<repo>/experiments/genesis/job/_stages/…)`
STILL raise (the DONE's second bullet). `out_dir_refusal` refuses `<repo>/{samples,samples/x425,vendor/jobs/a,extracted/y,
experiments/genesis/probe}` and four Autodesk-install shapes with one `\n`-free line ending in the path; returns `None`
for `<tmp>/samples/x`, `<tmp>/vendor`, `<tmp>/experiments/genesis/y`, `<repo>/out/demo`, `<repo>/experiments/frontdoor/job-1`
(the default out dir), `<repo>/samplesheet`, `<repo>`, `<repo>/experiments`. `tests/test_stagelog.py::
test_tripwire_refusal_degrades_exactly_like_an_oserror` (arms with no `outputs`) is untouched and green: the observer's
last resort stays.

### Gates

* `tests/test_out_dir_guard.py` 25 passed; `tests/test_frontdoor.py tests/test_stagelog.py tests/test_out_dir_guard.py`
  108 passed / 6 skipped (2 `RVT_SKIP_LARGE`, 2 chmod-as-root, rst sample, pinned research base);
  `tests/test_frontdoor_standalone.py` 10 passed / 1 skipped (research-machine donor hatch) — the two clean-env E2E
  builds run with the guard armed the whole time.
* Whole merged CI shard (`shard_list.py --print`, `RVT_SKIP_LARGE=1 -p no:cacheprovider`, this exact head): **1531 passed /
  134 skipped / 3 xfailed, 0 failed** in 442.68 s.
* `tools/sync_plugin.py` → validation passed, zip rebuilt (5217 KB), `--check` clean; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `tools/dev/check_portable_paths.py` ok.
* Full suite NOT run (SUITE-COORDINATION). Nothing staged for the viewer: no format byte changes (the delivered
  `samples/x1` output is byte-count-identical to the plain-dir control and validates the same).

### Findings / follow-ups (outside this territory — noted, not done)

1. **The refusal belongs one level up, in `run()` (`src/rvt/frontdoor/__init__.py`), for all three routes.** Today the
   prompt/ifc routes still write `intent.json` + the handoff package + the manifest into `<repo>/samples/x` before and
   after `build_intent` refuses, and the `--rvt --edit` route (no tripwire at all) *delivers* into the quarantine dir —
   an output that `is_autodesk_sample()` then classifies as an Autodesk sample forever. `__init__.py` is outside #425's
   territory and `edit.py`/`router.py` are held by eng #448 this wave, so it is filed as **#452** (`Refs #425`) with
   this patch, which makes the CLI answer rc 2 through the existing `FrontDoorError` path *and* keeps `build_intent`'s
   check as the in-process backstop:
   ```python
   # src/rvt/frontdoor/__init__.py :: run()
       route = req.route()
       out_dir = _out_dir(req, route)
   +   from .standalone import out_dir_refusal
   +   line = out_dir_refusal(out_dir)
   +   if line:
   +       raise FrontDoorError(line)          # before makedirs: nothing lands in the quarantine dir
       os.makedirs(out_dir, exist_ok=True)
   ```
   (whether the CLI should also print ONE JSON for `FrontDoorError` under `--json` is the same hot-file question as
   `InputReleaseRefused`'s stderr-only answer, #176.) Should the edit route *arm* the tripwire too? No: its input is by
   definition a user file that may live anywhere (including a dir named `samples/`), and it authors nothing from
   bundled assets; the out-dir refusal is the only part of the law that applies to it.
2. `manifest.build.errors` lists every build error **twice** (`build_manifest` concatenates `build["errors"]` with the
   route's `errors`, which already did `errors += br.errors`); `AuthorResult.errors` has it once. Pre-existing,
   cosmetic, `manifest.py`/`__init__.py` — noted here rather than filed.
3. The corpus law is a path-*segment* heuristic, so a checkout or an unzipped plugin that itself lives under a
   directory named `samples/` (`~/samples/tekton-plugin/…`) trips on its own engine files the moment the build lazily
   imports one (`io.open_code` audits as `open` — verified: a module under `<tmp>/samples/pkg/` raises on import while
   armed). Pre-existing and unchanged by this PR (the `outputs` exemption covers only the out dir); anchoring the four
   corpus markers to `quarantine_roots()` instead of any segment would fix it but *is* a strictness change the issue
   told this stream not to make (it would stop catching corpus copies outside the checkout) — recorded for whoever
   next owns §7.
4. "This checkout's quarantine" now has three definitions in `src/`: `base.is_autodesk_sample` (`samples/` only,
   hot file), `convert.add_to_project.quarantined_input` (`vendor/` + `samples/`), and `quarantine_roots()` (all four).
   The first two could call `quarantine_roots()`; both are outside this territory — noted for the reuse pass of
   whoever next touches them.

### `/simplify` (4 lenses) — applied / skipped

Applied: one `_dirp()` prefix normaliser behind `_inside`/`_nested`/the `outputs` filter (the segment-boundary rule
lived in five expressions); one `_is_autodesk_install()` predicate shared by the hook and `out_dir_refusal` (rule 2's
test written once); the two refusal strings folded into one `f"--out refused (nothing built): it lies inside {why} --
choose another --out than {ap}"`; the quarantine clause derives its `samples/`-style name from `_RESEARCH_DIRS`
instead of a second `repo_root()` + `relpath`; `_GUARD["outputs"]` is a tuple so the hook does one
`str.startswith(tuple)` C call per open (efficiency lens: the added per-open cost is ~0.3 µs × a few thousand opens ≈
1 ms per build; nothing hoistable remains, no realpath/stat in the hook, no closure capture); the test fixture yields
`forbid_research_inputs` directly. Skipped, with reasons: collapsing `allow=` and `outputs=` into ONE exemption lane
(altitude #1) — it would change `allow`'s standing semantics (the resolved base under `experiments/genesis/` must
stay exempt, and `allow` precedes the Autodesk check today) which is behaviour outside #425; moving the refusal to
`run()` (altitude #2) — follow-up 1 above, out of territory; a shared `conftest.py` arm/disarm fixture for the three
test files (reuse #3) — wider than this diff; findings 4 above (reuse #1) — out of territory.

### Review round 1 (tech lead 🟡 on 92e9e49) — the overlap test now compares ONE canonical spelling

The reviewer's 21 read-probes matched `main`; three *arming/refusal* shapes did not, all one cause — quarantine
roots were compared in the checkout's `abspath(__file__)` spelling, case-sensitively, while `outputs` carried
abspath+realpath and were filtered per spelling:

* **E1** `--out <repo>/Samples/x425` → not refused and prefix-exempted; on NTFS/APFS that IS `samples/x425`
  (main: every read under it raised, the segment law being case-blind);
* **D5** engine imported through a symlinked checkout spelling + `--out <real>/samples/Snowdon` →
  `out_dir_refusal() is None`, `_GUARD["outputs"] == ('<real>/samples/Snowdon/',)`, reads under it allowed;
* **D3** a direct caller arming `outputs=[<treelink>/samples/Snowdon]` kept the link spelling as a prefix.

Fix: `_canon(path) = _dirp(normcase(realpath(path)).lower())` and `_inside`/`_nested` compare canonical forms
of BOTH sides (so any spelling of the out dir meets any spelling of the root; case-blind like the hook's own
segment law); an output is dropped **entirely** when the output itself — hence any of its spellings — nests a root,
and only surviving outputs contribute their abspath+realpath prefixes to the hook. Re-measured at the CLI:
E1 → rc 3, the one line (`… than /home/user/tekton/Samples/x425`), files `{}`; D5 (`python <treelink>/tools/frontdoor.py
… --out /home/user/tekton/samples/Snowdon`, `repo_root()` confirmed = the link spelling) → rc 3, the one line;
the stranger (`--out <tmp>/samples/x9`, uid nobody) → rc 0, PROOF-ONLY, `degradations []`, unchanged. Four tests
added to `tests/test_out_dir_guard.py` (29 total, 0.7 s): the case variant, the symlinked-checkout spelling
(`repo_root` monkeypatched to a `tmp/treelink -> <repo>` symlink), the symlink-spelled output arming (+ a
link-spelled ancestor), and the positive twin — a stranger dir reached through a symlink stays exempt under BOTH
spellings (`_GUARD["outputs"] == {link/, real/}`, its `build.log` appends under either).

Also taken (the reviewer's optional item, one token, caused by this stream's signature change):
`tools/genesis_compose_2025.py::_forbid_with_base(*, allow=(), **kw)` passes `outputs=` through instead of
`TypeError`-ing inside the obsolete `--simulate-allow-fix` dev simulation. Gates on this head: stream-local
`test_frontdoor + test_stagelog + test_out_dir_guard + test_frontdoor_standalone` **122 passed / 7 skipped**;
whole merged shard on this head **1535 passed / 134 skipped / 3 xfailed, 0 failed** (441.44 s); `sync_plugin.py
--check` clean, `validate_plugin` PASS, portable paths ok.

## BRANCH STATE (eng #425)

* Branch `cam/425-out-dir-not-research-input` from `origin/main` @ af15f6c.
* Files written: `src/rvt/frontdoor/standalone.py` (§7: `_RESEARCH_DIRS`, `quarantine_roots`, `out_dir_refusal`,
  `forbid_research_inputs(outputs=)`), `src/rvt/frontdoor/build.py` (`build_intent` up-front refusal; arming call passes
  `outputs=[opts.out_dir]`), `tests/test_out_dir_guard.py` (new, 29), `tests/ci_shard.d/425-out-dir-guard.txt` (new),
  `tools/genesis_compose_2025.py` (`**kw` pass-through, review round 1),
  `tests/test_frontdoor.py` (quarantined-name test tightened to rc 0 + delivered; new refused-up-front twin),
  `docs/inbox/standalone.md` (this section); regenerated mirrors `plugin/lib/src/rvt/frontdoor/{standalone,build}.py`.
* Gates: as listed above (shard 1531/134/3x on 92e9e49; **1535 passed / 134 skipped / 3 xfailed** after review round 1); `sync_plugin.py --check` clean; `/verify`: bare-unzip
  `go author --prompt "…6 panels" --out <tmp>/samples/j1 --json` (uid nobody, system python3) → READY, exit 0, PROOF-ONLY,
  `combined` + `families_dir`, `build.log, json, md`, `errors []`; the 6-panel `.rvt` built into `<tmp>/samples/v1`
  `rvt_validate` VALID (no errors; 1 known warning) and `provenance.py --baseline all --streams` shows exactly the
  plain-dir control's rows (the standing G2/#19 identity + base-residue items), nothing new; nothing staged for the
  viewer; nothing awaits a human.
* Shipped vs staged: everything in this PR ships. Follow-up 1 filed as #452 (`Refs #425`).
