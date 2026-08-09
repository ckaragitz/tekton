# FAMGEN-CI — the downlight verb emits a VALID `.rfa` again, and the famgen suites run per-PR (issue #161)

Stream: **famgen-ci** (2026-08-09, issue #161, branch `cam/161-famgen-luminaire-ci`,
engineer session `eng161` started by the tech-lead session's fan-out).

Charter (issue #161, Refs #108 / #102, PG3): a documented CLI verb —
`tools/make_family.py luminaire --kind downlight` — crashed with
`TypeError: cylinder() got an unexpected keyword argument 'segments'`, and nothing
in CI could notice: every famgen *composition* test self-skipped on a fresh clone /
CI because its `HAVE_SCHEMA` gate predated the bundled-schema fallback (#44), and no
`test_famgen_*` file was in `tests/ci_shard.txt`.

**DONE (the issue's four bullets):** (a) the downlight verb exits 0, family-mode
VALID, provenance ok; (b) the factory / skeleton / geometry / adoc famgen suites
compute `HAVE_SCHEMA` as "`rvt.schema.load_schema()` succeeds", so composition runs
without `extracted/` or `vendor/`, plus a new test that composes + writes all four
kinds; (c) `test_famgen_factory.py` + `test_famgen_catalog.py` in the CI shard,
shard < 10 min; (d) `tools/sync_plugin.py --check` clean after the fix.
Wording throughout is "validates in family mode, provenance clean" — no file here is
claimed to load in Revit (hard rule 4); nothing was staged for the viewer.

---

## 1. The crash and its fix (`src/rvt/famgen/factory.py`, `make_luminaire`)

`make_luminaire(kind="downlight")` built the housing can with
`G.cylinder(L/2, Hh, ctx, doc.ids, ..., segments=4)`.  `geometry.cylinder`
(the true two-half-arc `CylSurf` cylinder, `geometry.py:2178`) takes no `segments`;
the inscribed 4-gon prism that does is `geometry.polygon_cylinder`
(`geometry.py:1358`, "kept from the first delivery; `cylinder` is the true
arc-profile cylinder now").  The call site — its `segments=4` kwarg, its
`"downlight housing can (polygonal approximation)"` role string and the product note
`"housing = OUR polygonal can …; the true curved profile is phase 2"` — predates that
split and was never moved to the new name.

Fix: call `G.polygon_cylinder(...)`.  That is the smallest change that restores the
composition the code and its notes describe, and it is why the second half of DONE
(a) needs no new code: the 4-gon prism is built by the same `prism_form` as a box, so
its geometry-history tags are `_box_tags(4)` and `box_face('top')` (start cap, tag 1,
edge tags `[3, 6, 10, 14]`) / `add_connector(face='top')` address the can's top cap
exactly as they address a box's.  Deliberately **not** done here: switching the
downlight to the true `G.cylinder`.  That would be a behaviour change to a shipped
family (a `CylSurf` B-rep on a from-scratch family; a different cap/edge tag map —
top = end cap tag 0, edges `[3, 6]` — that `box_face` does not model), i.e. its own
single-variable step with its own evidence, not a crash fix.

Result, fresh cloud clone, `.venv/bin/python tools/make_family.py luminaire --kind downlight -o out/d.rfa --json`:

| | before | after |
|---|---|---|
| exit | 1 (`TypeError … 'segments'`, `factory.py:1204`) | **0** |
| `validate.family_mode` | — | **VALID, 0 errors / 0 warnings** (info 2) |
| `provenance.ok` / checks | — | **true, 11/11**, `suspects == []` |
| family | — | "Recessed Downlight 6in aperture", Lighting Fixtures, 39 elements, 1 connector, type `6in 3500K`, form `cylinder(polygon)` 0.3125 × 0.3125 × 0.625 ft, rep solid |
| file | — | 217,088 B, `container_mode: bundled-base` |

Independent re-checks on the same file: `tools/rvt_validate.py --family out/d.rfa`
→ `verdict: VALID (no errors); warnings=0 info=2`; `tools/make_family.py provenance out/d.rfa` → `"ok": true`.

All four advertised kinds after the fix (same clone, CLI, `--json`):

| verb | exit | family_mode | provenance | elements | bytes |
|---|---|---|---|---|---|
| `panelboard` | 0 | VALID 0/0 | ok 11/11 | 45 | 217,088 |
| `transformer` | 0 | VALID 0/0 | ok 11/11 | 43 | 217,088 |
| `luminaire --kind recessed-troffer` | 0 | VALID 0/0 | ok 11/11 | 39 | 217,088 |
| `luminaire --kind downlight` | 0 | VALID 0/0 | ok 11/11 | 39 | 217,088 |

**Determinism (report only — #168 owns it):** two back-to-back downlight runs with
identical arguments differ (sha256 `4eced8ca…` vs `634c8b48…`, 7,598 differing bytes,
first at offset 8825).  Per stream: `BasicFileInfo` (1905 vs 1909 B), `Contents`,
`Global/History` (130 vs 134 B), `Global/PartitionTable`, `PartAtom`, `Partitions/0`
(7638 vs 7646 B) differ; `Formats/Latest`, `Global/Latest`, `Global/ElemTable`,
`Global/ContentDocuments`, `Global/DocumentIncrementTable` are identical — i.e. the
per-save identity (document GUID / episode / timestamp-bearing streams), not the
family content.  Not touched here.

## 2. The gates that hid it (`tests/test_famgen_{factory,skeleton,geometry,adoc}.py`)

`HAVE_SCHEMA` was `exists(extracted/racbasicsampleproject/Formats__Latest.gz/000.bin) or exists(vendor/…/racbasicsamplefamily-2026.rfa)`
— both git-ignored research inputs — while the code under test gets its schema from
`rvt.schema.load_schema()`, whose default-path call falls back to the sha-pinned
bundled genesis base's own `Formats/Latest` (#44).  Each of the four files now
computes

```python
def _have_schema() -> bool:
    try:
        from rvt.schema import load_schema
        load_schema()
        return True
    except Exception:
        return False
```

(one probe per file, kept local to the territory; `load_schema` is memoized by
content sha since #183, so the probe costs one parse per process and the tests reuse
it).  Tests moved onto that gate are exactly the ones whose only dependency is a
schema — verified by forcing every gate open in scratch copies on this sample-less
clone and keeping only what passed with **unchanged expectations**:

* `test_famgen_factory.py`: the six composition tests (already `needs_schema`) now
  run; `test_panelboard_rfa_verifies_validates_and_is_provenance_clean` moves from
  `needs_rfa` (`HAVE_RFA and HAVE_SCHEMA`) to `needs_schema` — it writes from the
  bundled base and itself asserts `container_mode == "bundled-base"`, so the sample
  `.rfa` was never a dependency; the now-unused `RFA` / `HAVE_RFA` / `needs_rfa`
  constants are removed.  **New:** `test_every_kind_writes_a_family_mode_valid_provenance_clean_rfa[panelboard|transformer|troffer|downlight]`
  composes each advertised kind, writes it to `tmp_path`, and asserts read-back ok,
  family-mode `VALID` / 0 errors, `provenance.ok`, no suspects, every provenance
  check true, size > 100 kB.  The downlight case is the regression test for §1.
* `test_famgen_skeleton.py`: the four whole-document tests (`needs_schema`) now run;
  the byte-exact specimen reconstructions and the `to_rfa` emissions keep
  `needs_rfa` / `needs_rme` (they read the samples — confirmed failing without them).
* `test_famgen_geometry.py`: gains `HAVE_SCHEMA` / `needs_schema`;
  `test_box_bundle_schema_roundtrip[solid|dummy]`,
  `test_plate_and_polygonal_cylinder_roundtrip`, `test_solid_cylinder_brep_structure`,
  `test_cylinder_bundle_schema_roundtrip[solid|dummy]` move from `needs_rfa` to
  `needs_schema` (they build bundles against `ctx`, which already falls back to the
  from-scratch `FamilyDocContext()` when the sample is absent, and round-trip through
  the schema).  Specimen reproductions and donor-splice emissions keep `needs_rfa` /
  `needs_rme`.
* `test_famgen_adoc.py`: gains the probe; `test_inventory_of_our_document` moves from
  `needs_stack` to `needs_schema` (it inventories our own S0e document, no archetype
  read).  Everything using `author_family_adocument` / the archetype keeps its gate.

Fresh cloud clone (no `samples/`, `extracted/`, `vendor/`), `.venv/bin/python -m pytest tests/test_famgen_<f>.py -q -rs`:

| file | before | after | remaining skips |
|---|---|---|---|
| `test_famgen_factory.py` | 12 passed / 12 skipped | **23 passed / 5 skipped** (4 new) | 5 × rme/rst sample |
| `test_famgen_skeleton.py` | 1 / 13 | **5 / 9** | 6 × sample .rfa, 3 × rme |
| `test_famgen_geometry.py` | 6 / 13 | **12 / 7** | 5 × rfa sample, 2 × rme |
| `test_famgen_adoc.py` | 7 / 12 | **8 / 11** | 11 × archetype .rfa (+assembler) |
| `test_famgen_catalog.py` | 28 / 0 | 28 / 0 | — |

No previously-passing test changed behaviour and no expectation was edited; every
remaining skip reason names a sample file.

## 3. The shard (`tests/ci_shard.txt`)

`tests/test_famgen_factory.py` and `tests/test_famgen_catalog.py` appended (+51
tests).  Measured on this cloud VM: the two files run in 1.3 s + 0.05 s; the whole
shard (`grep -vE '^\s*(#|$)' tests/ci_shard.txt | xargs pytest -q`) =
**736 passed / 43 skipped / 1 xfailed in 2 min 15 s** once the plugin mirror was
regenerated (before the sync the only red was `test_plugin_sync` on the stale
`plugin/lib` copy of `factory.py`, as expected).  CI wall time for the shard from
this PR's run is quoted in the PR.

## 4. Gates run

```
.venv/bin/python -m pytest tests/test_famgen_{factory,skeleton,geometry,adoc,catalog}.py -q -rs   # table in §2
.venv/bin/python -m pytest tests/test_plugin_sync.py -q          # 7 passed
.venv/bin/python tools/sync_plugin.py                            # synced 1 file (plugin/lib/src/rvt/famgen/factory.py); deny-audit clean; validation passed; zip rebuilt
.venv/bin/python tools/sync_plugin.py --check                    # plugin in sync with source
.venv/bin/python plugin/scripts/validate_plugin.py               # 24 assertions, RESULT: PASS
python3 tools/dev/check_portable_paths.py                        # ok: 2750 tracked paths are portable
.venv/bin/python tools/rvt_validate.py --family out/{d,p,x,t}.rfa  # VALID 0 errors each
.venv/bin/python tools/make_family.py provenance out/{d,p,x,t}.rfa # ok: true each
```

The full suite was not run (SUITE-COORDINATION).

## 5. Follow-ups

* The true curved can (`G.cylinder` + a cylinder face map for `add_connector`) is a
  product step, not a fix — file when the downlight's geometry matters to a user; it
  needs its own family-mode + provenance evidence and, for any "loads" claim, a
  staged viewer batch.
* Byte-level determinism of `make_family` output: #168 (streams listed in §1).

## BRANCH STATE

* Branch `cam/161-famgen-luminaire-ci` from `main` @ dc0980f; PR closes #161.
* Files written: `src/rvt/famgen/factory.py` (downlight can → `polygon_cylinder`),
  `plugin/lib/src/rvt/famgen/factory.py` (regenerated by `tools/sync_plugin.py`,
  not hand-edited), `tests/test_famgen_factory.py` (schema probe, delivery re-gate,
  new four-kinds test), `tests/test_famgen_skeleton.py`,
  `tests/test_famgen_geometry.py`, `tests/test_famgen_adoc.py` (schema probe +
  re-gates), `tests/ci_shard.txt` (+2 lines), this record.
* Gates: §4, all green locally.
* Nothing staged for the viewer; no `.rvt`/`.rfa` committed; no ledger change;
  `tekton-plugin.zip` regenerated locally, not committed.
