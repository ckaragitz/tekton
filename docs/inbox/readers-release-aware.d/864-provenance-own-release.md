# 864 — the provenance instruments read a 2024 / 2025 family in its own release

Stream **readers-release-aware** (tech-lead session, 2026-10-06). Closes #864, including the second problem added to it from #939's review.

## The two defects, reproduced on main (`900b932`)

A 45 kVA transformer was built for 2026, 2025 and 2024.

- **Defect 1: the CLI cannot read a 2024 / 2025 family.** `tools/make_family.py provenance` on the 2025 file: `factory refused the job: unexpected Partitions header: v=9 cls=0x391`. On the 2024 file: `… cls=0x37b`. The same class as #700: the file was read under the built-in 2026 framing constants.
- **Defect 2: the v2 ledger judges by the wrong release.** `famdoc_adoc.provenance_scan_v2`, run under `enter_own_release` on the 2025 file, returns `ok=False` on `formats_latest_is_format_constant`. Its Formats/Latest was compared with the 2026 pin, which only a write's release context swaps.
- **`tools/rvt_analyze.py --provenance`:** `ok False` on the 2025 and 2024 files, through defect 1's library call.

## What changed

- **`famdoc_adoc.in_own_release(scan)`** runs a provenance scan inside the file's own release (`global_framing.enter_own_release`, nest-safe inside a write's release context). A rung other than the file's own schema is reported as `release_note`.
  - `provenance_scan_v2` is wrapped with it.
  - So is `factory.provenance_scan`; its body is now `_provenance_scan`, unchanged apart from the check below.
- **`famdoc_adoc.is_release_schema_constant(fmt_sha, bfi)`.** Formats/Latest is judged against the schema constant of the release the file's own `BasicFileInfo` declares (`versions.KNOWN_RELEASES`), compared in full rather than by an 8-character prefix. A file whose release is not detected falls back to the pin in force.
  - Both scans use it.
  - The factory report's note now says the class map is identical "in every file of the release its BasicFileInfo declares", where it used to say "every Revit 2026 file".
- `src/rvt/versions/` (a hot file) is untouched: only its existing `detect_release_from_bfi` and `KNOWN_RELEASES` are read.

## Evidence

- **`tests/test_provenance_releases_864.py`, plus the #707 scaffolding check: 36 passed** (the scaffolding module grew on main). It covers:
  - the CLI on the 2026, 2025 and 2024 transformer: rc 0, `ok: true`, Formats/Latest constant true;
  - `provenance_scan_v2` on each: `ok` and the constant check true;
  - `is_release_schema_constant`: a 2025 schema in a 2025 file is true, a 2026 schema in a 2025 file is false, an empty one is false.
- **Every module that runs a provenance scan or the CLI** (8 modules) plus `test_plugin_sync`: **292 passed, 24 skipped**.
- **DONE 3, the CLI sweep:**
  - `make_family.py provenance`: fixed (above).
  - `rvt_analyze --provenance`: was `False` on main for 2025 and 2024; now `True`, through the same library call.
  - `rvt_validate`: VALID on all three releases, unchanged.
  - `family_anatomy profile`: already release-aware (#842), and reads all three with `framing_fallback` 0.
  - `tools/provenance.py`: the project-baseline tool. It reads 2026, 2025 and 2024 with identical totals (691 unbaselined, no framing complaint); rc 2 is its findings code on all three, because a bare family has no baseline.
- **Cost:** a panelboard write's median goes from 0.233 to 0.240 s (6 writes each, same machine). The own-release entry is about 7 ms, within noise.
- `tools/sync_plugin.py --check`: clean.

## Also in this PR: the 🟡 nits of #1031's final review (#863)

- **`skip=` in `standards.apply_safe(facts=)`** names a table row exactly, as `apply()` reads it. A skip spelled by an alias (`"Rated Frequency"`) no longer withholds the fact while `apply` still authors the slot.
- **`filled_from_facts`** matches the table's own spelling by meaning. A row named by an alias still reports its fact's provenance.
- **Records:**
  - #863's BRANCH STATE names the `matrix.py` mirror;
  - #863's transformer row lists every no-fact blank;
  - #877's retroactive BRANCH STATE says "where mirrored" and names `876-map-proposal.md`.
- **Test:** `tests/test_standards_facts_863.py` gives **21 passed** (+1).

## BRANCH STATE

- Files:
  - `src/rvt/famgen/famdoc_adoc.py`, `src/rvt/famgen/factory.py` (`provenance_scan` → wrapper + `_provenance_scan`) and their plugin mirrors;
  - `tests/test_provenance_releases_864.py` and the drop-in `tests/ci_shard.d/864-provenance-releases.txt`;
  - the #1031 nits: `src/rvt/famgen/standards.py` (and its mirror), `tests/test_standards_facts_863.py`, the #863 and #877 records;
  - this record.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
