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
