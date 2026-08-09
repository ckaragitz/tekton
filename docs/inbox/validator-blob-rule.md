# validator-blob-rule — the 0x0f3f unit-footer-blob presence law is a validator rule (issue #7)

Stream: engineer session for #7, 2026-08-09 (cloud, fresh clone; fanned out
by the tech-lead session per steer #58). Charter (#7): the instance-audit
campaign proved Autodesk's open-time audit rejects any file in which a placed
instance walks into a save unit whose 64-byte `0x0f3f` footer blob is empty
(genesis-audit VERDICTS #36 — E3/E6 FAIL empty, **E1b PASS random**, so
presence-only), while an uninstanced empty-blob unit is tolerated (H10 /
L_v2 / the L1a loads PASSED). The writers were fixed that night
(`factory.build_family_save_unit` → `famdoc_adoc.build_footer` nonce), but
`rvt_validate` still said **VALID** on an empty-blob file, so a writer
regression would stay invisible until a viewer round. Territory:
`src/rvt/validate.py`, new `tests/test_validate_footer_blob.py`,
`tests/ci_shard.txt` (+1 line), this record, regenerated mirror
`plugin/lib/src/rvt/validate.py`.

## What was built

Two halves of one law in `src/rvt/validate.py`:

| layer | where | severity | fires when |
|---|---|---|---|
| L1 structure | `Validator._check_unit_footers(pname, walker)` — called for every `Partitions/<N>` walker | **WARNING** | any save unit whose `0x0f3f` blob is not `UNIT_FOOTER_BLOB_LEN` (64) bytes — empty *or* truncated. Exempt: an EMPTY partition (header `elem_table_count == 0`, the dach `Partitions/85` form — the same predicate the consistency layer already uses). |
| L3 semantic | `Validator._check_instanced_unit_footers(typed_checks, sym_family, fam_guids, inst_ids)` at `where = "unit-footer"` | **ERROR** | a loaded-family unit (index ≥ 1, keyed by its separator GUID) has a short blob **and** (a) at least one placed instance resolves into it — instance `m_symbolId` / `m_masterSymbolId` → `FamilySymbol.m_familyId` → host `Family` famdoc GUID (`m_oFamDoc.m_contentDocGUID`, which *is* the unit GUID on our files, or `m_famDocGUID`) == unit GUID — or (b) some `FamilyInstance`'s chain breaks before reaching a GUID, so the validator cannot show the short unit is uninstanced. |

One detector, two severities: `_short_blob_units(walker)` is the single
predicate both layers consume; `Validator._content_units()` is the single
"loaded units + GUID string" iterator (the four-registry rule E1 now uses it
too, instead of its own copy of the uuid loop).

Design points worth keeping:

* **Never VALID on a possibly-failing file.** Case (b) is deliberate: the
  validator is calibrated so every audit-FAILED file carries ≥ 1 error. An
  unresolvable instance + a short-blob unit is convicted rather than waved
  through. Native files cannot false-positive on it — no corpus content unit
  has a short blob (2,071/2,072 carry 64 B; the 2,072nd is the exempt
  empty-partition unit), so the branch is only reachable on our own output,
  where a short blob is a writer regression whatever the instances do.
* **Unit 0 stays a WARNING.** Every element lives in unit 0, so "instanced"
  is meaningless for it and no verdict ever isolated an empty *host*-unit
  blob; the corpus and all our bases carry 64 B there. Hygiene, not
  rejection evidence.
* **No third decode pass.** The symbol→family and family→GUID maps and the
  set of FamilyInstance-derived owners are harvested inside the existing
  seq-102 decode loop (chain-based: any class deriving from `FamilyInstance`
  / `FamilySymbol` / `Family`), and the instance→symbol edges are the
  Symbol-typed `typed_checks` the symbol-typing rule already collects —
  filtered only after the "any short unit?" early exit, so the common case
  costs nothing. `chain_names` moved above the loop to serve both.
* **Reusing the census scan.** The issue asked to reuse
  `tools/famdoc_blobs.py::unit_footer_census` rather than re-derive the
  scan. Its scan *is* `rvt.partitions.StreamWalker` (`Unit.footer_blob`,
  read by `_read_footer`) — the validator already holds those walkers for
  every partition, so the rule reads `w.units[*].footer_blob` directly. The
  tool itself cannot be imported from the engine: `src/rvt/validate.py`
  ships in the plugin as `plugin/lib/src/rvt/validate.py`, `tools/famdoc_blobs.py`
  does not ship at all (and pulls sample-quarantined bisect machinery), and
  engine → tool is the wrong dependency direction. `UNIT_FOOTER_BLOB_LEN = 64`
  is a local constant for the same reason (no `famgen` import at validator
  import time); a test pins it to `famdoc_adoc.FOOTER_BLOB_LEN` and
  `len(build_footer())`.

## Evidence

Synthetic violations are made by `strip_footer_blob(src, dst, unit, new_len)`
in the test: unframe the one `Partitions/<N>` stream (`ecc.unframe_stream`),
rewrite that unit's `u16 0x0f3f + u32 n + blob` in place, re-frame
(`ecc.frame_stream`), rewrite the container (`cfb_writer.write_cfb`). Only
the footer changes, so every other check stays green — which is exactly why
the pre-change validator said VALID on all of them:

| file | before this change | after |
|---|---|---|
| `plugin/assets/genesis/G_ABPD.rvt` / `_2025` / `_2024` (certified, 1 unit, blob 64 B each) | OK 0 err | **OK 0 err, no 0x0f3f finding** (silent) |
| one-panel prompt build (`FD.author`, pinned base; units 64/64 B) — load-only stage and combined deliverable; the two generated `.rfa` (unit 0 = 64 B) | OK | **OK, silent** |
| G_ABPD_2024 with unit 0 blob → 0 B | OK 0 err | OK, **1 WARNING** structure `Partitions/21`: `1/1 save unit(s) … (unit:len u0:0)` |
| G_ABPD with unit 0 blob → 16 B | OK | OK, **1 WARNING** `u0:16` |
| load-only stage, family unit 1 blob → 0 B (no instance) | OK | OK, **1 WARNING** `u1:0` |
| combined deliverable, family unit 1 blob → 0 B (1 placed panel) | **OK 0 err** (the invisible regression) | **FAIL, 1 ERROR** semantic `unit-footer`: `1 placed instance(s) walk into 1/1 loaded-family save unit(s) … Partitions/21 u1 (e227a02f, blob 0B) <- instance(s) [1472647]` + the L1 warning; `rvt_validate --quiet` exits 1 |
| same load-only probe + a synthetic FamilyInstance whose symbol is unknown | — | **ERROR** `… 1 placed FamilyInstance(s) [111] whose family document could not be resolved … counted against every short-blob unit`; a non-instance owner of the same dangling symbol id adds nothing; an instance resolving to another famdoc GUID adds nothing |

Gates (this branch, fresh clone, `.venv` from `scripts/cloud-setup.sh`):

* `pytest tests/test_validate_footer_blob.py -q` → **10 passed** (~15 s; the
  prompt build is ~6 s, once per module); `tests/test_validate_release.py`
  → 7 passed (17 passed together in 18 s after the `/simplify` pass).
* `tools/rvt_validate.py` on the three pinned bases → `OK errors=0` ×3
  (G_ABPD keeps its pre-existing DataStorage decode-gap warning).
* `tools/sync_plugin.py` → synced 1 file (`plugin/lib/src/rvt/validate.py`),
  deny-audit clean, validation passed, zip rebuilt (not committed);
  `--check` → in sync.
* `tools/dev/check_portable_paths.py` → ok, 2655 tracked paths.
* `plugin/scripts/validate_plugin.py` → PASS, 23 assertions.
* `RVT_SKIP_LARGE=1 pytest $(ci_shard)` → **139 passed, 23 skipped** (37 s;
  the new file is in the shard).
* Full suite NOT run (SUITE-COORDINATION).
* `/simplify` pass ran (4 review angles): applied — one shared short-unit
  predicate + content-unit iterator (E1 reuses it), instance owners collected
  in the decode loop instead of threading `recs102`/`chain_names` into the
  rule, Symbol refs filtered after the early exit, plain-slice truncation per
  house style, test helpers deduplicated behind one `_entries()` generator
  and a module fixture. Skipped with reason: importing
  `tools/famdoc_blobs.unit_footer_census` / `tools/terminal_diff` private
  helpers into the test (they walk without `enter_own_release`, so the
  2025/2024 bases would not frame), and the two out-of-territory homes noted
  below.

## Follow-ups (filed as task issue #71, `Refs #7`)

* The 64-byte length is a *reader* fact: its natural home is
  `rvt/partitions.py` beside `FOOTER_TAG` (where `_read_footer` parses
  `blen`), imported by both `famdoc_adoc.FOOTER_BLOB_LEN` and the validator;
  likewise a `Unit.guid_str` property would retire the five
  `str(uuid.UUID(bytes_le=...))` sites, and `rvt.provenance._family_docguid_map`
  should call `validate._famdoc_guids` instead of mirroring it. All outside
  this issue's territory (`src/rvt/partitions.py`, `provenance.py`,
  `famgen/`), so recorded, not done here.

## Findings

* On our loaded files the host `Family.m_famDocGUID` is a *different* minted
  GUID from the unit/ContentDocuments GUID; the unit is named by
  `Family.m_oFamDoc.value.m_contentDocGUID`. The rule keys on both (as
  `rvt.provenance._family_docguid_map` already did), so either convention
  resolves.
* `FamilyInstance` keeps its symbol at `m_pInstanceInfo.value.m_symbolId`
  and `m_masterSymbolId` (top level) — both already captured by the
  ElementId-typed ref walk, so instances are found by field name at any
  depth, and any element class holding a symbol ref into a short-blob
  family convicts the unit (Revit would load the famdoc for it too).

## Open questions / follow-ups (not filed — no evidence they are needed yet)

* Nested families: a famdoc unit's own `Family` rows for *its* nested
  families are harvested too (the maps are file-wide), so a nested unit
  instanced only from inside another famdoc is covered in principle; there
  is no fresh-clone fixture with nested loads to prove it.
* If a verdict ever shows the audit also demands the blob on an
  *uninstanced* unit or on unit 0, flip `_check_unit_footers` to
  `rep.error` — one line; the tests name which cases move.

## BRANCH STATE

* Branch `cam/7-footer-blob-rule` from `main@af59d26`; PR closes #7.
* Files: `src/rvt/validate.py` (rule + docstring bullets + `UNIT_FOOTER_BLOB_LEN`
  + `_famdoc_guids`), `tests/test_validate_footer_blob.py` (new, 10 tests),
  `tests/ci_shard.txt` (+1 line), `docs/inbox/validator-blob-rule.md`
  (this), regenerated `plugin/lib/src/rvt/validate.py`.
* Gates green as listed above; nothing staged for the viewer (read-path
  only — no output bytes change, so no certification round is implied).
* Shipped vs staged: everything in the PR; no experiments, no assets, no
  samples touched; `tekton-plugin.zip` regenerated locally, not committed.
