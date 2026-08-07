# genesis-integrate — THE LAW IN CODE, THE PROVENANCE MEASURE OF Y9, AND THE FAMILY BATCH (workstream record, 2026-08-04)

Charter (post ORCHESTRATOR VERDICTS #17): three integration jobs on top of the
breakthrough (the in-place substitution ladder K4 → Y9 LOADS): (1) fold THE
REDUCTION LAW into code — a guard module + tests + the exact diffs that make the
neutralise-referrers pre-pass unable to produce a genesis base ever again;
(2) measure the honest genesis-progress number of Y9 byte-weighted and per
stream, reconciled with the 1,333 / 3,342 element census; (3) verify the
family-genesis artefacts and write their probes manifest in the batch-gate
schema so the orchestrator can stage them.

**Deliverables (this stream's territory only):** `src/rvt/reduce_law.py` (new
module), `tests/test_reduce_law.py` (35 pass, ~1.8 s),
`docs/writer/y9-provenance.md` (the measure), `experiments/families/genesis2/
probes.json` (REPLACED — gate schema, every file's base resolvable), and this
record.  No existing `src/rvt/*.py`, tool, test or `.rvt`/`.rfa` was edited; no
browser / viewer used.  The two diffs for files OUTSIDE this territory
(`tools/genesis_triage.py`, `src/rvt/reduce.py`) are in §5 below, NOT applied.

## Result in one screen

* **Job 1 — the law is code, and the K1 regression is nailed.**
  `rvt.reduce_law` carries THE LAW as data (five clauses, the sanctioned
  generator table, the three banned neutralise rules, the purpose policy),
  the byte-strict `element_diff` instrument (k1_autopsy's method over seq
  101/102/103, full framed-record identity incl. the stamp),
  `assert_edit_free(before, after)` (THE GUARD: raises `SurvivorEditedError`
  on any edited survivor / added id, classifying every edit into the clause it
  breaks with the decoded evidence — nulled id leaves, dropped struct entries,
  pruned view maps), the K3/K4 byte-vindication technique
  (`vindication_sources`), the in-place law the substitution engine can
  assert (`check_substitution` / `assert_substitution`), the generator
  policy (`law_policy()` / `guard_generator("neutralise-referrers",
  "genesis-base")` → `BannedGeneratorError`), and the sanctioned replacement
  for the pre-pass (`deletion_with_content_seed` = the referrers to ADD to
  the maxgc seed so they are deleted WITH the content).  **Verified on the
  real files:** `assert_edit_free(R5, K1a_editfree)` ACCEPTS (599 removed, 0
  survivors edited); `assert_edit_free(R5, K1)` REJECTS with exactly the
  autopsy's accounting — 2,117 removed, **23 edited survivors: 4×clause 1
  (family/type orphaning), 4×clause 2 (schedule / topology / arrow structs),
  7×clause 3 (model-view state maps), 7×clause 4 (sheets) + the sheet
  1457028 marked BYTE-VINDICATED by K3 when K3/K4 are supplied** — and
  `assert_substitution(K4, Y1, {2})` reads the certified in-place rung
  correctly.  `.venv/bin/python -m rvt.reduce_law` prints the whole demo.
* **Job 2 — the honest number: 6.3 % of Y9's bytes are our expression; the
  census's 39.9 % of elements and it are the same fact.** Y9 = 4,385,733
  inflated bytes: **(i) OUR constructed element objects 275,603 (6.28 %)**
  [+10,363 constructor output byte-identical to Autodesk's, 57 slots];
  **(ii) Autodesk element residue 1,643,673 (37.48 %)** (the 2,009);
  **(iii) the two product corpora 1,830,415 (41.73 %)** (`Formats/Latest`
  496,597 + the ESSchemaStorage Forge corpus inside `Global/Latest`
  1,333,818 — counsel C4); **(iv) format / machinery 625,679 (14.27 %)**
  (non-corpus ADocument scaffold 246,256 + the landed elements' Autodesk
  headers/reps 215,025 + ElemTable 133,718 + fingerprints 30,602 + 78).
  Excluding the corpora, ours = 10.8 % of authored bytes; of the host
  seq-102 OBJECT bytes 18.0 % are our constructors'.  The provenance
  instrument's element verdicts reconcile with the census with NO remainder
  (2,059 "sample" = 2,002 residue + our 57 identical slots; 1,283 "modified"
  = our 1,276 changed slots + 7 K3-lineage usage-nulled types), the tool's
  "0.0 % ours" is a 4-KB-block-granularity artefact, and `Global/Latest` +
  `Global/ElemTable` are BYTE-IDENTICAL to K4 (zero registration motion
  re-verified at Y9).  The residue re-ranked BY BYTES: 70 % of it is four
  removal / ship-product-data questions (466 param definitions 423 KB, 18
  appearance assets 319 KB, the 125-KB assembly-code table + property sets,
  the HVAC product database 188 KB); the two real constructor gaps (X6b
  subcategories 178 KB, curtain systems 58 KB) are 14 %.  Full accounting +
  reproduction: `docs/writer/y9-provenance.md`.
* **Job 3 — the family batch is stageable.** All seven v2 `.rfa` files and
  `L_v2_panel_loaded.rvt` EXIST and validate (family-mode 0/0 on every .rfa;
  the authentic Autodesk archetype scores WORSE — 2 family-mode errors — as
  the calibration control; L_v2 project-mode 0 errors / 1 warning, identical
  to the certified L1a).  `experiments/families/genesis2/probes.json` is
  rewritten in the gate schema: **every file resolves to a declared base**
  (verified with `probe_batch.py resolve`: L_v2 → `samples/rstbasicsample
  project.rvt` [sample, certified by rule]; FG1/FG3/FG4/FG5 → the family
  ARCHETYPE `vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa`
  [not yet certified]; FGa/FGb/FGc → FG1).  The archetype is NOT certified and
  **no standalone .rfa has ever been read by the viewer**, so the manifest
  proposes THREE gated rounds: **F1 (admissible NOW — `probe_batch.py check`
  says ADMISSIBLE): L_v2 + the archetype as candidate-base (+ the auto
  control, preferably `--control-from` the certified L1a)**; F2 (after the
  archetype PASSES / is ledgered): FG1 flagship + FG3/FG4/FG5 attribution on
  the certified archetype; F3 (after FG1): FGa/FGb/FGc one-change variants
  of FG1.

## Evidence log

### E1. The guard reproduces the K1 autopsy record-for-record (job 1)
`.venv/bin/python -m rvt.reduce_law` (0.4 s to load R5 / K1a / K1):
`check_reduction(R5, K1a_editfree)` → `[EDIT-FREE] removed 599, added 0,
common 26,133, SURVIVORS EDITED 0`.  `assert_edit_free(R5, K1)` raises
`SurvivorEditedError`: `removed 2,117, added 0, SURVIVORS EDITED 23
(vindicated 1)`, `clause1=4, clause2=4, clause3=7, clause4=7` (22
unvindicated), each survivor line naming id / class / name / seqs / clause /
evidence, e.g. `876569 FamilySymbol -> CLAUSE 1 | nulled 2: m_familyId,
m_ownerInstanceId`, `1250040 DBViewGraphSchedColumn -> CLAUSE 2 | dropped
seq102:m_visGridIntPntArr 27->0`, `1250103 DBView3d 'Structure (Foundation)'
-> CLAUSE 3 | dropped m_oHiddenElementsViewSettings.m_hiddenElements 278->0`,
and the sheet 1457028 `[VINDICATED by K3,K4]`.  This is the autopsy table
(k1-autopsy.md §2) recomputed by the guard's own instrument — the byte-diff
sees what the ElemTable ("6,540 clean rows") could not.

### E2. The instrument criterion is the full framed record (job 1)
`element_diff` compares (seq, class_id, stamp, body_size, sha1(payload),
trailer_ok) per record — the whole on-disk framing.  Measured on the real pairs:
the strict criterion and k1_autopsy's payload+class criterion agree exactly
(R5→K1a: 599 removed / 0 modified; R5→K1: 2,117 / 23), so the guard is
byte-strict at no false-positive cost.

### E3. The census and the byte measure are one fact (job 2)
Union of the nine cumulative rung reports (Y1..Y9 `byte_delta`): 1,276 changed
landed slots + 57 landed-but-byte-identical (Y2 4, Y3 3, Y5 40, Y9 10) = 1,333.
The direct K4↔Y9 record diff finds **exactly the same 1,276 changed slots**,
every one seq-102 only; 11 of 12 streams byte-identical to K4 (only
`Partitions/21` differs); Y9 host id set == K4's (3,342).  The Y9↔rst diff and
the provenance tool's element table cross-tabulate onto the census with zero
remainder (§4 of the doc; the 7 residue elements that differ from rst are the
K3 usage-nulled attribute/callout/viewport TYPES, sample lineage with one field
nulled).  Residue byte total 1,643,673; every one of the 2,009 residue elements
falls in an Yn bucket (0 unbucketed) — bucket byte table in the doc §3.

### E4. Global/Latest attribution (job 2)
`rvt.adocument.decode_latest(Y9)` decodes clean (1,580,060 / 1,580,066 bytes
consumed + the constant trailer); `bytes_by_appinfo()['ESSchemaStorage']` =
1,333,818 (893 unit-schema pairs 796,204 string bytes + 422 parameter-schema
pairs 537,134); the remaining 246,256 bytes are the sample's registry scaffold
(CategoryTracking 53,528, AppInfoElementsAssociations 33,526, NumberingAppInfo
29,071, SymbolIdMgr 19,146, ETD 12,948, …).  Y9's Latest is BYTE-IDENTICAL to
K4's and 99.95 % identical to rst's (810 bytes = the K3/K4 registry
reconciliation, inherited).

### E5. The family files verify; the manifest resolves (job 3)
`rvt.famgen.famdoc_adoc.validate_family_file` on all seven v2 `.rfa`: family-mode
`ok=True`, 0 errors, 0 warnings each; raw-arbiter residuals = the known 3
family-shape calibration gaps (ProjectInformation missing / PartAtom
unframed).  Same instrument on the archetype
`vendor/.../racbasicsamplefamily-2026.rfa` (417,792 B, md5 6854cceb…):
`ok=False`, 2 family-mode consistency errors (its GraveyardRec / DIT layouts
are outside our project-calibrated decoders) + 5 raw errors — the authentic
Autodesk file scores worse than ours, exactly as the family-genesis assay
recorded.  `tools/rvt_validate.py --quiet` on `L_v2_panel_loaded.rvt` and the
certified `L1a_rstbasic_loaded_levelhead.rvt`: both `OK errors=0 warnings=1`.
`probe_batch.py resolve` on all 8 genesis2 files: 8/8 declared bases resolve
(L_v2 → sample [admissible now]; the four constructions → the archetype
[unknown = not yet certified]; the three attribution variants → FG1 [unknown
until FG1 certified]) — ZERO "NO DECLARED BASE".  `probe_batch.py check
experiments/families/genesis2/L_v2_panel_loaded.rvt --candidate-base
vendor/.../racbasicsamplefamily-2026.rfa` → **ADMISSIBLE**.  `check` on FG1
alone → the intended CERTIFICATION refusal ("upload the base as a
candidate-base first, certify it, then re-propose") — a lineage refusal by
design, not a resolution refusal.

### E6. Manifest-resolution gotcha found and worked around (job 3)
The gate's path extractors (`_PATH_RE`, `_name_index`) only see `experiments/`,
`samples/`, absolute paths and unique bare names — a repo-relative `vendor/...`
string is UNRESOLVABLE (and, worse, the absolute-path regex lazily matches the
bogus substring `/phi-ag-rvt/...rfa` out of a relative `vendor/phi-ag-rvt/...`
string).  The .rfa entries therefore declare `base` as a DICT whose FIRST
value is the archetype's ABSOLUTE path (what today's gate resolves — `rel()`
turns it back into `vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-
2026.rfa`) followed by the repo-relative path + rationale.  Verified: both the
dict form and the absolute-first string form resolve to the repo-relative
archetype path.  The clean fix is one line in the gate (§5c).

## New laws / method findings (for KNOWLEDGE.md)

1. **THE LAW is now executable, and executable is how it should be enforced.**
   `rvt.reduce_law.assert_edit_free(parent, child)` is the mechanical clause 4;
   `guard_generator("neutralise-referrers", "genesis-base")` refuses the
   pre-pass before it emits; the substitution engine's byte-delta assertion is
   `assert_substitution(parent, child, landed_ids)`.  A rung is not "clean"
   because its author says so — it is clean when the guard read the two files.
   `[verified: the K1 regression, E1]`
2. **The guard's rejection is diagnostic, not just a veto.** Classifying each
   edited survivor by class group + edit signature (nulled id leaves / dropped
   structured entries / pruned view maps) reproduces the autopsy's five edit
   groups from the bytes alone and names the certified ALTERNATIVE per clause
   (put the referrer in the seed).  A future crash file can be triaged by the
   guard before any viewer round. `[verified: E1]`
3. **Byte-vindication generalises: an edited survivor whose exact after-bytes
   exist in ANY viewer-PASSED file is reader-legal without a viewer round.**
   The guard takes certified Documents as `vindication_sources`; K1's sheet
   edit vindicates against K3/K4, the orphaned symbol does not (in no passing
   file). `[verified: E1, tests]`
4. **Element census and byte-weighted provenance are one fact seen through
   registration count vs payload weight** — and they reconcile with zero
   remainder ONLY when the provenance instrument's block-granular stream
   classes are replaced by record-granular accounting.  The tool's "0.0 %
   ours" for an in-place-substituted file is an interleaving artefact (our
   objects sit between Autodesk's inside one save unit; no whole 4-KB block
   is ours), never quote it. `[measured: E3, doc §1/§4]`
5. **The genesis endgame is dominated by removal / ship-product-data
   decisions, not by missing constructors** — by BYTES, 70 % of the Y9
   residue is param-definitions GC + appearance/material companions + the
   assembly-code / property tables + the HVAC product database; the two
   genuine constructor gaps are 14 %.  Byte-weighting reorders the Yn queue
   the census counted by elements. `[measured: doc §3/§6]`
6. **Zero registration motion held to the deepest rung** — Y9's
   `Global/Latest` and `Global/ElemTable` are byte-identical to K4's, the
   ONLY differing stream is `Partitions/21`, and every one of the 1,276
   changed records is seq-102: the in-place law is a property of the whole
   ladder, re-verified independently of the rung reports' own assertions.
   `[verified: E3]`
7. **The viewer has never been shown a standalone .rfa** — the family lineage
   has NO certified base source (its Autodesk archetype lives under `vendor/`,
   outside the ledger's sample rule).  The archetype must go first, as a
   candidate-base: its PASS certifies the family lineage's base AND
   establishes the family-domain oracle; its FAIL would mean the reader does
   not process standalone families at all (a capability boundary, not our
   defect), collapsing the family question onto the load-into-project path
   (L_v2 / L1a — already gated and admissible).  `[E5, probes.json]`
8. **The archetype is a valid calibration control at file level** — the
   certified family validator scores the authentic Autodesk `.rfa` WORSE
   than every constructed v2 file (2 family-mode errors vs 0), so a viewer
   FAIL of ours with an archetype PASS can never be pinned on the raw-arbiter
   residuals both share. `[verified: E5]`

## Gotchas found

1. The batch gate's base extractors do not see `vendor/` repo paths and its
   absolute-path regex lazily matches a bogus `/subpath.rfa` out of any
   relative string containing slashes — declare a `vendor/` base with the
   ABSOLUTE path first (dict form) until the one-line gate fix lands (§5c).
2. `probe_batch._iter_probe_entries` reads only the `probes` and `viewer_queue`
   blocks: probes filed under any other key (my first draft's
   `attribution_probes`) are invisible to `resolve` — every file that must
   resolve lives in `probes`.
3. `rvt.provenance`'s stream ledger inflated size for `Global/*` includes the
   8-byte per-stream prefix; my direct `f.inflate()` measure excludes it — an
   8-byte reconciling difference per Global stream, immaterial but recorded.
4. `Document.value(eid)` returns `None` name fields for FamilySymbols keyed
   by other name fields — the guard's `_name_of` tries m_viewName / m_name /
   m_text / m_familyName and tolerates None.

## How to use (orchestrator + other streams)

```
# THE GUARD on any reduction / genesis emission (parent then child):
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from rvt.reduce_law import assert_edit_free_files
assert_edit_free_files('PARENT.rvt', 'CHILD.rvt')      # raises SurvivorEditedError on any edit
"
.venv/bin/python -m rvt.reduce_law                       # demo: K1a ACCEPTED, K1 REJECTED (classified), policy, K4->Y1
.venv/bin/python src/rvt/reduce_law.py PARENT.rvt CHILD.rvt [--vindication CERTIFIED.rvt ...] [--json]
.venv/bin/python -m rvt.reduce_law --policy             # the law + clauses + tables as JSON

# in a generator (BEFORE emitting):
from rvt import reduce_law as RL
RL.guard_generator("maxgc", "genesis-base")              # ok
RL.guard_generator("neutralise-referrers", "genesis-base")   # raises BannedGeneratorError
seed |= RL.deletion_with_content_seed(state_doc, targets)     # the sanctioned replacement
# the substitution engine's law:
RL.assert_substitution(parent_doc, out_doc, landed_ids, allow_seqs=(102,))

# THE FAMILY BATCH, round F1 (admissible now):
.venv/bin/python tools/probe_batch.py stage experiments/families/genesis2/L_v2_panel_loaded.rvt \
    --candidate-base vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa \
    --control-from experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt
# rounds F2 / F3: see experiments/families/genesis2/probes.json 'rounds'
```

## 5. Diffs / hooks proposed for files OUTSIDE this territory (NOT applied)

### 5a. `tools/genesis_triage.py` — the pre-pass can never again build a genesis base

Three surgical changes.  (i) `neutralise_referrers` calls the guard FIRST and
takes an explicit `purpose` (default `"genesis-base"` → REFUSED; the autopsy /
`neutralise_grouped` research callers pass `purpose="research-probe"`);
(ii) `build_K1` stops calling it — the placed model's REFERRERS join the maxgc
SEED (deletion-with-content, the certified K1v recipe) so no survivor is edited;
(iii) `gc_rung` proves every rung edit-free before recording it.

```diff
--- tools/genesis_triage.py
+++ tools/genesis_triage.py
@@ def gc_rung(name: str, parent_path: str, st: dict, seed: Set[int], *,
     struct_ok = verify_reduced(out, delete)
     val = validate(out)
     cen = census(out)
+    # THE REDUCTION LAW (rvt.reduce_law): a rung is a rung only if every
+    # survivor is byte-identical to its parent -- prove it, never assert it.
+    # st["doc"] = the parent's loaded Document (rvt_reduce.build_state_v2).
+    # The guard reads ELEMENT RECORDS: purge_deleted_from_latest's sanctioned
+    # ADocument registry reconciliation edits Global/Latest only and cannot
+    # trip it; any surviving-record edit or added id will.
+    from rvt import reduce_law as RL
+    from rvt.mutate import Document
+    law_rep = RL.check_reduction(st["doc"], Document.from_file(out),
+                                 before_label=parent_name, after_label=name)
     lat_dangling = len(st["ext"].get("Global/Latest", set()) & delete)
     rep = {
         "rung": name, "kind": "gc-delete", "parent": _relp(parent_path),
@@
         "latest_purge": purge_rep,
         "structural_ok": bool(struct_ok["ok"]),
+        "reduction_law": law_rep.to_json(),
         "validator": val,
@@
-    if not (struct_ok["ok"] and val["ok"] and val["errors"] == 0):
+    if not (struct_ok["ok"] and val["ok"] and val["errors"] == 0 and law_rep.ok):
         rep["FAILED_SELF_CHECK"] = True
         log(f"[{name}] *** SELF-CHECK FAILED -- not a valid probe: "
-            f"{val.get('error_messages')} {struct_ok if not struct_ok['ok'] else ''}")
+            f"{val.get('error_messages')} {struct_ok if not struct_ok['ok'] else ''} "
+            f"{law_rep.summary() if not law_rep.ok else ''}")
     return rep
@@
-def build_K1(st5: dict) -> dict:
-    """Two-step: (1) neutralise the SURVIVOR references to the placed model
-    (views' hidden-element lists / ad-hoc overrides / schedule columns /
-    sheet title-block ids, trackers, plan topologies) exactly as Revit does
-    when it deletes an element (the M2-certified soft-referrer rule), then
-    (2) maximal-GC the placed model + the annotation residue it releases."""
+def build_K1(st5: dict) -> dict:
+    """R5 minus the placed model WITHOUT the neutralise pre-pass (THE REDUCTION
+    LAW, k1-autopsy.md sec.4): the model's REFERRERS (the views' state maps,
+    the graphical schedule, the sheets' title blocks, the orphanable type
+    layer, the plan topologies) are SEEDED FOR DELETION WITH THE CONTENT
+    they reference -- deleted where nothing outside pins them, LEFT
+    BYTE-IDENTICAL where something does.  Zero survivor edits (the K1v /
+    K1a shape, both viewer-PASSED); one step, one maxgc, from certified R5."""
+    from rvt import reduce_law as RL
     t0 = time.time()
     placed = _ids_of_classes(st5, K1_PLACED) | _inplace_family_chains(st5)
     placed = _own_fixpoint(st5, placed)
-    step1 = os.path.join(TRIAGE, "K1_step1_neutralised.rvt")
-    nrep = neutralise_referrers(st5, placed, step1, name="K1")
-    st1 = RR.build_state_v2(step1)
-    seed = {e for e in placed if e in st1["host"]}
-    seed |= _ids_of_classes(st1, K1_RESIDUE_SWEEP)
-    seed = _own_fixpoint(st1, seed)
+    seed = {e for e in placed if e in st5["host"]}
+    # deletion WITH the content: the referrers join the seed instead of
+    # being edited (the certified alternative to every neutralise rule)
+    seed |= RL.deletion_with_content_seed(st5["doc"], placed)
+    seed |= _ids_of_classes(st5, K1_RESIDUE_SWEEP)
+    seed = _own_fixpoint(st5, seed)
     rep = gc_rung(
-        "K1", step1, st1, seed, parent_name="R5",
+        "K1", R5, st5, seed, parent_name="R5",
         desc="R5 (viewer PASS) minus every PLACED model element ...
@@
     rep["parent"] = _relp(R5)
-    rep["kind"] = "modify+gc-delete"
-    rep["step1_neutralise"] = nrep
-    rep["intermediate_not_uploaded"] = _relp(step1)
+    rep["kind"] = "gc-delete (deletion-with-content, edit-free)"
     rep["seconds"] = round(time.time() - t0, 1)
@@ def neutralise_referrers(st: dict, targets: Set[int], out_path: str,
-                         *, name: str) -> dict:
+                         *, name: str, purpose: str = "genesis-base") -> dict:
     """Emit ``out_path`` = st's file with every SURVIVOR field that names a
     ``targets`` id neutralised (scalar id -> -1, id-list entry removed,
-    structured entry mentioning it dropped) -- the manipulate module's
-    certified soft-referrer rule (M2/M3 acceptance files).  Targets are NOT
-    deleted here.  Returns the field-level edit log."""
+    structured entry mentioning it dropped) -- rvt.manipulate's soft-referrer
+    rules (M2/M3-certified for GENUINE USER EDITS ONLY).  BANNED for any
+    genesis-base / reduction-rung purpose by THE REDUCTION LAW: this call
+    RAISES ``rvt.reduce_law.BannedGeneratorError`` unless ``purpose`` is a
+    research / diagnostic purpose (the K1 autopsy bisection probes pass
+    ``purpose="research-probe"`` -- files that may never be a base).  The
+    sanctioned replacement is ``rvt.reduce_law.deletion_with_content_seed``.
+    Targets are NOT deleted here.  Returns the field-level edit log."""
     from rvt import manipulate as MP
+    from rvt import reduce_law as RL
+    RL.guard_generator("neutralise-referrers", purpose)   # raises on a base purpose
     doc = st["doc"]
```

Cascade: `build_K3` (which also calls `neutralise_referrers` for the family
USAGE fields) must pass `purpose="research-probe"` — or, better, be re-derived
edit-free by seeding the usage-referring type elements for deletion (its usage
edits ARE certified reader-legal, so this is a purity choice, not a bug fix);
`tools/k1_autopsy.py::neutralise_grouped` and `build_halves` pass
`purpose="research-probe"` (they manufacture the banned state on purpose and
their `probes.json` already forbids treating those files as bases); the
K2 / K5x / K6 builders derive from K1 and inherit the fixed base.

### 5b. `src/rvt/reduce.py` — the law as a post-condition of the writer

`delete_elements` is edit-free by construction (survivor records are copied
verbatim), so the guard here is defence-in-depth against any future
re-blocker / splice regression — and it makes the law's proof travel WITH the
emission instead of living in the caller.  Off by default only where the
caller already holds both Documents and calls the guard itself.

```diff
--- src/rvt/reduce.py
+++ src/rvt/reduce.py
@@
 def delete_elements(src_rvt: str, out_path: str, delete_ids: Iterable[int], *,
-                    target: int = BLOCK_TARGET) -> ReduceReport:
+                    target: int = BLOCK_TARGET, law_check: bool = False) -> ReduceReport:
     """Remove ``delete_ids`` from the host document of ``src_rvt`` -> ``out_path``.
@@
     write_cfb(out_path, out_entries)
-    return ReduceReport(pname, len(delete), count_before, count_after, watermark,
-                        removed, len(u0), sum(1 for b in w2.blocks if b.unit == 0),
-                        len(logical), len(part_logical), out_path)
+    rep = ReduceReport(pname, len(delete), count_before, count_after, watermark,
+                       removed, len(u0), sum(1 for b in w2.blocks if b.unit == 0),
+                       len(logical), len(part_logical), out_path)
+    if law_check:
+        # THE REDUCTION LAW as a post-condition: a delete-only path must
+        # leave every survivor byte-identical (raises SurvivorEditedError).
+        from .reduce_law import assert_edit_free_files
+        assert_edit_free_files(src_rvt, out_path)
+    return rep
@@
-def verify_reduced(path: str, deleted_ids: Iterable[int] = ()) -> dict:
+def verify_reduced(path: str, deleted_ids: Iterable[int] = (), *,
+                   parent: Optional[str] = None) -> dict:
     """Prove a reduced file is structurally healthy.
+
+    With ``parent`` also proves it obeys THE REDUCTION LAW (no survivor
+    edited, no id added) via ``rvt.reduce_law``; the verdict is folded into
+    ``ok`` and reported under ``reduction_law``.
     ...
     """
@@ (end of verify_reduced, before  rep["ok"] = (...))
+    if parent:
+        from .reduce_law import check_files
+        law = check_files(parent, path)
+        rep["reduction_law"] = law.to_json()
     rep["ok"] = (rep["crc_failures"] == 0 and rep["ecc_mismatches"] == 0
@@
-                 and rep["isize_identity_ok"])
+                 and rep["isize_identity_ok"]
+                 and (parent is None or rep["reduction_law"]["ok"]))
     return rep
@@
 __all__ = ["delete_elements", "verify_reduced", "reference_graph",
```

Follow-on for the reduction ladder tool (`tools/rvt_reduce.py::run_stage_v2`,
also outside my territory): pass `parent=<parent stage path>` to
`verify_reduced` (or call `reduce_law.check_files` next to it) so every R-rung
report carries the law verdict.

### 5c. `tools/probe_batch.py` — let a `vendor/` archetype resolve on its own
```diff
-_PATH_RE = re.compile(r"((?:experiments|samples)/[A-Za-z0-9_./+-]+?\.(?:rvt|rfa|rte))")
+_PATH_RE = re.compile(r"((?:experiments|samples|vendor)/[A-Za-z0-9_./+-]+?\.(?:rvt|rfa|rte))")
@@ def _name_index():
-    for pat in ("experiments/**/*.rvt", "experiments/**/*.rfa", "samples/*.rvt", "samples/*.rfa"):
+    for pat in ("experiments/**/*.rvt", "experiments/**/*.rfa", "samples/*.rvt", "samples/*.rfa",
+                "vendor/**/examples/Autodesk/*.rfa"):
```
…and once the archetype PASSES in round F1, either add
`vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa` to
`viewer-certified.json 'certified'` (kind: Autodesk sample source, family
domain) or extend `Ledger.is_sample_source` to that directory — then the
`probes.json` `.rfa` entries can shed the absolute-path first field.

### 5d. Other hooks
* **`src/rvt/manipulate.py`** (`delete_element(..., neutralise_referrers=True)`
  and `commit_plans`): the same guard call keyed on a `purpose` argument, so
  the M2/M3 user-modify path stays legal (`"user-modify"`) while any caller
  building a base is refused.  (`rvt.manipulate` is imported by
  `rvt.reduce_law.deletion_with_content_seed` for its `referrers` index —
  read-only.)
* **`tools/sync_plugin.py`**: `src/rvt/reduce_law.py` is a NEW module — if the
  plugin bundle's source copy list is explicit, add it (and re-run the sync)
  so the plugin-drift test stays green; nothing existing changed.
* **KNOWLEDGE.md owner**: merge findings 1–8 above and the y9 headline
  numbers (6.3 % / 41.7 % / 51.7 %; census reconciliation) into the
  provenance / genesis-status sections.

## Verification

* `.venv/bin/python -m pytest tests/test_reduce_law.py -q` → **35 passed**
  (1.75 s): law data tables; the purpose policy (16 parametrised refusals +
  sanctioned allowances + case-insensitivity + unknown purpose/mechanism);
  the byte-strict instrument (record signature covers stamp / class / bytes /
  seq; identical documents diff empty); **THE K1 REGRESSION** (K1a_editfree
  ACCEPTED with 599 removed / 0 edits; K1 REJECTED with 2,117 removed / 23
  edited survivors classified into clauses 1–4 with the per-id evidence the
  autopsy recorded); byte-vindication by K3/K4 (sheet 1457028 vindicated, the
  orphaned symbol not); the in-place law on the certified K4→Y1 rung
  (accept / stray-slot refusal / seq-violation / unchanged-landed tolerance);
  `deletion_with_content_seed` on R5's in-place family (returns the K1_suspect
  trio + instance + family-scoped content, never the target); the clause-4
  fallback for ungrouped classes.
* `.venv/bin/python -m rvt.reduce_law` → the demo transcript in E1 (exit 0).
* `.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` (full suite,
  this session): see BRANCH STATE.
* `tools/provenance.py experiments/genesis/subst_k4/Y9.rvt --baseline all
  --streams --json ...` re-runs job 2's raw ledger (9.5 s); the record-granular
  accounting recipe is inline in `docs/writer/y9-provenance.md` §7.
* `tools/probe_batch.py resolve` on the 8 genesis2 files (8/8 bases resolve)
  and `check ... L_v2 --candidate-base <archetype>` (ADMISSIBLE) reproduce
  job 3's gate readings.

## Open questions (need the viewer / a decision)

* **Round F1** (stageable now): does the reader open an authentic standalone
  `.rfa` (the archetype), and does L_v2 load?  The archetype's verdict
  decides whether the standalone-family branch (FG1..FG5, FGa/b/c) exists at
  all.
* Whether the identity layer should be applied to the ladder's Y files before
  the next genesis-progress quote (this measure excludes it by design; V30–V32
  certify each identity move standalone but not stacked on Y9).
* Counsel C4 (the 41.7 % product-corpus class): ship-verbatim vs
  reconstruct/drop — the family-scale purity probe (FGa) is the first
  empirical datum, project-scale untested.
* The guard is wired to NOTHING yet — its value is realised when 5a/5b (and
  the manipulate hook) land in the callers' territories.

## BRANCH STATE

No VCS (plain directory).  NEW files (this stream's territory only):
`src/rvt/reduce_law.py`, `tests/test_reduce_law.py` (35 pass),
`docs/writer/y9-provenance.md`, `docs/inbox/genesis-integrate.md` (this file).
REPLACED (create/replace territory): `experiments/families/genesis2/probes.json`
— the family-genesis stream's five probes + three attribution rungs are all
still there (their tests / if_PASS / if_FAIL rationale preserved); every entry
now carries `file` / `md5` / `base` (resolvable) / `phase`, plus a
`candidate_bases` entry for the archetype and a three-round staging plan.  NO
existing `src/` module, tool, test, `.rvt` or `.rfa` was edited; no browser /
viewer use; the diffs for `tools/genesis_triage.py`, `src/rvt/reduce.py`,
`tools/probe_batch.py` and `rvt.manipulate` are proposed above, unapplied.
Full suite this session (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`): **968 passed, 3 failed** (971 tests, 16:25); this
stream's 35 are among the 968.  The 3 failures: (a) `tests/test_plugin_sync.py::
test_plugin_is_in_sync_with_source` — plugin DRIFT: this stream's NEW
`src/rvt/reduce_law.py` plus a CONCURRENT stream's new
`src/rvt/genesis/residue_a.py` / `residue_b.py` (being written this tick) are
not yet copied into `plugin/lib/src/rvt/`; the fix is the one standing command
`python tools/sync_plugin.py` (copies + re-zips), which this stream did NOT run
so as not to bundle the other stream's in-flight modules into `rev-revit.zip`
mid-tick — orchestrator: run it once this tick's streams land (the drift test
is green again after it); (b, c) the pre-existing, other-stream
`tests/test_provenance.py` G0 assertions (`test_G0_resource_refs_are_counted`,
`test_G0_identity_dit_usernames_still_leak` — stale pins on the pre-genesis-2
G0, owner: the provenance stream) that every recent record lists.  None of the
three touches this stream's files.
DONE per charter: (1) the guard + tests + the two diffs, (2) the y9-provenance
document, (3) the family probes manifest — STOPPED AT READY.  Next work: land
5a/5b so the guard is load-bearing; stage round F1; walk the byte-ranked
residue queue (definitions GC / appearance companions / product-data
decisions before the constructor gaps).
