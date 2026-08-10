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
| `MANIFEST.md` of the edit | gate list only (`gate base_provenance: PROOF-ONLY, NOT-DELIVERABLE`), no reason, no authorship, no Honesty section | `- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — <the #284 sentence naming G_ABPD>` · `- base authorship (issue #143 census): **descends-from-pinned-genesis** — descends from G_ABPD (Revit 2026; 2,679 of 2,680 composed slots byte-identical, share 0.9996 ≥ 0.95), ledgered against the pin `G_ABPD.rvt` and its census — 2,680 of 3,102 base elements ours by composition; residue 422 still byte-identical to the Autodesk ancestor (11 never authored, 411 re-emitted identically by our constructors; recorded dispositions {…})` · `- this file's ledger (everything the chain created): 118 created elements ours, 0 created with lineage into the residue` · `## Honesty` with `- **PROOF-ONLY, NOT-DELIVERABLE** (a label: the file is delivered)` + tiers + release |
| same chain on the 2025 pin (`--target-version 2025`, walls-only X) | — | `descends-from-pinned-genesis`, `descends_from G_ABPD_2025`, totals 925 / 2,391 / 4 transitive-cloned (F2), `ledgered_against G_ABPD_2025.rvt`, `target_version.output_release 2025`, MD line "descends from G_ABPD_2025 (Revit 2025; 2,390 of 2,391 …)" |
| a foreign file (`tekton-eval-kit/TEST-KIT/02_*.rvt`, F5's non-descendant) edited | gate list only | `edit.gates.base_provenance.base_kind` **user-base**, totals 3,345 sample / 1 modified, no `ledgered_against`, MD `- base authorship: **user-base** (no census: everything inherited from the base is ledgered as the base's)`, stamped PROOF-ONLY, delivered |
| an edit whose gate says `census: STALE …` / `UNAVAILABLE (…)` (synthetic job manifest) | dropped | `edit.gates.base_provenance.census` carried, ONE `edit.degradations` line via `authorship_census_note` ("… conservative reading … hard rule 1"), MD `- base authorship: **pinned-composed-genesis** (census **STALE …**…)` + `**degradation**: …` — the #303 behaviour of the create routes, now on the edit route (F11) |
| create routes' `MANIFEST.md` | as #418 | byte-for-byte the same authorship lines (now emitted by the shared `status_gate_lines`); the Honesty stamps gain the suffix "(a label: the file is delivered)" — the only create-route wording change |
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
* Files: `src/rvt/frontdoor/manifest.py`, `tests/test_status_gate.py`, this section; regenerated mirror
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
