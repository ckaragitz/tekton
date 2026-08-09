# BARE-FAMILY-VALIDATE — per-family `validate` on the bare plugin surface (issue #75)

Stream: **bare-family-validate** (2026-08-09, issue #75, branch
`cam/75-bare-family-validate`, engineer session started by the tech-lead
session for the fan-out).

Charter (issue #75): from a bare unzip of `tekton-plugin.zip` with system
Python (no numpy, no repo on the path) `go author --prompt "an electrical room
with 6 panels"` reported `READY` / `ok: true` while **every generated family's
own report said `validate.ok = false`** with
`ValueError('final block is not CRCIO-framed (raw stream?)')` and
`family_mode: None` — an honesty inversion on exactly the surface a stranger
runs (PG3), and a hard-rule-1 smell (a checker crashing instead of delivering
a labelled verdict).

**DONE state (the issue's four bullets): bare unzip + system Python →
`families/*.json` all `validate.ok == true` with a `family_mode.verdict`
present, no `CRCIO-framed` error; root cause named and fixed at its layer (the
validator's numpy-free ECC branch), not by swallowing the exception; a
CI-shard test that exercises the family validator with numpy hidden on an
emitted `.rfa`; the bare-run / `surface_bench` output quoted below.**

---

## 1. Root cause

`skeleton.validate_family` (what `famdoc_adoc.validate_family_file` and hence
every family report calls) runs the certified arbiter **twice**: once with
`family=True` (PartAtom unframed, ProjectInformation not required) and once
in raw project mode for the honest `arbiter_raw` comparison.  In project mode
the family's `PartAtom` stream — plain Atom XML, not CRCIO-paged — is handed
to the ECC tier `validate.ecc_verify_stream`.

* **numpy present** (dev checkout): `_candidate_final_geometries(tail)` finds
  no size class → an in-report ERROR *"final block (833 bytes) is not
  CRCIO-framed"* + the raw bytes passed through; the run completes, family
  mode is VALID, project mode is INVALID-as-expected.
* **numpy absent** (#45's degrade branch): the whole stream was delegated to
  the strict codec inverse `ecc.unframe_stream(raw)`, which by contract
  **raises** on any final block that does not re-encode byte-exactly.  The
  `ValueError` escaped `validate_file`, `validate_family`, and
  `validate_family_file`; `standalone.py` caught it per family as
  `{"ok": false, "error": repr(e)}`.

So the defect was never in the files (they were VALID all along) nor in
`ecc.py`'s codec: it was that the validator had **two ECC code paths with
different failure semantics**, and only the numpy one had ever met a family
container.  The same branch would also have crashed on any *damaged* final
block of a project (unframe_stream demands an exact re-encode), where the
numpy path repairs single-bit damage and reports a foreign trailer as an
ERROR.

## 2. What was built

The fix removes the divergence instead of patching the symptom: there is now
**one** ECC engine on every surface, stdlib only.  The bare surface
*verifies* every CRCIO block (it used to skip them), and a dev checkout runs
the very code path the plugin ships — `rvt.validate` no longer imports numpy
at all.

`src/rvt/ecc.py`

* `lane_syndromes(block, first, second, poly, m) -> list[int]` — the per-lane
  CRC syndromes of one encoded block.  Bit-sliced: the `m` CRC state bits
  live in `m` Python big-ints whose bit *i* is lane *i*'s state bit, so a
  round is `1 + popcount(poly)` big-int XORs over `second` (≤ 2047) bits; the
  codeword is sliced off the block 64 rounds at a time.  It belongs with the
  codec (same interleave law as `encode_block`).
* `final_block_candidates(tail) -> [(params, data_len)]` — the pad-count-field
  decode that `unframe_stream` and the validator's
  `_candidate_final_geometries` each carried a byte-identical copy of; both
  now call it.  `unframe_stream` keeps its strict raise-on-mismatch contract
  (right for a codec inverse, and tested); the validator just no longer uses
  it as a degrade path.

`src/rvt/validate.py`

* `ecc_verify_stream(name, raw, rep)` is single-path: every full page and
  every final-block candidate geometry is scored with `ecc.lane_syndromes`;
  `_repair_block` takes a plain `Sequence[int]`.  Deleted: the numpy
  `_syndromes` batch decoder, `_numpy_available` / `_NP_STATE`, the
  `lazy_import("numpy")`, the unused `batch` parameter, and the "ECC page
  verification SKIPPED: numpy not installed" warning with its branch.
  −60 / +25 lines net in the ECC tier.
* Why delete numpy rather than keep it as an accelerator (review, measured
  on this VM): batched numpy only wins past ~8 full pages *per stream*
  (n=1: numpy 7.5 ms vs stdlib 1.8 ms; n=64: 0.92 vs 1.74 ms/page); the
  pinned bases carry ≤ 2 full pages per stream, whole-file validate was
  406 ms (numpy) vs 396 ms (stdlib), and the price of keeping it was a second
  engine + state + a lazy import + a cross-engine parity test forever.  The
  only loser is a multi-hundred-page dev sample (~+1 ms/page), which no
  product surface validates.

`tests/test_bare_family_validate.py` (new, in `tests/ci_shard.txt`) — 42
tests, 6.7 s, sample-free (bundled `G_ABPD*.rvt` only): `lane_syndromes`
clean == all-zero and one flip == exactly its lane + locating signature for
all 8 parameter classes + a full page; damaged blocks equal two independent
oracles (a scalar per-lane CRC, and — when numpy is installed in the test
env — the vectorised decoder the validator used to carry, kept in the test
as an oracle only); `frame_stream`/`unframe_stream`/`final_block_candidates`
round-trip every size class incl. the page-boundary cases (the samples-gated
`test_ecc.py` cannot run in CI); `unframe_stream` still raises on a raw
stream; `ecc_verify_stream`: clean silent, single-bit page/tail damage
repaired with one WARNING, zeroed trailer one ERROR with original bytes
downstream, **non-CRCIO stream → one ERROR finding, raw bytes through, no
exception**; the three pinned bases 0 errors with pages verified and nothing
"SKIPPED"; **the validator never imports numpy** even where it is installed
(subprocess); an emitted constructive `.rfa` → project mode reports
PartAtom/ProjectInformation findings (no traceback), `validate_family` /
`validate_family_file` ok + `family_mode VALID` / `project_mode INVALID`, and
once more in a genuinely numpy-less `-I -S` subprocess (engine + the plugin's
vendored olefile only; premise-checked that numpy is unimportable there).

`tests/test_coldstart.py::test_prompt_fallback_build_runs_without_numpy` —
the existing bare `go author` build test now also asserts every
`families/*.json` has `validate.ok is True` and `family_mode.verdict ==
"VALID"` (the issue's first DONE bullet, verbatim, in the shard); docstrings
no longer describe the retired "in-report ERROR / SKIPPED" degrade.

## 3. Evidence (numbers; cloud session, fresh clone, `python3` 3.11.15 with neither numpy nor olefile installed)

**Before** (zip built from `main` @ 33622e3, bare unzip, system python3):

```
$ python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json
exit=0  wall=19.7s  go.ready=true
families/pp1..pp6 *.json: validate = {'ok': False, 'error': "ValueError('final block is not CRCIO-framed (raw stream?)')"}  family_mode: None   (6/6)
```
Direct traceback (bare, `validate_file(rfa)` project mode):
`validate.py:758 _layer_structure → ecc_verify_stream → validate.py:454 ecc.unframe_stream(raw) → ecc.py:213 ValueError`.
`validate_file(rfa, family=True)` on the same surface: ok=True — confirming the second (project-mode) pass as the trigger.

**After** (this branch, `tools/sync_plugin.py` rebuilt zip, fresh bare unzip, system python3; two builds measured — quiet host, then the final single-engine build while a pytest run shared the CPU):

```
build 1: cold exit=0 wall=16.9s | warm exit=0 wall=17.3s   (go.job_seconds 16.7 / 17.2)
build 2: cold exit=0 wall=19.0s | warm exit=0 wall=18.5s   (go.job_seconds 18.9 / 18.4; host busy)
families/pp1..pp6 *.json: validate.ok=True family_mode=VALID n_errors=0        (6/6, every run; 0 "error" keys; 0 Tracebacks on stderr)

$ python3 skills/tekton-inspect/scripts/_bootstrap.py go rvt_validate.py --family out/cold/families/pp1_….rfa --json v.json
run1 0.169s / run2 0.164s, exit 0:  verdict: VALID (no errors); warnings=0 info=2   pages_checked=11
$ … go rvt_validate.py out/cold/prompt_room.rvt          -> VALID, warnings=1 (the known DataStorage decoder gap), 0.6s, exit 0
```
Same `.rfa` under the repo `.venv`: `VALID; warnings=0 info=2` — identical
counts, and `numpy` is not in `sys.modules` afterwards.  Note the bare
`--family` run previously carried `warnings=1` (the SKIPPED notice); it is
now `warnings=0` because the pages are actually verified.  (Steer #108: the
`go author` wall time is dominated by the build, not validation — per-family
validate is ~0.17 s of it; before/after job time moved 19.7 s → 16.9–19.0 s,
i.e. within host noise, no regression.)

Verdict parity across the change (in-process, `.venv`; "before" = numpy
engine on `main`, "after" = the single stdlib engine):

| file | ok | E/W/I before → after | pages | structure layer before → after |
|---|---|---|---|---|
| G_ABPD.rvt (2026) | True | 0/1/2 → 0/1/2 | 14 | 0.13 s → 0.04 s |
| G_ABPD_2025.rvt | True | 0/0/2 → 0/0/2 | 15 | 0.05 s → 0.04 s |
| G_ABPD_2024.rvt | True | 0/0/2 → 0/0/2 | 15 | 0.05 s → 0.04 s |
| emitted .rfa, family=True | True | 0/0/2 → 0/0/2 | 11 | 0.02 s → 0.01 s |
| emitted .rfa, project mode | False | 3/0/2 → 3/0/2 (ProjectInformation missing; PartAtom not CRCIO-framed; PartAtom no gzip member) — *bare surface before: ValueError* | 11 | 0.02 s → 0.01 s |

Micro-benchmark of the decoder alone: full 64,896-byte page — stdlib
bit-sliced 1.8–1.9 ms, numpy single block 6.1–7.5 ms, numpy batched (64
pages) 0.92–0.98 ms/page.  The stdlib engine is faster than numpy at every
size a product surface validates (≤ 15 pages, ≤ 2 per stream) and ~1 ms/page
slower only on multi-hundred-page dev samples.

`tools/surface_bench.py --zip tekton-plugin.zip` (this host; bench python 3.11.15):

| job | shell calls | cowork | codeexec | local |
|---|---|---|---|---|
| preflight | 1 | 0.1s | 0.1s (+0.2s extract) | 0.1s |
| author-prompt | 1 | 4.4s | 4.8s (+0.1s extract) | 5.1s |
| go-author-prompt | 1 | 4.1s | 4.5s (+0.1s extract) | 4.8s |
| author-ifc | 1 | 0.2s FAIL | 0.3s (+0.1s extract) FAIL | 24.9s |
| edit-roundtrip | 3 | 1.8s | 2.1s (+0.4s extract) | 1.9s |
| validate | 1 | 0.6s | 0.9s (+0.1s extract) | 0.9s |
| **session total** |  | **11.2s / 8 calls** | **12.8s / 8 calls** (+1.0s extract) | **37.7s / 8 calls** |

(cowork/codeexec here = system python3, `numpy=NO`.  The `author-ifc` FAIL on
those two columns is **pre-existing and out of territory**: the IFC route's
placement/geometry resolver requires numpy and says so as a labelled
`ImportError` in a delivered manifest, exit 0, no traceback — see §5.)

Gates (this session, final tree): `tests/test_bare_family_validate.py`
**42 passed** (6.7 s); `tests/test_bare_family_validate.py
tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py
tests/test_surface_perf.py tests/test_validate_release.py
tests/test_validate_footer_blob.py tests/test_verify_manipulated_release.py
tests/test_famgen_adoc.py tests/test_famgen_skeleton.py
tests/test_famdoc_scan_fp.py tests/test_frontdoor_standalone.py` →
**122 passed / 30 skipped** in 80 s (skips = vendor `.rfa` / ladders absent
and surface_perf's "no bare python3 with numpy on this host", as designed);
`tools/sync_plugin.py` then `--check` clean; `plugin/scripts/validate_plugin.py`
PASS (23 assertions); `tools/dev/check_portable_paths.py` ok (2665 paths).
CI shard: see PR body.

## 4. Findings

* The bare surface no longer *degrades* ECC verification — it performs it.
  #45's "SKIPPED" warning was honest but left the plugin's primary surface
  with a weaker structure tier than dev machines; that asymmetry is what hid
  this bug (no dev run ever took the branch that crashed).  There is now no
  surface-dependent branch left in `rvt.validate`.
* numpy was never load-bearing for ECC: at product file sizes the bit-sliced
  stdlib decoder is faster than the vectorised one, so "install numpy for
  full verification" was advice that bought nothing.  numpy remains a
  genuine dependency only of the geometry/IFC placement code (`_lazyimp`
  hint "geometry resolution") — see §5.
* `skeleton.validate_family`'s double run (family mode + raw project mode) is
  deliberate (the `arbiter_raw` honesty comparison) and stays; so does
  `standalone.py`'s per-family `except Exception → {"ok": false, "error"}`
  guard (rule 1: it turned a crash into a delivered, labelled report — which
  is how this bug was visible at all).  Both are now safe on every surface.
* Review pass (reuse/simplify/efficiency/altitude): applied — collapse to one
  engine, dedupe the final-block decode into `ecc.py`, drop the unused
  `batch` parameter and the best/best_syn/best_bad triple; skipped — hoisting
  `BARE_PY` / the emitted-`.rfa` fixture into `tests/conftest.py` (touches
  four other streams' test files; noted for whoever next edits conftest) and
  rewriting `encode_block`'s scalar lane loop on top of `lane_syndromes`
  (certified writer path; no behaviour to gain).

## 5. Follow-ups (filed as task issues, `Refs #75`)

* IFC route on a numpy-less surface: `author --ifc` fails fast with a
  labelled `ImportError: numpy is required here (IFC placement / geometry
  resolution)`.  Honest and delivered (manifest written), but PG3 says "bare
  unzip + system Python"; either the IFC placement math gets a stdlib path
  like this one, or the skills/README state numpy as an IFC-route
  prerequisite and `preflight` says so up front.  Filed as **#127** (`P2`,
  `area:frontdoor`, `area:plugin`, `ready`; searched first, no prior issue) —
  not this stream's territory.

## 6. Open questions

None for this stream.

## BRANCH STATE

* Branch `cam/75-bare-family-validate` from `main` @ 33622e3; PR closes #75.
* Files written: `src/rvt/ecc.py` (+`lane_syndromes`,
  +`final_block_candidates`, `unframe_stream` on top of it),
  `src/rvt/validate.py` (ECC tier single stdlib engine; numpy decoder,
  lazy import, `_NP_STATE`, SKIPPED branch removed),
  `tests/test_bare_family_validate.py` (new, 42 tests),
  `tests/test_coldstart.py` (family-report assertions + docstrings),
  `tests/ci_shard.txt` (+1 line), this record, and the `tools/sync_plugin.py`
  mirrors `plugin/lib/src/rvt/{ecc,validate}.py`.
* Gates: listed in §3; all green locally.
* Nothing staged for the viewer; no `.rvt`/`.rfa` committed; no ledger
  change; `tekton-plugin.zip` regenerated locally, not committed.
