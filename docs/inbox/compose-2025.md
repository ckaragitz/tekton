# COMPOSE 2025 — THE 2025 COMPOSER + FLIP PREP (G25-4 close + G25-5 staging)

Stream: **compose-2025** (2026-08-04, launched at VERDICTS #28 — the 2025
reduction lineage certified; B2025_K4 a CERTIFIED base).  Charter:
(1) prove `tools/genesis_compose.py` correct under the 2025 emit context by
the 2026-style ANCHOR; (2) compose `G_ABPD_2025` at the registry relpath as
the sibling streams' rungs land; (3) FLIP PREP — the exact G25-5 data diff,
gated, NOT applied — plus the staged viewer batch; (4) the finish-line dry
run of `tests/test_target2025.py`'s self-arming test.

**DONE state: anchor PROVEN byte-identical; the FULL `G_ABPD_2025.rvt`
composed at the exact registry relpath — COMPOSED-VALID, zero problems,
and BYTE-IDENTICAL to the residue stream's own deletion-proof file (the
whole-chain replay is EXACT); flip diff written with the real pin values
(gate: viewer verdict only); batch 29 staged (certified control + the
candidate); finish-line dry run executed in four modes with the exact
three-gap ladder.**

Tool: `tools/genesis_compose_2025.py` (anchor / compose / stage /
finishline / flipdiff / all).  Tests: `tests/test_compose_2025.py`
(12, all green).  Artifacts: `experiments/genesis/subst_k4_2025/compose/`.

---

## 1. THE 2025 COMPOSE CONTEXT (why a wrapper, what it patches)

`genesis_compose.py` is IMPORTED, never edited.  The wrapper's
`context_compose_2025` = `tools/genesis_2025.py::context_2025` (the SEVEN
module-local framing-tag patches + `versions.reading` + the ADocument
decoder — the reduce stream's proven set) PLUS the codec swaps the Y2025
ladder runner proved out (`run_ladder2025.py`): `rvt.encode._DEFAULT_
ENCODER`, the lazy `ObjectDecoder` factories in `rvt.regadd`/`rvt.regdiff`,
and `genesis_compose._DEC` (its report decoder) — all bound to the pinned
2025 schema, all restored on exit (tested).

## 2. THE ANCHOR — PROVEN (the 2026 correctness proof transfers to 2025)

**compose(B2025_K4, [the NINE cumulative Y2025 rung deltas]) == the
ladder's deepest cumulative rung `Y9_2025.rvt`, BYTE-IDENTICALLY.**  The
canonical ladder is DISCOVERED, not hard-coded: the chain walker follows
each rung's OWN parent declaration (report `parent` field) from the
certified base, nodes keyed by md5 so byte-identical aliases collapse —
it picked up the y2025-settings stream's Y1..Y7 and the y2025-views
stream's Y8/Y9 the moment they landed.

```
[anchor-2025] 1,308 merged slots over 9 rung sets, seqs [102]; COMPOSED-VALID
[anchor-2025] reproduction md5 79c310409848ef2932eb7e86f5b0e781
[anchor-2025] target       md5 79c310409848ef2932eb7e86f5b0e781  (Y9_2025.rvt)
[anchor-2025] BYTE-IDENTICAL: True
```

Evidence: `compose/anchor_2025.json` + `G_Y2025_anchor.manifest.json`
(Latest + ElemTable byte-identical, in-place law ok, per-rung fidelity,
validator 0 errors, four-registry coherent 1/0/0/0).  The 2026 anchor
(compose(Y9, Group A) == ZA_deep) has its 2025 twin.

## 3. G_ABPD_2025 — THE FULL COMPOSED 2025 CANDIDATE, chain-replay EXACT

All sibling layers landed during this stream and were composed the moment
they settled:

* **Y layer** (y2025-settings + y2025-views): cumulative `Y1_2025..Y9_2025`
  on the certified base — nine rung deltas, 1,308 slots, seq 102.
* **Residue layer** (the 2025 residue stream): the cumulative chain
  `Z_RA_2025` (431 slots) → `Z_RB_2025` (623) → `Z_RC_2025` (30, seqs
  101+102) → `RC_2025_inplace` (6 view-header slots, mostly seq-101
  cleanups) — discovered by the same parent-chain walk (`R*`/`Z_*`
  byte-identical aliases collapse; single-change probes are leaves the
  trunk-preference rule skips).
* **Deletion layer**: `D_2025_stragglers_full.json` — the 17-id lawful
  straggler set (policy maxgc, purpose genesis-base); its published
  constituent subsets (D_2025_constraint_dim / links_pair /
  vendor_datastorage) are detected as strict subsets and composed once via
  the union (the 2026 D_all-vs-singles shape).

**The result** — `experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt`
(the EXACT relpath `genesis_base.json releases.2025` reserves):

* **598,016 B, sha256 `6242c3aaccf86e7187fbd56879d450089c6fd33ad677d5847cb7c56d5e2b1171`,
  md5 `470087732a98168af313f8a253f65edd`**
* Composed CHAIN-FAITHFULLY as two compose calls (substitute THEN delete),
  because slot 1250031 is both substituted (Y5) and in the deletion seed —
  dropping the substitution (plain delete-wins) changes the reference
  graph and maxgc then pins the RvtLinkSymbol (16/17); the chain order
  deletes 17/17:
  - Phase 1 `G_ABPD_2025.phase1.rvt` (602,112 B): 13 rung sets, 2,392
    merged slots, seqs [101, 102] — COMPOSED-VALID; Latest + ElemTable
    byte-identical, in-place law ok, per-rung fidelity ALL OK, validator
    0E/2W, four-registry coherent 1/0/0/0, ADocument clean.
  - Phase 2: the 17-id straggler set under the reduction law — deleted 17
    (CurveElem 5, RefPlane 3, DataStorage, AreaSchemePlanTopologies,
    LinearDimString, LevelRoomPlan, RoomElem, RvtLinkSymbol,
    RvtLinkInstance, CopyWatchProperties, SketchPlane), reduce-law
    **EDIT-FREE**, validator **0E/1W**, four-registry coherent, manifest
    `G_ABPD_2025.manifest.json`.  (Phase 2's base is the phase-1 output —
    recorded with the composer's not-certified WARNING; the ULTIMATE base
    B2025_K4 is the certified one, and the phase-1 file is byte-anchored,
    see below.)
* **THE TWO END-TO-END PROOFS (both hold, both re-checked from disk by
  tests):**
  - the in-place layer == the residue stream's deepest in-place file
    `RC_2025_inplace.rvt` **byte-for-byte**;
  - the FINAL output == their deletion-applied proof file `RC_2025.rvt`
    **byte-for-byte** — the composer replayed the ENTIRE sibling chain
    (9 Y rungs + 4 residue steps + the deletion set) onto the certified
    base in its own passes and landed in the exact same bytes.

### The linearizer (new in the wrapper; the composer itself untouched)

Replaying a CUMULATIVE chain onto its root violates the composer's
disjointness/parent-coherence laws wherever a deeper rung re-emits an
earlier rung's slot (RC_2025_inplace re-emits five Y-owned view headers —
and only their seq-101 attributes).  `linearize_chain_specs` resolves this
lawfully, PER (seq, slot): chain continuity asserted (the deeper delta's
"before" bytes must equal the previous writer's bytes), last-writer-wins,
per-seq records MERGED into the slot's final owner (e.g. the Y layer's
seq-102 object + the residue layer's cleaned seq-101 attributes), parent
baselines rewritten to the chain root's bytes, every supersede/merge noted
in the manifest.  Getting this wrong is detectable: the first (per-slot)
version reverted five seq-102 view objects to base bytes, the link symbol
stayed pinned (16/17), and the byte-proof caught it — the per-seq version
deletes 17/17 and matches the proof file exactly.

### Re-composition is ONE command (rungs move, the tool re-discovers)

```
.venv/bin/python tools/genesis_compose_2025.py all
```

The sibling streams iterated WHILE this stream composed (the views stream
re-emitted Y9_2025 at 23:16; the residue stream re-emitted its whole set
at 23:19 and renamed its deletion spec at 23:22) — each re-run of the
tool re-discovers the current chain by parent declarations and re-proves
both byte-identities.  If a sibling re-emits again, the on-disk pins go
stale and `tests/test_compose_2025.py` fails RED (md5s re-checked from
disk) — re-run the one command.

## 4. THE STAGED BATCH — batch 29 (nothing uploaded; the orchestrator uploads)

Staged through the `tools/probe_batch.py` gate into `compose/`
(`batch_29.json` + `probes.json`; gate PASSED — the declared base is
certified):

| order | file | kind | note |
|--:|---|---|---|
| 0 | `CTRL_B2025_K4_b29.rvt` | control | byte-identical copy of the CERTIFIED `experiments/genesis2025/reduce/B2025_K4.rvt` (md5-asserted) |
| 1 | `G_ABPD_2025.rvt` | candidate-base | the FULL composed candidate; base declared = the certified reduce path; `probe_batch.resolve_base` verified |

* Batch NUMBER 29 = 1 + the highest `batch_N.json` anywhere under
  `experiments/**` (the parallel 2024 stream staged batch_28 mid-session;
  an early batch_18 staging was renumbered before anything was uploaded).
* Reading order: control first (control FAIL ⇒ round VOID).
* G_ABPD_2025 PASS additionally certifies BY BYTES the residue stream's
  `RC_2025.rvt` (byte-identical), and vice versa if their batch uploads
  first — redundant by construction, not in conflict.
* `if_FAIL`: bisect with the sibling ladders' own batches (Y ladder:
  `experiments/genesis/subst_k4_2025/probes.json`, bisection-first).

## 5. FLIP PREP — the G25-5 data diff (ready to apply, NOT applied)

Generator: `.venv/bin/python tools/genesis_compose_2025.py flipdiff`
(re-prints with live values + gate status).  **Gate status now: BLOCKED
solely on the viewer verdict** (the composition-completeness condition is
met).  Apply ONLY after `G_ABPD_2025.rvt` enters
`docs/coverage/viewer-certified.json`:

```
--- 1. src/rvt/frontdoor/assets/genesis_base.json (releases.2025) ---
     "relpath": "experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt",
-    "sha256": null,
+    "sha256": "6242c3aaccf86e7187fbd56879d450089c6fd33ad677d5847cb7c56d5e2b1171",
-    "bytes": null,
+    "bytes": 598016,
-    "status": "pending certification",
+    "status": "certified",
   (pending_reason may be deleted or left; release_status reads only status + sha256 + the flag)

--- 2. src/rvt/versions/__init__.py (KNOWN_RELEASES[2025]) ---
-        samples_dir="samples/2025", creation_certified=False),
+        samples_dir="samples/2025", creation_certified=True,
+        genesis_base="experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt"),

--- 3. tools/sync_plugin.py (bundle the 2025 base beside the 2026 one) ---
after GENESIS_MANIFEST_SRC (~line 70):
+GENESIS_BASE_2025_SRC = os.path.join(ROOT, "experiments", "genesis",
+                                     "subst_k4_2025", "compose", "G_ABPD_2025.rvt")
+GENESIS_MANIFEST_2025_SRC = os.path.join(ROOT, "experiments", "genesis",
+                                         "subst_k4_2025", "compose",
+                                         "G_ABPD_2025.manifest.json")
in asset_mappings() (~line 196):
+    (GENESIS_BASE_2025_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2025.rvt", True),
+    (GENESIS_MANIFEST_2025_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2025.compose.json", False),
in verify_assets(), after the default-pin cross-check (~line 305):
+    base25_dst = os.path.join(PLUGIN, GENESIS_DST_DIR, "G_ABPD_2025.rvt")
+    if os.path.exists(base25_dst) and os.path.exists(FRONTDOOR_PIN):
+        try:
+            with open(FRONTDOOR_PIN) as fh:
+                pin = json.load(fh)
+            want = str((pin.get("releases", {}).get("2025") or {}).get("sha256") or "").lower()
+            got = _hash(base25_dst)
+            if want and got != want:
+                problems.append(
+                    f"2025 genesis base asset sha256 {got[:16]}.. != releases.2025 pin "
+                    f"{want[:16]}.. — the front door would REFUSE the bundled 2025 base")
+        except (KeyError, ValueError, OSError) as e:
+            problems.append(f"cannot read frontdoor pin {FRONTDOOR_PIN}: {e}")
```

Then `tools/sync_plugin.py` (re-sync + re-zip; the zip re-adds `assets/`
wholesale so the new .rvt ships automatically); `tests/test_target2025.py`
arms itself; the TODAY-tests flip to their certified branches; the
fallback line disappears.  This makes target-2025's §3.2 flip concrete +
the verify_assets guard.  If a re-composition ever changes the file,
REGENERATE the diff (`flipdiff`) — never pin stale bytes.

## 6. THE FINISH-LINE DRY RUN — resolution honest; the FULL build has a
## three-gap ladder (run, not speculated)

`tests/test_target2025.py::test_END_STATE_author_2025_produces_a_2025_file`
run manually with the flip applied IN MEMORY ONLY (KNOWN_RELEASES[2025] +
the registry slot patched process-locally; nothing on disk changed —
pinned by `test_flip_not_applied_*`).  All four modes re-run against the
FULL `G_ABPD_2025.rvt`; reports `compose/finishline_2025*.json`.

| mode | result |
|---|---|
| handoff-only (resolution + manifest honesty) | **WOULD PASS**: creation_status supported + release_status certified (three-source rule agrees), `resolve_base(target_release=2025)` returns the composed file (pinned, certified, `detect_release`=2025), `author` ok, `target_version.status == "match"`, no fallback line |
| FULL build (the test's actual body) | **WOULD FAIL — gap A**: `StandaloneError: standalone build touched a research-machine input: .../G_ABPD_2025.rvt` |
| FULL build + gap-A fix simulated | **WOULD FAIL — gap B**: family LOAD blocked: `ValueError: unexpected Partitions header: v=9 cls=0x391` (famgen loader cannot walk 2025 framing) |
| FULL build + gap-A fix + the whole 2025 emit context | **WOULD FAIL — gap C**: `EncodeError: missing field 'm_maxSafeTag' @ Level.m_pGeomTable->GeomTable.m_maxSafeTag` (famgen skeleton constructs 2026-shaped objects; 2025 GeomTable has extra fields) |

The gap ladder, named for their owners (cross-territory — reported, not
fixed here):

* **Gap A — standalone tripwire (front door).**  `build.py:193` arms
  `forbid_research_inputs(allow=[opts.specimen_src])`; the allow list
  gains only `standalone.bundled_base_path()` = the DEFAULT (2026) slot's
  path, so a resolved 2025 base under `experiments/` trips `_R5_MARKER`.
  **One-line fix**: `allow=[p for p in (opts.specimen_src, opts.base.path)
  if p]` — sound because `resolve_base` has already sha256-pin-verified
  any base it returns.
* **Gap B — release activation on the build path (versions/front door).**
  The build never enters `rvt.versions.reading`; `standalone.install_
  schema(base)` reroutes the SCHEMA chokepoints to the base's own
  Formats/Latest (that half already works) but not the PARTITION framing
  ordinals.  This is the `versions.creating(2025)` context the reduce
  (§4), port (§4.3) and now compose streams have all needed — fold the
  shared patch set into `rvt.versions`.
* **Gap C — constructor shapes (genesis/famgen).**  Under the full 2025
  context the famgen skeleton still ENCODES 2026-shaped dicts; 2025-only
  fields (e.g. `GeomTable.m_maxSafeTag`; corpus default (−1,−1) per the
  port miners) are missing.  The fix is wiring the EXISTING
  `rvt.genesis.port2025.adapt()` layer (the Y2025 ladder already uses it)
  into the famgen document build — not new research.
* **Predicted gap D (not yet reachable): the specimen ancestor.**  The
  walls path clones specimens from `experiments/genesis/R5.rvt` (2026);
  a 2025 build needs a 2025-release specimen ancestor.  `R5_2025.rvt` was
  staged in batch 17 but is NOT in the ledger (verdict #28 read "ALL
  FOUR" — control/R9/K3/B2025_K4; R5_2025's verdict appears unread).
  Orchestrator: confirm R5_2025's verdict; `genesis_base.json` will want
  a 2025 `specimen_ancestor` slot when the walls path is exercised.

**Meaning for G25-5**: the data flip makes the front door RESOLVE 2025
and speak honestly (the self-arming test's resolution assertions pass);
the full `author → native 2025 .rvt` additionally needs gaps A–C closed
(A is one line; B is the already-proposed shared context; C is wiring the
existing port layer into famgen).  Post-flip, the finish-line test fails
loudly on gap A until the build path is 2025-ready — exactly what a
self-arming finish line is for.

## 7. Files (this stream's territory only)

* `tools/genesis_compose_2025.py` — the wrapper tool (context; md5-keyed
  parent-chain discovery for Y/residue layers; per-(seq,slot) chain
  linearizer; chain-faithful two-phase compose; deletion-spec discovery
  with subset dedupe; anchor; stage; finishline; flipdiff)
* `tests/test_compose_2025.py` — 12 tests, all green (anchor byte-identity
  re-checked from disk; candidate invariants across both phases; the two
  chain proofs re-checked from disk; registry-path discipline; batch
  control identity + base resolution; flip-not-applied pins; context
  patch/restore)
* `experiments/genesis/subst_k4_2025/compose/` — `G_ABPD_2025.rvt`
  (+ `.manifest.json`, `.phase1.rvt`, `.phase1.manifest.json`,
  `.inplace.rvt`), `G_Y2025_anchor.rvt` (+ manifest), `anchor_2025.json`,
  `compose_2025.json`, `probes.json`, `batch_29.json`,
  `CTRL_B2025_K4_b29.rvt`, `finishline_2025{,_simfix,_incontext}.json`
* `docs/inbox/compose-2025.md` (this record)

Touched OUTSIDE territory: **NOTHING**.  All cross-release adjustments are
process-local context patches inside the wrapper (restored on exit); the
gap-A/B/C fixes and the flip diff are PROPOSED (§5/§6), not applied.

## SUITE RESULT

Full suite (`.venv/bin/python -m pytest -q --continue-on-collection-errors`)
launched 23:13 from repo root; log:
`/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/suite_compose2025.log`.
**STILL RUNNING at record close (00:11), 57 minutes in: 661 tests
completed — ALL 661 PASSED, zero F/E marks — at ~46%, crawling because
the machine is running at least FOUR other CPU-pinned pytest processes
concurrently (the integrator's sharded suite runs + a frontdoor run + a
validator-regression script; verified via ps — the local-ceiling
contention tell from KNOWLEDGE.md, live).**  Orchestrator: read the log's
final line for the count (background waiters in this session's task list
fire when it lands), or prefer the integrator's own sharded run that was
executing simultaneously.  Known-green against the FINAL tree,
re-run standalone after every artifact regeneration:
`tests/test_compose_2025.py` **12/12 (0.6 s)**.  This stream edited no
existing source or test file (purely additive: one new tool, one new test
module, artifacts, this record), so its expected full-suite delta is
exactly +12 passes over whatever baseline the concurrent streams settle.

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — not a git repo (no commits);
  integration is the orchestrator's.  All work is on disk as listed in §7.
* DONE check against the charter:
  * **Anchor proven** ✓ (§2, byte-identical to Y9_2025; re-checkable).
  * **G_ABPD_2025 composed at the registry relpath** ✓ (§3: FULL — Y +
    residue + the lawful 17-id deletion set; COMPOSED-VALID, zero
    problems; the in-place layer AND the final bytes each byte-identical
    to the residue stream's own chain files — the replay is exact).
  * **Flip diff** ✓ (§5, real pin values; gate = the viewer verdict,
    nothing else; NOT applied — no file under `src/` or `tools/` outside
    this stream's tool was modified).
  * **Staged batch** ✓ (§4, batch 29: certified control + the FULL
    candidate, gate-clean; NOTHING uploaded).
  * **Finish-line dry run** ✓ (§6: resolution WOULD PASS; the full-build
    gap ladder A/B/C named with exact errors + fix directions; flip
    stayed in memory).
* STOP at READY: no viewer upload, no certification claim, no flip.
  `KNOWN_RELEASES[2025].creation_certified` remains False;
  `genesis_base.json releases.2025` remains pending with `sha256: null`
  (both pinned by tests).
