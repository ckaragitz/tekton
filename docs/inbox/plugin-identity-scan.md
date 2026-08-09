# plugin-identity-scan — issue #193 (Refs #19, #108; PG5)

## What was built

The plugin's deny-audit (`tools/sync_plugin.py` `DENY_PATH_PARTS`) is path-based;
until now nothing looked at the **bytes** we ship. This stream adds a content
audit that freezes today's inherited identity residue and forces it to shrink.

**1. `tools/sync_plugin.py` — `audit_identity_strings()` / `check_identity_strings()`.**
Scans `plugin/**/*.{rvt,rfa,json,md,txt,ifc,tksc}` (the issue's five extensions
plus our `.ifc` examples and `.tksc` schema-cache assets — both named leak
vectors in the Why, both clean today) and, when it exists, every such member of
the built `tekton-plugin.zip`. Tokens = `rvt.provenance.AUTODESK_EMPLOYEE_USERNAMES`
(imported, no copy; the constant was already public and in `__all__`) +
`C:\Users\`. Every token is matched ASCII **and** UTF-16LE (the interleaved-NUL
spelling, no decode pass), case-insensitively, plus the JSON/markdown-escaped
`C:\\Users\\` spelling, in **one** regex pass over each blob's lowered bytes.
`.rvt`/`.rfa` are opened with our own `rvt.container` (`RvtDocument` over a
`BytesIO`, so zip members need no temp file) and scanned **per CFB stream**: the
stream's uncompressed prefix (the whole stream when it has no gzip members, e.g.
`BasicFileInfo`) plus every gzip member **inflated** — a raw skim of the container
sees only `BasicFileInfo`/`ProjectInformation`/`TransmissionData` and is blind to
`Global/DocumentIncrementTable` and `Partitions/*`, where most of the usernames
live; the compressed envelope itself is not skimmed (a token cannot survive
deflate). A zip member whose central-directory `(CRC32, size)` equals a tree
file's is that file again and reuses its result **without being extracted**, so
the zip — which repeats the tree verbatim — costs ~nothing. A container that will
not open (`OSError` from olefile) falls back to a raw scan under member `<raw>`
(still caught); anything else inside the walk, and a missing `olefile`, fails
loudly instead of silently degrading to that skim.

**2. `tools/plugin_identity_allowlist.json` (new).** Exactly the 41
`(file, member, token, count)` rows measured on `main` @ `c66333e`, all three
genesis bases, every row `tracked_by: "#19"`, one row per line so #19's scrub PR
is a readable deletion. `member` (the CFB stream) is a refinement of the issue's
`(file, token, count)`: it is what the issue's own Evidence was measured in, and
it lets #19 retire `BasicFileInfo` rows before `DocumentIncrementTable` ones.

**3. `--check` prints the table and exits 1** on any *mismatch*: one list of
`(origin, file, member, token, got, want)` covers both directions — a hit with no
allowlist row or a different count is `UNEXPECTED` (tree **or** zip), an
allowlist row with 0 hits in the tree is `VANISHED … delete its row` (diffed
against the tree only: the allowlist has no origin dimension and the zip can only
ever *add* unexpected hits). The full build (`sync_plugin.py` without `--check`)
runs the same audit *after* `rebuild_zip()` so the fresh zip is covered, prints
problems + summary only, and returns 5 on a mismatch. Zip rows are compared
against the same allowlist rows (member path == plugin relpath); a stale zip with
a leak the tree no longer has fails `--check` and the message says to rebuild —
the zip is git-ignored and absent in CI, where only the tree is scanned. One
formatter (`format_identity_report`) renders table / problems / summary for
`--check`, the build, the tests and `validate_plugin.py` alike.

**4. `plugin/scripts/validate_plugin.py` — `check_identity_strings()`.** Borrows
the very same audit *and its wording* from `../tools/sync_plugin.py` when the
plugin sits in the repo (CI's "Plugin structure" step, `[plugin-root]` argument
honoured; every `UNEXPECTED`/`VANISHED` line becomes a failure), so the two gates
cannot disagree; a bare install has no repo beside it and records `identity scan
skipped` as a note (the build that produced it ran the scan). In CI this means the
~0.25 s scan runs in both steps — the issue asks for both gates, and the docstring
says so, so nobody "optimises" one away.

**5. `tests/test_plugin_sync.py`** — `test_identity_scan_matches_allowlist`
(shipped tree == allowlist; allowlist hygiene: only the three bases, every row
`#19`, no duplicate keys, tokens ⊆ the engine's set) and
`test_identity_scan_catches_injected_strings` (tmp plugin + zip: mixed-case ASCII
`HansonJe` in a reference `.md`, UTF-16LE `C:\Users\…` in a `.txt`, `okapaw` in a
non-CFB `.rfa` → `<raw>`, the same `.rfa` stored verbatim in the zip (CRC/size
reuse path), a zip-only member, a JSON-escaped `c:\\users\\` path; a `.py`
carrying the deny constants is *not* scanned; against the real allowlist every
injected hit is UNEXPECTED and all 41 base rows are VANISHED exactly once (tree);
a matching allowlist passes; a stale count fails with `(got, want)`; and
`validate_plugin.py <tmp-root>` goes red with the identical wording). The existing
`test_plugin_is_in_sync_with_source` additionally asserts the table is printed.
`audit_deny()` and the new scan now share one `_shipped_files()` walker, and
`sync_schema_cache()` and the scan one `_src_on_path()`.

## Evidence (numbers, current `main` c66333e, this cloud VM)

Measured hits — identical whether walked with `rvt.provenance.content_units`
(release-aware, per save-unit) or the lighter `rvt.container` per-stream walk
that ships (chosen: same numbers, no framing/schema dependency, ~4× faster warm):

| base | BasicFileInfo | Global/DocumentIncrementTable | ProjectInformation | TransmissionData | Partitions/N |
|---|---|---|---|---|---|
| G_ABPD.rvt (2026) | C:\Users\ 2, hansonje 2 | campbes 2, gbs_subsuser6 2, hansonje 2, loboarch 18, okapaw 8, xuew 6, youyi 4, zhangg 2 | C:\Users\ 2, hansonje 2 | C:\Users\ 2, hansonje 2 | — |
| G_ABPD_2025.rvt | same | same but loboarch 16 | same | **none** | Partitions/20: C:\Users\ 1, hansonje 1 |
| G_ABPD_2024.rvt | same | same but loboarch 20 and **no hansonje** (7 names) | same | **none** | Partitions/21: C:\Users\ 1, hansonje 1 |

Differences from the numbers quoted in the issue body (measured again, as asked):
the issue's `DIT{hansonje:2, zhangg:2}` undercounts — the increment table carries
all 8 names (7 on 2024, as the issue's identity_report list already said) with
2–20 occurrences each; the issue's "2025 = same + Partitions/20" implies a
`TransmissionData` hit on 2025 — there is none on 2025 or 2024 (only 2026 ships
that stream with a path in it), and 2024 has its own `Partitions/21` hit the issue
did not list; the issue's `BFI{Autodesk:2}` is real but `Autodesk` is not in this
gate's token set (DONE = usernames + `C:\Users\`; the author-string question is
counsel C1 / #19's identity block, and `rvt.provenance.RESOURCE_PATTERNS` already
ledgers it). All other text/example/asset files in the plugin: **0 hits** (also
0 for `.py/.js/.toml` apart from the engine's own deny constants, which is why
source files are deliberately outside the scan set).

Wall time (steer S-2026-08-09-g — this runs on every `--check`):

| command | before | after |
|---|---|---|
| `tools/sync_plugin.py --check`, no zip (CI / fresh clone) | 0.34 s | 0.55 s (scan itself 0.21–0.23 s: 97 files, 3 containers ≈ 12 MB inflated) |
| `tools/sync_plugin.py --check`, zip present | 0.35 s | 0.56–0.57 s (97 files + 97 zip members, 0.22–0.24 s — zip members match the tree by CRC/size and are never extracted) |
| `plugin/scripts/validate_plugin.py` | 0.05 s | 0.33 s (engine import + the same ~0.23 s scan) |
| `tools/sync_plugin.py` full build (sync + `claude plugin validate` + zip + scan) | — | 1.9–2.1 s total, scan 0.23 s |
| `tests/test_plugin_sync.py tests/test_plugin_validate.py` | 13 tests | 15 passed in 1.3–1.5 s |

(First cut, before the `/simplify` pass: 0.58–0.70 s `--check`; the review removed a
temp-file round trip per zip container, the sha256 of every zip member, and the
skim of each stream's compressed envelope.)

Scan-strategy bench on G_ABPD.rvt (3.8 MB inflated): 18× `bytes.count` 64 ms;
one case-sensitive alternation regex 27 ms; `re.IGNORECASE` on bytes 509 ms (!);
`lower()` + case-sensitive regex ≈ 30 ms ← shipped. Container open + inflate ≈ 20 ms
warm per base; the first container pays ~45 ms of engine import.

`/verify` (driven for real, this VM, final head): (1) `tools/sync_plugin.py` build →
`97 file(s) + 97 zip member(s) scanned in 0.23 s: 82 hit(s), 0 mismatch(es)`, exit 0,
zip 5.1 MB; (2) `--check` exit 0 in 0.56 s; (3) temp copy of `plugin/` with
`last saved by C:\Users\HansonJe\Desktop` appended to
`skills/tekton-author/references/GENESIS-BASE.md` → `validate_plugin.py <copy>` exit 1,
`FAILURES: 2`: `identity scan: UNEXPECTED skills/tekton-author/references/GENESIS-BASE.md
carries 'C:\\Users\\' x1 …` and `… carries 'hansonje' x1 -- remove the string from the
file (never extend the allowlist)`; (4) one allowlist count bumped 2→3 → `--check` exit 1,
`UNEXPECTED assets/genesis/G_ABPD.rvt :: BasicFileInfo carries 'hansonje' x2, allowlist
says x3` (tree + zip rows, `2 mismatch(es)`); (5) a phantom row added
(`Global/History okapaw 1`) → `--check` exit 1, `VANISHED assets/genesis/G_ABPD.rvt ::
Global/History 'okapaw' x1 is gone from the bytes -- delete its row`, `1 mismatch(es)`
(once, tree only); allowlist restored byte-identical after (4) and (5); (6) the rebuilt
zip unzipped bare into `out/verify/pz`, system `python3 skills/tekton-author/scripts/
_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json`
→ `go.ready = True`, `prompt_room.rvt` + families delivered, status `PROOF-ONLY
(self-checks PASS)`, 3.6 s wall. (Validates/READY — not a "loads in Revit" claim, rule 4.)

## Findings

* The leak set is bigger than the path audit ever suggested: **82 tracked hits**
  across tree + zip, 8 distinct Autodesk usernames, and a `C:\Users\hansonje\…`
  path in four different streams of the 2026 base including an element record
  inside `Partitions/20|21` on 2025/2024 — #19's scrub has to reach into the
  partition, not only the metadata streams.
* `re.IGNORECASE` on a bytes alternation is ~19× slower than lowering the
  haystack once; worth remembering for any future byte-level guard.
* `validate_plugin.py` used to pass under a bare `python3` with no deps; it now
  needs `olefile` (the engine's one runtime dep) when run inside the repo, and
  says so (`identity scan could not run: No module named 'olefile' -- run with the
  repo's .venv/bin/python`). CI installs the package first, `cloud-setup.sh` uses
  `.venv`, and a bare *install* (no repo beside it) skips the scan, so no
  supported path regressed — but it is a behaviour change and is stated here.

* `/simplify` review (4 angles) found a second instrument for the same measurement:
  `tools/genesis_identity.py:455 byte_scan()` (#19's rung checker) scans the same
  usernames plus a **wider** path-needle set (`PATH_NEEDLES`: `\AppData\Local\`,
  `ProgramData\Autodesk`, `Program Files\Autodesk`, `OneDrive - Autodesk`,
  `\Desktop\Downloadable Files`). Measured with that wider set, the three bases carry
  **17 more residue hits this gate does not freeze** (e.g. `TransmissionData` on
  2025/2024: `ProgramData\Autodesk` x2 — no `C:\Users\` there, so this gate sees that
  stream as clean; `Partitions/20|21`: `OneDrive - Autodesk` 1 + `ProgramData\Autodesk` 1;
  `ProjectInformation`: `\AppData\Local\` x2 on all three). Kept to the issue's DONE
  (usernames + `C:\Users\`) here; unifying the two scanners behind one
  `rvt.provenance` primitive and deciding whether this gate widens is filed as **#305**.

## Open questions / follow-ups

* **#305** (filed by this stream, `Refs #193`): one identity-residue scan primitive
  shared by `genesis_identity.byte_scan` and this gate; decide the plugin gate's
  path-needle set with a measured false-positive check over `plugin/**/*.md`.
* When #19 lands its scrubbed bases, its PR must delete the matching rows here —
  the gate enforces that mechanically (VANISHED → exit 1), so no separate issue.
* `Autodesk` / `Autodesk Revit` author strings in `BasicFileInfo` are outside this
  gate on purpose (counsel C1, #23/#19). If the owner wants them frozen the same
  way, it is one more token here — file it then, not now.
* Review findings deliberately *not* taken: dropping the scan from `validate_plugin.py`
  (the issue asks for both gates; cost 0.25 s per CI step); short-circuiting pinned
  bases by sha (would make the gate trust recorded hits instead of reading bytes);
  scanning `.py/.js` too and allowlisting the engine's own deny constants (every edit
  of `provenance.py` would then churn the allowlist); re-implementing the gzip member
  walk to avoid `RvtDocument.members()`' measure-then-inflate double pass (~8 ms/base,
  not worth a private copy of engine logic).

## BRANCH STATE

* Branch `cam/193-plugin-identity-scan` from `main` @ c66333e.
* Files written: `tools/sync_plugin.py` (+identity audit, wired into `--check` and
  the full build; `audit_deny` now shares `_shipped_files()`), `tools/plugin_identity_allowlist.json`
  (new, 41 rows), `plugin/scripts/validate_plugin.py` (+`check_identity_strings`),
  `tests/test_plugin_sync.py` (+2 tests, shared `_sync_plugin()` loader),
  `docs/inbox/plugin-identity-scan.md` (this record). No hot file, no `src/`
  change (the username constant was already public), no asset change.
* Gates (final head): `tests/test_plugin_sync.py` + `tests/test_plugin_validate.py`
  **15 passed**; `tools/sync_plugin.py` build exit 0 then `--check` exit 0 (identity
  scan == allowlist, 0 drift — `sync_plugin.py` is not mirrored into `plugin/lib/tools/`);
  `plugin/scripts/validate_plugin.py` **PASS (25 assertions)**;
  `tools/dev/check_portable_paths.py` ok (2763 paths); `/simplify` ran (4 review
  agents; fixes applied, skips listed above); `/verify` ran (six drives above).
* Follow-up filed: #305. Shipped in the PR; nothing staged for the viewer (no bytes changed).
