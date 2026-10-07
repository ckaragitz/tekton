# 1037 — the ExtrusionGStep history, measured in both directions

Stream **family-geometry** (tech-lead session, 2026-10-07). Refs #1037. It also carries #1036's and #1035's review nits.

## The measurement (private corpus, every third file, counts only)

#1030 changed only the cached solid's cap tags. The form's `ExtrusionGStep` history had not been compared with born End-above-Start extrusions. Measured now:
- **Face history:** tag 0 → `[2,-1,-1]` (the End cap) and tag 1 → `[1,-1,-1]` (the Start cap), in **745 / 745** extrusions. Of these, 655 have End above Start and 90 below.
- **Edge history:** tag 3 → `[1,i,0,-1]` and tag 4 → `[1,i,1,-1]` in every extrusion read, both directions. `i` is the loop's first curve.

With #1030's solid law (the `[1,i,0]` rail bounds the cap at the higher offset), a born End-above-Start extrusion therefore has:
- its rail tag 3 on the End cap, tag 0;
- face key 2 on tag 0.

That is exactly what `extrusion_gstep` writes for an `end_on_top` form. **No code change.** The `solid_box_brep` docstring now cites the measurement instead of "not compared".

## Carried review nits

**#1036's review:**
- `tests/test_cap_tags_1030.py` now requires named makers to build **and** carry cap locks. Before, any build that raised was skipped as long as 50 rows remained. The makers are the panelboard, transformer, troffer, downlight, device, fan coil, strut trapeze and lighting control panel. The floor is now 200 locks: 179 + 21.
- The #1030 record names the 4 locks that were already on their plane (the trapeze's true-cylinder rods) and counts the troffer / downlight / device / fan coil locks.
- One long docstring line is wrapped.

**#1035's review:**
- `famdoc_adoc.is_release_schema_constant`: a file that declares a release we hold no constant for, such as a future year, is not judged constant. Only an *undetected* release falls back to the pin.
- `standards.apply_safe`: a bare-string `skip="Frequency"` is one name, never its characters. It is normalised before `apply()` sees it too.
- `filled_from_facts` matched by meaning: there is now a test with an alias-spelled fact table ("Rated Frequency").

## Evidence

- `tests/test_standards_facts_863.py`, `tests/test_cap_tags_1030.py` and `tests/test_provenance_releases_864.py`: **36 passed**.
- `test_famgen_standards`, `test_famgen_factory`, `test_plugin_sync`, `test_matrix_evidence_984`, `test_matrix_evidence_981`, `test_conftest_scaffolding`, `test_standards_apply_safe`, `test_rvt_analyze` and `test_readers_own_release`: **303 passed, 6 skipped**.
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/{geometry,standards,famdoc_adoc}.py` and their plugin mirrors;
  - `tests/test_{cap_tags_1030,standards_facts_863,provenance_releases_864}.py`;
  - `docs/inbox/family-geometry.d/1030-cap-tags.md`;
  - this record.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
