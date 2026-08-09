# perf-ecc-encode — bit-sliced CRCIO page-ECC encoder (issue #182)

Stream: `eng182` (engineer session under the tech-lead session; branch
`cam/182-ecc-encode-bitslice`). Refs #124, #110, #108 (latency is
first-class on the plugin/skill path; done only with a measured before/after
from a bare surface).

## 1. What was built

`rvt.ecc.encode_block` — the CRCIO page-ECC **encoder** on the WRITE path
(`frame_stream` / `page_trailer`, called from `commit.py`, the famgen loader,
`rfa_assemble`, `reduce*`, and by `unframe_stream` itself to confirm the
final block) — was a bit-at-a-time transcription of `CRCIO.cpp`: 519,168
Python-level iterations per 64,896-byte page, ~87 ms/page, and 57 % of the
flagship bare `go author` wall time (#182 evidence).

It is now **lane-parallel (bit-sliced), stdlib only, byte-identical**:

* `_crc_planes(buf, rounds, second, poly, m)` — bit `p` of the prefix bytes
  belongs to lane `p % second`, round `p // second`, so round `r`'s input
  bit of *every* lane is `second` contiguous bits. The `m` CRC state bits
  are `m` Python ints ("planes", bit `i` = lane `i`); one round = AND +
  shift + `del c[0]; c.append(fb)` (state ≫ 1 with the reflected poly's
  always-set top tap folded in) + one XOR per remaining tap, over ≤ 2047-bit
  ints — 2,036 rounds per full page instead of 519,168 scalar steps. The
  prefix is serialised once and consumed in byte-aligned 8-round chunks
  (`int.from_bytes` of a slice), so nothing is O(page²).
* `encode_block` builds the whole codeword as one int: data bits | zero
  slack | the N-bit pad-byte-count field at bit `pre-N` (now
  `assert 0 <= pad_bytes < 2**N` instead of silently writing N bits) | the
  `m` parity planes packed small-int-first and OR-ed in once at bit `pre` —
  plane `j` at `pre + j*second` *is* CRCIO's layout "parity bit j of lane i
  → bit pre + i + j·second" — then one `int.to_bytes`. No per-bit loops
  remain (pad field and parity scatter included).
* The original loop is kept verbatim as `_encode_block_ref` (test oracle).
* Signature, `page_trailer`, `frame_stream`, `unframe_stream`, geometry and
  size-class selection are untouched. **Framing bytes are unchanged, so no
  viewer round is needed** (hard rule 4 is about Autodesk's reader; the
  bytes it reads are identical — proven below, not assumed).

Overlap with PR #128 (#75, open, not on `main` when this was built): it adds
`lane_syndromes` on the VERIFY side with the same plane slicing. This change
is independent of it (no shared lines; both add functions to `ecc.py` at
different anchors). Once both are on `main`, `lane_syndromes` can become
`_crc_planes(big, first, second, poly, m)` + its plane→lane transpose — a
10-line follow-up, deliberately not done here to keep the two PRs
conflict-free.

## 2. Evidence — before/after (this VM: cloud CCR, 4 vCPU Xeon @ 2.1 GHz, Python 3.11.15)

Bare surface exactly as DONE 3: `tools/sync_plugin.py` → unzip
`tekton-plugin.zip` to a temp dir → `/usr/bin/python3` (**no numpy, no
olefile**; vendored olefile via the bootstrap) →
`skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical
room with 6 panels" --out out/jN --json`, twice per build. BEFORE zip built
from `main @ a1bba74`, AFTER zip from this branch; both READY, `result.ok
true`, exit 0.

| measure (bare `/usr/bin/python3`, no numpy) | BEFORE (main) | AFTER (this branch) | ratio |
|---|---|---|---|
| `go author` 6 panels — `go.job_seconds` run 1 / run 2 | **22.13 / 22.41 s** | **10.58 / 9.69 s** | 0.46× |
| same, process wall | 22.34 / 22.58 s | 10.78 / 9.86 s | |
| `go author` walls-only prompt ("an empty electrical room 6 by 8 meters") job_seconds | 2.06 s | 1.20 s | 0.58× |
| `encode_block`, one random 64,896-B page (min of 30) | 86.8 ms | **0.71 ms** | **121×** |
| `encode_block`, 3,000-B final block (class m=9) | 4.05 ms | 0.095 ms | 43× |
| `tools/surface_bench.py --zip … --python-bare /usr/bin/python3`: cowork `go-author-prompt` | 5.2 s | **2.7 s** | 0.52× |
| surface_bench cowork `author-prompt` / `edit-roundtrip` / `validate` | 6.1 / 2.2 / 0.9 s | 3.2 / 1.2 / 0.6 s | |
| surface_bench session total cowork / codeexec (8 calls) | 14.7 / 15.8 s | **8.1 / 10.3 s** | 0.55× / 0.65× |
| ECC share of the 6-panel job (cProfile cum, `encode_block` 298 calls) | 37.75 s of 64.7 s profiled (scout VM, #182) | 0.31 s of 20.3 s profiled (intermediate 1.7 ms/page build; final build ≈ 0.15 s) | |

Issue targets: job_seconds ≤ 14 s (scout baseline 27.0–28.6 s, i.e. ≤ 0.52×)
→ **met** (9.7–10.6 s here from a 22.1–22.4 s baseline = 0.46×; the scout's
own prototype landed at 11.35 s); surface_bench cowork go-author-prompt ≤ 4 s
→ **2.7 s**; per-page encode new ≤ old/5 → **old/121**. An intermediate
build of this branch (64-round int-shift chunks, list re-allocation per
round, per-plane OR into the page int) measured 1.72 ms/page and 11.04 /
10.31 s job; the `/simplify` efficiency pass (byte-aligned 8-round chunks
from a once-serialised prefix, `del/append` rotate with the top tap folded
in, planes packed before one OR) took the page to 0.71 ms — every variant
re-proven equal to the reference across all `PARAM_CLASSES` **and**
`ALT_PARAMS` (342 cases). (surface_bench's `local` column runs the repo
interpreter against the working tree in both runs, so it is not a
before/after pair; the `author-ifc` FAIL on the two numpy-less columns is
pre-existing and filed as #127.)

### Byte-identity (framing unchanged)

* `encode_block == _encode_block_ref` for seeded-random data at 25 sizes
  (0, 1, 5, 8, 50, 300, 1000, 5000, 12345, 30000, 64896, every `_THRESH`
  size-class boundary and the byte after it) × all 8 `PARAM_CLASSES` (200
  cases) + `select_params(n)` at 28 sizes × up to 3 seeds + all-zero /
  all-ones / first-bit / last-bit pages in two classes — `tests/test_ecc_encode.py`
  (239 passed + 1 strict xfail = the #236 marker).
* Every full page of the three pinned bases
  (`plugin/assets/genesis/G_ABPD{,_2025,_2024}.rvt`, 17 pages): new trailer
  == reference trailer == **the bytes in the certified file**; every
  ECC-framed stream of the three bases (27) `frame_stream(unframe_stream(raw))
  == raw` and the final block == the reference encoder's.
* Front-door output, same inputs, before vs after: the walls-only prompt job
  is deterministic and its `prompt_room.rvt` (581,632 B) is **byte-identical**
  (`cmp` clean, md5 `da6324e9…` both builds). The 6-panel job is *not*
  deterministic run-to-run even on one build (fresh family/document GUIDs —
  #168/#9: `b1 ≠ b2` for every stage above `stage_L0_base`), so for it the
  check is done at the framing layer instead: every ECC stream of BEFORE's
  `prompt_room.rvt`, `stage_L6_pp6.rvt`, `pp1_….rfa` and the walls file (36
  streams, 19 full pages) re-frames byte-identically with the new encoder.
* The three pinned bases re-validate `VALID (no errors)` with
  `tools/rvt_validate.py` (G_ABPD warnings=1 = the known DataStorage decoder
  gap; 2025/2024 warnings=0).

## 3. Gates run

* `tests/test_ecc_encode.py` (new, sample-free, in `tests/ci_shard.txt`):
  **239 passed, 1 xfailed** in 6.0 s.
* `tests/test_ecc_encode.py tests/test_ecc.py tests/test_ecc_intel.py
  tests/test_coldstart.py tests/test_bootstrap.py tests/test_plugin_sync.py`
  → **265 passed / 28 skipped / 1 xfailed** (skips = the two sample-gated ECC
  files; `samples/` absent in a cloud clone). `tests/test_bare_family_validate.py`
  does not exist on `main` yet (PR #128 open) — not run.
* CI shard exactly as CI runs it (`tests/ci_shard.txt` incl. the new file,
  `RVT_SKIP_LARGE=1`) → **425 passed / 31 skipped / 1 xfailed**.
* `tools/sync_plugin.py` run (1 file mirrored: `plugin/lib/src/rvt/ecc.py`;
  deny-audit clean; zip rebuilt 4982 KB), `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS (23 assertions);
  `tools/dev/check_portable_paths.py` ok (2678 paths).
* Full suite NOT run (SUITE-COORDINATION).

## 4. Findings

1. **The encoder, not numpy, was the bare-surface tax.** With the encoder
   fixed, the numpy-less cowork column (2.8 s go-author-prompt) is now
   *faster* than the scout's numpy venv figure; ECC is 1.5 % of the job.
2. **Next hot spots** (AFTER, cProfile of the bare 6-panel job, 20.3 s
   profiled ≈ 10.5 s wall; un-profiled timer in brackets):
   `stage_load` 13.05 s cum for 6 families [`load_family_into_project` 7.33 s
   = 58 % of wall; `verify_loaded_project` 3.97 s of that];
   `schema_cache.parse_cached` **79 calls = 5.94 s cum** for ≤ 3 distinct
   bundled digests (`payload_to_schema` 4.84 s, `_tuple_to_field` 2.31 s
   tottime, `marshal.loads` 0.96 s) — already filed as #183 / #216, now the
   single biggest lever (~25 % of the remaining wall); `validate_file` 13
   calls = 4.02 s [3.10 s]; `decode_latest` 44 calls = 4.10 s [1.27 s];
   `copy.deepcopy` 1.41 s; `factory.write` ×6 = 3.65 s. Numbers posted on
   #124 and #110.
3. **Pre-existing reader ambiguity found by the new round-trip test (not
   fixed here, filed as #236):** a *final* block of 64,388–64,895 data bytes
   selects the full-page class with 255 lanes and encodes to exactly
   `PAGE_STRIDE` (65,249) bytes with pad field 1..508; `ecc.unframe_stream`
   walks `>= PAGE_STRIDE` and takes it for a full page, returning 64,896
   bytes, so a logical stream whose length mod 64,896 falls in that
   508-value window round-trips 1..508 bytes too long. The engine already
   knows the right rule — `reduce.unframe_exact` decodes the LAST
   stride-sized block by its pad field (its docstring records the real hit,
   R1s: a 64,875-byte final block) — but the codec's own inverse, used by
   `validate.py`, does not; #236 is "one deframer". Both encoders agree there
   (it is the decoder) and the writer is unaffected. Kept out of this PR to
   stay byte-identical-only and conflict-free with #128's `unframe_stream`
   refactor; the test carries an `xfail(strict=True)` case citing #236 so the
   workaround retires itself.

## 5. Open questions

* None blocking. Whether Revit's own reader disambiguates the stride-sized
  final block by the pad field (expected) or by an out-of-band length is for
  the follow-up issue to confirm against a sample whose stream length lands
  in the window.

## BRANCH STATE

* Branch `cam/182-ecc-encode-bitslice` from `main @ a1bba74`; PR closes #182.
* Files written: `src/rvt/ecc.py` (+`_crc_planes`, `encode_block` rewritten,
  old loop kept as `_encode_block_ref`), `tests/test_ecc_encode.py` (new, 184
  tests), `tests/ci_shard.txt` (+1 line), this record; `tools/sync_plugin.py`
  mirror `plugin/lib/src/rvt/ecc.py`.
* Gates: §3, all green locally.
* Nothing staged for the viewer (framing byte-identical — no certification
  claim, no round needed); no `.rvt`/`.rfa` committed; no ledger change;
  `tekton-plugin.zip` regenerated locally, not committed.
