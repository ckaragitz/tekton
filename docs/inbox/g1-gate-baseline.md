# g1-gate-baseline — the status gate ledgers a build on OUR pinned base against the base's true residue (issue #143)

Stream `eng143` (engineer session for #143, P1, PG1 honesty). Territory used:
`tools/rvt_job.py` (the gate), `tools/ifc_intent.py` (`status_gate` pass-through),
`src/rvt/provenance.py` (one new provenance class + one kwarg), `src/rvt/frontdoor/manifest.py`
(one MANIFEST.md line), **new** `src/rvt/frontdoor/census.py` + `src/rvt/frontdoor/assets/genesis_census.json`
(the authorship census, mirrored into the plugin), **new** `tools/genesis_census.py` (derives the
census from tracked evidence), **new** `tests/test_status_gate.py` (in `tests/ci_shard.txt`).
No hot file touched (`base.py` is imported read-only; `versions/` used via `rvt.versions.reading`).

## Result in one screen

* **Before** (main `a5a853f`, `frontdoor author --prompt "an electrical room with 6 panels"`):
  `status_gate = {base_is_autodesk_sample: false, g1.verdict: "FAIL — 3,058 Autodesk-derived
  element(s) in expression-bearing categories", blocking incl. loadable-families transitive-cloned 6
  + family-types-symbols transitive-cloned 6 (OUR famgen families) + object-styles autodesk-sample
  1,591 + parameter-definitions 822 …, provenance_totals {autodesk-sample: 3,102, ours-created: 102,
  transitive-cloned: 16}, reason: "P0 genesis gate G1 fails (the base carries derived expression
  that G1 blocks) … Nothing built on a sample base is a product"}`. Cause, exactly as the issue
  says: `provenance_gate` ran `rvt.provenance` with the output's OWN composed base as the
  "Autodesk baseline", so every element inherited from OUR base read `autodesk-sample` and every
  created element referencing our own category styles / wall type read `transitive-cloned`.
* **After** (this branch, same command, all three targets, file delivered + `rvt_validate` 0 errors each):

  | target | base_kind | ours by composition | residue (byte-identical to ancestor) | G1 element blockers | created | reason (measured) |
  |---|---|--:|--:|--:|---|---|
  | 2026 `G_ABPD` | pinned-composed-genesis | 2,680 / 3,102 | 422 (349 machinery, 35 coincident, 27 RC-year, 2 RC-preview, 9 straggler; 11 never authored) | **395** (was 3,058) | 118 ours-created, **0** transitive-cloned | G2 #19: 2 inherited lineage GUIDs (identity layer) · G3 #23 human gate · residue #21: 422/3,102 · no "sample base" |
  | 2025 `G_ABPD_2025` | pinned-composed-genesis | 2,391 / 3,316 | 925 (585 never authored + 340 re-emitted identically) | 890 | 108 ours-created, 10 transitive-cloned (finding F2) | same shape |
  | 2024 `G_ABPD_2024` | pinned-composed-genesis | 2,355 / 3,278 | 923 (586 + 337) | 889 | 108 / 10 (F2) | same shape |

  The 2026 sentence, verbatim: "P0 gates on the certified composed genesis base G_ABPD: G2
  identity (#19): 2 inherited lineage identifier(s) still aboard (unique_document_guid,
  central_episode_guid); G3 counsel (#23: C1 author string, C4 the two shipped schema corpora, C5
  footer token) is a human gate, open; element residue (#21): 422 of the base's 3,102 slots still
  byte-identical to the Autodesk ancestor, the other 2,680 ours by composition. G1 ledger: FAIL —
  395 Autodesk-derived element(s) in expression-bearing categories; 2 identity violation(s) (this
  build's created content is ours unless listed as transitive-cloned). PROOF-ONLY is a label: the
  file is delivered." — every clause but G3 is READ OFF THE FILE by this run (identity layer,
  census, element ledger); G3 is counsel's and said to be. Status stays the LABEL
  `PROOF-ONLY, NOT-DELIVERABLE`. A base that IS an Autodesk sample keeps the v1 sentence verbatim
  ("…the base is an Autodesk sample project … Nothing built on a sample base is a product") and
  the v1 element-only ledger; an explicit user `--base` that is not a pin is worded as
  "user-supplied base with no authorship census" (everything inherited ledgered as the base's —
  nothing presumed ours); a pin whose census entry is missing (re-pin without rebuild) is still
  OUR base, ledgered conservatively, and the manifest says `census: STALE … run
  tools/genesis_census.py build`.
* Wall time unchanged (steer #108): prompt job 10.4 s before / 10.2–10.4 s after (repo, `.venv`);
  bare unzip + system Python `go author` 8.5 s READY exit 0; the gate itself 0.8–0.9 s (was
  0.75 s; +0.1 s = the identity layer on our base). The census lookup is one sha256 of the 580 KB
  base (2 ms) + a 38 KB JSON load (cached).

## What was built

1. **The authorship census of the pinned bases** — `tools/genesis_census.py {build,check,show}`
   writes `src/rvt/frontdoor/assets/genesis_census.json` (schema `tekton.frontdoor.genesis-census/1`,
   keyed by base sha256, 38 KB, mirrored to `plugin/lib/…` by `sync_plugin.py`). For each certified
   pin it opens the pinned `.rvt` (ids + classes, under `rvt.versions.reading` for 2025/2024) and
   walks the composition chain from the compose manifest: every rung's certified report
   (`landed_slots`; `byte_delta.records_changed_ids` / `changed_ids`), aliases resolved
   (`Z_RA_2025 → RA_2025`, `Z_RB → RB → RB2_mepcat → RB1_defs`), recursively through `parent`
   until the file no rung produces (= the reduced sample K4 / B2025_K4 / B2024_K4, recorded as
   `ancestor`). `identical_to_ancestor` = base ids NO rung changed. **The law is the provenance
   instrument's own byte law** (byte-identical to the sample ⇒ `autodesk-sample`): slots our
   constructors landed but re-emitted byte-identically (content-free machinery, coincident
   designation facts) stay IN the residue — reported with their recorded disposition, never argued
   away — so the census claims nothing `tools/provenance.py --baseline all` would not on the
   owner's machine. **Cross-check:** on 2026 the chain method reproduces the byte-ground-truth
   `experiments/genesis/subst_k4/residue_c/census.json` (seq-102 compare vs K4, genesis-12 §1.1)
   **id for id: 422 = 422, 11 never authored** — which is what licenses the same method on
   2025/2024, where no byte census was ever tracked (their 585/586 never-authored counts equal
   `residue_after_RC_{2025,2024}.json` exactly).
2. **`rvt.frontdoor.census`** — `pinned_sha256s()` (joins THROUGH the registry:
   `base.PIN` + `release_status`, read-only), `lookup(path) -> (pinned id | None, census | None)`
   (bytes first: a pin is a pin whatever the file is named; pinned-without-census = stale asset,
   said as such), `for_file(path)`, `BaseCensus{residue_ids, never_authored_ids,
   landed_but_identical, by_disposition, summary()}`; `load()` is `lru_cache`d.
3. **`rvt.provenance`** — new class `ours-composed` (`P_COMPOSED`, in `PROVENANCES`, not in
   `DERIVED`); `classify_elements(..., composed_residue_ids=)` / `provenance(..., composed_residue_ids=)`:
   baseline ids outside the residue → `ours-composed` (inherited or edited), residue ids keep
   `autodesk-sample`/`ours-modified`, the clone index is restricted to residue specimens and lineage
   only follows sample verdicts — so created content is `transitive-cloned` only through the true
   residue. A composed slot this build EDITS keeps its change-state (`ElementVerdict.edited`, still
   listed in `modified_elements`). Report gains `baseline_kind` + `composed{…}`; `format_report`
   prints one line. v1 behaviour byte-for-byte when the kwarg is absent (multi-baseline = the
   samples themselves, forces it off).
4. **`tools/rvt_job.provenance_gate`** — `classify_base()` decides once, bytes first
   (`census.lookup`): `base_kind ∈ {pinned-composed-genesis, autodesk-sample, user-base}`; on our
   pin it passes the residue AND runs the ledger's identity layer (`identity=True`, no corpus
   needed) so `_pinned_reason()` composes the sentence from what ran (G2 from the identity
   blockers, residue from the census, G1 verdict) plus the one constant that cannot be measured
   (`G3_COUNSEL`); other kinds keep `_gate_reason()` (v1 sample sentence / user-base sentence). A
   census import failure is recorded through the module's `OPT` holder like every other optional
   capability. `tools/ifc_intent.status_gate` passes `base_kind`/`residue`/`census` through;
   `manifest.py` renders a "base authorship (issue #143 census)" + "this build" pair under Build.
5. **`tests/test_status_gate.py`** (11 tests, 17 s here / ~5 s under CI's `RVT_SKIP_LARGE=1`,
   fresh-clone): census asset current (rebuilds byte-identically) · covers every certified pin
   with residue in the hundreds · 2026 chain ≡ byte truth · census applies only to exact PINNED
   bytes (a sample-named copy of our base is still our base; one byte off is nothing) · gate on
   each pinned base (kind, label, totals, element blockers 100–1000 all `autodesk-sample`,
   identity layer ran, reason cites G2 #19 measured / G3 #23 / residue #21 with the census
   numbers, no "sample base") · sample wording + v1 ledger unchanged · user-base wording · STALE
   census on a pin is said, never mistaken for a user base · end-to-end prompt job (`@slow`): 0
   transitive-cloned, no loadable-families / placed-model-content / embedded-family-documents
   blockers, "G2 identity (#19): 2 inherited lineage identifier(s)" measured, file delivered,
   MANIFEST.md line present.

## Findings

* **F1 — the ~260 of verdict #24 vs the 422 measured.** `genesis_base.json`'s
  `residue_disclosure` still says "~260 Autodesk-authored elements remain"; genesis-12 measured 422
  serialization-identical on the shipped `G_ABPD` (38 with genuine Autodesk values, 384
  machinery/coincident) and retired the 38 in `RC_zero` — which is certified but NOT the pin. The
  gate now reports the measured 422 with dispositions; re-pinning to `RC_zero` (issue #21's lane)
  drops it to 384 and `tools/genesis_census.py build` follows automatically (the test goes red on a
  re-pin without a rebuild). Not touched here: `genesis_base.json` wording belongs with the re-pin — filed as **#275**.
* **F2 — a real per-release gap the honest gate now surfaces.** On 2025/2024 our 4 walls reference
  `BasicWallType 600634` and our 6 loaded families reference `ElectricalLoadClassification 113944`,
  both still byte-identical to the Autodesk ancestor on those bases (the 2026-only rungs
  `ZC_systype` / `ZC_elec` were never ported to the 2025/2024 lanes — `residue_after_RC_2025.json`
  buckets "constructor-partial: BasicWallType 1", "constructor-exists: ElectricalLoadClassification
  18"). So 10 created elements are correctly `transitive-cloned` there and 0 on 2026. Follow-up
  filed as **#274** (port the two rungs to the 2025/2024 compose; owner-machine + viewer-gated).
* **F4 — edit-of-our-output is one lineage step further (follow-up).** `frontdoor --rvt X --edit`
  ledgers against X itself; when X is a prior tekton output grown on a pin, X's bytes are not the
  pin's, so it reads `user-base` and its inherited composed slots read `autodesk-sample` again —
  no worse than `main` (which miscounted everywhere), but the census could be made transitive
  (`residue(X) = census(pin).residue ∩ {slots of X byte-identical to the pin}` behind a descent
  test such as History[0] GUID equality). Filed as **#284** rather than grown here (needs its
  own edit-route tests). The `/simplify` altitude pass also suggested carrying the residue as a
  property of a Baseline descriptor instead of a kwarg and teaching `tools/provenance.py` a
  `--composed-base auto`; both belong with that follow-up (`tools/provenance.py` is outside this
  issue's territory).
* **F3 — instrument note.** `residue_c.census` needs the git-ignored K4 bytes; the rung-chain
  derivation needs only tracked JSON + the pinned file, and the two agree exactly on 2026. That
  makes the census reproducible in CI and on any contributor's clone — the asset is checked, not
  trusted.

## How to run

```bash
.venv/bin/python tools/genesis_census.py show          # one screen per pinned base
.venv/bin/python tools/genesis_census.py build         # after any re-pin (then tools/sync_plugin.py)
.venv/bin/python -m pytest tests/test_status_gate.py -q
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/g1 --json
python3 -c "import json;print(json.load(open('out/g1/manifest.json'))['build']['status_gate']['reason'])"
```

## BRANCH STATE

* Branch `cam/143-g1-gate-baseline` from `main@a5a853f`; PR closes #143.
* Files: `tools/genesis_census.py` (new), `src/rvt/frontdoor/census.py` (new),
  `src/rvt/frontdoor/assets/genesis_census.json` (new, generated), `src/rvt/provenance.py`,
  `tools/rvt_job.py`, `tools/ifc_intent.py`, `src/rvt/frontdoor/manifest.py`,
  `tests/test_status_gate.py` (new) + `tests/ci_shard.txt`, this record, a pointer header in
  `docs/inbox/frontdoor.md`; plugin mirrors regenerated by `tools/sync_plugin.py`
  (`plugin/lib/src/rvt/{provenance.py,frontdoor/census.py,frontdoor/manifest.py,frontdoor/assets/genesis_census.json}`,
  `plugin/lib/tools/{rvt_job,ifc_intent}.py`, `plugin/skills/*/scripts/{rvt_job,ifc_intent}.py`).
* Gates: `tests/test_status_gate.py` 11 passed (17 s); neighbours `test_frontdoor test_router test_job
  test_provenance test_plugin_sync test_bootstrap test_coldstart test_surface_perf
  test_plugin_validate` 146 passed / 38 skipped (57 s, skips = samples-gated); `sync_plugin.py --check` clean;
  `validate_plugin.py` PASS (24 assertions); portable paths ok (2725); bare unzip `go author`
  READY 8.5 s exit 0; three CLI runs (2026/2025/2024, `out/verify/`) delivered + `rvt_validate`
  0 errors (1/0/0 warnings — the standing DataStorage ES-blob decode gap on 2026). `/simplify`
  4-angle review applied (reuse: `base.sha256_of` / `resolve_base` / `release_status`;
  simplification: one classification, sets not dicts, regex id folding, split manifest bullets;
  altitude: bytes-first, registry-joined stale state, measured G2, change-state kept).
* Shipped vs staged: everything ships with the merge; no viewer claim (the pinned bases' bytes are
  untouched — the census READS them), so no probe batch.

---

## eng #284 — 2026-08-10 — the census applies TRANSITIVELY: an EDIT of our own output is judged against the pin it descends from

Stream `eng284` (engineer session for #284, P1, PG1 honesty; finding F4 above). Territory used:
`src/rvt/frontdoor/census.py` (descent test + `Lineage`), `src/rvt/provenance.py` (the small
`ComposedBaseline` descriptor replacing the `composed_residue_ids` kwarg; `same_records` made public),
`tools/rvt_job.py` (`classify_base` / `_pinned_reason` / `provenance_gate` only), `tools/provenance.py`
(`--composed-base auto` only), `tests/test_status_gate.py` (already in `tests/ci_shard.txt` — no drop-in
needed), this record. No hot file, no NO-GO file touched; plugin mirrors regenerated by
`tools/sync_plugin.py`.

### Result in one screen

`frontdoor author --prompt "an electrical room with 6 panels" [--target-version Y]` → X, then
`frontdoor author --rvt X --edit "move PP-1 to 3,1,4.66"` → Y. Fields: the job manifest
`<out>.rvt.manifest.json` → `gates.base_provenance.{base_kind, residue.descends_from, residue.descent,
ledgered_against, provenance_totals, reason}`; the front-door `manifest.json` echoes
`edit.gates.base_provenance.{status, deliverable, base_is_autodesk_sample, reason}` and links the job
manifest as `edit.job_manifest` (F7).

| | `base_kind` | `provenance_totals` | G1 element blockers | layers | reason |
|---|---|---|--:|---|---|
| **before** (main `b169376`), 2026 edit | `user-base` | autodesk-sample **3,219**, ours-modified 1 (the moved PP-1) | **3,166** — incl. our 6 embedded family documents, 18 loadable-family records, 8 symbols | elements | "a user-supplied base with no authorship census; everything inherited from it is ledgered as the base's" |
| **after**, 2026 edit | `descends-from-pinned-genesis` | autodesk-sample **422**, ours-composed **2,680**, ours-created **118** — the create route's reading of X, exactly | **395** (= create) | elements + identity | names `G_ABPD`: "the input descends from the certified composed genesis base G_ABPD (2,679 of the pin's 2,680 composed slots byte-identical; History[0] episode == the pin's), so the output is ledgered against that pin and its authorship census: G2 identity (#19): 2 … measured; G3 #23 …; element residue (#21): 422 of the pin's 422 residue slots still aboard byte-identical to the Autodesk ancestor; 2,680 of its 2,680 composed slots inherited (ours); everything the chain created is ledgered as created content. G1 ledger: FAIL — 395 … PROOF-ONLY is a label: the file is delivered." |
| after, 2025 edit | `descends-from-pinned-genesis` | 925 / 2,391 / 108 + **10 transitive-cloned** (F2: `ElectricalLoadClassification 113944`, `BasicWallType 600634` are residue there and the chain's walls/families reference them) = create exactly | 890 (= create) | elements + identity | names `G_ABPD_2025`, 2,390/2,391 |
| after, 2024 edit | `descends-from-pinned-genesis` | 923 / 2,355 / 108 + 10 = create exactly | 889 (= create) | elements + identity | names `G_ABPD_2024`, 2,354/2,355 |

Status/stamps unchanged in kind: `PROOF-ONLY, NOT-DELIVERABLE` (a label — the edited file is written;
`rvt_validate` 0 errors on all three, identity PASS, structural PASS), `deliverable: false`, the same
open G2 / G3 / residue caveats — rule 1 honoured: nothing withheld, nothing promoted to DELIVERABLE. A
residue slot an EARLIER edit changed (set-mark on the Autodesk-identical `GStyleElem 307`) reads
`ours-modified` in every later edit's ledger (421 sample + 1 modified, "1 more edited along the way and
still derived") — never promoted; a second-generation edit still descends (share 0.9996; the level it
edits reads `ours-composed, edited`). **Gate dicts on the three pinned bases themselves are identical
before/after** (`provenance_gate(pin, pin)` for 2024/2025/2026, `json.dump(sort_keys=True)` diff =
empty: `Lineage.summary()` IS `BaseCensus.summary()` when the bytes are the pin, and the new
`ledgered_against` key appears only on the descendant path). A genuinely foreign file keeps `user-base`
(tests + F5).

### What was built

1. **`rvt.frontdoor.census.lineage(path, doc=None, *, exact_only=False) -> Lineage | None`.** Bytes first,
   as `lookup`: exact sha256 of a certified pin ⇒ `Lineage(exact=True)` (kind `pinned-composed-genesis`).
   Otherwise the **descent test** against the certified pin *of the file's own release*
   (`versions.detect_release` → `pin_file(year)`: registry-direct — `release_status` + `PIN.release_slot`
   + `PIN.candidate_paths`, sha-verified, repo path or plugin bundle; deliberately not `resolve_base`, so a
   firm's `$RVT_GENESIS_BASE` cannot hide our pin): the pin is parsed **once per process** (`_pin_of_release`,
   keyed by sha — it is immutable), `identical = {e ∈ pin ∩ file : seq 101/102/103 byte-identical}` via
   `provenance.same_records` (the ledger's own byte law, now public), and `|composed ∩ identical| /
   |composed| ≥ DESCENT_MIN_IDENTICAL = 0.95` with `composed = pin ids − census.residue` (all pin ids when
   the census is stale). Only then are the evidence numbers gathered (`min_share, share, probed,
   pin_slots_probed, probed_identical, pin_slots_edited, pin_slots_dropped, history_head_guid_matches_pin`).
   `Lineage{pinned_id, census|None(stale), exact, pin_path, pin_doc (descendant only), evidence}`;
   `.kind`; `.composed_baseline()` = the pin's census as a `ComposedBaseline` (None when stale);
   `.summary()` = `BaseCensus.summary()` (+ `descends_from` + `descent` for a descendant). Any read
   failure ⇒ `None` ⇒ name heuristic (fail-safe: never over-claims). `exact_only=True` = sha + name only,
   no parsing (used by every gate path that skips the ledger, so `--no-provenance` stays ~1 ms).
2. **The descendant is ledgered against THE PIN** (`tools/rvt_job.provenance_gate`): the base is parsed
   once inside the timed block, `classify_base(base_path, base)` decides `(kind, lineage)` (exact ⇒ descent
   ⇒ sample-by-name ⇒ user-base), and for `descends-from-pinned-genesis` the candidate is handed to
   `rvt.provenance.provenance(cand, lineage.pin_doc, composed=lineage.composed_baseline(), identity=True)`;
   `gate["ledgered_against"]` names the pin file. Everything the issue asks for then falls out of the
   existing #143 ledger with **no new classification branch**: the pin's residue still aboard
   byte-identical ⇒ `autodesk-sample`; residue any build in the chain edited ⇒ `ours-modified` (derived,
   never promoted); composed slots ⇒ `ours-composed` (`edited` when the chain changed them); everything
   above the pin's watermark (created by any build in the chain, incl. this edit's adds) ⇒ created and
   lineage/clone-refined ⇒ `transitive-cloned` exactly where the create route says so; embedded family
   documents are judged against the (family-free) pin's units ⇒ ours. What THIS edit touched is the job
   manifest's `edit.edited_ids/deleted_ids/created_ids`, as before. `_pinned_reason(lineage, g1, totals)`
   words both kinds from measured numbers (identity blockers, census, ledger totals);
   `_record_base_kind()` writes kind / residue / STALE / UNAVAILABLE once for every path.
3. **`rvt.provenance.ComposedBaseline(residue_ids, pinned_id)`** replaces the `composed_residue_ids`
   kwarg of `classify_elements` / `provenance` (both callers were in this territory; nothing else used
   it) — the descriptor the #143 altitude note asked for; the report's `composed{}` names the pin and
   `format_report` prints it. No verdict class, no gate law changed.
4. **`tools/provenance.py --composed-base auto`** — ledgers FILE against the pinned composed base it IS
   or DESCENDS FROM (`composed_lineage()`: `lineage.pin_doc` is the baseline, `composed_baseline()` the
   census), and is the **fallback when no sample baseline resolves** (a fresh clone has no `samples/`;
   the pre-ship command `--baseline all` printed "everything unbaselined" there and now gives the gate's
   reading, 422 / 2,680 / 118 on Y). Streams layer skipped with a stderr note (the byte-weighted stream
   ledger needs a SAMPLE corpus; the census is element-level) ⇒ never certifies G1; `--composed-base
   off` restores the old behaviour; `auto` + `--baseline` is an error; explicit `auto` on a non-descendant
   exits 1 with one line. Report gains `composed_base{kind, pinned_id, pin, census, descent}`.
5. **Tests** (`tests/test_status_gate.py`, 21 total; `RVT_SKIP_LARGE=1`: 20 passed / 1 skipped in 8.0 s;
   full: 21 passed in 12.8 s): the #143 eleven unchanged in intent (the two that staged a "sample"/"user"
   base by patching `lookup` now also lift the descent bar — `_no_lineage`); new:
   `test_edit_of_our_output_descends_from_the_pin[2024|2025|2026]` (walls-only prompt job → `--rvt --edit
   "delete wall <id>"` through `rvt.frontdoor.author`, famgen-free ≈ 2 s per release: kind, label,
   delivered file, `residue` == the pin's census summary + `descends_from`/`descent`, `ledgered_against`
   the pin, totals == the create route's with one wall gone, F2's `transitive-cloned` walls survive on
   2025/2024 and name `600634`, blockers hundreds ≤ create's, identity layer ran, reason citations, no
   "user-supplied"/"sample base", the front-door manifest echoes label + sentence);
   `test_second_generation_edit_still_descends`; `test_lineage_api` (incl. `pin_file`, `exact_only`,
   `pin_doc` reuse, same `ComposedBaseline` for pin and descendant); `test_no_byte_descent_keeps_user_base`
   (byte law patched to "every slot differs" ⇒ `user-base` wording, > 3,000 sample — the fail-safe
   direction; the 0.95 bar alone decides; `skip=True` never parses);
   `test_a_relative_that_is_not_a_descendant_stays_user_base` (real bytes, F5; skips if the eval-kit
   specimen is absent); `test_residue_slot_edited_upstream_stays_derived` (**real bytes**: set-mark on a
   residue `GStyleElem`, then a later edit ⇒ 421 / 1 modified / 4 / 2,680 both times, the slot
   `ours-modified`, reason "421 of the pin's 422 residue slots still aboard … 1 more edited along the way
   and still derived"); `test_provenance_cli_composed_base_auto` (same totals as the gate, streams
   skipped, `certifies_G1` false, `--baseline all` fallback on a sample-less clone, `auto`+`--baseline` ⇒
   1). The `@slow` 6-panel e2e now also edits its output: same totals one step later, family documents /
   loadable families / placed instances not among the blockers, `ledgered_against` the pin.

### Findings

* **F5 — the History episode GUID is evidence, never the test.** `tekton-eval-kit/TEST-KIT/02_*.rvt`
  and `07_*.rvt` (older tekton outputs, tracked) carry **every one of the pin's 3,102 ids and the pin's
  `History[0]` GUID** (`34447475-…`, which the pin itself inherited from its Autodesk ancestor — a sample
  would match it too), yet only 1,706 / 1,975 of the 2,680 composed slots are byte-identical (64 % /
  74 %: grown on an earlier rung, before later constructors re-authored those slots). No census can vouch
  for the differing ~700–1,000 slots, so they correctly read `user-base`; 03–06 of the same kit descend
  at 100 %. Hence the byte share of *composed* slots is the deciding law and the GUID rides along in
  `descent.history_head_guid_matches_pin` and the reason only.
* **F6 — cost (steer #108).** Create route unchanged (exact sha hit before any parse; pinned-base gate
  0.2 s as before). Edit route: one parse of the ~580 KB pin per process + one payload compare per shared
  slot; wall time of `frontdoor author --rvt X --edit "set level 311 elevation to 1 ft"` (repo `.venv`, 3
  runs each): 6-panel X 0.99/1.01/1.15 s before → 1.02/1.06/1.13 s after; walls-only X 0.71/0.76/0.78 s
  → 0.79/0.80/0.82 s (≈ +0.05 s). `--no-provenance` does no parsing (bytes + name only). Bare unzip +
  system Python 3.11: `go author --prompt` (walls-only) READY 1.31 s exit 0, then `go author --rvt
  out/j1/prompt_room.rvt --edit "set level 311 elevation to 1 ft"` READY **0.81 s** exit 0,
  `descends-from-pinned-genesis`, share 0.9996, `ledgered_against` the *bundled* `assets/genesis/G_ABPD.rvt`.
* **F7 — two edit-route manifest gaps outside this territory (follow-up filed as **#406**, `Refs #284`).**
  `rvt.frontdoor.manifest.edit_manifest` echoes only `{status, deliverable, base_is_autodesk_sample,
  reason, …}` of each job gate, so the front-door `manifest.json` of an edit shows the transitive
  sentence but not `base_kind` / `residue` / `provenance_totals` / `ledgered_against` (one hop away in
  the linked `edit.job_manifest`), and its `honesty.proof_only_stamps` is `[]` while `status` says
  PROOF-ONLY (the create routes stamp both). `manifest.py` is held by eng #359 this wave; the wanted change
  is two lines (extend the pass-through tuple; feed the job's status label into `_honesty(...,
  extra_stamps=...)`).
* **F8 — `/simplify` changed the design, for the record.** The first cut ledgered Y against X and taught
  the classifier three descendant branches (`lineage_watermark`, `modified_residue_ids`, an `inherited`
  flag, a units special case) to reconstruct what ledgering against the pin gives for free; the review
  pass replaced it with "descent test picks the pin, the pin is the baseline" — same totals (asserted),
  −150 lines, one mechanism for the gate and the CLI. Also from that pass: registry-direct `pin_file`,
  per-process pin cache, evidence gathered only past the bar, no parsing on `--no-provenance`, dead
  `residue_for` / kwarg shim dropped. `history_head_guid` now exists in `census.py` and (older) in
  `tools/rvt_job.py` + inline in `rvt/mep/views_spaces.py`; consolidating into `rvt.stream_encoders` is
  outside this territory (noted in the follow-up).

### How to run

```bash
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/p --json
.venv/bin/python tools/frontdoor.py author --rvt out/p/prompt_room.rvt --edit "move PP-1 to 3,1,4.66" --out out/e --json
python3 -c "import json,glob;g=json.load(open(glob.glob('out/e/*.rvt.manifest.json')[0]))['gates']['base_provenance'];print(g['base_kind'],g['provenance_totals'],g['ledgered_against']);print(g['reason'])"
.venv/bin/python tools/provenance.py out/e/prompt_room.edited.rvt --composed-base auto --no-examples
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_status_gate.py -q -rs
```

### BRANCH STATE (eng #284)

* Branch `cam/284-edit-census-descent` from `main@b169376`; PR closes #284.
* Files: `src/rvt/frontdoor/census.py`, `src/rvt/provenance.py`, `tools/rvt_job.py`
  (`classify_base` / `_pinned_reason` / `_record_base_kind` / `provenance_gate` only), `tools/provenance.py`,
  `tests/test_status_gate.py`, this record; regenerated mirrors
  `plugin/lib/src/rvt/{frontdoor/census.py,provenance.py}`, `plugin/lib/tools/rvt_job.py`,
  `plugin/skills/{tekton-author,tekton-edit,tekton-native}/scripts/rvt_job.py`.
* Gates: `tests/test_status_gate.py` 20 passed / 1 skipped (`RVT_SKIP_LARGE=1`, 8.0 s), 21 passed
  without (12.8 s); neighbours `test_provenance test_job test_go_edit test_census test_frontdoor
  test_router test_ifc_intent test_plugin_sync test_bootstrap test_coldstart test_surface_perf` 243 passed
  / 54 skipped (`RVT_SKIP_LARGE=1`, 65 s; skips = large/samples-gated + 2 root-chmod); `tools/sync_plugin.py`
  then `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2869); pyflakes clean on the five files; pinned-base gate dicts
  identical before/after (empty JSON diff, 2024/2025/2026); bare-unzip `go` create + edit READY (F6);
  `/simplify` four-angle pass applied (F8).
* Shipped vs staged: ships with the merge; no bytes of any pinned base change (the descent test READS
  them), no viewer claim, no probe batch.

---

## eng #303 — 2026-08-10 — census hardening: the note reaches the front door, broken evidence voids the census, DELIVERABLE needs a certified G1 + G3

Stream `eng303` (engineer session for #303, P1, PG1/PG5 honesty; the post-merge audit of #276).
Territory used: `tools/ifc_intent.py` (the `status_gate` whitelist tuple only), `src/rvt/frontdoor/manifest.py`
(`authorship_census_note` + one MANIFEST.md branch), `tools/genesis_census.py` (laws, reconciliation, exit
codes, docstring), `tools/rvt_job.py` (the flip condition only: `G3_CLEARED` + `deliverable_now`; #396's `--json`
mode and #407's descent code untouched), `src/rvt/provenance.py` (docstrings only), `tests/test_status_gate.py`
(already in `tests/ci_shard.txt`, no drop-in needed), this section. No hot file, no NO-GO file; the census
asset `src/rvt/frontdoor/assets/genesis_census.json` is **byte-identical** (its shape is what
`rvt.frontdoor.census` reads — the new reconciliation numbers live in the tool's `audit`/stdout, not the
asset); plugin mirrors regenerated by `tools/sync_plugin.py`.

**Correction to §4 of the eng143 section above** ("`tools/ifc_intent.status_gate` passes
`base_kind`/`residue`/`census` through"): it passed `base_kind` and `residue`, **not** `census` — so on the
product path a STALE census or a census import failure was recorded in the job runner's gate dict and then
dropped before `manifest.json`; the front door showed our own pin as a plain `user-base` /
"user-supplied base with no authorship census". Fixed here (1 below).

### Result in one screen

| | before (main `2b87024`) | after (this branch) |
|---|---|---|
| `frontdoor author --prompt "an electrical room with 6 panels"`, census applied | `build.status_gate` keys: status, deliverable, base, base_is_autodesk_sample, base_kind, residue, g1, provenance_totals, created_elements, reason, elapsed_s | + `modified_elements` (the ProjectInfo this build edited: 1) — `census` absent because the census applied (`residue` present); no degradation; MANIFEST.md base-authorship line unchanged; totals 422 / 2,680 / 118, 395 element blockers, PROOF-ONLY, delivered, `rvt_validate` 0 errors |
| same, census import forced to fail (`_census_mod → None`, in-process) | `base_kind: user-base`, reason "a user-supplied base with no authorship census…", **no trace of why** in manifest.json / MANIFEST.md | `build.status_gate.census = "UNAVAILABLE (ImportError: …): base_kind decided by file name only; a pinned base reads as user-base until fixed"`; `build.degradations` += "status-gate authorship census UNAVAILABLE (…) -- the ledger fell back to the conservative reading … over-states, never under-states; the label and the delivered file are unaffected (hard rule 1)"; MANIFEST.md: "- base authorship: **user-base** (census **UNAVAILABLE (…)**: everything inherited from the base is ledgered as the base's)" + "- **degradation**: status-gate authorship census UNAVAILABLE …"; file delivered, PROOF-ONLY, totals 3,101 sample / 16 transitive-cloned (the honest over-count) |
| same, STALE census (re-pin without rebuild; `lookup → (id, None)`) | gate said STALE, front door dropped it | `status_gate.census = "STALE: … run tools/genesis_census.py build"`, degradation + MANIFEST.md line as above, `base_kind` stays `pinned-composed-genesis` |
| `tools/genesis_census.py check` | exit 0; a rung report with `unexpected_changed_ids ≠ []` / `assertion_holds: false`, a changed id its constructor never landed, or `cross_check.agree: false` would still have exited 0 (build) / been recorded only | exit 0 today with the law line per base ("changed => landed holds on every rung; reconciliation: 2,700 = 2,680 aboard + 20 deleted in phase 2 …, none unaccounted"); any of the four breaks ⇒ **one `LawViolation` naming every broken base, exit 1, nothing written** (tests inject each synthetically on a deep copy of the parsed evidence) |
| `provenance_gate` flip | `if g1.passes: DELIVERABLE` | `if deliverable_now(g1)` = `certifies_G1 and G3_CLEARED` (`G3_CLEARED = False`, owned by #23); a synthetic zero-blocker element+identity PASS on the pin ⇒ still `PROOF-ONLY, NOT-DELIVERABLE`, reason ends "G1 ledger: PASS (elements+identity layer(s) ONLY) — NOT a G1 certification … " beside "G3 counsel (#23 …) is a human gate, open"; a certified G1 with G3 open ⇒ PROOF-ONLY; flag True + certified ⇒ DELIVERABLE (the flag is the switch) |
| `provenance_gate(pin, pin)` on 2024/2025/2026 (`json.dump(sort_keys=True)`, `elapsed_s` dropped) | — | **diff empty on all three** (`diff before_Y.json after_Y.json` → rc 0, no output) — #407's behaviour and every existing key untouched |
| edit of the 6-panel output (`--rvt … --edit "move PP-1 to 3,1,4.66"`) | descends | still `descends-from-pinned-genesis`, share 0.9996, totals 422 / 2,680 / 118 = the create route's, `ledgered_against` the bundled `G_ABPD.rvt`, 0 errors |

### What was built

1. **The census note reaches the front door.** `tools/ifc_intent.status_gate`'s whitelist now carries
   `census`, `modified_elements` and `ledgered_against` (the keys `provenance_gate` wrote that never left the
   job runner; `ledgered_against` appears on a create route whose `--base` is itself a prior tekton output).
   `rvt.frontdoor.manifest.authorship_census_note(status_gate)` turns a `census: STALE …` /
   `census: UNAVAILABLE (…)` into ONE `build.degradations` line (so `--json` summaries and every skill that
   lists degradations see it), and `_render_md`'s existing no-residue base-authorship line names the census
   state ("(census **STALE …**: everything inherited …)") instead of a flat "(no census: …)". Nothing changes
   when the census applied (`residue` present ⇒ no `census` key ⇒ no note) or when the base genuinely has
   none (sample / user `--base`: no `census` key either — `_record_base_kind` writes it only for our pin or a
   downed lookup).
2. **The census tool's laws** (`tools/genesis_census.py`). `Chain._rung` now checks "changed ⇒ landed by
   our constructor" three ways per rung — the id sets themselves (`records_changed_ids ⊆ landed_slots`), the
   rung report's own `byte_delta.unexpected_changed_ids == []`, and its `assertion_holds is True` — and
   `Chain.reconcile(aboard)` checks that every id a rung changed/landed that is not aboard the pin is one of
   the compose's recorded phase-2 deletions (`phase_2_deletions.specs[].source_file → ids`, tracked JSON) and
   that no deleted id is aboard (an unreadable deletion spec is itself a violation, never a silent `[]`). Measured today: **47/47 rung reports hold all three** (2026: 19, 2025: 14,
   2024: 14); reconciliation 2026 **2,700 changed = 2,680 aboard + 20 deleted** (all 20 ∈ `D_all.spec.json`'s
   240), 2025 **2,392 = 2,391 + 1** (`1250031` ∈ `D_2025_stragglers_full.json`'s 17), 2024 **2,356 = 2,355 + 1**
   (same id, `D_2024_…`); `ours_by_composition == changed_aboard` on each. A byte-ground-truth census that
   contradicts the chain (`cross_check.agree is not True`, 2026 only today) is the fourth violation ("CHAIN vs
   BYTE TRUTH DISAGREE — the chain says N identical, <truth> says M (only in truth …, only in chain …)"): byte
   truth overrules the chain. `census_one` raises `LawViolation`; `build_census` collects one per base and
   raises ONE naming them all; `main` prints "LAW VIOLATED, no census derived (nothing written)" and exits 1 for
   every verb — `build` **without rewriting the asset**, so the shipped census stays the last one the evidence
   supported and a re-pinned base then reads STALE in the gate (the conservative ledger), never an over-claim.
   (`/simplify` merged an earlier separate `disagreements()`/second exit path into this one mechanism.) The
   reconciliation is returned through an optional `audit` dict (`build_census(audit)`) and printed by every
   verb; it is deliberately NOT added to the asset (whose shape `rvt.frontdoor.census.load` reads and whose
   bytes the plugin ships).
3. **The DELIVERABLE flip** (`tools/rvt_job.py`): `G3_CLEARED = False` (owned by #23 — flipped only by the
   PR that records counsel's answer and rewords `G3_COUNSEL`) and `deliverable_now(g1) = certifies_G1 ∧
   G3_CLEARED` replace `if g1.get("passes")`. The PROOF-ONLY branch is unchanged, so on our pin the sentence
   already explains a passing-but-uncertified G1 ("G1 ledger: PASS (… layer(s) ONLY) — NOT a G1
   certification: streams, strings not ledgered") next to the open G3. Module docstring + `provenance_gate`
   docstring say so. `manifest["deliverable"]`/`--require-deliverable` follow the gate as before.
4. **Docstrings say what is trusted** (`src/rvt/provenance.py` module docstring for `ours-composed`, the
   `P_COMPOSED` comment, `ComposedBaseline`, `classify_elements`; `tools/genesis_census.py` module docstring):
   the law actually applied is "a base slot is ours iff a certified rung's `byte_delta` changed its record
   AND its `landed_slots` emitted there"; the ledger applies the census's residue set as given (it cannot
   re-verify against the ancestor, which is not shipped) and judges the residue by its own byte law against
   the baseline; the old "never declares anything ours that `--baseline all` would not" phrasing is gone from
   the tool docstring (it survived nowhere else).
5. **Tests** (`tests/test_status_gate.py`, 21 → 30; `RVT_SKIP_LARGE=1`: **29 passed / 1 skipped in 19 s**;
   the `@slow` e2e alone: 1 passed in 5 s): `test_census_laws_hold_and_reconcile_on_every_pin` (audit numbers
   above, `main(["check"]) == 0`); `test_census_tool_refuses_evidence_that_breaks_the_law[stray change |
   unexpected flag | assertion fails | truth loses one]` (a doctored deep copy of the once-parsed `ReportIndex` —
   tracked files untouched — ⇒ `LawViolation` with the specific wording, `build --out tmp` exits 1 and writes no
   file, `check` exits 1; the fourth case is the chain-vs-byte-truth disagreement, G_ABPD 422 vs 421);
   `test_deliverable_flip_needs_certified_g1_and_g3_cleared` (truth table over `deliverable_now` × `G3_CLEARED`;
   stubbed `gate_G1`: zero-blocker uncertified PASS on the pin ⇒ PROOF-ONLY with the "NOT a G1
   certification"/G3 wording and the file present; certified + `G3_CLEARED` patched True ⇒ DELIVERABLE);
   `test_census_unavailable_reaches_the_front_door_manifest` / `test_stale_census_reaches_…` (real walls-only
   prompt jobs through `rvt.frontdoor.author`: `status_gate.census`, the degradation, the MANIFEST.md line,
   never the plain user-base line, delivered, PROOF-ONLY, > 3,000 sample = over-states);
   `test_applied_census_adds_no_note`. Changed: the `@slow` 6-panel e2e derives 2,680/422 from
   `C.for_file(pin)` and the G2 count from the sentence's own field list cross-checked against the gate's
   identity blockers (no literals); `_pinned()` / `_built_census()` **skip** (not error) when
   `$RVT_GENESIS_BASE` resolves a non-pinned base or the tool refuses the override.

### Findings

* **F9 — the phase-2 deletion seed is id-level evidence after all.** The issue expected only a count-level
  reconciliation on 2025/2024; the compose manifests' `phase_2_deletions.specs[].source_file` name tracked
  spec JSONs whose `ids` are the exact seed (17 / 17 / 240), so the reconciliation is id-exact on all three
  releases and is enforced as such (`unaccounted == []`, `resurrected == []`). What 2025/2024 still lack is
  a byte-ground-truth census (K4-relative seq-102 compare) — owner-machine material; the per-rung law is
  their evidence meanwhile, and `show` says so per base.
* **F10 — the pinned-base gate lists are truncated at 16 blockers** (`gate["g1"]["blocking"][:16]`, pre-existing):
  on the raw 2024/2025 pins (unscrubbed identity) that hides some identity rows, while the reason sentence is
  built from the full list. Not changed here (would alter the pinned-gate JSON the issue wants identical); the
  e2e test therefore takes the G2 count from the sentence and only checks the listed identity rows are among
  the named fields. Worth a line in #406's manifest work if a consumer ever counts rows.
* **F11 — edit-route echo stays with #406.** The edit route's front-door `manifest.json` still echoes only the
  reduced gate tuple (no `base_kind`/`census`); the full note is one hop away in `edit.job_manifest`. #406 owns
  that tuple (and can call `authorship_census_note` from `edit_manifest` in one line); not duplicated here.
* **F12 — DELIVERABLE is unreachable on the product path by construction (intended), but the gate cannot say
  which layers are missing.** `provenance_gate` runs the ledger with elements + identity only, so `certifies_G1`
  is never True there and `gate["g1"]` carries `passes/verdict/layers/blocking` but not `certifies_G1` /
  `missing_layers` — a reader learns it from the verdict prose ("NOT a G1 certification: streams, strings not
  ledgered"). Adding the two keys is a one-liner but changes the pinned-gate JSON this issue pins identical;
  left for the PR that wires the streams/strings layers into the gate (owner-machine corpus) or for #23's flip PR.
  Likewise `G3_CLEARED` lives as a module constant in `tools/rvt_job.py` (the only place that flips the label);
  the `/simplify` altitude pass suggests a `gates` block in `genesis_base.json` read by engine + plugin alike —
  #23's decision when it has something to record.

### How to run

```bash
.venv/bin/python tools/genesis_census.py check                     # laws + reconciliation per base, exit 0
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_status_gate.py -q -rs
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/g --json
python3 -c "import json;m=json.load(open('out/g/manifest.json'));sg=m['build']['status_gate'];print(sorted(sg), sg.get('census'), m['build']['degradations'])"
```

### BRANCH STATE (eng #303)

* Branch `cam/303-status-gate-census-hardening` from `main@2b87024`; PR closes #303.
* Files: `tools/genesis_census.py`, `tools/rvt_job.py` (flip only), `tools/ifc_intent.py` (whitelist only),
  `src/rvt/frontdoor/manifest.py`, `src/rvt/provenance.py` (docstrings only), `tests/test_status_gate.py`,
  this section; regenerated mirrors `plugin/lib/src/rvt/{frontdoor/manifest.py,provenance.py}`,
  `plugin/lib/tools/{rvt_job,ifc_intent}.py`, `plugin/skills/tekton-author/scripts/{rvt_job,ifc_intent}.py`,
  `plugin/skills/{tekton-edit,tekton-native}/scripts/rvt_job.py`. Census asset unchanged (check: current).
* Gates: `tests/test_status_gate.py` 29 passed / 1 skipped (`RVT_SKIP_LARGE=1`, 19 s) + the `@slow` e2e 1 passed
  (5 s); neighbours `test_provenance test_job test_go_edit test_census test_frontdoor test_router test_ifc_intent
  test_plugin_sync test_bootstrap test_coldstart test_surface_perf test_plugin_validate` **256 passed / 54 skipped**
  (`RVT_SKIP_LARGE=1`, 88 s; skips = large/samples-gated, root-chmod, no bare numpy python); `tools/sync_plugin.py`
  then `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py`
  ok (2879); pinned-gate JSON diff empty ×3; front door prompt (4.5 s) + edit + census-down prompt all delivered,
  `rvt_validate` ok / 0 errors / 1 warning (the standing DataStorage ES-blob gap; 0 warnings on the 2025 output); bare unzip +
  system Python 3.11 `go author` READY exit 0 — walls-only 1.44 s, the 6-panel job 4.77 s (422 / 2,680 / 118, PROOF-ONLY,
  `modified_elements` in `status_gate`, 0 degradations); `/verify` re-drove prompt (2026 + `--target-version 2025`:
  925 / 2,391 / 4 transitive-cloned = F2) + edit after the final diff, all rc 0.
* Shipped vs staged: ships with the merge; no bytes of any pinned base or of the census asset change, no viewer
  claim, no probe batch.

---

## eng #406 — 2026-08-10 — the front door's OWN edit manifest says what the gate says: kind / residue / ledgered_against / totals, the base-authorship line, the label as a stamp

Stream `eng406` (engineer session for #406, P2, PG1 honesty; the follow-up F7/F11 above named). Territory
used: `src/rvt/frontdoor/manifest.py` (`edit_manifest`, `_honesty`, the MANIFEST.md renderer — rebased on
`main@b253668`, i.e. after #418 and #426 landed there), `tests/test_status_gate.py` (already in
`tests/ci_shard.txt`; no drop-in needed), this section; regenerated mirror
`plugin/lib/src/rvt/frontdoor/manifest.py`. Nothing else: `tools/rvt_job.py` (eng #424), `tools/ifc_intent.py`
(eng #397), `router.py`, `__init__.py`, every hot file untouched; the gate itself (`provenance_gate`,
`census.py`) is READ, never changed.

### Result in one screen

`frontdoor author --prompt "an electrical room with 6 panels"` → X (2026 pin), then
`frontdoor author --rvt X --edit "move PP-1 to 3,1,4.66" --json` → Y, run as an unprivileged fresh clone
(no `samples/`; the bundled `plugin/assets/genesis/G_ABPD.rvt` is the pin).

| | before (`main@b253668`) | after (this branch) |
|---|---|---|
| `manifest.json` → `edit.gates.base_provenance` keys | `base_is_autodesk_sample, deliverable, reason, status` | + `base_kind` **descends-from-pinned-genesis**, `residue` (the pin's census summary + `descends_from: G_ABPD` + `descent{share 0.9996, 2,679/2,680 composed slots byte-identical, min_share 0.95, history_head_guid_matches_pin true}`), `ledgered_against` = the bundled `…/assets/genesis/G_ABPD.rvt`, `provenance_totals` **422 / 2,680 / 118** — every echoed key `==` the job manifest's `gates.base_provenance`, totals `==` the create route's `build.status_gate.provenance_totals`; a `census` (STALE/UNAVAILABLE) note passes through too when the gate wrote one. NOT echoed (one hop away in `edit.job_manifest`, by design): `g1.blocking`, `created_elements`, `modified_elements`, `base`, `elapsed_s` |
| `honesty.proof_only_stamps` / `--json` → `stamps` on the edit | `[]` / `[]` while `status` = `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` | `["PROOF-ONLY, NOT-DELIVERABLE"]` both — the gate's label, the same string the create routes stamp (`_honesty(status_gate=…)` is now the ONE rule both routes use) |
| `MANIFEST.md` of the edit | gate list only (`gate base_provenance: PROOF-ONLY, NOT-DELIVERABLE`), no reason, no authorship, no Honesty section | `- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — <the #284 sentence naming G_ABPD>` · `- base authorship (issue #143 census): **descends-from-pinned-genesis** — descends from G_ABPD (Revit 2026; 2,679 of 2,680 composed slots byte-identical, share 0.9996 ≥ 0.95), ledgered against the pin `G_ABPD.rvt` and its census — 2,680 of 3,102 base elements ours by composition; residue 422 still byte-identical to the Autodesk ancestor (11 never authored, 411 re-emitted identically by our constructors; recorded dispositions {…})` · `- this file's ledger (everything the chain created): 118 created elements ours, 0 created with lineage into the residue` · `## Honesty` with `- **PROOF-ONLY, NOT-DELIVERABLE** (a label, never a refusal)` + tiers + release |
| same chain on the 2025 pin (`--target-version 2025`, walls-only X) | — | `descends-from-pinned-genesis`, `descends_from G_ABPD_2025`, totals 925 / 2,391 / 4 transitive-cloned (F2), `ledgered_against G_ABPD_2025.rvt`, `target_version.output_release 2025`, MD line "descends from G_ABPD_2025 (Revit 2025; 2,390 of 2,391 …)" |
| a foreign file (`tekton-eval-kit/TEST-KIT/02_*.rvt`, F5's non-descendant) edited | gate list only | `edit.gates.base_provenance.base_kind` **user-base**, totals 3,345 sample / 1 modified, no `ledgered_against`, MD `- base authorship: **user-base** (no census: everything inherited from the base is ledgered as the base's)`, stamped PROOF-ONLY, delivered |
| an edit whose gate says `census: STALE …` / `UNAVAILABLE (…)` (synthetic job manifest) | dropped | `edit.gates.base_provenance.census` carried, ONE `edit.degradations` line via `authorship_census_note` ("… conservative reading … hard rule 1"), MD `- base authorship: **pinned-composed-genesis** (census **STALE …**…)` + `**degradation**: …` — the #303 behaviour of the create routes, now on the edit route (F11) |
| create routes' `MANIFEST.md` | as #418 | byte-for-byte the same authorship lines (now emitted by the shared `status_gate_lines`); the Honesty stamps gain the suffix "(a label, never a refusal)" — the only create-route wording change |
| status / delivery | PROOF-ONLY, delivered | unchanged: `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`, `ok: true`, `files: [edited]`, `rvt_validate` ok / 0 errors / 1 warning (the standing DataStorage ES-blob gap) — rule 1: nothing withheld, nothing promoted |
| `provenance_gate(pin, pin)` JSON, 2024 / 2025 / 2026 (`sort_keys`, `elapsed_s` dropped) | — | `diff` empty on all three (the gate is not touched; recorded for the ledger) |

### What was built

1. **`edit_manifest` echoes the gate like `build.status_gate`.** The per-gate whitelist is one module
   constant `_EDIT_GATE_KEYS` (the old inline tuple + `base_kind`, `residue`, `census`, `ledgered_against`,
   `provenance_totals`); `bp = gates["base_provenance"]` then drives three things the create routes already
   did: `_honesty(..., status_gate=bp)` stamps its PROOF-ONLY label (the `_honesty` rule now takes the gate
   explicitly — `build_manifest` passes `build.status_gate`, `edit_manifest` passes `bp` — instead of
   fishing it out of `build`, so there is ONE stamping rule); `authorship_census_note(bp)` appends the
   STALE/UNAVAILABLE line to `edit.degradations`; and the renderer prints the gate.
2. **`status_gate_lines(sg, ledger_of=…)`** (public) is the ONE MANIFEST.md wording for a P0 gate on both
   routes: the deliverability label + reason, then the base-authorship line — pinned (`**kind** G_ABPD (Revit
   N) — …`, unchanged text), **descendant** (new: "descends from <pin id> (Revit N; i of n composed slots
   byte-identical, share s ≥ min), ledgered against the pin `<file>` and its census — <the same census
   numbers>"), or the no-residue line (sample / user base / STALE / UNAVAILABLE, unchanged text) — then the
   ledger-totals line (`this build:` on create, `this file's ledger (everything the chain created):` on an
   edit; `+ ", k residue slot(s) edited and still derived"` when `ours-modified` is non-zero, e.g. the
   set-mark-on-GStyleElem chain of `test_residue_slot_edited_upstream_stays_derived`). `_honesty_lines(hon)`
   likewise renders the Honesty section for both routes (the edit MD had none).
3. **Tests** (`tests/test_status_gate.py`, 30 → 34): `test_edit_manifest_surfaces_the_gate_like_the_create_routes[2024|2025|2026]`
   (reuses the module-cached walls-only `_chain(year)`: echoed keys `==` the job gate's on
   `status/deliverable/base_is_autodesk_sample/base_kind/residue/ledgered_against/provenance_totals/reason`
   and nothing element-level leaks; `descends_from` == the release's pin id; `ledgered_against` basename ==
   the pinned file; composed/sample totals == the create route's, created 4 → 3; the label in
   `honesty.proof_only_stamps` AND `AuthorResult.as_json()["stamps"]`; delivered; no census degradation when
   the census applied; MANIFEST.md contains exactly the three `status_gate_lines` + the Honesty stamp line,
   with the descendant wording checked clause by clause against the gate's own numbers) and
   `test_edit_manifest_words_a_foreign_base_and_a_downed_census_honestly` (synthetic job manifests, no
   bytes: user-base line + reason line + stamp, other gates trimmed to their summary keys; STALE ⇒ `census`
   echoed + one degradation + the census MD line; a `SKIPPED (--no-provenance)` gate ⇒ deliverability line,
   no authorship line, no stamp; a refused input (no job) ⇒ `gates == {}`, no stamp, FAILED status).
   `/simplify` (four angles) applied before the final diff: one stamping rule (`status_gate=`), the
   deliverability line folded into the shared helper, one Honesty renderer, the duplicated
   `base.input_kind/ledgered_against` keys dropped again, tests assert via the helper instead of a copied
   f-string. Skipped with reason: a per-gate-kind whitelist map (no key collides across the job's four gates
   today — speculative), sharing the key list with `tools/ifc_intent.status_gate` (out of territory; the
   create route deliberately carries the element lists the edit echo leaves one hop away).

### Findings

* **F13 — the two #407 keepers.** `tools/ifc_intent.py:1331` already passes `ledgered_against` (and
  `census`, `modified_elements`) through — #418 (eng #303) landed it; nothing left there. `tools/rvt_job.py:455`
  (`_pinned_reason` opens every descendant with "P0 gates on an **edit** of our own output" although the same
  branch fires on `--prompt … --base <prior output>`) is eng #424's file this wave and stays open; the MD line
  added here is route-neutral ("descends from …"), only the echoed `reason` string carries the word.
* **F14 — two wording nits outside this territory (record only, no issue: each is one line for whoever next
  holds the file).** `src/rvt/frontdoor/__init__.py` `_route_rvt_inner`'s `base_note` still says
  "deliverability of the result is ledgered against that input", which for a descendant is now "against the
  pin it descends from" (the gate block right below it says so, so no reader is misled); and
  `router.py:_absorb_author` stamps the edit cell with `r.status` ("PROOF-ONLY, NOT-DELIVERABLE (hard gates
  PASSED)") rather than the manifest's `honesty.proof_only_stamps` ("PROOF-ONLY, NOT-DELIVERABLE"), so
  `route run --rvt … --prompt "move …"` and `frontdoor author --rvt … --json` name the same label with and
  without the parenthesis (eng #424 holds `router.py`).
* **F16 — a CREATE on `--base <a prior tekton output>` now prints the descendant wording too.** Because
  `status_gate_lines` is shared, `frontdoor author --prompt … --base X` (X descends from the pin; #407 probed it:
  `descends-from-pinned-genesis`, 422 / 2,680 / 122) renders "descends from G_ABPD (…, share …), ledgered against the
  pin …" in the create route's MANIFEST.md instead of the pinned form `**descends-from-pinned-genesis** G_ABPD (Revit
  2026)`. More honest, and it makes the plain pinned/sample/user forms the only ones that imply "these ARE the base's
  bytes"; the reviewer of #435 flagged it as intended-but-worth-recording.
* **F17 — one test contract updated deliberately (Refs #376).** `tests/test_input_release.py::
  test_route_known_release_proceeds_as_before_and_reports_the_block` asserted "a KNOWN-release edit carries no stamps at
  all" (`not r.as_json()["stamps"]`) as shorthand for "no UNVERIFIED-RELEASE label"; with #406 a PROOF-ONLY edit is
  stamped like the create routes, so the clause now reads `not any("UNVERIFIED" in s for s in stamps)` — the intent
  (#176/#376: known ⇒ unchanged, no UNVERIFIED anywhere) is kept, nothing else in that file loosened. Caught by the
  tech-lead's sandboxed shard run, not by my neighbour list — lesson: run the merged shard
  (`python3 tools/dev/shard_list.py --print`) before reporting, not only the stream-local neighbours.
* **F15 — `history_head_guid` consolidation not done** (the issue's optional tidy-up): two of the three
  copies live in NO-GO files this wave (`tools/rvt_job.py`, and `rvt/mep/views_spaces.py` is nobody's but the
  third caller alone is not a consolidation). Filed as its own small task (#434, `Refs #406`) so it is picked up
  when `rvt_job.py` is free; the `scrub_identity(document_guid=…)` casing caveat is carried into it.

### How to run

```bash
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/p --json
.venv/bin/python tools/frontdoor.py author --rvt out/p/prompt_room.rvt --edit "move PP-1 to 3,1,4.66" --out out/e --json | python3 -c "import json,sys;print(json.load(sys.stdin)['stamps'])"
python3 -c "import json;g=json.load(open('out/e/manifest.json'))['edit']['gates']['base_provenance'];print(g['base_kind'],g['provenance_totals'],g['ledgered_against']);print(g['residue']['descent'])"
grep -n "deliverability\|base authorship\|ledger\|## Honesty" out/e/MANIFEST.md
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_status_gate.py -q -rs
```

### BRANCH STATE (eng #406)

* Branch `cam/406-edit-manifest-gate` from `main@b253668`; PR closes #406.
* Files: `src/rvt/frontdoor/manifest.py`, `tests/test_status_gate.py`, `tests/test_input_release.py` (one clause, F17), this section; regenerated mirror
  `plugin/lib/src/rvt/frontdoor/manifest.py`. No hot file, no NO-GO file, no asset, no pinned-base byte touched.
* Gates: `tests/test_status_gate.py` **33 passed / 1 skipped** (`RVT_SKIP_LARGE=1`, 27 s; the skip is the
  `@slow` 6-panel e2e, which passes alone without the flag: 1 passed, 6 s); stream-local + neighbours
  `test_status_gate test_frontdoor test_go_edit test_router test_job test_plugin_sync test_bootstrap
  test_coldstart test_surface_perf` **251 passed / 27 skipped** (`RVT_SKIP_LARGE=1`, 127 s; skips =
  large/samples-gated, root-chmod ×2, no bare numpy python ×5); `tools/sync_plugin.py` then `--check` clean
  (deny-audit clean, identity scan == allowlist); `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2893); `provenance_gate(pin, pin)` JSON diff empty ×3; `/verify`
  drove: front door prompt (6 panels, 5.3 s) → edit (rc 0, stamps `["PROOF-ONLY, NOT-DELIVERABLE"]`,
  descends, 422/2,680/118, `rvt_validate` ok 0 errors / 1 warning) → foreign edit (user-base, rc 0) → 2025
  chain (descends from G_ABPD_2025, 925/2,391/4) → `route run --output rvt --rvt X --prompt "move PP-2 …"`
  (rc 0, delivered) → bare unzip + system Python 3.11 `go author --prompt` READY 2.27 s exit 0 then `go author
  --rvt out/j1/prompt_room.rvt --edit …` READY 1.2 s exit 0, `descends-from-pinned-genesis`, ledgered against
  the *bundled* `assets/genesis/G_ABPD.rvt`, the authorship line in its MANIFEST.md.
* Shipped vs staged: ships with the merge; manifest wording only — no bytes of any output, base or asset
  change, no viewer claim, no probe batch.

## eng #434 — 2026-08-10 — ONE engine reader for the History[0] episode GUID (`rvt.stream_encoders.history_head_guid`); the identity scrub receives the same bytes

Stream `eng434` (engineer session for #434, P2/XS, PG6 engine hygiene; the tidy-up eng #284 F8 and eng #406
F15 above deferred while `tools/rvt_job.py` was held). Territory used: `src/rvt/stream_encoders.py` (the new
function, next to `decode_history`), `src/rvt/frontdoor/census.py` / `tools/rvt_job.py` /
`src/rvt/mep/views_spaces.py` (import swaps only), one new test `tests/test_history_head_guid.py` + its shard
drop-in `tests/ci_shard.d/434-history-head-guid.txt`, this section; regenerated mirrors (`plugin/lib/src/rvt/
{stream_encoders,frontdoor/census,mep/views_spaces}.py`, `plugin/lib/tools/rvt_job.py`, the three
`plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`). No hot file, no NO-GO file, no asset touched.

### Result in one screen

| | before (`main@af15f6c`) | after (this branch) |
|---|---|---|
| definitions of "History entry[0] GUID of a file" | 3: `census.history_head_guid` (`inflate_global_stream` + `.lower()`), `rvt_job.history_head_guid` (`inflate_global_stream`, un-lowered, fed to `scrub_identity`), inline in `views_spaces.commit_elements` (`f.inflate` scan, un-lowered) | 1: `rvt.stream_encoders.history_head_guid(path_or_doc)`; census re-exports it (`C.history_head_guid is SE.history_head_guid`), `rvt_job` imports it in `identity_gate` / `create_from_spec` / `_cmd_edit`, `views_spaces` calls it — `grep -rn "def history_head_guid" src tools` → `src/rvt/stream_encoders.py:250` only |
| the casing rule | implicit ×3 (one `.lower()`, two not) | documented once: the canonical lowercase `str(uuid.UUID)` form `decode_history` already yields — measured: all three old copies returned the identical lowercase string on all three pins (the `.lower()` was a no-op), so nothing any caller receives changes |
| what `own_basic_file_info(document_guid=…)` receives in an `rvt_job edit` of each pin (spy) | `'34447475-…cdbe1'` / `'527cedc9-…59e3'` / `'badabcab-…e7ca'` (2026/2025/2024) | the same three strings, same type, same case (asserted before == after by the snapshot script; pinned going forward by `test_edit_hands_the_identity_scrub_history0_verbatim[year]`) |
| `identity_gate(pin)` JSON ×3, `provenance_gate(pin, pin)` JSON ×3 (`sort_keys`; `elapsed_s` and the checkout's absolute `base` path aside) | — | `diff` empty on all six |
| front door `author --prompt "an electrical room with 6 panels"` → `build.validation.combined.identity` | `{history_head_guid 34447475-…, identity{author rvt-writer, unique_document_guid 34447475-…, …}, issues [], PASS}` | byte-identical JSON; the output's `BasicFileInfo` stream bytes identical (1,911 B) |
| front door `author --rvt X --edit "move PP-1 to 3,1,4.66"` (same X both sides) → `edit.gates.identity` | PASS, GUID `34447475-…` | byte-identical JSON **and the whole edited `.rvt` sha256-identical** before/after |

### What was built

* `rvt.stream_encoders.history_head_guid(path_or_doc) -> Optional[str]` — a `.rvt`/`.rfa` path or an
  already-open `rvt.container.RvtDocument`; `Global/History` → `inflate_global_stream` → `decode_history` →
  `entries[0][0]`; None when absent/empty/unreadable, never raises. Docstring carries the one casing rule and
  why the value exists (BFI Unique Document GUID must == History entry[0]; minimal commits record no new
  episode, so the scrub is handed this GUID instead of a fresh one).
* `census.py`: local def deleted; `lineage()` imports the engine reader in its existing lazy try-block, and a
  five-line module `__getattr__` keeps `census.history_head_guid` (in `__all__`, used by
  `test_status_gate::test_a_relative_…`) resolving to the SAME object without a bare `import
  rvt.frontdoor.census` loading the codec/container modules (measured: a module-level import cost +33 ms and
  +8 modules incl. `olefile` on a bare census import; now 46 ms / 9 `rvt` modules / no olefile == `main`). The
  "corroborating only" note moved to a two-line comment on the `history_head_guid_matches_pin` evidence key.
  `rvt_job.py`: local def deleted (a three-line section comment keeps the why), three function-local imports
  (the file's lazy-import idiom; `identity_gate` reads it from the already-open document, one `open_rvt` fewer).
  `views_spaces.py`: the inline try/decode block → one call.
* `/simplify` (four angles) applied: duck-typed `.raw()` for the open-doc arm, docstring cut to contract + casing
  rule (no caller changelog), the census laziness above, the brittle `decode_history(` source-grep dropped from
  the test. Skipped, with reason: hoisting `_pinned` / the `rvt_job` loader into `tests/conftest.py` (third copy
  now — touches `test_status_gate.py` / `test_job.py`, outside this territory; filed as #451), the consumer-side
  `h0.lower()` in `identity_gate` (harmless; "touch nothing else" in `rvt_job.py`), caching the pin's History[0]
  next to `_PINS` (pre-existing ~4 ms per `lineage()` call, not a regression).
* `tests/test_history_head_guid.py` (7 tests, 2.2 s, fresh-clone safe — tracked pins only): per certified year
  the engine value == an independent decode (`container.inflate` + `content.parse_history().document_guid`) ==
  canonical lowercase == the pin's BFI GUID, census re-export is the same object, open-doc form agrees, absent /
  non-container → None; no former call site defines or re-derives it; and a real `rvt_job edit` of each pin with
  a spy on `rvt.identity.own_basic_file_info` receives `document_guid == History[0]` verbatim, manifest
  `base.history_head_guid` and `gates.identity` coherent + PASS.

### Findings

* **F18 — the "casing caveat" was latent, not live.** `decode_history` stringifies `uuid.UUID`, whose `str()`
  is always lowercase, so `census`'s `.lower()` never changed a byte and `rvt_job`'s un-lowered value was already
  canonical. The consolidation therefore changes no output byte anywhere; the rule is now written down where the
  value is made so a future reader that upper-cases (e.g. a BFI-side GUID) cannot drift in unnoticed.
* **F19 — `provenance_gate(pin, pin)` differs run-to-run only in `elapsed_s` and the absolute `base` path** (as
  eng #406 noted); the prompt route's whole-file sha differs run-to-run for reasons outside this stream (famgen
  determinism, #9) while its `BasicFileInfo` bytes and identity gate are stable — the edit route is fully
  byte-reproducible on the same input.

### How to run

```bash
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_history_head_guid.py tests/test_status_gate.py tests/test_job.py -q -rs
grep -rn "def history_head_guid" src tools            # -> src/rvt/stream_encoders.py only
.venv/bin/python -c "import sys;sys.path.insert(0,'src');from rvt.stream_encoders import history_head_guid as h;print(h('plugin/assets/genesis/G_ABPD.rvt'))"
```

### BRANCH STATE (eng #434)

* Branch `cam/434-history-head-guid` from `main@af15f6c` (after #443 landed in `tools/rvt_job.py`); PR closes #434.
* Files: `src/rvt/stream_encoders.py` (+`history_head_guid`), `src/rvt/frontdoor/census.py`, `tools/rvt_job.py`,
  `src/rvt/mep/views_spaces.py` (import swaps), `tests/test_history_head_guid.py` (new, 7 tests),
  `tests/ci_shard.d/434-history-head-guid.txt`, this section; regenerated mirrors `plugin/lib/src/rvt/{stream_encoders,
  frontdoor/census,mep/views_spaces}.py`, `plugin/lib/tools/rvt_job.py`, `plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`.
  No hot file, no NO-GO file, no asset, no pinned-base byte touched. Follow-up filed: #451 (test helpers → conftest).
* Gates: `tests/test_history_head_guid.py` **7 passed** (2.6 s); neighbours `test_status_gate test_job test_stream_encoders
  test_mep_views_spaces` **36 passed / 108 skipped** (`RVT_SKIP_LARGE=1`; skips = samples-gated ×107 + the `@slow` 6-panel
  e2e; `test_lineage_api` green); the WHOLE merged CI shard (`shard_list.py --print`, 73 files incl. the new drop-in)
  **1512 passed / 134 skipped / 3 xfailed** in 7 m 04 s on the final tree (an earlier run on the pre-`/simplify` tree: same
  counts); `tools/sync_plugin.py` then `--check` clean (deny-audit clean, identity scan == allowlist, assets verified);
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (2901); `grep -rn "def
  history_head_guid" src tools` → `src/rvt/stream_encoders.py:250` only; before/after snapshot (worktree of `main` vs this
  branch, same venv): History[0] of the three pins identical by all readers, `own_basic_file_info(document_guid=)` kwarg
  identical ×3, `identity_gate(pin)` JSON identical ×3, `provenance_gate(pin, pin)` JSON identical ×3 (`elapsed_s`/abs
  path aside); bare `import rvt.frontdoor.census` 46 ms / 9 rvt modules / no olefile (== main). `/verify` drove: front
  door prompt (6 panels; `build.validation.combined.identity` PASS, GUID `34447475-…`, JSON byte-identical to main's, output
  `BasicFileInfo` bytes identical) → edit of it (rc 0, `ok true`, stamps `["PROOF-ONLY, NOT-DELIVERABLE"]`,
  `gates.identity` PASS + JSON identical to main's, **edited `.rvt` sha256-identical to main's from the same input**,
  descends-from-pinned-genesis 422/2,680/118, `rvt_validate` ok 0 errors / 1 warning = the standing DataStorage ES gap) →
  edit of the 2025 pin (`--rvt G_ABPD_2025.rvt --edit "set level 694 elevation to 12"`: rc 0, identity PASS, format 2025,
  GUID `527cedc9-…`, validation PASS 0) → bare unzip + system Python 3.11.15: `go author --prompt …` **READY** exit 0 5.7 s,
  then `go author --rvt out/j4/prompt_room.rvt --edit "move PP-1 …"` **READY** exit 0 2.2 s, identity PASS,
  descends-from-pinned-genesis, ledgered against the bundled `assets/genesis/G_ABPD.rvt`.
* Shipped vs staged: ships with the merge; a refactor with zero output-byte change — no viewer claim, no probe batch.

## eng #451 — 2026-08-10 — the pin/loader test helpers live ONCE in `tests/conftest.py`; `dir(census)` lists the lazy re-export; `history_head_guid` takes a path or an `RvtDocument`, nothing else

Stream `eng451` (engineer session for #451, P2/XS, PG7 test hygiene + the two review nits of PR #454 parked on
#451). Territory used: `tests/conftest.py`, `tests/test_status_gate.py` / `tests/test_job.py` /
`tests/test_history_head_guid.py` (helper swap only), `src/rvt/frontdoor/census.py` (a module `__dir__` only),
`src/rvt/stream_encoders.py` (`history_head_guid` argument check + docstring only), this section; regenerated
mirrors `plugin/lib/src/rvt/{frontdoor/census,stream_encoders}.py`. No hot file, no NO-GO file, no asset touched.

### What was built

* `tests/conftest.py` gains the ONE copy of three helpers that had grown to three copies (#434 `/simplify`
  reuse finding): `CERTIFIED_YEARS` (release years whose pinned composed base is certified — the parametrize
  axis), `pinned_base(year)` (the certified pin's path or a clean `pytest.skip`, with `test_status_gate`'s
  fuller skip wording: bundle absent / `$RVT_GENESIS_BASE`·`--base` override in force), `load_tool(name)`
  (`tools/<name>.py` executed as module `name`, registered in `sys.modules[name]` — `tools/ifc_intent.py` does
  `import rvt_job`, and a test driving it wants the module it patched) and the module-scoped fixture `job` =
  `load_tool("rvt_job")` — named `job` because that is the parameter all three files already request, so no test
  body changes; module scope kept on purpose (a fresh `rvt_job` per test file, exactly as before, so one file's
  patches never reach the next).  Cost of the new conftest-time `import rvt.frontdoor.base`: +5 modules / 13 ms,
  no olefile (measured; conftest already imports `rvt.schema` + `rvt.ifc._fallback`); `CERTIFIED_YEARS` 1 ms
  (pin JSON, no hashing).
* The three files import them (`from conftest import CERTIFIED_YEARS, load_tool, pinned_base`; call sites renamed
  `_pinned(` → `pinned_base(` ×21, `_load_tool(` → `load_tool(` ×2 — mechanical, no assertion changed); their local
  `_pinned` / `CERTIFIED_YEARS` / `_load_tool` / `_load_job` / `job` definitions and the now-unused
  `importlib`/`sys`/`base` imports are gone.  `grep -rn 'def _pinned\|_pinned(\|spec_from_file_location("rvt_job"'
  tests` → **nothing** (conftest spells them `pinned_base` / `load_tool(name)`); `grep -rn "def job(" tests` →
  `conftest.py` + `test_gates_shared_walk.py` (a different loader on purpose: `rvt.frontdoor.edit.load_job_module`,
  outside this territory — see follow-up below).
* `census.__dir__()` returns `sorted(set(globals()) | set(__all__))`, so `dir(census)` lists `history_head_guid`
  (lazy `__getattr__` re-export since #454) again; bare `import rvt.frontdoor.census` still 64 new modules, no
  `olefile` / `rvt.container` / `rvt.stream_encoders` (== `main@a1927c8`, measured same interpreter).
* `stream_encoders.history_head_guid(path_or_doc)`: the duck-typed `hasattr(x, "raw")` arm is replaced by an
  explicit contract — `str`/`bytes`/`os.PathLike` → open the container; `rvt.container.RvtDocument` → read the
  open document; **anything else raises `TypeError`** (decided: a plain binary file object or a `mutate.Document`
  is a caller bug and must not read as "no History" = `None`; the old duck-typing matched `io.BufferedReader.raw`
  and was swallowed to `None`).  Path / document behaviour unchanged: absent file, non-container, empty or
  unreadable stream → `None`, never raises; the three pins return the same GUIDs by both arms
  (`34447475-…cdbe1` / `527cedc9-…59e3` / `badabcab-…e7ca`, == eng #434's table; `test_one_reader_one_casing[year]`).
  The `RvtDocument` name is a `TYPE_CHECKING`-only import (annotation), the runtime `isinstance` import is local
  to the non-path arm, so pure-payload importers of the codec module still never load olefile.  All six
  engine/tool callers pass a real path or an `RvtDocument`.
* `test_history_head_guid.py` gains ONE unparametrized test, `test_argument_contract_and_census_dir` (file object /
  `None` → `TypeError`; `"history_head_guid" in dir(C)`; same object as the engine's) — pin-independent, so it
  runs on a bundle-less clone too (a `/simplify` altitude finding: the first draft rode inside the year-parametrized
  test).  Every pre-existing test id is unchanged.
* `/simplify` (four angles) applied: aliases dropped for real call-site renames (greppable), the false "engine code
  imports rvt_job" rationale corrected to `tools/ifc_intent.py`, the "ONE loader" over-claim dropped (20+ files
  still hand-roll `spec_from_file_location` for other tools), the contract asserts split out, docstring trimmed.
  Skipped, with reason: `job` → `rvt.frontdoor.edit.load_job_module()` (reuse + altitude both asked; it is
  process-cached under `_frontdoor_rvt_job`, so tests would share ONE module object across files and with the
  `--rvt` route — a semantics change for a helper-move PR; filed as a follow-up), `functools.lru_cache` on
  `pinned_base` (would mask a mid-run `$RVT_GENESIS_BASE` monkeypatch for ~20 × few-ms saved), `job` session
  scope (same isolation argument), a `raw()`-Protocol instead of the nominal `RvtDocument` check so
  `rvt.validate.WalkedFile` also passes (validate.py is another engineer's this wave; no caller needs it today).

### How to run

```bash
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_history_head_guid.py tests/test_status_gate.py tests/test_job.py -q -rs
.venv/bin/python -c "import sys;sys.path.insert(0,'src');import rvt.frontdoor.census as c;print('history_head_guid' in dir(c), c.history_head_guid is __import__('rvt.stream_encoders',fromlist=['x']).history_head_guid)"   # True True
```

### BRANCH STATE (eng #451)

* Branch `cam/451-tests-conftest` from `main@a1927c8` (after #454/#459); PR closes #451.
* Files: `tests/conftest.py`, `tests/test_status_gate.py`, `tests/test_job.py`, `tests/test_history_head_guid.py`,
  `src/rvt/frontdoor/census.py`, `src/rvt/stream_encoders.py`, this section; regenerated mirrors
  `plugin/lib/src/rvt/frontdoor/census.py`, `plugin/lib/src/rvt/stream_encoders.py`. No new test file → no shard drop-in.
* Gates: collected ids — before 47 (`test_history_head_guid` 7, `test_status_gate` 34, `test_job` 6; `pytest --collect-only
  -q | tail -1` each), after the helper move 47 with a sorted-id `diff` empty, final tree 48 = the same 47 + the one new
  `test_argument_contract_and_census_dir`; the three files **42 passed / 5 skipped** before, **43 passed / 5 skipped** after
  (`RVT_SKIP_LARGE=1`; skips unchanged = famgen catalog absent ×1, `samples/rst…` ×4); the WHOLE merged CI shard
  (`shard_list.py --print`, 75 files) **1592 passed / 134 skipped / 3 xfailed** in 5 m 49 s on the final tree (pre-`/simplify`
  tree: 1591 / 134 / 3 — the +1 is the new test); `tools/sync_plugin.py` then `--check` clean (deny-audit clean, identity
  scan == allowlist, assets verified); `validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (2908);
  bare `import rvt.frontdoor.census` 64 new modules, no olefile/container/stream_encoders (== main). `/verify` drove:
  `history_head_guid` on the three pins by path and by open document (equal, GUIDs above), a `BufferedReader` →
  `TypeError: history_head_guid() takes a .rvt/.rfa path or an open rvt.container.RvtDocument, not 'BufferedReader'`,
  an absent path → `None`; front door `author --prompt "an electrical room with 6 panels"` rc 0, `PROOF-ONLY (self-checks
  PASS)`, `build.validation.combined.identity` PASS with `history_head_guid 34447475-…` == BFI GUID, `rvt_validate` VALID
  0 errors; front door `--rvt G_ABPD_2025.rvt --edit "set level 694 elevation to 12"` rc 0, `ok true`, output release 2025,
  stamps `["PROOF-ONLY, NOT-DELIVERABLE"]`, job manifest `base.history_head_guid 527cedc9-…` == identity gate PASS GUID,
  edited file VALID 0 errors; bare unzip + system Python 3.11.15 `go author --prompt …` `ready true` in 4.8 s, identity
  PASS `34447475-…`, `base_kind pinned-composed-genesis`.
* Follow-up filed: #470 (Refs #451) — conftest `job` could delegate to `rvt.frontdoor.edit.load_job_module()` so tests and the
  `--rvt` route share one `rvt_job` module object (and `test_gates_shared_walk` / `test_edit_own_release` drop their own
  fixture) — needs a decision on per-file isolation vs one shared module, hence not folded into this XS.
* Shipped vs staged: ships with the merge; test refactor + one argument check, zero output-byte change — no viewer claim.

## eng #470 — 2026-08-10 — ONE `rvt_job` module object per pytest process: the conftest `job` fixture IS `rvt.frontdoor.edit.load_job_module()`, aliased as `sys.modules["rvt_job"]`

Stream `eng470` (engineer session for #470, P2/XS, PG7 test hygiene; the follow-up #451 filed). Territory used:
`tests/conftest.py` (the `job` fixture + a `load_tool` guard), `tests/test_gates_shared_walk.py` (its local `job`
override deleted — it was part of the decision), this section (a `tests/test_manipulate.py` hunk was carried
briefly and dropped — it lands as #484, see below). `src/rvt/frontdoor/edit.py` was READ only; the one
change it could use is a patch below, not applied. No `src/` `tools/` `skills/` `plugin/` file touched → no mirror,
no shard drop-in (no new test file). Decision: **delegate** (the issue's first option), not "document the split".

### Result in one screen

| measured in ONE pytest process over the four `job` consumers (`test_status_gate`, `test_job`, `test_history_head_guid`, `test_gates_shared_walk`) | `main@2767197` | this branch |
|---|---|---|
| distinct live `rvt_job` module objects by the end (probe plugin, both file orders) | **4** (`rvt_job` ×3 fresh per file + the engine's `_frontdoor_rvt_job`) | **1** |
| `sys.modules["rvt_job"]` (what `tools/ifc_intent.py`'s `import rvt_job` = the prompt/IFC routes' identity + status gates gets) | whichever test file loaded last — it stays registered after that file's teardown | the engine's object, `is rvt.frontdoor.edit._JOB` |
| state at every file boundary: `G3_CLEARED` / `OPT.errors` / `_census_mod` patched? / `_RUN` | `False` / `{}` / no / defaults except `manifest` = last one `main()` wrote | identical: `False` / `{}` / no / same `manifest` residue |
| the four files, forward and reversed order (`RVT_SKIP_LARGE=1 -rs`) | 55 passed / 5 skipped, 55 / 5 | 55 / 5, 55 / 5 (same five skips: famgen catalog ×1, `samples/rst…` ×4) |
| `pytest --collect-only -q` ids of the four files | 60 | 60, `diff` empty |
| `--setup-plan` | `SETUP M job` ×4 / `TEARDOWN M job` ×4 (a fresh exec per file) | `SETUP S job` ×1 / `TEARDOWN S job` ×1 (session scope — see below) |
| `grep -rn "def job(" tests` | `conftest.py`, `test_gates_shared_walk.py` | `conftest.py` only |
| WHOLE merged CI shard (78 files, `RVT_SKIP_LARGE=1`) | 1 failed (`test_manipulate`'s `from test_job import _load_job`, red since #471 = #476) / 1617 passed / 139 skipped / 3 xfailed | **1618 passed / 139 skipped / 3 xfailed** (5 m 49 s) measured with #476's three-line fix in the tree; that fix ships as #484, not here |

### What was built

* `tests/conftest.py::job` now returns `rvt.frontdoor.edit.load_job_module()` — the process-cached module the `--rvt`
  route (`edit.run_edit`), the router and `tools/rvt_edit.py` drive — and registers that same object as
  `sys.modules["rvt_job"]`, so a `monkeypatch.setattr(job, …)` in a test reaches BOTH the copy the engine calls and the
  copy `tools/ifc_intent.py` imports by name (before: three objects could disagree; `test_status_gate.py:380`'s
  `monkeypatch.setitem(sys.modules, "rvt_job", job)` existed only to paper over that and is now a same-value no-op —
  left untouched: outside this wave's territory, listed in #477's DONE). `load_tool(name)` stays for the other tools
  (`genesis_census`, `provenance`), fresh-per-call as before, and now **refuses** `"rvt_job"` (`ValueError` naming
  the fixture) so a future test cannot silently re-create the N-object world (`/simplify` altitude finding: the
  invariant was prose-only).
* Scope is `session`, decided: the OBJECT is process-wide whatever the scope says (the engine caches it in
  `edit._JOB`), so `session` is the honest declaration and `--setup-plan` now shows one `SETUP S job` per run. The
  first draft kept `module` "to re-assert the alias per file in case a file in between dropped it"; `/simplify`
  (simplification + altitude) called that a healer instinct — nothing in the suite drops the key except a
  `monkeypatch.setitem` that restores it, and a violation should trip, not be silently repaired — so it went.
  Test ids do not depend on fixture scope (60 = 60, `diff` empty).
* `tests/test_gates_shared_walk.py` loses its own module-scoped `job` (it already was `load_job_module()`; now that is
  what conftest hands every file). `tests/test_edit_own_release.py` has no `job` fixture — its one inline
  `load_job_module()` call (test 3) already yields the same object; nothing to swap, file untouched.
* **A fifth loader, and `main` was red on it** (found by the whole-shard run, reproduced on pristine `main@2767197`):
  `tests/test_manipulate.py::test_job_set_param_op_lands_an_elementid_row_via_holder` did `from test_job import
  _load_job` — the per-file loader #471 deleted from `test_job.py` hours earlier — so it has raised `ImportError`
  on `main` since #471 (`1 failed, 13 passed, 5 skipped` for the file; the shard `1 failed / 1617 / 139 / 3 xfailed`).
  The fix (the test requests the conftest `job` fixture like every other consumer; no assertion touched, ids
  identical; `14 passed / 5 skipped`) was first carried here, then **dropped from this PR on the tech lead's call**:
  it is tracked as #476 and lands separately as hotfix PR #484 (the identical three lines), which merges first —
  two PRs carrying one hunk only manufacture a conflict. This branch therefore leaves `tests/test_manipulate.py`
  as on `main`; the shard is green once #484 is in (the tech lead's sandbox merges `origin/main` into this head).

### Why sharing one module across test files is safe here (measured, then read)

The reason #451 kept a fresh module per file was "one file's patches never reach the next". Inventory of what could
carry over, `tools/rvt_job.py@2767197`:

* Module-level bindings (AST walk): constants (`HERE ROOT TOOL_VERSION FT_PER_M SAMPLES_DIR EX_* G3_COUNSEL G3_CLEARED
  OP_MANIPULATE OP_CREATE`) + exactly two mutable holders, `_RUN` (dict) and `OPT` (`.errors` dict). No `global`
  statement anywhere → nothing rebinds a module name at run time.
* Every test-side mutation of the module in `tests/` goes through `monkeypatch` (`setattr(job, "G3_CLEARED" |
  "_census_mod", …)`, `setitem(job.OPT.errors, …)`, `setitem(sys.modules, "rvt_job", …)`) — function-scoped, undone
  before the next test, let alone the next file; `grep -rnE '\bjob\.[A-Za-z_]+(\[[^]]*\])? *(=[^=]|\.append|\.update|\.clear|\.pop)' tests` → nothing.
* `_RUN`: reset at the top of every `main()` (#443) and READ only downstream of that reset inside the same call
  (`_record_manifest` ← `write_manifest`/`_write_stub_manifest` ← `run_gates`/`create_from_spec`/`_dispatch` ← `main`;
  no test and no engine caller reaches a manifest writer except through `main()` — `grep` of `run_gates|create_from_spec|
  write_manifest|_write_stub_manifest` outside `rvt_job.py` finds only `rvt.frontdoor.manifest.write_manifest`, a
  different function). The `manifest` residue the probe shows at file boundaries is therefore dead until overwritten —
  and it was already there on `main` in the engine copy.
* `OPT.errors`: written only when a lazy loader genuinely fails (environment-deterministic — a fresh module would record
  the same failure on its first call) or by `monkeypatch.setitem` (undone).
* Import-time behaviour of `rvt_job.py`: two `sys.path.insert`s and constants; every `rvt.*` import is lazy inside
  functions, so "first exec inside a non-2026 release context" cannot snapshot framing (cf. #455) — and the module now
  executes exactly once per process anyway.
* Measured with a throwaway `-p jobprobe` plugin (scratch, not committed: at each file's last teardown it records
  `id()`/`__name__`/`G3_CLEARED`/`OPT.errors`/`_RUN`/census-patched for `sys.modules["rvt_job"]`,
  `sys.modules["_frontdoor_rvt_job"]` and `edit._JOB`): table above, forward and reversed file order, before and after.

### Finding (product side, outside this territory) + patch

The same split exists in the PRODUCT process, not only under pytest: one interpreter that runs an `--rvt` edit job and a
prompt/IFC job (`FD.author(rvt=…, edit=…)` then `FD.author(prompt=…)`, i.e. any plugin session doing two jobs, or a
router chain) ends with **two** executed copies of `tools/rvt_job.py` — `_frontdoor_rvt_job` (from
`edit.load_job_module`) and `rvt_job` (from `tools/ifc_intent.py`'s `sys.path.insert(0, HERE); import rvt_job`);
a prompt-only process has one (`rvt_job`). Measured: `sorted(k for k,m in sys.modules.items() if m.__file__…endswith
("rvt_job.py"))` → `['_frontdoor_rvt_job', 'rvt_job']`, 2 distinct ids, both jobs `ok`. Harmless today (neither copy's
state is consulted by the other; `G3_CLEARED` is a constant), but it is one more exec of a 1.5 kloc module per mixed
session and the day `G3_CLEARED` or a census override becomes a runtime switch the two doors could disagree. The
fix is a few lines in `src/rvt/frontdoor/edit.py::load_job_module` (READ-only for eng #470 — hence a patch, filed as
a follow-up task, not applied):

```diff
@@ def load_job_module():
     global _JOB
     if _JOB is not None:
         return _JOB
+    already = sys.modules.get("rvt_job")            # tools/ifc_intent.py imported it by name first (a prompt/IFC job ran)
+    if already is not None and os.path.basename(getattr(already, "__file__", "") or "") == "rvt_job.py":
+        _JOB = sys.modules["_frontdoor_rvt_job"] = already
+        return already
     cands = [os.path.join(repo_root(), "tools", "rvt_job.py")]
@@
                 mod = importlib.util.module_from_spec(spec)
                 sys.modules[spec.name] = mod
+                sys.modules.setdefault("rvt_job", mod)  # ...and a later `import rvt_job` (ifc_intent) reuses THIS object
                 spec.loader.exec_module(mod)
```
With that in the engine, conftest's own `sys.modules["rvt_job"] = mod` line **must go** (or become
`assert sys.modules.get("rvt_job", mod) is mod`) and so must `test_status_gate.py:380`'s same-value `setitem` —
otherwise the test bootstrap silently heals any regression of the engine's one-object invariant (both listed in
#477's DONE). The better engine shape, also noted on #477: `tools/ifc_intent.py` goes through `load_job_module()`
instead of a bare `sys.path` import, so there is one loader and one name rather than one loader answering to two.

### How to run

```bash
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_status_gate.py tests/test_job.py tests/test_history_head_guid.py tests/test_gates_shared_walk.py -q -rs
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest --setup-plan tests/test_gates_shared_walk.py | grep ' job'      # SETUP    M job (from conftest)
.venv/bin/python -c "import sys;sys.path[:0]=['src','tests'];import conftest,rvt.frontdoor.edit as E;m=conftest.job.__wrapped__();print(m is E.load_job_module() is sys.modules['rvt_job'] is sys.modules['_frontdoor_rvt_job'])"   # True
```

### BRANCH STATE (eng #470)

* Branch `cam/470-one-job-loader` from `main@2767197` (right after #471); PR closes #470.
* Files: `tests/conftest.py`, `tests/test_gates_shared_walk.py`, this section (the `tests/test_manipulate.py` hunk of the
  first push, `7161bad`, was dropped in the second commit — it ships as #484 for #476). No `src/` `tools/` `skills/`
  `plugin/` file, no mirror, no asset, no hot file, no new test file → no shard drop-in.
* Gates: collected ids of the four `job` consumers 60 = 60 (`diff` empty); the four files **55 passed / 5 skipped** on
  `main` and on the branch, forward and reversed order (`RVT_SKIP_LARGE=1 -rs`; skips famgen catalog ×1, `samples/rst…`
  ×4); `--setup-plan` `SETUP S job` ×1 (was `M` ×4); probe: live `rvt_job` objects per process 4 → **1**,
  `sys.modules["rvt_job"] is edit._JOB` after every file, boundary state identical before/after; the WHOLE merged CI shard
  (`shard_list.py --print`, 78 files) **1618 passed / 139 skipped / 3 xfailed** in 5 m 49 s with #476's fix in the tree
  (without it, i.e. this branch alone on `main@2767197`: exactly the one pre-existing `test_manipulate` ImportError /
  1617 / 139 / 3 — green again once #484 is on `main`); `tools/sync_plugin.py --check` →
  in sync (nothing under `src/`/`tools/` touched); `check_portable_paths.py` ok (2911). `/simplify` four angles applied
  (docstring cut, `session` scope, `load_tool("rvt_job")` guard, "must go" wording for #477); `/verify` drove
  `frontdoor.py author --prompt "an electrical room with 6 panels"` (rc 0, `ok true`, status_gate `PROOF-ONLY,
  NOT-DELIVERABLE` / `pinned-composed-genesis`, identity PASS, `rvt_validate` VALID 0 errors / 1 warning) and
  `frontdoor.py author --rvt G_ABPD_2025.rvt --edit "set level 694 elevation to 12"` (rc 0, `ok true`, output release
  2025, job gates structural/validation/identity PASS, VALID 0 errors) — the two routes the two loaders serve.
* Follow-up filed: **#477** (Refs #470, `ready` `P2` `area:frontdoor` `good-first-pick`) — one product process running an
  edit job and a prompt/IFC job holds ONE `rvt_job` copy (`load_job_module()` ≡ `sys.modules["rvt_job"]`; preferably
  `ifc_intent` goes through the engine loader), then the conftest alias line and `test_status_gate.py:380` are deleted.
* Shipped vs staged: ships with the merge; test plumbing only, zero output-byte change — no viewer claim.

## eng #477 — 2026-08-10 — ONE executed copy of `tools/rvt_job.py` per PRODUCT process: `load_job_module()` registers `rvt_job`, and `tools/ifc_intent.py`'s gates go through it

Stream `eng477` (engineer session for #477, P2/XS, PG3/PG7; Refs #470, whose "Finding (product side) + patch"
above is the charter). Decision: the issue's **preferred** shape, not the fallback patch — the engine loader owns
the one name and `tools/ifc_intent.py` becomes a caller of it; no `setdefault`/adopt of a pre-existing
`sys.modules["rvt_job"]` (with no by-name importer left, such an entry can only be a regression, and adopting it
would bless exactly what the new test exists to catch — `/simplify` altitude agreed). Territory used, all inside
the issue's: `src/rvt/frontdoor/edit.py` (`load_job_module` only: spec name `_frontdoor_rvt_job` → `rvt_job`,
docstring), `tools/ifc_intent.py` (the two `sys.path.insert(0, HERE); import rvt_job` sites → one 4-line
`_job_runner()` = lazy `rvt.frontdoor.edit.load_job_module()`; `_jdump`/#495 untouched) + its two regenerated
mirrors, `tests/conftest.py` (the `job` fixture's alias line deleted, docstring), `tests/test_status_gate.py`
(line 380's same-value `setitem` deleted), NEW `tests/test_one_job_module.py` + `tests/ci_shard.d/477-one-job-module.txt`,
this section. Rebased on `main@4cc81dd` (after #495).

### Result in one screen

| the issue's probe — ONE process, `FD.author(rvt=G_ABPD_2025, edit=…)` + `FD.author(prompt="an electrical room with 6 panels")`, both orders | `main@4cc81dd` | this branch |
|---|---|---|
| live modules whose `__file__` ends in `rvt_job.py` (edit-first / prompt-first) | `['_frontdoor_rvt_job', 'rvt_job']`, 2 ids / same | **`['rvt_job']`, 1** / same |
| `edit.load_job_module() is sys.modules["rvt_job"]` | `False` / `False` | **`True` / `True`** |
| both jobs `ok` | True, True | True, True |
| front-door manifests, `tools/frontdoor.py author` — 6-panel `--prompt` / `--rvt G_ABPD_2025 --edit "set level 694 elevation to 12"` / `--ifc inputs/ifc/electrical-room-2500a.ifc` (main run twice = noise class: content GUIDs, sha256/md5, `*.seconds`/gate timings, `generated_at`) | 2973 / 164 / 4482 flattened keys | **0 / 0 / 0 diffs outside the noise class**; the edited `.rvt` md5-identical (`d8c892e4…`); status_gate `PROOF-ONLY, NOT-DELIVERABLE`/`pinned-composed-genesis` ×3, identity `PASS`, all four outputs `rvt_validate` VALID 0 errors |
| `python -X importtime -c "import rvt.frontdoor"` | 89 modules, no `rvt_job`, no `rvt.frontdoor.edit`; 50.9 ms | 89 modules, same absences (nothing eager added); 43.3 ms (noise) |
| bare unzip of `tekton-plugin.zip`, system `python3` 3.11 (no numpy), `go author --prompt "…6 panels"` then `go edit assets/genesis/G_ABPD_2025.rvt set-level --id 694 --elevation-ft 12` | READY / rc 0 / stderr **0 B** / wall 5.54 s; rc 0 / gates structural+validation PASS / stderr 0 B / 0.67 s | READY / rc 0 / stderr **0 B** / 5.43 s; rc 0 / PASS / 0 B / 0.73 s (unchanged) |
| neighbour files (`test_edit_own_release test_status_gate test_stagelog test_router test_router_load_release test_router_release test_frontdoor test_job test_history_head_guid test_gates_shared_walk test_manipulate test_frontdoor_json_strict test_ifc_intent`, `RVT_SKIP_LARGE=1 -rs`) | 395 passed / 28 skipped | 395 / 28 for the same 14 files (+3 = the new file → 398 / 28) |
| WHOLE merged CI shard (`shard_list.py --print`, 83 files incl. the new one) | — | **1737 passed / 139 skipped / 3 xfailed**, rc 0, 7 m 28 s (re-run on the final post-`/simplify` tree: see BRANCH STATE) |
| new `tests/test_one_job_module.py` on `main` (copied in) vs here | 3 failed (`['_frontdoor_rvt_job','rvt_job']`, ids 2) | 3 passed, 4.1 s (two ~1.9 s subprocess probes + one 30 ms structural check) |

### What was built

* `rvt.frontdoor.edit.load_job_module()` executes `tools/rvt_job.py` under the ONE name `rvt_job` (was the private
  `_frontdoor_rvt_job`) and stays the process cache (`edit._JOB`). Nothing else about the loader changed: same
  candidates (`<repo_root>/tools/rvt_job.py`, then `$RVT_PLUGIN_ROOT/skills/tekton-native/scripts/rvt_job.py`), same
  ImportError. In the bundle `repo_root()` is `<plugin>/lib`, so `lib/tools/rvt_job.py` serves `go author --rvt … --edit`
  and `go edit` exactly as before (driven, table above).
* `tools/ifc_intent.py::identity_gate` / `status_gate` (the prompt + IFC routes' gates) obtain the module through
  `_job_runner()` → `load_job_module()` — imported lazily inside the helper like every other `rvt.*` use in that file, so a
  dev tool's `import ifc_intent` pays nothing extra at import and the front door (which already holds `rvt.frontdoor`)
  pays a `sys.modules` hit. Side effect removed, not added: the old sites pushed `tools/` onto `sys.path` once per gate
  call (a slow leak of duplicate entries); `rvt_job.py` still inserts its own `HERE`/`SRC` once at exec, so anything
  that relied on `tools/` being importable after a gate ran still finds it.
* Test side: conftest's `job` fixture is now just `load_job_module()` (the engine registers the name; the fixture no
  longer can mask a regression by aliasing), and `test_status_gate.py`'s census-unavailable test patches `job` directly —
  it IS the object `ifc_intent.status_gate` drives. `tests/test_one_job_module.py` pins (1) structure in-process:
  `job is load_job_module() is sys.modules["rvt_job"]`, `__name__ == "rvt_job"`, and `build.load_ifc_room_module()._job_runner() is job`;
  (2) behaviour per job ORDER in a fresh interpreter each (the cache is process-global, so only a subprocess can say who
  loaded first): edit-then-prompt and prompt-then-edit on the bundled pins (2025 edit input, famgen-free walls prompt on
  2026, `no_handoff=True`, `quiet=True`) → `names == ["rvt_job"]` and the loader's object is that entry. Shard drop-in
  `tests/ci_shard.d/477-one-job-module.txt`.
* `/simplify` (4 angles) applied: loader docstring no longer enumerates callers (rots); `_job_runner` docstring cut to why-lazy;
  test reuses `conftest.ROOT`, the all-pins level id 1351691 (as `test_edit_own_release`) instead of a 2025-only id, drops the
  derivable `ids` count and the retired-name changelog assert. Skipped with reason: hoisting `WALLS_PROMPT` into
  `conftest.py` (outside this issue's one-line conftest territory; cross-importing `test_status_gate` is the #476 smell) and
  dropping one parametrized order (the DONE names both; cost 1.9 s).

### Findings

* No second door remains in the product process: `grep` of `src/ tools/ tests/ plugin/skills/_shared/` finds no `import rvt_job`,
  no `_frontdoor_rvt_job`, no other by-path exec of `rvt_job.py`; `tools/rvt_edit.py` and the router already used the loader.
  (`python tools/rvt_job.py` as `__main__` is the classic script double-import and out of scope, as the issue says.)
* Same disease elsewhere, follow-up-shaped, NOT this PR: `rvt.frontdoor.build.load_ifc_room_module()` registers
  `tools/ifc_intent.py` as `_frontdoor_ifc_room` while dev tools `import ifc_intent` by name, and `src/rvt/famload_fix.py`
  carries a scan-all-aliases workaround for that split; and `tools/rvt_job.py` loads `spec_to_rvt`/`seed_audit`/`ifc_to_spec`
  under `_rvtjob_<name>` (eng #486's file this wave). Searched issues first (none); filed as **#507** (`Refs #477`, `ready` `P2` `area:frontdoor` `good-first-pick`).
* `/verify` probe, pre-existing and already tracked as **#127** (reproduced identically on the `main` unzip): bare-unzip
  `go author --ifc skills/tekton-author/examples/electrical-room-2500a.ifc` on system Python without numpy → rc 3,
  `FAILED (IFC intent failed: ImportError: numpy is required here (IFC placement / geometry resolution))`, stderr 0 B — the
  prompt and `--rvt` routes are READY on the same interpreter.

### How to run

```bash
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_one_job_module.py -q -rs          # 3 passed (~4 s)
.venv/bin/python - <<'PY'                                                                # the issue's probe, one process
import os, sys; sys.path.insert(0, "src"); import rvt.frontdoor as FD
FD.author(rvt="plugin/assets/genesis/G_ABPD_2025.rvt", edit="set level 694 elevation to 12", out="out/p477/e", no_handoff=True, quiet=True)
FD.author(prompt="an electrical room with 6 panels", out="out/p477/p", no_handoff=True, quiet=True)
import rvt.frontdoor.edit as E
print(sorted(k for k, m in sys.modules.items() if (getattr(m, "__file__", "") or "").endswith("rvt_job.py")), E.load_job_module() is sys.modules["rvt_job"])   # ['rvt_job'] True
PY
```

### BRANCH STATE (eng #477)

* Branch `cam/477-one-job-module` from `main@4cc81dd`; PR closes #477.
* Files: `src/rvt/frontdoor/edit.py`, `tools/ifc_intent.py`, mirrors `plugin/lib/src/rvt/frontdoor/edit.py` +
  `plugin/lib/tools/ifc_intent.py` + `plugin/skills/tekton-author/scripts/ifc_intent.py` (written by `tools/sync_plugin.py`,
  byte-identical to source), `tests/conftest.py`, `tests/test_status_gate.py`, NEW `tests/test_one_job_module.py`,
  NEW `tests/ci_shard.d/477-one-job-module.txt`, this section. No hot file, no asset, no `TRACKER.md`.
* Gates: `tools/sync_plugin.py` then `--check` → in sync (deny-audit clean, identity scan == allowlist, assets verified);
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok; new file 3 passed; neighbours
  395/28 = 395/28 (+3); whole merged shard 1737 passed / 139 skipped / 3 xfailed (7 m 28 s) and re-run on the final tree
  = **1737 / 139 / 3 xfailed** again (7 m 42 s); `/simplify` applied (above); `/verify` PASS — drove `frontdoor.py author` ×3 routes (rc 0, manifests
  = main outside noise, VALID 0 errors ×4), the bare-unzip `go author --prompt`, `go author --rvt … --edit`, `go edit`
  (READY / hard gates PASS / stderr 0 B each, wall unchanged) and `tools/ifc_intent.py --help` (imports clean).
* Shipped vs staged: ships with the merge; loader/name plumbing only, zero output-byte change (edited `.rvt` md5-identical,
  manifests identical outside noise) — no viewer claim, nothing staged.
* Follow-up filed: **#507** (Refs #477) — the same one-name cure for `tools/ifc_intent.py` (`_frontdoor_ifc_room` vs
  `import ifc_intent`, and `famload_fix`'s alias scan); `tools/rvt_job.py`'s `_rvtjob_<name>` loaders noted there.

## eng #507 — 2026-08-10 — ONE executed copy of `tools/ifc_intent.py` per process: `load_ifc_room_module()` registers (or adopts) `sys.modules["ifc_intent"]`, and `famload_fix` patches that one object by its one name

Stream `eng507` (engineer session for #507, P2/S, PG3/PG7; Refs #477, whose "Findings" bullet above is the charter).
Territory used, all inside the issue's: `src/rvt/frontdoor/build.py` — **`load_ifc_room_module` body only, a
tech-lead exception to the #498 fence on `build.py`, announced on #498** (no import/format/docstring churn outside
that function); `src/rvt/famload_fix.py` (the alias scan `_ifc_intent_modules()` deleted, its one caller reads
`sys.modules.get("ifc_intent")`, docstring); their two regenerated mirrors under `plugin/lib/`; NEW
`tests/test_one_ifc_module.py` + `tests/ci_shard.d/507-one-ifc-module.txt`; this section. `tools/ifc_intent.py`
untouched (no by-path self-import turned up; its `_jdump`/gate sites are #495/#509's). Based on `main@fdcbf12`.

Decision that differs from eng #477's on purpose: #477 could refuse to adopt a pre-existing `sys.modules["rvt_job"]`
because it removed the last by-name importer; here **some 20 files under `tools/` + `tests/` keep `import ifc_intent` by
name** (dev probes, bisect tools, two test modules — none on the product path, all legitimate) and the DONE says
*either order*, so the loader registers the name when it is first and **adopts the by-name copy when it is second**
(`mod = sys.modules.get("ifc_intent")` before exec). A failed exec pops the name again so a retry never adopts a
half-executed module. The product process (front door, `go`, router, `add_to_project`) never imports the name before
the loader, so for it nothing changed but the key: `_frontdoor_ifc_room` → `ifc_intent`.

### Result in one screen

| the issue's probe — ONE process, `build.load_ifc_room_module()` + `sys.path.insert(0, tools); import ifc_intent`, both orders | `main@fdcbf12` | this branch |
|---|---|---|
| live modules whose `__file__` ends in `ifc_intent.py` (loader-first / import-first) | `['_frontdoor_ifc_room', 'ifc_intent']`, 2 ids / same | **`['ifc_intent']`, 1** / same |
| `load_ifc_room_module() is sys.modules["ifc_intent"]` | `False` / `False` | **`True` / `True`** |
| `famload_fix.fixed_product_path()` patches `_connector_manager_for` on … | both copies (alias scan) | the one copy, by name; reverted on exit (both orders) |
| same probe with a real prompt job (`FD.author(prompt=walls)`, 2026 pin) instead of the bare loader, both orders | `['_frontdoor_ifc_room', 'ifc_intent']`, loader ≠ entry | **`['ifc_intent']`**, loader is entry, job `ok` |
| inside the bare unzip (`tekton_env.ensure_engine()`, `lib/tools` on path, import-first) | — | `ifc_intent lib/tools/ifc_intent.py True ['ifc_intent']` |
| front-door manifests, `tools/frontdoor.py author` — 6-panel `--prompt` / `--ifc inputs/ifc/electrical-room-2500a.ifc` (main run twice = noise class: content GUIDs, sha256/md5, paths under the out dir, `*.seconds`, `generated_at`; 149 / 214 noisy keys) | 2848 / 4310 flattened keys | **0 / 0 diffs outside the noise class** (the 3 / 5 residual keys are the checkout location — `base.path`, `status_gate.base`, `inputs.ifc`, `intent.summary.source` — and one `validate.seconds` 0.4→0.3); status `PROOF-ONLY (self-checks PASS…)`, status_gate `PROOF-ONLY, NOT-DELIVERABLE` / `pinned-composed-genesis` ×2, both outputs `rvt_validate` VALID 0 errors (1 known DataStorage warning) |
| `python -X importtime -c "import rvt.frontdoor"` ×3 | 89 modules, neither `rvt.frontdoor.build` nor `ifc_intent` eager; 45.3 / 44.4 / 57.3 ms | 89 modules, same absences; 73.1 (cold) / 43.2 / 43.6 ms — unchanged |
| bare unzip of `tekton-plugin.zip`, system `python3` 3.11.15 (no numpy, no olefile), `go author --prompt "an electrical room with 6 panels" --json` ×2 | READY / rc 0 / stderr **0 B** / wall 5.06 s, 4.80 s | READY / rc 0 / stderr **0 B** / 5.12 s, 4.50 s (unchanged) |
| neighbour files (`test_ifc_intent test_famload_fix test_famload test_famload_batch test_frontdoor test_router test_router_release test_router_load_release test_one_job_module test_frontdoor_json_strict test_famdoc_bisect test_instbug test_place_fixtures test_intent_device_plan test_mep_devices test_status_gate`, `RVT_SKIP_LARGE=1 -rs`) | 426 passed / 74 skipped | 426 / 74 for the same 16 files (+4 = the new file → **430 passed / 74 skipped**, 3 m 57 s) |
| new `tests/test_one_ifc_module.py` on `main` (copied in) vs here | 4 failed (`['_frontdoor_ifc_room','ifc_intent']`, `loader_is_entry False`) | 4 passed, 2.8 s |
| WHOLE merged CI shard (`shard_list.py --print`, incl. the new drop-in) | — | **1809 passed / 133 skipped / 3 xfailed**, rc 0, 7 m 39 s (88 files) |

### What was built

* `rvt.frontdoor.build.load_ifc_room_module()` keeps its cache (`build._ROOM`), its candidate path
  (`<repo_root>/tools/ifc_intent.py` — `<plugin>/lib/tools/ifc_intent.py` in the bundle) and its `BuildError`s; it now
  (a) returns `sys.modules["ifc_intent"]` if a by-name import already executed the file, else (b) executes it under the
  spec name `ifc_intent` and registers that, popping the entry if exec raises. Every in-process caller of the loader
  (`build_intent`, the router, `standalone`, `convert.add_to_project`, five dev tools, six test files) is unchanged.
* `rvt.famload_fix.fixed_product_path()` (D1): the `_ifc_intent_modules()` alias/duck-type scan over all of
  `sys.modules` is gone; the D1 branch patches `sys.modules.get("ifc_intent")._connector_manager_for` if the module is
  live and, as before, never loads it itself. Its two callers (`tests/test_famload_fix.py`,
  `experiments/instbug/fix/build_fix_probes.py` — whose "pre-load every module the patch set must reach: `import
  ifc_intent` + `load_ifc_room_module()`" idiom is exactly the pain this removes) behave the same; the idiom is now
  merely redundant, not wrong, so those files are left alone.
* `tests/test_one_ifc_module.py` — every assertion in a FRESH interpreter (the loader is process-cached, and
  `conftest.load_tool("ifc_intent")` deliberately rebinds the name to a fresh copy for `test_frontdoor_json_strict`, so
  an in-process identity check would depend on file order): (1) structure × {loader-first, import-first}: one object,
  it is the `sys.modules` entry and the loader's, `__name__ == "ifc_intent"`, and `fixed_product_path(fix_specimen_phase=False)`
  patches then reverts it; (2) behaviour × {prompt-first, import-first}: `FD.author(prompt=<famgen-free walls>)` on the
  bundled 2026 pin + a by-name import → `names == ["ifc_intent"]`, loader is the entry, job ok. ~0.7 s per probe.

### Findings

* The `_rvtjob_<name>` loaders in `tools/rvt_job.py:113` (`spec_to_rvt`, `seed_audit`, `ifc_to_spec`) never meet a
  by-name import in a product process: `grep` finds no `import spec_to_rvt|seed_audit|ifc_to_spec` under `src/ tools/
  plugin/skills/_shared/`; only `tests/test_inventory.py:159` and `tests/test_readers_own_release.py:64` exec
  `seed_audit.py` under its own name inside a pytest process. Noted, not changed (the issue: "don't gold-plate";
  `tools/rvt_job.py` is another engineer's file this wave).
* One more by-path exec of `tools/ifc_intent.py` exists off the product path: `src/rvt/render/wallgeom.py:1854`
  `_load_ifc_intent_tool()` registers `_ifc_intent_tool` for the wall-bake probe builder `build_walls_file()` (called
  only from that module's own probe driver, no product caller). Follow-up-shaped (make it call
  `build.load_ifc_room_module()`); outside this issue's territory — searched issues (none), filed as **#544** (Refs #507).
* `tests/test_intent_device_plan.py:264` execs the file as `_room` inside its own subprocess — a test's private
  interpreter, harmless.

### How to run

```bash
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_one_ifc_module.py -q -rs          # 4 passed (~3 s)
.venv/bin/python - <<'PY'                                                                # the issue's probe, one process
import sys; sys.path.insert(0, "src"); sys.path.insert(0, "tools")
import rvt.frontdoor as FD
FD.author(prompt="an electrical room with 6 panels", out="out/p507/p", no_handoff=True, quiet=True)
import ifc_intent
from rvt.frontdoor import build as B
print(sorted(k for k, m in list(sys.modules.items()) if (getattr(m, "__file__", "") or "").endswith("ifc_intent.py")), B.load_ifc_room_module() is sys.modules["ifc_intent"] is ifc_intent)   # ['ifc_intent'] True
PY
```

### `/simplify` and `/verify`

* `/simplify` (4 angles). Applied: the test's shared `_HEAD` is formatted once with `ROOT` and the prompt travels by
  `argv`, so both probe tails are plain source (no `{{…}}` escaping, no per-call `.format`); the job probe keys results
  by step name instead of re-deriving the order index; `famload_fix`'s docstring parenthetical trimmed to what the code
  does. Reuse and efficiency: clean (no existing helper the fenced body could call — `router._load_tool` lacks
  adopt/pop and sits downstream of `build`; the D1 patch is one `dict.get` replacing a scan of all `sys.modules`; the
  four fresh interpreters cost 2.9 s total and each is load-bearing). Skipped with reason: (a) *"make `sys.modules`
  the authority on every call, `_ROOM` a memo of it"* (altitude) — following a rebinding on every call would let
  `conftest.load_tool("ifc_intent")`'s deliberately private fresh copy silently become the product path's module
  mid-process (the opposite of that helper's documented purpose), no actor in a product process rebinds the name, and
  the tech-lead constraint is the minimum body diff; the deep fix is on the test side and is filed as **#545** (a session
  `room` fixture + `load_tool` refusing `"ifc_intent"`, the #470 move); (b) dropping `loader_is_entry` from the
  structure probe as derivable — kept, it is the DONE's literal wording and costs nothing; (c) one shared by-path tool
  loader for the six hand-rolled ones in `src/rvt/` — out of territory (two call sites fenced), filed as **#546**
  (`blocked` until the #498 fence lifts).
* `/verify` PASS on the final tree — drove `tools/frontdoor.py author` on three routes: `--prompt "…6 panels"` (rc 0,
  stderr 0 B, `prompt_room.rvt` + 6 `.rfa`, status `PROOF-ONLY (self-checks PASS…)`), `--ifc
  inputs/ifc/electrical-room-2500a.ifc --target-version 2025` (rc 0, 0 B, `rvt_analyze` → release 2025 / schema
  release 2025), `--rvt G_ABPD_2025.rvt --edit "set level 694 elevation to 12"` (rc 0, 0 B, `PROOF-ONLY,
  NOT-DELIVERABLE (hard gates PASSED)`); all three outputs + one generated `.rfa` (`--family`) `rvt_validate` **VALID, 0
  errors** under their own release; `provenance.py --baseline all --streams` on the prompt output: baseline_kind
  `pinned-composed-genesis`, totals `autodesk-sample 422 / ours-created 118 / ours-composed 2680` (= main's manifest),
  0 warnings, G1 FAIL as on main (the standing PROOF-ONLY reason, #19/#21). Bare unzip of the final
  `tekton-plugin.zip`, system `python3` 3.11.15 without numpy/olefile: `go author --prompt … --json` ×2 → `tekton:
  READY | engine bundled | genesis verified (Revit 2026)`, rc 0, stderr **0 B**, wall 5.2 s / 4.5 s, 1 `.rvt` + 6
  `.rfa` delivered. Probe: `--ifc README.md` → rc 3, status `FAILED (IFC intent failed: Error: Unable to parse IFC SPF
  header)`, stderr 302 B = ifcopenshell's own `__del__` KeyError noise, byte-identical on `main` (pre-existing, not
  this diff). No viewer claim anywhere: "validates 0 errors", never "loads".

### BRANCH STATE (eng #507)

* Branch `cam/507-one-ifc-module` from `main@fdcbf12`; PR closes #507.
* Files: `src/rvt/frontdoor/build.py` (`load_ifc_room_module` body only — tech-lead exception to the #498 fence,
  announced on #498), `src/rvt/famload_fix.py`, mirrors `plugin/lib/src/rvt/frontdoor/build.py` +
  `plugin/lib/src/rvt/famload_fix.py` (written by `tools/sync_plugin.py`, byte-identical to source), NEW
  `tests/test_one_ifc_module.py`, NEW `tests/ci_shard.d/507-one-ifc-module.txt`, this section. No hot file, no asset,
  no `TRACKER.md`, `tools/ifc_intent.py` untouched.
* Gates: `tools/sync_plugin.py` then `--check` → in sync (deny-audit clean, identity scan == allowlist, assets
  verified); `plugin/scripts/validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (2941 paths); new
  file 4 passed (4 failed when copied onto `main`); neighbours 426/74 on main = 426/74 here (+4 → 430/74); whole merged
  shard **1809 passed / 133 skipped / 3 xfailed** (7 m 39 s; the post-`/simplify` delta is test-template + docstring
  only and the two touched test files re-ran 12 passed / 5 skipped); `/simplify` applied, `/verify` PASS (above).
* Shipped vs staged: ships with the merge; loader-name plumbing only, zero output-byte change (manifests identical to
  main outside the noise class, outputs VALID) — no viewer claim, nothing staged.
* Follow-ups filed (searched first): **#544** (`wallgeom._load_ifc_intent_tool` third door, Refs #507), **#545** (test-side
  `room` fixture / `load_tool("ifc_intent")` refused), **#546** (one shared by-path tool loader; `blocked` on the #498 fence).
