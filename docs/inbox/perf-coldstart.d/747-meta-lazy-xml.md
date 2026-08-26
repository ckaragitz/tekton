# 747 — `rvt.meta` defers its XML parsers and `zipfile`: ~10 ms and 14 stdlib modules off every prompt job

Fragment of `docs/inbox/perf-coldstart.md` (issue #747, follow-up of #139 / PR #746). One PR.

## Why

After #139 took `xml.sax.saxutils` off the prompt path, the next stdlib weight there was
`rvt.meta` (imported by `rvt.stream_encoders` for the BasicFileInfo / DocumentIncrementTable
wrappers). `src/rvt/meta.py` imported `xml.dom.minidom`, `xml.etree.ElementTree` and `zipfile` at
module level although only two parsers use them: `parse_transmission` (ElementTree) and
`parse_project_info` (zipfile + ElementTree). `xml.dom.minidom` was imported and never used.

## What was built

* `src/rvt/meta.py`: the three module-level imports are gone; `parse_transmission` imports
  `xml.etree.ElementTree` locally, `parse_project_info` imports `zipfile` and `ElementTree`
  locally. No other line changed (mirror `plugin/lib/src/rvt/meta.py` via `sync_plugin`).
  Review round 1 (🟡): the two local-import comments now say "imported locally by the two parsers"
  (the first draft's "only this parser" was wrong for `ElementTree`); the sum rows above re-labelled.
* `tests/test_partatom_escape_139.py`: the family-build import budget `HEAVY` tuple is extended
  with `xml.dom.minidom`, `xml.etree.ElementTree`, `zipfile` (the existing gate, no third
  subprocess gate, as #747's DONE asks). Negative control: with `origin/main`'s `meta.py` the gate
  fails (`zipfile` et al. present).
* Refuted sub-claim: the issue's table attributed `urllib.parse` (2.2–2.3 ms) to `rvt.meta`; the
  `-X importtime` tree shows its parent is `pathlib` (stdlib, `quote_from_bytes` for `as_uri`), so it
  stays on the path regardless — recorded, not chased.

## Evidence (2026-08-26, Python 3.11.15, fresh cloud clone; warm second run of each pair)

`-X importtime` of the 6-panel prompt job (`tools/frontdoor.py author --prompt "an electrical room
with 6 panels" --out … --json`):

| | before (`main` @ `a7716bb`) | after |
|---|---|---|
| modules imported | 225 | **211** |
| import self-time sum (single warm sample — within run-to-run noise, see note) | 243.7 ms | 221.5 ms |
| `rvt.meta` cumulative | 12.5 ms | **2.1 ms** |
| `xml.dom.minidom` | 2.8 ms | absent |
| `xml.etree.ElementTree` | 2.0 ms | absent |
| `zipfile` | 5.6 ms | absent |
| `urllib.parse` (parent `pathlib`) | 2.9 ms | 3.8 ms (unchanged owner) |

Bare surface (fresh unzip of `tekton-plugin.zip`, `/usr/bin/python3`, `env -i`, proxies at a dead
port, `go author --prompt "an electrical room with 6 panels" --json`): modules 231 → **217**,
`rvt.meta` 11.7 → **0.8 ms**, the three modules absent, `go.ready` true, status
`PROOF-ONLY (self-checks PASS; …)` both runs (self-time sum 234.2 → 228.3 ms, single sample).

Note on the sums: the whole-job import sums are single warm samples and sit inside the run-to-run
noise band (the independent review re-measured three warm pairs in its sandbox: head 203.7 / 225.4 /
236.9 ms vs main 223.0 / 225.9 / 234.4 ms); the robust numbers are the module counts (225 → 211,
231 → 217 on every run) and the `rvt.meta` cumulative (~12 → ~2 ms), i.e. the ~10 ms this change
removes. That delta is below `tools/surface_bench.py`'s wall-time resolution, so — as for #139 —
the `-X importtime` protocol is the before/after of record for O10 rather than a bench row.

Outputs: the three parsers run against the pinned base's real streams (`BasicFileInfo` 2,171 B,
`ProjectInformation` 969 B, `TransmissionData` 3,838 B) through `main`'s `meta.py` and this branch's
give byte-identical JSON (sha256 `04e8a0559e4542b5` both). The 6-panel job's manifest before/after:
same status, `report.validation {VALID, 0, 1, true, 1}`, 22 elements created; the emitted `.rvt`
re-validates `ok: true`; provenance against the pinned base clean (`pinned-composed-genesis`
baseline, no suspects).

Gates: `tests/test_partatom_escape_139.py` (incl. the extended budget gate) + `test_stream_encoders.py
test_input_release.py test_genesis_identity.py test_lazy_ifc_import.py` → 67 passed / 88 skipped
(sample-absence skips); `test_frontdoor.py test_plugin_sync.py test_bootstrap.py test_coldstart.py
test_go_report_185.py test_skipped_selfchecks_751.py test_famgen*.py` → 380 passed / 50 skipped
(`RVT_SKIP_LARGE=1`); `tools/sync_plugin.py` rebuilt + `--check` in sync; `validate_plugin.py` PASS;
portable paths ok.

## Findings

1. After this, `rvt.meta`'s remaining 0.8–2.1 ms is its own body; the top warm entries on the prompt
   path are our own modules' import-time work (`rvt.frontdoor.build`, `prompt_intent`,
   `rvt.famgen.factory`, per #139's record) — a different class of task than stdlib diets.
2. `src/rvt/strings_scan.py` is the only other `rvt` module importing an XML/zip stdlib module; it is
   not on the prompt path (absent from both trees).

## BRANCH STATE

* branch `cam/747-meta-lazy-xml` from `main` @ `a7716bb`; files: `src/rvt/meta.py`,
  `plugin/lib/src/rvt/meta.py` (sync), `tests/test_partatom_escape_139.py` (HEAVY tuple), this
  fragment + one index line in `docs/inbox/perf-coldstart.md`.
* shipped in the PR: all of the above. Staged for a human: nothing (no viewer claim; no delivered bytes change).
* not touched: `src/rvt/stream_encoders.py`, hot files.
