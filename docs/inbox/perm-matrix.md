# perm-matrix stream — THE PERMUTATION MATRIX + THE ROUTER

Stream: perm-matrix (matrix + router). Date: 2026-08-04.
Charter: formalize EVERY meaningful (inputs, output) cell over inputs
{prompt, ifc, rvt, rfa, spec} → outputs {rvt, rfa, ifc} with honest
works/partial/missing status + runnable evidence; build the router that
composes the EXISTING certified stages (no new business logic); wire a new
CLI; demonstrate five routes; test every claim.

## What landed (all NEW files; nothing frozen was edited)

* **`src/rvt/frontdoor/matrix.py`** — the machine-readable truth table:
  `STAGES` (14 composable stages, dotted impls resolved lazily), `CELLS`
  (21 explicit cells: all 15 singles + 6 combinations), `CHAINS` (4 named
  multi-hop routes), `cell_for` / `closest_supported` /
  `unsupported_line` (THE one clear line), and **`verify_evidence()`** —
  the self-audit that every cited test/worked path exists on disk and
  every `certified:` citation is really in
  `docs/coverage/viewer-certified.json`'s CERTIFIED list. A stale or
  invented claim FAILS the suite, not just the doc.
* **`src/rvt/frontdoor/router.py`** — `route(inputs, output, **opts)`:
  looks the cell up, executes the stage chain by IMPORTING the existing
  stage functions (`rvt.frontdoor.author` composite, `prompt_intent`,
  `intent`/`ifc_out`, `tools/ifc_intent.py stage_families`,
  `rvt.ifc.product_facts` + `famfrom_ifc` + the certified four-registry
  `rvt.famload` loader, `tools/rvt_job.py create`, the certified edit
  pipeline), delivers EVERY intermediate (intent JSON, IFC, families,
  facts, underlying manifests) beside the final output, and writes a
  route manifest (`route.json` + `ROUTE.md`: cell, steps+timings, stamps,
  caveats-after-delivery, matrix evidence, detected Revit release of
  every delivered .rvt/.rfa). Missing/unknown cells return `ok=False` +
  the one clear line naming the closest supported route — never a
  traceback. Adds NO authoring logic (routing/adaptation only: famspec →
  the existing constructors verbatim; edit-shaped-vs-authoring-prompt
  dispatch via the existing `parse_edit_spec`).
* **`tools/route.py`** — the CLI: `run` (any permutation; `--via
  ifc|family` selects chains), `matrix` (prints the live table + runs the
  evidence self-audit), `explain` (one cell). Exit codes: 0 delivered /
  2 usage / 3 incomplete / 4 unsupported-cell-with-clear-line.
* **`tests/test_router.py`** — 48 tests: matrix shape + honesty audit
  (`verify_evidence()==[]`), matrix↔router coherence (every non-missing
  cell resolves to a registered impl; chains too), all 15 singles
  enumerated, every missing cell parametrized to assert the clear-line
  behavior, per-works-cell structural smoke always on, end-to-end smokes
  for prompt→rfa / prompt→ifc(round-trip) / spec→ifc / ifc→ifc /
  prompt+rvt-edit / spec→rfa chain / famspec→loaded-rvt / prompt→ifc→rvt
  chain / ifc→rvt (heavy ones gated file-presence + `RVT_SKIP_LARGE`,
  mirroring test_frontdoor), route-manifest contract, CLI exit codes.
  **48 passed** (181 s full; 44 passed / 4 skipped in 8 s with
  `RVT_SKIP_LARGE=1`).
* **`docs/product/PERMUTATION-MATRIX.md`** — the user-facing capability
  truth table (rendered from the machine matrix; states the deliverable
  rule, the status vocabulary, every caveat, the named gaps).
* **Demonstrations** — `experiments/routes/demo1..demo5` (below).

## The honest cell census

* **works: 12** — prompt→{rvt,rfa,ifc}; ifc→{rvt,rfa,ifc}; spec→{rvt,rfa,
  ifc}; rfa→rvt (famspec contract); prompt+rvt→rvt (edit); spec+rvt→rvt
  (job-runner seed).
* **partial: 3** — ifc+rvt→rvt (merge onto YOUR base: certified stage
  code + gates run, viewer evidence only on the genesis base);
  rfa+rvt→rvt (load into YOUR host: four-registry mechanism + gates,
  viewer evidence on rst host + genesis lineage only); prompt+ifc→rvt
  (build-then-edit composition; intent-level merge unbuilt).
* **missing: 6** — rvt→rvt (no-op without instructions), rvt→ifc (no
  RVT→intent resolver), rvt→rfa (family extraction unimplemented + the
  content rule forbids redistributing vendor family bytes), rfa→ifc (no
  family→IFC emitter), rfa→rfa and prompt+rfa→rfa (no family-edit
  pipeline). Every one answers with the matrix row + closest supported
  route in one line (exit 4).
* **Everything else** (any unenumerated combination) falls back to the
  same clear-line answer by construction — the matrix is total.

## Five demonstrated routes (all delivered under `experiments/routes/`)

1. **demo1-prompt-to-rfa** (single): panel prompt → **2 .rfa** (validator
   VALID family-mode, provenance ok) + intent.json; 3.0 s.
2. **demo2-spec-to-ifc** (single): chicago room-spec → IFC4, 657
   entities, 13 equipment, deterministic; 0.3 s.
3. **demo3-prompt-via-ifc-rvt** (**the mandated CHAIN** prompt→IFC→RVT):
   the 2500 A room prompt → intent → our IFC4 → re-resolved by our own
   resolver → .rvt on the certified genesis base; open-bug stamp riding
   the combined file, both intents delivered
   (intent-from-prompt.json + the ifc leg's intent.json); 23.0 s.
4. **demo4-rfa-loaded-rvt** (**the mandated COMBINATION** RFA→loaded-RVT):
   famspec `{"kind": "downlight"}` → our .rfa (delivered) → the SAME
   family document four-registry-LOADED into the loader-certified rst
   host → loaded .rvt, **project validator 0 errors**, load report
   delivered; 35.5 s. (Reproduces the viewer-certified
   L1a/L_downlight_loaded mechanism.)
5. **demo5-prompt-rvt-edit** (combination): prompt+rvt on demo3's output
   — "move DP-1 to 3,1,4.66; delete LP-4 with cascade" → edited .rvt,
   hard gates PASSED (PROOF-ONLY stamp); 1.8 s.

Bonus (verified, scratch only): **product-IFC auto-fallback** — routing
`--output rvt --ifc chicago-plenum-downlight.ifc` finds nothing
room-buildable and falls back to ifc→facts→rfa→loaded-rvt, ok=True,
6 steps traced in route.json; 89.8 s.

## Named findings / blockers hit live

* **rename/set-mark on OUR created instances fails** (already a named
  blocker in docs/inbox/frontdoor.md): "rename panel LP-1 to LP-9" on a
  frontdoor-built file dies in planning — `rvt.manipulate` finds no param
  set on the created instance (param rows not authored yet). The router
  surfaced it as ONE honest status line, no traceback. Move/delete/
  cascade (the certified ops) work on the same file.
* **famload consumes FamilyDoc/builder, never an .rfa path** — there is
  no .rfa→FamilyDoc reconstitution anywhere in the tree
  (famdoc_adoc.derive_family_inventory reads an .rfa's unit 0 but yields
  an inventory, not a loadable doc). Hence the rfa input contract is a
  famspec (rebuild-by-constructor); a bare .rfa path is refused with the
  matrix row. Flipping this needs a reconstitution stage (proposed below).
* **spec→rvt has two live routes**: the modern chain
  spec→ifc→intent→rvt (genesis base) and the legacy direct
  `rvt_job.py create --spec` (template/seed project, V23-certified) —
  the matrix keeps the legacy one as the spec+rvt (seed) cell instead of
  pretending there is one route.
* **`intent.json` collision in chains**: both chain legs write
  `out_dir/intent.json`; the router renames the prompt leg's to
  `intent-from-prompt.json` so BOTH intents are delivered.

## COORDINATION — the in-flight convert streams flip my cells (orchestrator)

Discovered mid-stream: `src/rvt/convert/` is landing CONCURRENTLY
(convert-B record `docs/inbox/convert-b.md`, still open at my close;
territory disjoint from mine) with `add_to_project` (prompt+rvt→rvt INTO
the target), `merge_ifc` (ifc+rvt→rvt), `modify_family` (prompt+rfa→rfa),
plus further modules with no closed record yet (`rvt_to_ifc`,
`extract_family`, `rfa_assemble`, `edit_family`) — i.e. implementations
for exactly the cells my matrix marks partial/missing. Per "act only on
queryable state" I did NOT claim those cells: their record is unfinished
and their proofs are not yet ledgered. **The integration is one edit per
cell by design**: in `src/rvt/frontdoor/matrix.py` update the Cell's
status/stages/evidence (verify_evidence() will hold the citations honest),
and register the impl in `router._IMPLS` — e.g. prompt+rvt's partial
authoring branch should dispatch to `rvt.convert.add_to_project` once
convert-B closes with its evidence; likewise ifc+rvt → `merge_ifc`,
prompt+rfa → `modify_family`, rvt→ifc → `rvt_to_ifc`, rvt→rfa →
`extract_family`, bare-.rfa reload → `rfa_assemble`.
`tests/test_router.py` will force the closest-route lines and smoke
coverage to follow.

## Proposed follow-up work (for the orchestrator's tracker)

1. **RVT→intent resolver** — flips rvt→ifc, enables true ifc+rvt /
   prompt+ifc intent-level merge and rvt→rvt re-authoring. Biggest
   single unlock of the missing column.
2. **.rfa→FamilyDoc reconstitution** — flips bare-.rfa loads and is the
   prerequisite of the family-edit pipeline (prompt+rfa→rfa).
3. **Standalone catalog-kind famload** (panelboard/transformer/luminaire
   outside the room pipeline) — widens the rfa cells beyond downlight.
4. **Instance param rows on created instances** — unlocks rename/set-mark
   edits on our own output (the demo5 finding).

## The tools/frontdoor.py integration (PATCH ONLY — file untouched)

tools/frontdoor.py is frozen for the 2024/2023 release fleets; verified
byte-identical after this stream (md5 1d8dca7b678896cf773db9c4b23ee552 ==
pristine). The patch below adds an epilog pointer + a read-only `matrix`
subcommand delegating to tools/route.py. It parses, dry-run-applies
cleanly, and the patched copy was functionally checked (matrix prints;
author unaffected) before being deleted. The raw patch file sits beside
this record as `docs/inbox/perm-matrix-frontdoor.patch`; apply with:
`cd tools && patch -p1 frontdoor.py < ../docs/inbox/perm-matrix-frontdoor.patch`

```diff
--- a/frontdoor.py
+++ b/frontdoor.py
@@ -64,7 +64,10 @@
         description="THE FRONT DOOR: prompt / IFC / (rvt + edit) -> the ONE intent model -> our "
                     ".rvt on the certified genesis base + a deliverable manifest.",
         formatter_class=argparse.RawDescriptionHelpFormatter,
-        epilog="One entrypoint, three inputs -- exactly ONE of --prompt / --ifc / --rvt.")
+        epilog="One entrypoint, three inputs -- exactly ONE of --prompt / --ifc / --rvt.\n"
+               "Any OTHER permutation (rfa/spec inputs, combinations, chains, rfa/ifc\n"
+               "outputs): tools/route.py -- the permutation router over the same stages\n"
+               "(matrix: docs/product/PERMUTATION-MATRIX.md; `route.py matrix` prints it).")
     sub = ap.add_subparsers(dest="cmd", required=True)
     pa = sub.add_parser("author", help="author from a prompt, an IFC, or an existing .rvt + edit")
     src = pa.add_argument_group("input (exactly one)")
@@ -119,6 +122,9 @@
                     help="skip the handoff package (fallback build only)")
     pa.add_argument("--json", action="store_true", help="print the result as JSON")
     pa.add_argument("--verbose", "-v", action="store_true", help="stream the build log")
+    pm = sub.add_parser("matrix", help="print the permutation matrix (all routable "
+                                       "input/output cells; tools/route.py runs them)")
+    pm.add_argument("--json", action="store_true")
     return ap
 
 
@@ -184,11 +190,23 @@
     return EX_OK
 
 
+def cmd_matrix(a) -> int:
+    import importlib.util
+    p = os.path.join(HERE, "route.py")
+    spec = importlib.util.spec_from_file_location("_frontdoor_route", p)
+    mod = importlib.util.module_from_spec(spec)
+    sys.modules[spec.name] = mod
+    spec.loader.exec_module(mod)
+    return mod.cmd_matrix(a)
+
+
 def main(argv=None) -> int:
     ap = build_parser()
     a = ap.parse_args(argv)
     if a.cmd == "author":
         return cmd_author(a)
+    if a.cmd == "matrix":
+        return cmd_matrix(a)
     ap.error("unknown command")
     return EX_USAGE
```

(Plugin skill docs mentioning the router are likewise NOT touched —
plugin/skills/*/SKILL.md is frozen; suggested one-liner for the owner:
"any other permutation: scripts/route.py — see PERMUTATION-MATRIX.md".)

## Honesty notes

* No cell claims viewer acceptance the ledger does not carry: `certified:`
  citations are checked MECHANICALLY against
  docs/coverage/viewer-certified.json by `verify_evidence()`, which both
  `tools/route.py matrix` and the test suite run.
* Router outputs in this stream are validator/census/identity-gated but
  NOT viewer-tested; nothing here adds acceptance claims. All outputs
  carry the PROOF-ONLY stamps of their underlying pipelines.
* The 2024/2023 release-fleet territory was not entered:
  tools/frontdoor.py (md5-verified pristine), plugin/skills/**,
  src/rvt/frontdoor/base.py, src/rvt/versions/** untouched. All new code
  in new modules.

## Full suite (run to completion on the LIVE, concurrently-edited tree)

`.venv/bin/python -m pytest` over all 85 test files (run in 9 sequential
chunks to fit the 10-min tool ceiling; one interpreter per chunk, every
file run exactly once; ~34 min total, 2026-08-05 ~00:00-00:35):
**1,664 passed, 7 failed, 2 skipped.**

The suite grew live DURING this stream (new files landed mid-run from
sibling streams: test_coldstart, test_compose_2025, test_convert,
test_convert_combo, test_genesis_2023, test_surface_perf, test_y2025_*).
The 7 failures, attributed:

* **5 = ONE shared regression, not this stream's code** — between my
  48/48 test_router run (~23:20) and the chunked suite, `rvt.validate`
  gained two new semantic laws that the CURRENT authoring pipeline's own
  output does not satisfy: (a) *"placed FamilyInstance(s) carry a
  connector manager of an unlawful class (corpus 13,636/13,636 =
  FamilyInstanceConnectorManager or null)"* and (b) *"ContentTable
  m_ContentRecSet is NOT ascending by ContentKey GUID (rvt.famload
  sorts, chained rvt.famgen.loader loads did not)"*. VERIFIED outside my
  territory: the UNTOUCHED `tools/frontdoor.py author --rvt` on the
  committed worked example now fails validation with exactly these two
  errors. Fails: `tests/test_router.py::{test_e2e_prompt_rvt_edit,
  test_e2e_prompt_via_ifc_to_rvt_chain, test_e2e_ifc_to_rvt}` (my three
  end-to-end canaries — correctly red: the router honestly propagates
  the gate verdict) and `tests/test_surface_perf.py::{...author...,
  ...edit_roundtrip...}` (another stream's new tests, same root cause).
  Owner: whichever stream tightened the validator ahead of the
  famgen-loader/connector-manager fix — the checks look RIGHT
  (corpus-law-shaped); the pipeline needs to catch up, or the laws need
  to land WITH the fix. Escalated to the orchestrator.
* **1 = genesis territory**: `tests/test_genesis_assemble.py::
  test_ladder_end_to_end` — G0a rung four-registry incoherence
  (units/CD 14 vs CT/FamilyMgr 52) in a fresh ladder build.
* **1 = 2025-fleet territory**: `tests/test_y2025_a.py::
  test_probes_manifest` — KeyError 'certified_by' (probes manifest
  schema drift).

All 45 other test_router tests pass on the current tree; the full
48/48 (including the three canaries) passed at ~23:20 against the
pre-tightening tree, and the five demonstration deliveries under
`experiments/routes/` were produced and gate-green at that time. The
earlier `test_plugin_sync` drift (lib copies of in-flight
versions/convert files) was already re-synced by its owner mid-run and
passes in the chunked suite.

## BRANCH STATE

* Branch/tree: working tree at repo root (no worktree; no commits made —
  integration is the orchestrator's).
* NEW files: `src/rvt/frontdoor/matrix.py`, `src/rvt/frontdoor/router.py`,
  `tools/route.py`, `tests/test_router.py`,
  `docs/product/PERMUTATION-MATRIX.md`, `docs/inbox/perm-matrix.md`,
  `docs/inbox/perm-matrix-frontdoor.patch`, `experiments/routes/README.md`,
  `experiments/routes/demo{1,2,3,4,5}-*/**` (deliveries incl. route.json
  + ROUTE.md each).
* MODIFIED files: none outside the list above; frozen territory verified
  untouched (frontdoor.py md5 == pristine).
* Patches to apply by the integrator: the tools/frontdoor.py diff above
  (optional; additive only).
* DONE check: honest matrix (21 cells + total fallback, evidence
  self-audited) ✓; working router (composes existing stages, delivers
  intermediates + manifest, clear-line fallback) ✓; five demonstrated
  routes incl. the mandated chain (prompt→IFC→RVT) and combination
  (RFA→loaded-RVT) ✓; tests (48, incl. per-works-cell smokes and
  missing-cell message asserts) ✓; full suite run + counted ✓.
