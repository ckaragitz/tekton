# codec-bases-ci — every codec layer round-trips on the three bundled bases, in CI (issue #132)

Stream: eng #132 (cloud engineer session, fresh clone, 2026-08-09).
Charter (#132, PG4 / O6): the byte-exact writer chain KNOWLEDGE.md calls
proven end to end (gzip → CRCIO page ECC → CFB → the six small stream
codecs → schema-directed object codec → ADocument) had **zero pre-merge
protection**, because every corpus test that proves it keys on `samples/`
or `extracted/` and self-skips in a fresh clone / CI (test_encode 11/11
skipped, test_stream_encoders 88/89, test_ecc 19/19, test_objects 10/10,
test_roundtrip 12/15, test_adocument 9/14, test_commit 1/1), and nothing
guarded the 2025/2024 framing ordinals at all. Territory:
`tests/test_codec_bases.py` (new), `tests/ci_shard.txt` (+1 line), this
record. **No `src/` change**; `src/rvt/versions/` (hot) is *called*
(`records32.reading32`), not edited. Zero donor bytes: the only files read
are our three composed, certified bases shipped in the plugin.

## What was built

`tests/test_codec_bases.py` — 37 cases, parametrized over
`plugin/assets/genesis/G_ABPD{,_2025,_2024}.rvt` (ids `2026`/`2025`/`2024`).
The `base` fixture opens each file inside
`rvt.versions.records32.reading32(base)` (own framing ordinals by name from
the file's own `Formats/Latest`; the 32-bit record layer would switch in for
a ≤ 2023 pin), and an autouse `_constants_restored` fixture asserts after
every case that `rvt.partitions` carries the `LATEST_RELEASE` framing table
again (the `tests/test_validate_release.py` pattern). Per base:

| DONE | test | asserts |
|---|---|---|
| (a) | `test_every_gzip_member_crc_ok` | every gzip member of every stream `crc_ok`; `Formats/Latest`, `Global/Latest`, `Contents` and every partition carry ≥ 1 member |
| (b) | `test_ecc_full_page_trailers_and_reframe` | `ecc.page_trailer(page)` == the stored 353-byte trailer for every full page; `frame_stream(unframe_stream(raw)) == raw` for every CRCIO-framed stream (≥ 6) |
| (b′) | `test_ecc_verifies_with_numpy_hidden` | the same two laws on the 2025 base from a **bare interpreter** (`-I -S`: no site-packages → `find_spec('numpy') is None`, only `src/` + the plugin's vendored `olefile` on the path), inside `reading32`, and `'numpy' not in sys.modules` afterwards — the `tests/test_coldstart.py` recipe |
| (c) | `test_stream_codec_roundtrip_byte_exact[<year>-<name>]` | `stream_encoders.CODECS` `enc(dec(x)) == x` for ElemTable / History / DocumentIncrementTable / PartitionTable (`Global/*` member 0), Contents (member 0), BasicFileInfo (raw) — 18 cases |
| (d) | `test_unit0_records_roundtrip_byte_exact` | `StreamWalker` 0 errors + every block `crc_ok` on every partition stream; unit 0: `roundtrip_segment` `fail == 0` and `pass == tested` per seq, Σ tested over 101/102/103 ≥ 9000; `reencode_segment(seg) == seg` and same record count, `tail == 0`, for each seq — encoder built on the base's **own** schema (`ObjectEncoder(schema_of(doc))`) |
| (e) | `test_adocument_decode_clean_and_encode_byte_exact` | `ADocumentDecoder(schema_of(base))`: `errors == []`, `clean`, trailer == `u32 0`, consumed + 2 + 4 == payload length, `encode_latest(adoc) == payload` |
| (f) | `test_cfb_roundtrip_is_stream_equal` | `rvt.roundtrip.roundtrip(base, tmp)` → CFB v4 / 4096-byte sectors; `verify_pair` reports no difference (the `(compoundfiles cross-check skipped …)` note is filtered — that reader is not a dependency) |
| (g) | `test_schema_matches_known_release_pin` | parsed schema `class_count` and `sha256` == `KNOWN_RELEASES[year]`; `detect_release == year` |

No record/page/member counts are hard-coded (bases get re-pinned, #19):
only structural minima (Σ tested ≥ 9000 from the issue, ≥ 6 framed
streams, ≥ 1 full page). Mismatch diagnostics reuse
`rvt.encode.first_divergence` (offset + hex window either side, the
`test_stream_encoders` / `describe_mismatch` style) and
`roundtrip_segment`'s own `failures` dicts.

## Evidence (this clone, `main@109345e`, py3.11.13)

Measured per base by the tests themselves (`-s`):

| base | gzip members / crc_ok | ECC full pages / framed streams | stream codecs exact | unit-0 records per seq (101/102/103) | tested / pass | `reencode_segment == seg` | ADocument | CFB verify_pair | schema classes / sha == pin |
|---|---|---|---|---|---|---|---|---|---|
| G_ABPD.rvt (2026) | 22 / 22 | 5 / 9 | 6 / 6 | 3103 / 3103 / 3103 (seq102: 1 unclean record excluded from the tested set, passed through verbatim by `reencode_segment`) | 9308 / 9308 | 3 / 3 | clean, encode == payload | [] | 4690 ✓ |
| G_ABPD_2025.rvt | 23 / 23 | 6 / 9 | 6 / 6 | 3317 / 3317 / 3317 | 9951 / 9951 | 3 / 3 | clean, encode == payload | [] | 4600 ✓ |
| G_ABPD_2024.rvt | 23 / 23 | 6 / 9 | 6 / 6 | 3279 / 3279 / 3279 | 9837 / 9837 | 3 / 3 | clean, encode == payload | [] | 4492 ✓ |

Segment sizes (bytes, seq 101/102/103): 2026 437,642 / 1,099,038 / 73,314;
2025 471,696 / 1,286,235 / 76,522; 2024 466,320 / 1,200,134 / 75,686.
Bare-interpreter ECC case (2025): olefile resolved from
`plugin/skills/_shared/_vendor/olefile`, `PT_CLASS` 3136 in force, 6 full
pages + 9 streams reframed, numpy absent.

**No assertion failed on any base → nothing to file, no strict-xfail added.**

### Runtime — `tests/test_codec_bases.py -q -rs --durations=10`

`37 passed in 3.90s` (wall 4.3 s; budget was < 30 s). Slowest:

```
1.03s call  test_unit0_records_roundtrip_byte_exact[2025]
0.97s call  test_unit0_records_roundtrip_byte_exact[2024]
0.90s call  test_unit0_records_roundtrip_byte_exact[2026]
0.16s call  test_ecc_verifies_with_numpy_hidden
0.09s call  test_adocument_decode_clean_and_encode_byte_exact[2026]
0.08s call  test_adocument_decode_clean_and_encode_byte_exact[2025]
0.08s setup test_every_gzip_member_crc_ok[2026]      (first reading32: schema parse, memoized after)
0.07s call  test_adocument_decode_clean_and_encode_byte_exact[2024]
0.06s setup test_every_gzip_member_crc_ok[2025]
0.06s setup test_every_gzip_member_crc_ok[2024]
```
Everything else ≤ 0.01 s.

### No leaked module state (run together with the other release-switching modules, both orders)

```
pytest tests/test_codec_bases.py tests/test_validate_release.py tests/test_versions.py tests/test_records32.py -q -rs
  91 passed, 19 skipped, 1 xfailed in 5.96s
pytest tests/test_records32.py tests/test_versions.py tests/test_validate_release.py tests/test_codec_bases.py -q -rs
  91 passed, 19 skipped, 1 xfailed in 5.93s
```
(the three siblings alone: 54 passed / 19 skipped / 1 xfailed — the 19
skips are `test_versions.py` dev-sample cases, the xfail is pre-existing.)

### Other gates

* `python3 tools/dev/check_portable_paths.py` → ok (2768 tracked paths before this branch's two new files; re-run after commit: ok).
* `.venv/bin/python tools/sync_plugin.py --check` → in sync (nothing under `src/`/`tools/`/`skills/` touched).
* `/verify`: SKIP — tests-only diff (`tests/test_codec_bases.py`, `tests/ci_shard.txt`, this record), no runtime surface.

## Findings

* All seven DONE laws hold byte-exact on all three pinned bases today; the
  2026 base's unit 0 carries exactly one record whose object decode is not
  clean (seq 102) — excluded from the tested set by `roundtrip_segment`'s
  contract and passed through verbatim by `reencode_segment`, which still
  reproduces the segment byte-for-byte. Not a defect of this stream; noted
  so a future re-pin that changes it is recognisable.
* The ECC read/verify path is a single stdlib code path (`rvt.ecc` imports
  no numpy at all since #182/#75), so "numpy hidden" changes nothing but
  the interpreter's `sys.path`; the bare case is kept as the tripwire that
  it stays that way.

## Open questions / follow-ups

None required by the charter. (If a fourth base — 2023, #17 — is pinned
under `plugin/assets/genesis/`, adding it to `BASES` exercises the
`ids32` rung of `reading32` with no other change.)

## BRANCH STATE

* Branch `cam/132-codec-bases-tests` from `main@109345e`; PR closes #132.
* Files: `tests/test_codec_bases.py` (new, 37 cases), `tests/ci_shard.txt`
  (+1 line), `docs/inbox/codec-bases-ci.md` (this). Nothing else.
* Gates: module 37 passed / 0 skipped / 0 xfailed in 3.90 s; cross-module
  both orders 91 passed / 19 skipped / 1 xfailed; portable paths ok;
  `sync_plugin.py --check` in sync. Nothing staged for the viewer (tests
  only — no output bytes exist, no certification round implied).
* Shipped vs staged: everything is in the PR; no experiments, assets or zip.
