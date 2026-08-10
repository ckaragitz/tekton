# rvt-to-ifc-param-carrier — the rvt → ifc tagging contract keys the value carrier on the ParamDef storage class (#355)

Stream: eng #355 (engineer session, one issue). Territory: `src/rvt/convert/rvt_to_ifc.py`
(`_family_param_defs`, `_param_value`, `_family_contract`), the new leaf `src/rvt/convert/param_carrier.py`,
`src/rvt/convert/modify_family.py` (import of the shared rule only — no behaviour change),
`src/rvt/frontdoor/matrix.py` (one prose clause) + the matching row prose in
`docs/product/PERMUTATION-MATRIX.md` (no status change), `tests/test_rvt_to_ifc_param_carrier.py` (new),
`tests/ci_shard.d/355-rvt-to-ifc-params.txt` (new), this record, regenerated `plugin/lib` mirror.
Not touched: `src/rvt/famgen/skeleton.py` (the #333/#336 storage-class law stays), no hot files.

## Why
#354/#356 fixed the family-edit inventory; the same spec-only fork lived on in the tagging contract
`rvt.convert.rvt_to_ifc` writes into `Pset_TektonElectrical`. `_family_param_defs` read only
`(caption, m_specTypeId)` and `_param_value(row, spec)` keyed integers on `"int64" in spec` — but a
family generated after fba7efb authors `NumberOfCircuits` / `Phases` / `Wires` as `ParamDefInt` with
**no spec**, so an rvt → ifc export of a project carrying OUR generated panelboards wrote them as
`IFCREAL(0.)`, and an empty `ParamDefString` came out as `0.0` instead of absent.

## What was built
* **One shared rule, not a third copy.** `carrier_for_param(def_class, spec)` moved out of
  `modify_family` into the new leaf module `rvt.convert.param_carrier` (no imports of its own; that one
  function is its whole surface). *Why a leaf and not an import from `modify_family`:* `rvt_to_ifc` and
  `modify_family` are sibling routes that both already sit on `add_to_project`; importing one route from
  the other would drag its regex/vocabulary import weight into every rvt → ifc call and invite a cycle
  the day `modify_family` wants the reader. `modify_family` imports the public name (its two call sites
  and one line of `tests/test_modify_family_carrier.py` renamed `_carrier_for_param` → `carrier_for_param`;
  behaviour unchanged, `_KIND_OF_CARRIER` stays private there — single consumer); a test asserts both
  modules hold the *same function object*.
* `_family_param_defs` now returns `(caption, def_class, spec)` — `def_class` is the schema-resolved
  `ptr_class` of `m_pParamDef` (available through `FamilyIndex` exactly as through `mutate.Document`).
* `_param_value(row, def_class, spec)`: carrier by class first, spec second; `m_int` carrier → `int`;
  `m_str` carrier → the text or `None` (never `0.0`); for a class the rule does not name (e.g.
  `ParamDefURL` on a FOREIGN family) a filled `m_str` is carried as text rather than its `0.0` — an
  explicit, tested branch (the old reader did this implicitly); otherwise the double is spec-converted
  exactly as before (ft → m, internal → V/VA, amps as-is). The built-in `ALL_MODEL_*` captions ride as
  `ParamDefString`.
* `matrix.py` prompt+rfa → rfa cell prose (and the rendered doc row): "storage class first
  (`ParamDefString` = text, `ParamDefInt` = integer — neither carries a spec), the spec of a
  `ParamDefValue` second, which also drives unit conversion". **No cell status changed.**

## Evidence (numbers)
Same front-door job (`author --prompt "an electrical room with 6 panels"`, 2026 base), same `.rvt`,
exported by `convert_rvt_to_ifc` on `main` @ ec62a06 vs this branch:
```
BEFORE  #72=IFCPROPERTYSINGLEVALUE('Phases',$,IFCREAL(0.),$);
        #79=IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCREAL(0.),$);
        #70=IFCPROPERTYSINGLEVALUE('PanelName',$,IFCLABEL('PP-1'),$);      (text survived only because m_str was non-empty)
AFTER   #72=IFCPROPERTYSINGLEVALUE('Phases',$,IFCINTEGER(3),$);
        #79=IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCINTEGER(42),$);
        #70=IFCPROPERTYSINGLEVALUE('PanelName',$,IFCLABEL('PP-1'),$);
```
On a freshly generated `panel_225a.rfa` read through `_family_contract(FamilyIndex(rfa), 0, None)`:
before `NumberOfCircuits 0.0 / Phases 0.0 / Wires 0.0`; after `42 / 3 / 4` (ints), `PanelName 'DP-1'`,
`BusRating 225.0`, `Voltage 208.0`, `Width 0.508` unchanged.

Gates (this session, fresh cloud clone, no `samples/`, after the `/simplify` edits):
* `tests/test_rvt_to_ifc_param_carrier.py` — **14 passed** in ~3.4 s (11 pure-rule rows incl. the
  foreign-text branch, shared-object identity, defs + contract on a law-built .rfa, and the end-to-end
  prompt → .rvt → .ifc read back through `rvt.ifc.steplite`: `('IfcInteger', 42)` / `('IfcLabel', tag)`).
  Listed via `tests/ci_shard.d/355-rvt-to-ifc-params.txt`.
* `tests/test_rvt_to_ifc_param_carrier.py tests/test_modify_family_carrier.py tests/test_convert.py
  tests/test_convert_combo.py tests/test_router.py tests/test_plugin_sync.py tests/test_shard_list.py`
  (full files) — **165 passed, 22 skipped** (acceptance fixture / generated .rfa under `experiments/` /
  rme sample / genesis specimen absent, one chmod-as-root — all expected fresh-clone skips), **0 failed**, 45 s.
  The `-k "matrix_doc or evidence_self_audit or rvt_to_ifc or ifc or carrier or param"` subset named in
  the brief: 86 passed, 6 skipped, 0 failed (pre-simplify run; superset above re-run after).
* `tools/sync_plugin.py` synced the mirrors (incl. the new `plugin/lib/src/rvt/convert/param_carrier.py`),
  then `--check`: in sync, deny-audit clean; `plugin/scripts/validate_plugin.py`: PASS (25 assertions);
  `tools/dev/check_portable_paths.py`: ok (2844 tracked paths); `tools/dev/shard_list.py --print | tail -3`
  ends with `tests/test_rvt_to_ifc_param_carrier.py`.
* `/simplify` (4 reviewers) applied: shared surface narrowed to the one function; alias imports dropped;
  docstrings trimmed to the file's density; the "filled `m_str`" heuristic turned into an explicit
  foreign-class branch with a test row; IFC assertions read through `steplite` (typed) instead of a regex
  over STEP text; the e2e test asserts on `convert_rvt_to_ifc`'s own `equipment` record instead of a
  second `extract_intent`; the separate defs test folded into the contract test (one `FamilyIndex` open).
  Skipped as out of scope (candidates for a test-infra follow-up, not filed from here): hoisting the
  `needs_catalog` / `law_rfa` / one-panel-job fixtures that ~10 test files each re-declare into
  `tests/conftest.py`, and a shared `ParamElemFamily → (caption, class, spec)` reader for the two loops
  in `modify_family.inventory_family` / `rvt_to_ifc._family_param_defs`.

## Findings / honesty notes
* `ParamDefYesNo` (base `ParamDefCombo` in the 2026 schema) is **not** given a class rule here: our
  generator authors no Yes/No family parameter today and this clone has no Revit-born family to read the
  carrier off a real row, so adding `→ m_int` would be an unverified guess that also changes
  `modify_family`'s parse behaviour (outside this issue's "no behaviour change there"). It keeps
  resolving by spec (→ `m_value`, a filled `m_str` still wins) exactly as before. When a Yes/No parameter
  is first authored or a sample row is decoded, it is a one-line addition in `param_carrier.py`.
* Validator/tests green is necessary, not certification (rule 4); no cell's honest status moves — the
  rvt → ifc cell was and stays `works` on our own output, PROOF-ONLY stamps unchanged.
* `tests/test_convert.py`'s two rvt → ifc cases self-skip in a fresh clone (they need the regenerable
  acceptance `.rvt`); the new file covers the same contract sample-free and rides in the shard.

## Open questions
None for this issue.

## BRANCH STATE
* Branch `cam/355-rvt-to-ifc-param-carrier` from `main` @ ec62a06.
* Files: `src/rvt/convert/param_carrier.py` (new), `src/rvt/convert/rvt_to_ifc.py`,
  `src/rvt/convert/modify_family.py`, `src/rvt/frontdoor/matrix.py`, `docs/product/PERMUTATION-MATRIX.md`,
  `tests/test_rvt_to_ifc_param_carrier.py` (new), `tests/ci_shard.d/355-rvt-to-ifc-params.txt` (new),
  `docs/inbox/rvt-to-ifc-param-carrier.md` (new), `plugin/lib/src/rvt/convert/{param_carrier,rvt_to_ifc,modify_family}.py`
  + `plugin/lib/src/rvt/frontdoor/matrix.py` (regenerated mirrors).
* Shipped in the PR: all of the above. Staged for a viewer round: nothing (no writer change).
* Gates: as listed under Evidence; `/simplify` and `/verify` run before the commit (results in the PR body).
