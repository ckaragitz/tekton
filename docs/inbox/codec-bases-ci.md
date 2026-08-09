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

`tests/test_codec_bases.py` — 40 cases, parametrized over
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
| (b) | `test_ecc_full_page_trailers_and_reframe` | `ecc.page_trailer(page)` == the stored 353-byte trailer for every full page; `frame_stream(unframe_stream(raw)) == raw` for every CRCIO-framed stream (everything not in `rvt.validate.UNFRAMED_STREAMS`); the framed set ⊇ `Formats/Latest`, `Global/Latest`, `Contents`, every partition |
| (b′) | `test_ecc_verifies_with_numpy_hidden` | the same two laws on the 2025 base (so non-default ordinals are in force) from a **bare interpreter** (`-I -S`: no site-packages → `find_spec('numpy') is None`, only `src/` + the plugin's vendored `olefile` on the path), inside `reading32`, and `'numpy' not in sys.modules` afterwards — the `tests/test_coldstart.py` recipe |
| (c) | `test_stream_codec_roundtrip_byte_exact[<year>-<name>]` | `stream_encoders.roundtrip(name, x)` byte-exact (`CODECS` `enc(dec(x)) == x`) for ElemTable / History / DocumentIncrementTable / PartitionTable (`Global/*` member 0), Contents (member 0), BasicFileInfo (raw) — 18 cases |
| (d) | `test_unit0_records_roundtrip_byte_exact` | `StreamWalker` 0 errors + every block `crc_ok` on every partition stream; unit 0: `roundtrip_segment` `pass == tested > 0` and `skipped_bad_trailer == 0` per seq, Σ tested over 101/102/103 ≥ 9000; `reencode_segment(seg) == seg` with `tail == 0` for each seq — encoder built on the base's **own** schema (`ObjectEncoder(schema_of(doc))`) |
| (d′) | `test_unit0_every_record_decodes_clean` | the stricter law behind (d): no unit-0 record is excluded from the tested set for a lossy object decode. **2026 strict-xfail → #138** (see Findings); 2025/2024 pass |
| (e) | `test_adocument_decode_clean_and_encode_byte_exact` | `ADocumentDecoder(schema_of(base))`: `errors == []`, `clean`, trailer == `u32 0`, consumed + 2 + 4 == payload length, `encode_latest(adoc) == payload` |
| (f) | `test_cfb_roundtrip_is_stream_equal` | `rvt.roundtrip.roundtrip(base, tmp)` → CFB v4 / 4096-byte sectors; `verify_pair` reports no difference (the `(compoundfiles cross-check skipped …)` note is dropped **only** when that optional second reader is genuinely absent — `find_spec("compoundfiles") is None` — so a real rejection by it on a machine that has it still fails the test) |
| (g) | `test_schema_matches_known_release_pin` | the engine's own pin law `rvt.versions._release_schema.verify_schema(KNOWN_RELEASES[year], schema_of(base))` (size, sha256, class_count, 0 unresolved refs); `detect_release == year` |

No record/page/member counts are hard-coded (bases get re-pinned, #19):
only structural minima (Σ tested ≥ 9000 from the issue, ≥ 1 full page,
named streams present). Mismatch diagnostics reuse
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

**Every DONE law (a)–(g) holds on all three bases → nothing loosened.** One
strict-xfail was added, on the *extra* stricter case (d′) for 2026 only,
against the already-open #138 (see Findings) — no new issue needed
(searched: `Extensible Storage DataStorage decode` → #138 is the tracker).

### Runtime — `tests/test_codec_bases.py -q -rsx --durations=8`

`39 passed, 1 xfailed in 4.81s` (budget was < 30 s). Slowest:

```
1.03s call  test_unit0_records_roundtrip_byte_exact[2025]
0.99s call  test_unit0_records_roundtrip_byte_exact[2024]
0.90s call  test_unit0_records_roundtrip_byte_exact[2026]
0.30s call  test_unit0_every_record_decodes_clean[2025]
0.28s call  test_unit0_every_record_decodes_clean[2024]
0.25s call  test_unit0_every_record_decodes_clean[2026]   (xfail, #138)
0.16s call  test_ecc_verifies_with_numpy_hidden
0.09s call  test_adocument_decode_clean_and_encode_byte_exact[2026]
```
Fixture setup (first `reading32` per base = schema parse, memoized after)
0.06–0.08 s ×3; everything else ≤ 0.01 s.

### No leaked module state (run together with the other release-switching modules, both orders)

```
pytest tests/test_codec_bases.py tests/test_validate_release.py tests/test_versions.py tests/test_records32.py -q
  93 passed, 19 skipped, 2 xfailed in 6.62s
pytest tests/test_records32.py tests/test_versions.py tests/test_validate_release.py tests/test_codec_bases.py -q
  93 passed, 19 skipped, 2 xfailed in 6.68s
```
(the three siblings alone: 54 passed / 19 skipped / 1 xfailed — the 19
skips are `test_versions.py` dev-sample cases and that xfail is
pre-existing; the second xfail is (d′)[2026] above.)

### Other gates

* `python3 tools/dev/check_portable_paths.py` → ok: 2770 tracked paths are portable.
* `.venv/bin/python tools/sync_plugin.py --check` → plugin in sync with source (nothing under `src/`/`tools/`/`skills/` touched).
* `/simplify` on the diff: applied — engine helpers instead of local re-derivations (`se.roundtrip`, `verify_schema`, `validate.UNFRAMED_STREAMS` as the sole ECC-exemption source), redundant assertions dropped, the compoundfiles filter gated on the reader's absence, the (d′) case added so the #138 gap is visible in CI rather than routed around by `only_clean`.
* `/verify`: SKIP — tests-only diff (`tests/test_codec_bases.py`, `tests/ci_shard.txt`, this record), no runtime surface.

## Findings

* All seven DONE laws hold byte-exact on all three pinned bases today. The
  2026 base's unit 0 carries exactly one record whose object decode is not
  clean: seq 102, element 1382860, class `DataStorage` (0x4a4), error
  `m_cellList->CellList.m_cells[0]->ESEntityCell.m_entityMap[0].second.m_blob:
  pointer token pid=-1 to unknown class 0x88ee` — the documented
  Extensible-Storage entity-blob gap (10-objects.md B1) that #138 exists to
  close. `roundtrip_segment` excludes it from the tested set by contract and
  `reencode_segment` passes it through verbatim (segment still byte-exact),
  so (d) is green; (d′) makes the gap itself red-able and is strict-xfailed
  on 2026 against #138 so it retires itself when that lands. 2025/2024 unit 0
  decode 100 % clean.
* `rvt.roundtrip.verify_pair` mixes an informational note
  (`(compoundfiles cross-check skipped: …)`, emitted from a bare `except
  Exception`) into its problem list, so callers must string-filter it and a
  genuine rejection by that second reader would be filtered too;
  `tests/test_roundtrip.py` asserts `problems == []` unfiltered and is only
  green because it self-skips without `samples/`. Small `area:engine`
  follow-up (notes vs problems split); out of this stream's no-`src/`
  territory, recorded here for the planner.
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
* Files: `tests/test_codec_bases.py` (new, 40 cases), `tests/ci_shard.txt`
  (+1 line), `docs/inbox/codec-bases-ci.md` (this). Nothing else.
* Gates: module 39 passed / 0 skipped / 1 xfailed (strict, #138) in 4.81 s;
  cross-module both orders 93 passed / 19 skipped / 2 xfailed; portable
  paths ok (2770); `sync_plugin.py --check` in sync. Nothing staged for the
  viewer (tests only — no output bytes exist, no certification round implied).
* Shipped vs staged: everything is in the PR; no experiments, assets or zip.

## 2026-08-09 — addition by stream #330 (review-nit sweep), not the codec-bases voice

The `verify_pair` notes-vs-problems follow-up recorded under *Findings* is done in
`src/rvt/roundtrip.py`: `verify_pair` now returns `VerifyResult(problems, notes)`
(a `NamedTuple`; unpack as `problems, notes = verify_pair(a, b)`). The
"`(compoundfiles cross-check skipped: reader not installed)`" line is a *note*, emitted
only when `_verify_with_compoundfiles` returns `None` because
`importlib.util.find_spec("compoundfiles") is None` (decided before the import, not by
catching `ImportError`); any exception from that reader once installed is a *problem*
(`compoundfiles could not read output: …`), so a genuine rejection can no longer be
filtered by anyone. Truthiness of the result follows `problems`
alone (`if verify_pair(a, b):` still means "differs"); comparing the result to
`[]` is now always False — compare `.problems`. Callers updated: the CLI
(`python -m rvt.roundtrip --verify`, prints notes after the verdict),
`tests/test_roundtrip.py`, and `tests/test_codec_bases.py`, whose prefix filter is
gone — law (f) asserts `problems == []` unfiltered and additionally that a note is
present iff `find_spec("compoundfiles") is None`.
BRANCH STATE: `cam/330-review-nit-sweep`; `tests/test_codec_bases.py
tests/test_roundtrip.py` → 42 passed / 12 skipped (samples, compoundfiles) /
1 xfailed (#138) in 6.0 s; mirror regenerated by `tools/sync_plugin.py`.
