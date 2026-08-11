# eng #641 — the photometric-web reference is ONE caption, `Photometric Web File` (2026-08-11)

*Fragment of the `family-standards` stream (index: `docs/inbox/family-standards.md`). Written by
eng #641 (cam-karagitz's engineer session for issue #641); nobody else appends here.*

Issue #641 (filed by eng #631, Refs #631 #622 #601; steer S-2026-08-11-a: one parameter per
meaning). #631 made the IFC-born downlight (`rvt.ifc.famfrom_ifc.make_downlight`) and the
prompt-born luminaire (`rvt.famgen.factory.make_luminaire`) spell all 19 shared quantities the
same way — except the IES / photometric-web **reference** (a text path / URL the user fills; never
an embedded `.ies`): `Photometric Web File` on the IFC route, `IES File (URL reference)` on the
factory route. Neither name was in the Lighting Fixtures table and no synonym row folded them, so
`standards.meaning_key` treated them as two quantities and the #631 parity instrument passed for
the wrong reason. A schedule keyed on one name missed the other route's families.

Territory used: `src/rvt/famgen/standards.py` (one `SYNONYM_GROUPS` row + its comment),
`src/rvt/famgen/factory.py` (the luminaire's two caption literals + the comment above them — see
*The caption flip* below for why this was unavoidable), their two `plugin/lib` mirrors via
`tools/sync_plugin.py`, NEW `tests/test_standards_photometric_641.py` +
`tests/ci_shard.d/641-standards-photometric.txt`, two flipped expectations in
`tests/test_famgen_factory.py::test_luminaire_family_composition` (the pinned caption moved),
this fragment. Not touched: `skeleton.py`, every other constructor, `src/rvt/ifc/**`, `SKILL.md`,
the index `docs/inbox/family-standards.md`, `TRACKER.md`.

## What was built

- **`standards.SYNONYM_GROUPS` +1 row** (photometric block):
  `("Photometric Web File", "Photometric Web", "Photometric File", "IES File (URL reference)",
  "IES File", "IES Photometric File")`. First spelling = the one we standardise on = Revit's own
  caption for the light source's photometric-web parameter. `meaning_key` now folds every
  spelling (plus the case/space/underscore variants it already folded: `photometric_web_file`,
  `IESFile`) onto `photometricwebfile`. No spelling is claimed by two groups (`check_specs`).
- **Decision (issue DONE 1): constructor-authored under ONE caption, NOT a table row.** In Revit
  `Photometric Web File` belongs to a family's *light source*, which not every lighting-fixture
  family defines; listing it as a category-wide `convention` row would grow a blank text
  parameter on every archetype / assembly lighting fixture (`make_generic_model`,
  `make_assembly` apply the same table) — a twin-in-waiting for the day a user turns the light
  source on — and would have changed those constructors' content. So both luminaire routes keep
  authoring it themselves, now under the same caption, and `apply` has nothing to skip or twin.
  The comment on the row says so. `test_the_table_is_sound_and_no_category_lists_the_reference_twice`
  pins the decision (no category row carries the meaning).
- **The caption flip (`factory.py`, two literals).** Issue DONE 2 — "both routes' written `.rfa`
  read back the same caption" — cannot hold with a synonym row alone: the moment the two names are
  one meaning, `tests/test_famfrom_ifc_standards.py`'s two parity tests
  (`…spell_every_shared_quantity_the_same_way`, `…read_back_the_same_captions…`) go red unless one
  route changes its spelling. The factory lost: `IES File (URL reference)` was ours alone (a
  label of our own coinage), `Photometric Web File` is Revit's caption and what the IFC route, its tests
  (`tests/test_ifc_family.py` ×4, `tests/test_famfrom_ifc_standards.py` ×2), `product_facts.py`
  prose and `docs/inbox/ifc-family.md` already pin — none of those move. `make_luminaire` now
  authors `_text(doc, "Photometric Web File", "photometrics")` and files the catalog's S2 URL under
  it on every type row; group (`lightPhotometrics`), storage class (text) and value are unchanged.
- **The `apply` guard, exercised.** A caller's `standard_values={"IES File (URL reference)": …,
  "IES File": …}` on `make_luminaire` grows nothing beside `Photometric Web File`; both spellings
  come back in `values_not_placed` (a constructor-owned quantity is filled by the constructor's
  own argument, never redefined by the standards step — the existing #622 rule, now reaching this
  quantity because the meaning folds).

## Evidence (numbers)

Instrument = the #631 record's: `standalone_family_write` on the bundled base + `FamilyIndex`
caption read-back of every `ParamElemFamily`; before = `origin/main` @ 3ec84d7, after = this branch.

| gate | before | after |
|---|---|---|
| `python -m rvt.famgen.standards --check` | `27 categories, 35 synonym groups, 0 problems` (exit 0) | `27 categories, 36 synonym groups, 0 problems` (exit 0) |
| `route.py matrix` | md5 `e9e2cc8d…59502`, 39 lines | byte-identical (`cmp` clean) |
| troffer `.rfa` (`make_luminaire()`) read-back | 23 captions, spellings present `['IES File (URL reference)']`, twins `{}` | 23 captions, `['Photometric Web File']`, twins `{}`, 23 distinct meanings; VALID 0 err 0 warn; provenance ok |
| downlight `.rfa` (`make_luminaire(kind="downlight")`) | 23, `['IES File (URL reference)']`, `{}` | 23, `['Photometric Web File']`, `{}`; VALID 0/0; provenance ok |
| IFC downlight `.rfa` (`famfrom_ifc.make_downlight`) | 33, `['Photometric Web File']`, `{}` | 33, `['Photometric Web File']`, `{}` — caption set identical; VALID 0/0; provenance ok |
| standards report `skipped` on the luminaire | Luminous Flux, Initial Color Temperature, Wattage, Voltage ("already authored by the constructor") | same four — no new row, so nothing new to skip and no twin possible |
| every OTHER constructor (doc digest: sorted captions + type rows + notes + standards report, sha256) | panelboard `7fa4974a…`, transformer `3b3c90b8…`, device `5789eb42…`, generic lighting_fixture `43773945…`, generic data_device `da61fab1…`, house switchboard `b9333389…`, IFC downlight `1ae2293d…` | **identical digests**; only `luminaire_troffer` (`0f4823f6…` → `2c7d99f7…`) and `luminaire_downlight` (`9d423a42…` → `e1934f59…`) change |
| surface (`tools/make_family.py luminaire --kind troffer --size 2x4 --wattage 38 --json`) | — | `ok: true`; family-mode `VALID`, `n_errors 0`, `n_warnings 0`; provenance `ok: true`, findings `[]`, all four checks true; 23 captions read back off the file, `Photometric Web File` present, `IES File (URL reference)` absent, 23 distinct meanings; `rvt_validate --family`: `VALID (no errors); warnings=0 info=2` |

(The written IFC downlight differs byte-wise before/after at offset 16609 — and differs at the
same offset between two writes on the *same* tree: per-write nondeterminism of the container, not
content; the document digest and the caption set are the instrument, and both are identical.)

Tests: `RVT_SKIP_LARGE=1 pytest tests/test_standards_photometric_641.py tests/test_famgen_standards.py
tests/test_famgen_factory.py tests/test_standards_apply_safe.py tests/test_records_layout.py -q -rs`
— before (without the new module, plus `test_famfrom_ifc_standards.py`): 210 passed / 5 skipped
(rme/rst samples absent); after (+ the new module, + `test_famfrom_ifc_standards.py`,
`test_ifc_family.py`): 234 passed / 8 skipped (same sample-absent skips). New module alone: 8 passed.
Whole merged shard: in the PR body. `sync_plugin.py` rebuilt then `--check` clean;
`validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (tracked paths portable, count in
the PR body); `shard_list.py --print` resolves the drop-in (line 110).

## What is NOT claimed

- No desktop round, no viewer batch: one caption string changed on a text `ParamElemFamily` of a
  family whose classes, specs, groups, connector and geometry are unchanged. VALID 0 errors +
  provenance clean is a fact about the file, not evidence Revit opens it (rule 4).
- `Photometric Web File` is also the caption of Revit's *built-in* light-source parameter. Our
  luminaires define no light source (no `ImposterLight` constructor), so there is nothing for the
  family parameter to collide with today — the same footing `Light Loss Factor` (a table row since
  #601) and the IFC route's `Photometric Web File` (`docs/inbox/ifc-family.md`, #631) already stand on. If a light
  source is ever authored, both become the built-ins' job and these family parameters retire.

## Patch offered, not applied (outside territory)

`src/rvt/famgen/facts/lithonia/blt-led-troffer.json`, `line_facts.photometry_reference.note`
still says *"the family carries an 'IES file (URL reference)' text parameter pointing at S2"*.
Nothing reads that note (the factory reads `.value`; `test_famgen_catalog` checks `value` /
`provenance`), so no output carries the stale name; the honest wording is now *"a 'Photometric
Web File' text parameter"*. One-line data-prose edit for whoever next holds the facts store.

## BRANCH STATE (eng #641)

- Branch `cam/641-photometric-synonym` from `main` @ 3ec84d7; PR `Closes #641`.
- Files written: `src/rvt/famgen/standards.py`, `src/rvt/famgen/factory.py`,
  `plugin/lib/src/rvt/famgen/{standards,factory}.py` (mirrors, via `tools/sync_plugin.py`),
  `tests/test_standards_photometric_641.py` (new, 6 tests / 8 cases),
  `tests/ci_shard.d/641-standards-photometric.txt` (new), `tests/test_famgen_factory.py`
  (2 expectations), `docs/inbox/family-standards.d/641-photometric-synonym.md` (this fragment; the
  index is untouched).
- Gates: the table above; whole merged CI shard count in the PR body. Staged vs shipped: nothing
  staged (no viewer batch); shipped = the code + tests above. Scratch outputs (before/after `.rfa`,
  read-back JSON, digests) live in the session scratchpad, not committed.
