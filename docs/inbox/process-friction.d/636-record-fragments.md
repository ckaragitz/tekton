# 636-record-fragments -- parallel PRs stop colliding at shared EOFs (process-friction stream, eng #636)

**Issue:** #636 (Refs #328, #56). **Date:** 2026-08-11. **Session:** eng #636 (cloud, `cse_012EJobpzoZSHnDvfDqk7vCT`).
This file is itself the first fragment written under the convention it introduces (index: `docs/inbox/process-friction.md`).

## Why

On 2026-08-11 (tech-lead log on #56, waves 29-31) five assembly-lane / famgen PRs each needed one or two keep-both
rebases although their content never conflicted: they all appended to the same ends of file --
`docs/inbox/ifc-assembly-rfa.md` (#583 → #626 → #627 → #632 → #635), `docs/inbox/family-standards.md` (#629 vs #633),
`docs/inbox/shard-docs-audit.md` (#594/#598/#600/#606/#618) and `tests/test_ifc_assembly.py`. Each rebase = one
engineer round-trip + one sandboxed CI re-run (~7 min) + other verdicts going stale under the freshness rule; #627 and
#635 were each blocked twice. #328 removed the identical collision for `tests/ci_shard.txt` with drop-in files; this
applies the same shape to records and to per-surface tests.

## What landed

1. **`docs/inbox/README.md` (new) -- the convention.** A record is either `docs/inbox/<stream>.md` (unchanged, nothing
   migrated) or that file kept as a short index plus one fragment per PR, `docs/inbox/<stream>.d/<issue>-<slug>.md`,
   never appended to by anyone else; preferred as soon as a second PR feeds a stream. Fragments carry their own
   `BRANCH STATE`; `learned-*.md` notes stay where they are.
2. **`CLAUDE.md` -- three sentences in §4 plus one clause in §3's map** (the auto-loaded guide; diff kept minimal;
   the §3 clause was authorised by the tech-lead review of #643 to remove a stale "one record per workstream" reading):
   * "The PR **must** include the stream record ..." now reads `(docs/inbox/<stream>.md, or your own fragment
     docs/inbox/<stream>.d/<issue>-<slug>.md — either way with its closing BRANCH STATE)`;
   * "**Every stream writes `docs/inbox/<stream>.md`**" became "**Every stream writes a record in `docs/inbox/`** —
     `docs/inbox/<stream>.md`, or, as soon as more than one PR feeds the stream, that file kept as the index (existing
     text left as is) plus one fragment per PR ... (preferred; the convention and its small law live in
     `docs/inbox/README.md`, #636)" -- "existing text left as is" spelled out after review so nobody reads it as
     "trim the old record" (DONE 4: no migration);
   * one sentence appended to the CI-shard drop-in paragraph: tests for a shared surface go in a new module
     `tests/test_<surface>_<issue>.py` (+ drop-in) instead of being appended to a large shared file, unless the PR
     genuinely edits existing tests;
   * §3 map: "`docs/inbox/` — one record per workstream (see §4)" → "the workstream records — one file, or an index +
     per-PR fragments (see §4)".
3. **`.github/pull_request_template.md`** -- the *Stream record* line names the fragment form first (preferred) and the
   single file second, and points at the README.
4. **`tests/ci_shard.d/README`** -- a paragraph "the same trick for the tests themselves" with the
   `tests/test_<surface>_<issue>.py` naming and the reuse-fixtures-through-conftest note.
5. **`tests/test_ifc_assembly.py`** -- a five-line `#` header comment above the module docstring: do not append here,
   create `tests/test_ifc_assembly_<issue>.py` + drop-in. Comment only; 90 tests still collect, none changed.
6. **`tests/test_records_layout.py` (new, 4 tests, 0.06 s) + `tests/ci_shard.d/636-records-layout.txt`.** The law is a
   pure function over inbox-relative *names*, `violations(names) -> [lines]` (the `check_portable_paths.check(paths)`
   shape, so a merge-time names gate can host it later without a rewrite), plus a ten-line `os.walk` gatherer
   `inbox_names(dir)`: every direct `<stream>.d/*.md` child must match `^[0-9]+-[A-Za-z0-9][A-Za-z0-9_.-]*\.md$`
   (issue number, dash, the same portable slug class as `shard_list.DROPIN_NAME`) and every `<stream>.d/` holding files
   needs `<stream>.md` beside it. Pinned three ways: the real `docs/inbox` (asserting this very fragment and its index
   are among the walked names, so the green verdict is not vacuous); one planted `tmp_path` tree that is lawful first
   (single files, fragments, a non-`.md` attachment, the existing `results/` shape, a file literally named
   `notes.d.md`, a deeper `deep.d/sub/free-form.md` that is deliberately not judged) and, after planting
   `shared.d/appendix.md` + `orphan.d/636-x.md` into the same tree, reports exactly those two breaches; and two
   parametrised pure-name rows (no number first; number without a portable slug: `636.md`, `636-.md`, `636-bad name.md`).
   /simplify pass applied: dropped a Windows-only skip guard and a colon fixture, three redundant table rows, the
   `str()`-returning planter, and a README-exists assertion the README itself called "not enforced".
7. **`tests/test_ci_fresh.py` -- one registry line, the documented way out.** The new shard file names `docs/inbox` as
   a path (it walks it), so #528's static meta-test `test_SHARD_READS_covers_every_docs_path_the_ci_shard_reads` must
   be told whether that is a *read* (widen `SHARD_READS` -- which would make every record-only merge stale every
   in-flight verdict, the opposite of this issue) or a *naming* (`NAMES_NOT_READS`, "saying why", still held to what
   it hands to `open()`). It is a naming: `"tests/test_records_layout.py": "the record-layout law (#636): walks
   docs/inbox for file NAMES, judges them, opens none"`. Control run: with that line deleted the meta-test goes red
   naming the new file; restored, `tests/test_ci_fresh.py` = 23 passed, 2 skipped (gawk/busybox absent here). This
   line is the one edit outside the issue's enumerated territory; the alternative that stays inside it (spelling the
   directory through `conftest.AUDITED_DIR` so the scanner cannot see it, as `tests/test_docs_read_audit.py` does for
   its fixtures) was rejected in the /simplify pass as evasion rather than a recorded decision.
8. **`tools/dev/coord.py` / `tools/dev/techlead.py` -- untouched, by evidence.** `grep -n inbox tools/dev/*.py`: coord.py
   has no hit; techlead.py's only record logic is `recent_records()` =
   `git log --since=14.days --name-only -- docs/inbox` (line 972), a *directory* pathspec that already lists
   `docs/inbox/<stream>.d/<n>-<slug>.md` paths (verified below). Nothing hard-codes `<stream>.md`.

## Evidence

* `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_records_layout.py tests/test_docs_read_audit.py tests/test_shard_list.py tests/test_techlead.py tests/test_coord.py -q -rs`
  → **81 passed, 1 skipped** (the docs-audit self-test reader, skipped by design) in 4.1 s.
* `python3 tools/dev/shard_list.py --print | grep -c records_layout` → **1**.
* `python3 tools/dev/check_portable_paths.py` → `ok: 3018 tracked paths are portable` (3013 before; the `.d` directory
  and fragment names pass).
* `.venv/bin/python plugin/scripts/validate_plugin.py` → `RESULT: PASS` (25 assertions; nothing under `plugin/` touched).
* `python3 tools/dev/techlead.py brief` → in this sandbox the GitHub API answers 403 (no token), so the brief exits at
  its first API call exactly as on `main`; the offline banner `techlead.py hello` prints its 4 lines; and the one piece
  of the brief this change could affect, `recent_records()`' `git log --since=14.days --name-only -- docs/inbox`, run
  after the commit, lists `docs/inbox/process-friction.d/636-record-fragments.md` and `docs/inbox/process-friction.md`
  (entries 177/178 of 263 distinct records touched in 14 days). Pre-existing and unrelated to shape: the function then
  keeps `sorted(...)[:30]`, i.e. the alphabetically first 30, so today the brief's "records touched" line ends at `c…`
  for single files and fragments alike -- noted on the follow-up issue #638, not changed here (`tools/dev/` is off-territory).
* `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_ci_fresh.py -q -rs` → 23 passed, 2 skipped (see item 7 for
  the red control without the registry line).
* Whole merged shard on the rebased head (`pytest -q -- $(python3 tools/dev/shard_list.py --print)`, `RVT_SKIP_LARGE=1`) → **2191 passed, 134 skipped, 3 xfailed in 490 s**; the session-end docs-read audit stayed silent (the law opens nothing under `docs/`).

## Findings / judgment calls the reviewer should weigh

* **The law reads names, never contents**, so it is deliberately *not* a `SHARD_READS` reader (item 7). The residual
  hole: `tools/dev/ci_fresh.sh` re-judges the *post-merge name set* only through `check_portable_paths.check()`, so a
  PR that renames/deletes an index while `main` docs-only-adds a fragment under it (or a PR whose verdict predates this
  law adding a mis-named fragment) can still meet on `main` red. Hosting `violations()` in that names gate closes it
  with no `ci_fresh.sh` change -- `tools/dev/` is outside this issue's territory, so it is filed as follow-up #638; the
  function already has the shape that move needs. No branch on `origin` carries a `docs/inbox/*.d/` path today
  (`git ls-tree` over every remote branch: zero hits), so nothing in flight can trip the new law.
* `.github/prompts/worker.md` (step list) and `docs/process/AUTONOMY.md`'s artefact table still say
  `docs/inbox/<stream>.md` only. Both stay *true* (the single file remains valid) and both are outside this issue's
  territory; the wording sync rides on the same follow-up #638 rather than widening this PR.

## Open questions

* Should the index line per fragment be law too (index mentions every fragment)? Left as convention: making it law
  would put the shared index back on every PR's critical path, which is the collision this removes.

## BRANCH STATE

* Branch `cam/636-record-fragments`, cut from `origin/main` @ ca74895, rebased onto 6d95f32 (#633) before review;
  PR #643, `Closes #636`; review 🟡 nits @ 41bc442 answered by one wording-only commit (N1–N3 + the two optionals).
* Files: `CLAUDE.md` (3 sentences in §4 + 1 clause in §3), `.github/pull_request_template.md` (record line), `tests/ci_shard.d/README`,
  `docs/inbox/README.md` (new), `docs/inbox/process-friction.md` (new index), this fragment,
  `tests/test_records_layout.py` (new) + `tests/ci_shard.d/636-records-layout.txt`, `tests/test_ifc_assembly.py`
  (header comment only), `tests/test_ci_fresh.py` (one `NAMES_NOT_READS` registry line). No engine, tools, plugin,
  workflow, TRACKER/KNOWLEDGE or other-record changes.
* Follow-up filed: #638 (`Refs #636`) — host `violations()` in the merge-time names gate + sync the two remaining
  `docs/inbox/<stream>.md`-only wordings (`.github/prompts/worker.md`, `docs/process/AUTONOMY.md`).
* Gates: above. `/verify` skipped with a `No-Verification-Needed:` trailer (process docs + a test; no runtime surface).
* Nothing staged for the viewer; no certification claim.
