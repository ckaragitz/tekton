# hostsym-product — the host symbol law lives in the two loaders now (#10)

Stream: **hostsym-product** (engineer session, 2026-08-09, issue #10, P1,
area:famgen). Territory: `src/rvt/famgen/loader.py`, `src/rvt/famload.py`,
`src/rvt/famgen/birthright.py` (v3 lane, comments only), tests, this record.
Status: **SHIPPED as a PR — corpus-law conformance fix; makes NO
certification claim and is NOT expected to close the open audit cell by
itself (BX_v3 carried this exact repair opt-in and FAILED, verdict #46/#54).**

## 1. The law (measured by the species stream, not re-measured here)

`docs/inbox/species.md` §1.2 / `experiments/species/cd_forensics.json`, 36
native rstbasic host `Family` rows: **zero** carry more than the one leading
blank `' '` current-values row, **zero** have `m_idx` on a blank when real
pairs exist, **zero** instances bind a blank-named symbol. The only
reduced-base PASS (T2a) registered exactly ONE real-named
`FamSymSurrogate`+`FamilySymbol` pair. The UNIT side keeps the born
blank-pair-first table (`[' ', real..]`, T2a `m_idx` 2, ours `m_idx` 1).

## 2. Where our loaders leaked the unit's blank pair to the host side

| loader | leak (before) | trigger |
|---|---|---|
| `rvt.famload._plan_family` | one host symbol pair per `doc.types` entry **including `' '`**; `plan.symbol_id` (= what an instance binds) = the first, i.e. the blank pair's (SC1) | any doc whose `doc.types` is blank-pair-first: birthright v2+ products, standalone-born shapes |
| `rvt.famgen.loader.author_host_family` | copied the baked unit table `[' ', real]` verbatim behind its OWN blank row → `[' ', ' ', real]`, `m_idx` 1 **on a blank** (DEMO v8, ×6 families) | same |
| `rvt.famgen.loader.plan_load` | `type_name = doc.types[current_type]` → a `' '`-named FamilySymbol + FamSymSurrogate when `current_type` sits on the blank | `convert.extract_family.RfaFamilyDoc` (foreign standalone-born `.rfa`: types `[' ', …]`, `current_type` hard 0) — the extract→place route |

The plain product document of the default pipeline (`doc.types` has no blank)
never triggered any of the three; the front door's prompt lane therefore
emits the same host shape before and after this change (shown in §4).

## 3. What changed (product code; birthright v3 becomes a no-op)

* `rvt.famgen.loader.real_type_names(doc)` / `symbol_type_name(doc, fallback)`
  — the law in one place: real-named types only; the symbol name = the
  current type if real-named, else the first real-named, else the family name.
* `rvt.famgen.loader.plan_load` uses `symbol_type_name`;
  `author_host_family` skips blank-named pairs when copying the unit table
  (its own single leading blank stays; `m_idx = 1 if pairs else 0` now always
  lands on a real pair). Docstring states the law.
* `rvt.famload._plan_family`: `type_names = real_type_names(doc) or [doc.name]`
  → surrogates, symbols, `symbol_ids`, and the instance-facing `symbol_id`
  exist for real-named types only.
* `rvt.famgen.birthright` v3: **kept, documented as promoted.**
  `apply_host_symbol_law` still strips `doc.types` ahead of famload (harmless;
  its refusals keep verifying the baked unit-side shape); the live-patched
  `apply_host_family_table_law` now finds nothing to drop on loader output and
  reports `applied: False, dropped_blank_rows: 0` (test-pinned). Nothing in
  the lane was deleted, so `tests/test_species.py` / `test_identity.py` and the
  recorded accounting stay valid byte-for-byte.
* Subtractive only: no value is added anywhere; zero donor bytes; nothing
  reads an Autodesk directory; delivery paths untouched.

## 4. Evidence

**New suite `tests/test_hostsym_product.py` — 16 tests, 1.9 s, runs in a
fresh clone** (rides on the pinned certified base
`plugin/assets/genesis/G_ABPD.rvt`; the sample-backed `test_famgen_loader.py`
/ `test_famload.py` skip in cloud sessions, which is why the law needed its
own file). It builds the flagship panelboard above the base watermark, gives
it the born blank-pair-first table (`_make_born_shaped`, = birthright v2's
TYPES lane shape; `current_on_blank=True` = the extracted-foreign-family
shape) and asserts, per loader: host Family table `[' ', '400A MCB 42ckt']`
`m_idx` 1; exactly one `FamilySymbol` + one `FamSymSurrogate`, both named
`'400A MCB 42ckt'`; famload `plan.type_names == ['400A MCB 42ckt']`,
`symbol_id` real; the symbol carries the real type's parameter row; the
unit-side table untouched `[' ', '400A MCB 42ckt']` `m_idx` 1; dry-run loads
through both `load_family_into_project` and `load_family_documents` pass the
round-trip gate (54/54, 0 failed); all-blank types fall back to the family
name; v3's loader half reports `applied: False`.

* Same 16 tests against the **pre-fix** loaders (`git stash` of the two `src/`
  files): **12 failed / 4 passed** — the 4 being the plain-doc pins and the
  v3-product-half composition. After: **16 passed**.
* Issue's named suites, this clone (`RVT_SKIP_LARGE=1`):
  `test_famgen_loader test_famload test_famload_fix test_species test_birthright
  test_identity test_hostsym_product` → **108 passed, 35 skipped** (all 35 =
  `samples/` / built probes absent — expected in a cloud clone; none newly
  skipped by this change).
* CI shard (`tests/ci_shard.txt`, now including the new file):
  **145 passed, 23 skipped, 30 s.** Bare-unzip gates `test_bootstrap
  test_coldstart test_surface_perf test_plugin_sync`: **26 passed, 4 skipped.**
* `tools/sync_plugin.py` → synced 3 files, deny-audit clean, validation
  passed, zip rebuilt; `--check` → in sync; `check_portable_paths` → ok (2654);
  `plugin/scripts/validate_plugin.py` → PASS (23 assertions).
* **Front door, as the issue asks** —
  `tools/frontdoor.py author --prompt "an electrical room with 2 panels"`
  (10 s): status `PROOF-ONLY (self-checks PASS)`, `prompt_room.rvt` delivered
  + 2 `.rfa`. Read back above watermark 1,472,524:

  ```
  Family 1472566 'Panelboard PP-1 480Y/277 225A MLO 42sp'  table [' ', '225A MLO 42ckt'] m_idx 1
  Family 1472625 'Panelboard PP-2 480Y/277 225A MLO 42sp'  table [' ', '225A MLO 42ckt'] m_idx 1
  FamilySymbol 1472582 '225A MLO 42ckt' familyId 1472566
  FamilySymbol 1472641 '225A MLO 42ckt' familyId 1472625
  FamSymSurrogate 1472583 '225A MLO 42ckt' -> 1472582
  FamSymSurrogate 1472642 '225A MLO 42ckt' -> 1472641
  FamilyInstance 1472647 m_masterSymbolId 1472582
  FamilyInstance 1472648 m_masterSymbolId 1472641
  ```
  `tools/rvt_validate.py`: `prompt_room.rvt` **0 errors** / 1 warning (the
  known DataStorage ES-blob decoder gap on the base) ; both `.rfa --family`
  **0 errors**. Validator green is necessary, not acceptance (rule 4): **no
  "loads" claim, no viewer batch staged** — the shipped default-pipeline bytes
  are unchanged by this PR, so there is nothing new to certify.

## 5. Findings for other streams (not this territory)

* `tools/species_probe.py` (DEMO v9) and `tools/identity_probe.py` (DEMO v10)
  gate a *rebuild* on `hostsym_loader[*].applied is True` — i.e. on the loader
  having been broken and v3 having repaired it. A rebuild after this PR would
  trip that gate although the emitted bytes are the lawful shape. The recorded
  accounting/tests are unaffected (they read the JSON on disk). Filed as a
  follow-up task issue (relax the gate to the *shape*: one leading blank,
  `m_idx` on real) rather than edited here.
* `convert.extract_family.RfaFamilyDoc.current_type = 0` on a blank-first
  foreign table is now harmless for naming (the loader picks the first real
  type), but the *baked* `m_idx` of the foreign file (T2a: 2) is still not
  honoured as the current type — worth a look by the convert-a stream if type
  choice on extract→place ever matters; not a law violation.

## BRANCH STATE

* Branch `cam/10-hostsym-blanks` from `origin/main` af59d26; commits:
  loader+famload fix + `tests/test_hostsym_product.py`; birthright v3 note +
  plugin mirrors (`plugin/lib/src/rvt/{famload.py,famgen/loader.py,famgen/birthright.py}`)
  + `tests/ci_shard.txt` (+1 line); this record.
* Gates: listed in §4 — all green in this clone; NO full-suite run (charter).
* Shipped vs staged: product code + tests shipped in the PR; **nothing staged
  for the viewer** (no certification claim; default-pipeline output bytes
  unchanged). No `.rvt`/`.rfa` committed (scratch outputs only, validated 0
  errors).
* Hot files: none touched (`famgen/loader.py` / `famload.py` are shared famgen
  files named in the issue's territory; no other open PR holds them at the
  time of writing).
