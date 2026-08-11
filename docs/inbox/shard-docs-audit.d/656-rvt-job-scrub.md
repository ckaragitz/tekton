# 656-rvt-job-scrub -- `tools/rvt_job.py::scrub_identity` (the edit lane's in-place BasicFileInfo rewrite of the job's own output) is `rewrite_entries(path, path, {"BasicFileInfo": own_basic_file_info(…)})`, byte-identically on the three pins (shard-docs-audit stream, eng #656)

**Issue:** #656 (filed by eng #646's reuse pass; Refs #646 / PR #661, #657 / PR #672, #640). **Date:** 2026-08-11.
**Session:** eng #656 (cloud, `bf5e6254…`), started by the tech-lead session. **Base:** `main` @ `345493c` (#669; #672
`own_streams` and #661's in-place `rewrite_entries` both merged) for every measurement below. Index:
`docs/inbox/shard-docs-audit.md` (left untouched -- the README makes the index line optional and that EOF is the hot spot
#636 exists to avoid). Written in this engineer's voice; no other record edited.

## Why

#646 / #661 folded the engine's ten `read_entries → dataclasses.replace → write_cfb` loops onto
`rvt.roundtrip.rewrite_entries` and gave that pass an atomic in-place path (sibling `mkstemp` + `copymode` + `os.replace`,
temp removed on any error, a read-only file refused with `PermissionError` before any temp exists). One hand-rolled copy
was left **outside `src/rvt/`**: `tools/rvt_job.py::scrub_identity(path, *, document_guid=None)` -- run by `rvt_job.py edit`
/ the front door's `--rvt … --edit` lane after `commit_plans` (which never touches `BasicFileInfo`) whenever the ops are
manipulate-only (`add-*` ops go through `commit_new_elements`, which already owns the identity block). It read the entries,
swapped `BasicFileInfo` through `rvt.identity.own_basic_file_info`, wrote `path + ".idtmp"` and `os.replace`d it -- no mode
copy, no temp cleanup (a dying write left `<out>.rvt.idtmp` beside the deliverable), its own `RuntimeError` for a missing
stream. Gate G2 (PG5) wants ONE identity path; #656 folds this last copy.

## What `scrub_identity` touches -- and why the fold uses `own_basic_file_info`, not `own_streams`

`scrub_identity` touches exactly ONE stream: `BasicFileInfo` (author / client := the product placeholder
`PRODUCT_AUTHOR_PLACEHOLDER`, username `""`, save path := the output's basename, central path `""`, Unique Document GUID
and central episode GUID := `document_guid` -- the lane hands it `History[0]` (`rvt.stream_encoders.history_head_guid`)
so the GUID pairing the validator checks holds; `None` mints a fresh uuid4 -- format/build/locale kept). It does **not**
touch `PartAtom`, `Global/History`, `ProjectInformation`, `TransmissionData` or `Global/DocumentIncrementTable` -- nothing
beyond what `own_streams` covers; if anything *less* (no increment table). So there was nothing extra to keep.

`rvt.identity.own_streams(doc, out_path, identity=…, keep_document_guid=True)` (#672) wraps the same primitive but with a
different contract: it takes an OPEN document (a second open of the file), and it **never raises** -- a missing or
undecodable `BasicFileInfo` is left out with a `warnings.warn`, which through `rewrite_entries` would mean "file rewritten
unchanged, scrub reported done". `scrub_identity`'s contract on `main` is the opposite: a missing stream is an error
("identity not scrubbed") and a decode failure propagates -- the job's `_failed` line then says so. The bytes are the same
either way (both end in `own_basic_file_info(raw, out_path=path, document_guid=…)`); the error contract is not. So the fold
calls the primitive `own_streams` wraps, directly, inside `rewrite_entries`' replace map -- one read, one write, main's
error contract kept:

```python
def scrub_identity(path, *, document_guid=None):
    from rvt.identity import BFI_STREAM, own_basic_file_info
    from rvt.roundtrip import rewrite_entries
    try:
        rewrite_entries(path, path, {BFI_STREAM: lambda raw: own_basic_file_info(
            raw, out_path=path, document_guid=document_guid)})
    except KeyError as exc:
        raise RuntimeError("BasicFileInfo stream not found; identity not scrubbed") from exc
    return {"scrubbed": True, "document_guid": document_guid}
```

`git grep -n "write_cfb\|read_entries" -- tools/rvt_job.py`: **3 → 0** (`write_cfb(` 1 → 0; the `rvt.cfb_writer` /
`rvt.roundtrip.read_entries` imports gone; `.idtmp` gone). `import dataclasses` stays: `_jsonable` (the manifest's JSON
default hook) uses `dataclasses.is_dataclass` / `asdict`. Signature, return value and every caller unchanged
(`_cmd_edit`'s `scrub_identity(out_path, document_guid=hist0)`; `tools/frontdoor.py` does not call it -- it reaches it only
through `rvt.frontdoor.edit` → `rvt_job._cmd_edit`; `tests/test_partition_header_verdict.py` monkeypatches it by name).

## Evidence

### (2) Byte identity -- every documented use, three pins, before (main's loop, twice) == after (the API)

Harness (scratch, not committed): per pin -- foreign pins (2025, 2024) first and under their own release context
(`enter_host_release`), native last -- three uses: **direct** = `scrub_identity(copy_of_pin, document_guid=FIXED)`;
**job** = `rvt_job.py edit <pin> --ops '[{"op":"set-level","id":1351691,"elevation_ft":5.0}]' -o out.rvt --no-provenance`
(manipulate-only → the lane's `scrub_identity(out, document_guid=History[0])`); **fd** = `rvt.frontdoor.author(rvt=<pin>,
edit="set level 1351691 elevation to 5 ft")` (the `--rvt --edit` route, same lane). sha256 of the output `.rvt`; "before"
run twice on the untouched tree to prove the rows are deterministic run to run (they are: 9/9), then once on the branch.

| use / pin | main loop (before, 2 runs equal) | rewrite_entries (after) | equal |
|---|---|---|---|
| direct/2024 | `3b58ca880bb6e8331bb8a22465345fdc216e0108d85edc319f451f5a42d08e41` | `3b58ca880bb6e8331bb8a22465345fdc216e0108d85edc319f451f5a42d08e41` | **yes** |
| direct/2025 | `3a5ac6c63c8b885bdcdaf6cd89fdb3558c2e7270029363f186abffc290c509b0` | `3a5ac6c63c8b885bdcdaf6cd89fdb3558c2e7270029363f186abffc290c509b0` | **yes** |
| direct/2026 | `5b5c87b6068c87a22112ed44f444c913b2e6399d23dbcd5782f7c4673eab09b0` | `5b5c87b6068c87a22112ed44f444c913b2e6399d23dbcd5782f7c4673eab09b0` | **yes** |
| fd/2024 | `7cdb4a39d2023968bb277f4c1a73019b3d36165e1557331854c40c23aacde875` | `7cdb4a39d2023968bb277f4c1a73019b3d36165e1557331854c40c23aacde875` | **yes** |
| fd/2025 | `da4560de8574d49183ad731a369693df72ce50c434044611fc877db8d501ed1f` | `da4560de8574d49183ad731a369693df72ce50c434044611fc877db8d501ed1f` | **yes** |
| fd/2026 | `c423489b7dff9fc206fb51032199042418304484d4bfc4501ff549043c2dede8` | `c423489b7dff9fc206fb51032199042418304484d4bfc4501ff549043c2dede8` | **yes** |
| job/2024 | `08c1c57927f05755e114c31df4a00b99beb2bad60ebb16dee1685bdcd5991711` | `08c1c57927f05755e114c31df4a00b99beb2bad60ebb16dee1685bdcd5991711` | **yes** |
| job/2025 | `53cd3bff7261574cfccfb60c87c48a803aa4b2e75600a0fc4d1587b7866fddaf` | `53cd3bff7261574cfccfb60c87c48a803aa4b2e75600a0fc4d1587b7866fddaf` | **yes** |
| job/2026 | `7b5a29b9e102d3014649e12fd3aa6bed14fbd90a98fdf41e9c331e524ec3ec9b` | `7b5a29b9e102d3014649e12fd3aa6bed14fbd90a98fdf41e9c331e524ec3ec9b` | **yes** |

**9/9 equal**, asserted before the old loop was deleted from the tree (the "before" JSONs were taken first).

The flagship prompt job once, `python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out <d>
--json`, on an `origin/main` worktree and on the branch: `ok: true`, route `prompt`, status `PROOF-ONLY (self-checks
PASS; see honesty.proof_only_stamps + status_gate)` both (delivered, stamped -- rule 1); `prompt_room.rvt` `VALID (no
errors); warnings=1` (the known DataStorage decoder-gap warning) both. Its `BasicFileInfo` identity fields main vs branch
are **identical**: author `rvt-writer` (= `PRODUCT_AUTHOR_PLACEHOLDER`), client `rvt-writer`, username `''`, build
`20250227_1515(x64)`, format `2026`, save path `prompt_room.rvt`, central path `''`, locale `ENU`, GUID
`34447475-…` (the base's); the `BasicFileInfo` / `Global/DocumentIncrementTable` / `Global/History` streams are
byte-identical (sha256 `6238f9a1…` / `4369cefc…` / `4b9bea18…` -- the same digests #657 recorded), 9/12 streams equal and
the three that differ are the per-run family-GUID carriers (`Partitions/21`, `Global/ContentDocuments`, `Global/Latest`),
as between any two `main` runs. Honest note: the prompt lane never reaches `scrub_identity` (its identity is
`commit_new_elements`' `own_streams`); this run proves the diff did not disturb the flagship, not that it exercised it --
the edit lane rows above are the exercise.

### (3) In-place behaviour

* **A write that dies mid-way** (test row, `write_cfb` monkeypatched to write half the bytes then `ENOSPC`): the job's file
  is byte-identical to before, the directory holds only it (the sibling temp left with the error), and the bytes were never
  aimed at the file itself. On `main` the same failure left `<out>.rvt.idtmp` (half-written) beside an intact output.
* **Missing `BasicFileInfo`** (test row on a BFI-less copy of a pin): `RuntimeError("BasicFileInfo stream not found;
  identity not scrubbed")` exactly as on `main`, now `__cause__` = the API's `KeyError("no stream 'BasicFileInfo' in …")`,
  raised before a byte is written (file intact, directory clean); `_failed("edit", exc)` -- what the lane prints on stderr
  and stores as the stub manifest's `status` -- reads `FAILED (edit: RuntimeError: BasicFileInfo stream not found; identity
  not scrubbed)`. (The lane itself cannot reach the scrub with such a file: `versions.detect_release` reads `BasicFileInfo`
  at manifest time, long before.) I kept `RuntimeError` rather than letting the bare `KeyError` out because the issue's DONE
  asks that the user-facing line still say "identity not scrubbed" plainly, and `str(KeyError)` is a quoted repr of the
  API's path sentence; the API's error rides along as the cause in the traceback `_failed` writes to the log.
* **A read-only file** -- what `main` did, measured (old loop extracted verbatim, run as `nobody` on a `0444` copy of the
  2026 pin in a writable dir): **it neither raised nor skipped -- it scrubbed the file through the rename and silently
  turned `0444` into `0644`** (new inode, default mode; on Windows the same `os.replace` over a read-only target is an
  `Access denied` *after* the `.idtmp` was written, leaving it behind). The branch inherits `rewrite_entries`' documented
  gate (#661): `PermissionError` before anything is written, file and mode untouched -- pinned by a test row (skipped under
  root, where the OS lets the open through; run here once as `nobody` together with #646's twin row: **2 passed**). This is
  the one behavioural difference of the fold, and it is unreachable from the lane: `_cmd_edit` scrubs `out_path`, the file
  `commit_plans` created itself one step earlier under the process umask. Flagged for the reviewer rather than papered over
  (a `chmod` dance in the tool would re-implement what the API deliberately refuses).
* Mode kept on the happy path: a `0640` copy is still `0640` after the scrub (test row); `main` reset it to the umask default.

### (4) Tests

`tests/test_rvt_job_scrub_656.py` (new, 11 rows: 10 passed / 1 skipped under root) + drop-in
`tests/ci_shard.d/656-rvt-job-scrub.txt` (`shard_list.py --print` lists it, line 114). Rows: in place == the API apart +
OUR identity + `identity_gate` PASS + mode kept + directory clean, per pin (3); no GUID → fresh uuid4 as on main; the
`rvt_job.py edit` lane per pin delivers `identity` gate PASS with GUID == History[0] == the manifest's
`base.history_head_guid`, author the placeholder, no `.idtmp`/`.tmp` left (3); BFI-less → "identity not scrubbed" from
`KeyError`, nothing written, the FAILED line; dying write → intact + clean; read-only → `PermissionError` (skip under
root); no `read_entries` / `write_cfb` / `cfb_writer` / `.idtmp` token left in `tools/rvt_job.py`.

Gate suites (`RVT_SKIP_LARGE=1 … -q -rs`, the brief's list with the files that exist: `test_frontdoor*.py` (5),
`test_bootstrap.py`, `test_identity_helper_657.py`, `test_rewrite_entries_646.py`, `test_records_layout.py`, plus the
issue's `test_edit_own_release.py`, `test_edit_status.py`, `test_rvt_edit_refusal.py`, `test_one_job_module.py` and
`test_partition_header_verdict.py` (it monkeypatches `scrub_identity`)): **268 passed / 7 skipped before → 268 / 7 after**
(same 13 files; skips = `RVT_SKIP_LARGE` ×2, samples absent ×2, root ×2, research-machine ×1); with the new module +
`test_plugin_sync.py` + `test_coldstart.py` added: **303 passed / 8 skipped**. Whole merged shard: see BRANCH STATE.

### `/simplify` (four angles on the diff) -- what it found and what changed

Production side judged clean by all four (reuse: `rewrite_entries` + `own_basic_file_info` + `BFI_STREAM` is the right
reuse and `own_streams` is not a substitute; altitude: the primitive is the established depth for path-level callers --
`tools/genesis_identity.py`, `tools/genesis_addpath_probes.py` call it the same way -- and no `KeyError` can escape today's
`decode`/`encode_basic_file_info` to be mislabelled "stream not found" (fixed-key dicts; corrupt bytes raise
`struct.error`/`IndexError`/`ValueError`), the chained cause covering a future codec change; efficiency: one read, one
write as before, +~6 metadata syscalls). Applied: the docstring no longer restates `rewrite_entries`' in-place contract
(it names the API and its law instead -- that text moved twice already, #646/#661); in the tests `_bfi` reads through
`open_rvt(...).raw` and is decoded once per file, the release context is `host_release_context` (not a hand-rolled
`ExitStack` + `enter_host_release`), the dying-write injector is four lines instead of a copy of #646's `_DiskFull`, the
FAILED-line row asserts the phrase not `_failed`'s exact format, and the "no private loop" tripwire inspects
`scrub_identity`'s own source instead of grepping the whole 1,500-line runner. Skipped, with the reason: dropping the
dying-write and read-only rows as duplicates of #646's (the brief and the issue's DONE ask for exactly those rows through
the tool); moving the now five-fold `pin` fixture / four-fold `_bfi` helper into `tests/conftest.py` (shared file, not this
territory -- noted here as the pattern it has become rather than filed: it is a two-line consolidation for whoever next
touches conftest's own-release scaffolding, #579).

## Findings / follow-ups

None filed. The one judgement call (read-only: adopt the API's refusal instead of main's silent mode reset) is stated
above for the reviewer; if the verdict is "keep main's outcome", the place to change is the call site's expectations, not
`rewrite_entries` (settled by #661) -- and I would argue against it: a deliverable the user made read-only should not be
rewritten behind their back.

## BRANCH STATE

- **Branch:** `cam/656-rvt-job-scrub` from `main` @ `345493c`; PR opened ready (not draft), `Closes #656`.
- **Files written:** `tools/rvt_job.py` (`scrub_identity` body + docstring only; −16/+12), its four generated mirrors via
  `tools/sync_plugin.py` (`plugin/lib/tools/rvt_job.py`, `plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`),
  `tests/test_rvt_job_scrub_656.py` (new), `tests/ci_shard.d/656-rvt-job-scrub.txt` (new), this fragment (new). Not
  touched: `src/rvt/identity.py`, `src/rvt/roundtrip.py`, `tools/frontdoor.py`, `src/rvt/famgen/**`, `src/rvt/frontdoor/**`,
  any hot file, the stream index, `TRACKER.md`.
- **Gates:** sha table 9/9 equal (above; re-taken after the `/simplify` edits: still 9/9); grep 3 → 0; gate suites 268/7 →
  268/7 (+ new module 10/1, + plugin sync/coldstart 25/0 → 303/8); whole merged CI shard on the final tree
  (`RVT_SKIP_LARGE=1 … $(shard_list.py --print)`, 116 files): **2406 passed / 136 skipped / 3 xfailed** in 7 m 56 s (run
  twice, identical) -- `main` @ `345493c` is therefore expected at 2396 / 135 / 3 (the new module is the only delta:
  +10 passed, +1 root-skip); `tools/sync_plugin.py` rebuilt (4 files synced, deny-audit clean, identity scan 82 hits / 0
  mismatches == allowlist) then `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok; drop-in resolves (`shard_list.py --print` line 114); bare-unzip surface:
  `tools/surface_bench.py --zip tekton-plugin.zip --surfaces local --jobs preflight,go-author-6panels,go-edit`: **PASS /
  PASS / PASS** (0.1 s / 4.7 s / 0.6 s, 1 shell call each; go-edit structural PASS, validation PASS 0 errors).
  `/simplify` RAN (above). `/verify` RAN: front door `author --rvt <pin> --edit "set level 1351691 elevation to 5 ft" --out
  <d> --json` on all three pins → `ok`, route `rvt`, status `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` (delivered,
  stamped -- rule 1; NOT-DELIVERABLE is the standing `base_provenance` verdict of the pinned composed bases: the P0 gates
  G2 #19 / G3 #23, unchanged by this diff), manifest gates
  identity / structural / validation **PASS** ×3, each output `VALID (no errors)` under its own release (2026: the known
  DataStorage warning), identity quoted: author `'rvt-writer'`, client `'rvt-writer'`, username `''`, central path `''`,
  save path = the basename, build = the pin's own (`20250227_1515(x64)` / `Development Build` / `20230308_1635(x64)`),
  GUID == History[0] ×3, no `.idtmp`/`.tmp` in any out dir -- and their sha256 (`c423489b…` / `da4560de…` / `7cdb4a39…`)
  **equal the table's fd rows, i.e. main's bytes**; from a bare unzip of the rebuilt zip with system Python:
  `go author --prompt "an electrical room with 6 panels"` → `tekton: READY | … | genesis verified (Revit 2026)`, `ready:
  true`, result `ok`, `PROOF-ONLY (self-checks PASS …)`, `prompt_room.rvt` `VALID (no errors)`, author/client
  `'rvt-writer'`, username `''`, GUID == History[0]; `go author --rvt assets/genesis/G_ABPD_2025.rvt --edit "set level
  1351691 elevation to 5 ft"` (the shipped `rvt_job.py`) → READY, `ok`, `G_ABPD_2025.edited.rvt` `VALID (no errors)`,
  sha256 `da4560de…` = main's fd/2025 row.
- **Staged vs shipped:** nothing staged for the viewer; no certification claim (rule 4 -- byte identity to already-measured
  outputs is the claim, not "loads"); `tekton-plugin.zip` regenerated locally, not committed.
