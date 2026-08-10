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
