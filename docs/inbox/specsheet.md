# specsheet — a user-supplied spec sheet read into CITED facts

Stream: `specsheet` (2026-08-11), issue #688 under steer #685 / #687. Code:
`src/rvt/specsheet/**`. Tests: `tests/test_specsheet_values.py` (56),
`tests/test_specsheet_read.py` (20). Confidence tags: **[V]** verified by a
test in this branch, **[D]** design decision, **[O]** open / not done here.

## 0 · Why this lane exists

Steer #685 drew a hard line: model knowledge may supply taxonomy and standard
practice, but **never a manufacturer's dimensions as a `fact`**. Recalled
numbers written into `famgen/facts/**` would be fabricated catalog data at
scale. A spec sheet the **user** supplies is a *source*, so this lane is the
honest route to real member data — and it is the one lane where a generated
family may wear a real manufacturer / model / part number on its identity
parameters, because the user supplied the document that says so.

Everything below follows from that: the value of the lane is entirely in the
provenance being exact, so the design refuses far more than it accepts.

## 1 · Shape [D]

Five modules, in the order the data flows:

| module | does |
|---|---|
| `pdftext.py` | stdlib-only text-layer PDF reader → positioned `Fragment`s per page. Scans the object body directly (not `/XRef`), decodes `FlateDecode` via `zlib`, walks `BT`/`Tm`/`Td`/`TJ`/`Tj`/`'`, reads `/ToUnicode` CMaps. |
| `_backend.py` | picks the optional `pdfplumber` wheel when installed, the stdlib reader otherwise; `RVT_PDFLITE_FORCE=1` forces stdlib. Both backends return the same `Document` in the same coordinate convention. |
| `table.py` | fragments → `Row`/`Cell` grouped by baseline `y`, ordered by `x`; mints the `Citation` (document, page, row text, cell text). |
| `values.py` | reads ONE number from a cell **or refuses with a reason**. |
| `sheet.py` | assembles the cited `FactSheet`; renders the parsed table AS READ. |

## 2 · No new REQUIRED runtime dependency [V]

`olefile` remains the only declared runtime dep. `pdfplumber` lives in a new
`[pdf]` extra, exactly as `ifcopenshell` lives in `[ifc]`, and the posture is
copied from `rvt.ifc._fallback` (#130): optional wheel wins when present,
stdlib reader serves otherwise, a `*_FORCE` env forces the fallback for A/B,
and an availability predicate is the one definition of "is the real library
here". `tests/test_specsheet_read.py::test_the_stdlib_reader_serves_with_no_pdf_wheel_installed`
reads a full sheet with `RVT_PDFLITE_FORCE=1`; no test in this branch needs
the wheel.

**One deliberate difference from `_fallback` [D].** `rvt.ifc` falls back by
appending a look-alike `ifcopenshell` package to `sys.path`, because its
consumer modules already say `import ifcopenshell` and must not be edited.
This lane's consumers are all ours and new, so selection is an ordinary
function call and no global path is mutated. Same user-visible contract,
simpler mechanism, nothing global touched.

## 3 · Every value is a `fact` with a citation [V]

A `Fact` from this lane carries `kind="fact"` and a `source` that is the full
citation — **file, page, and the row/cell text it came from**:

```
length_in = 47.75   fact   acme-tl24.pdf p.1: "47.75 in" in row "Length  47.75 in"
```

A length stated in another unit keeps the **stated figure as the fact** and
adds our conversion as a separate `derived` entry (`<field>_derived_in`), so
the sheet's statement and our arithmetic can never be confused. Nothing is
interpolated; nothing is rounded into a fact. Fractions (`2-3/8"` → 2.375)
are exact at the denominators sheets use.

## 4 · What the value gate REFUSES [V]

This is the heart of the lane. Each refusal below is a cell a real sheet
prints, and each would be a fabricated dimension if resolved:

| cell | refused because |
|---|---|
| `36-90`, `36 to 90`, `36–90` | the sheet states a **range**; we do not pick an end |
| `15, 30, 45` | a **list**; same reason |
| `Contact factory`, `N/A`, `—`, `TBD` | the sheet states **no value** — never `0` |
| `up to 90`, `approx. 47`, `<10`, `± 5`, `nominal 24` | a **qualifier** changes the claim; dropping it turns a bound into a dimension |
| `100 A 3P` | **two numbers**; picking one guesses the column |
| `47.7� in` | the text could not be **decoded**; a guessed glyph is a guessed number |

A refused field gets **no Fact at all** and its reason is recorded, so the
report says *why* a field is blank rather than leaving a silent hole. A
mixed fraction's `-` is tested explicitly so it is never read as a range.

## 5 · Show the extraction before trusting it [V]

`SheetReading.parsed_table()` prints the table **as read** — every row, every
cell, including the cells we refused — so a wrong column is visible rather
than silently built into a family. Row/cell grouping uses tolerances and an
estimated glyph advance; those decide *placement only* and never rewrite,
round or synthesise text. When a caller truncates the table the output says
so and gives the full row count, rather than looking like the end of the sheet.

## 6 · Hard rule 1 — an unreadable sheet is one clear line [V]

Every unreadable input comes back as a single-line `SheetError`, never a
traceback: a missing file, a non-PDF, a truncated PDF, an encrypted PDF, a
directory path, and (through `pdftext`) an unsupported stream filter, which
is **named** rather than swallowed. A page with **no text layer** is reported
as scanned — never as "the sheet says nothing" — and a mixed document still
delivers the pages that did read. The optional backend's own exception types
are wrapped so they cannot escape as a traceback either.

## 7 · Tests, written against PR #674's three recurring failure classes [V]

#674 took six review rounds and twenty-six findings, all after CI was green.
The recurring classes drove the test design here:

* **(a) text asserting behaviour the code did not implement** — the report's
  claims are each asserted against what the code did: the table shows every
  parsed cell, names its backend, states truncation, states scanned pages.
* **(b) parsing that silently dropped or invented a number** — the whole of
  `test_specsheet_values.py` (56 cases), plus round-trip assertions that the
  citation quotes the row the value came from.
* **(c) an exception escaping and withholding a file** — seven unreadable
  inputs, each asserted to be one clear line.

One real bug was caught this way during the build and is worth recording: the
dictionary-value reader stopped at the first `/`, so `/Filter /FlateDecode`
captured an **empty** filter and every compressed page silently produced zero
text — a full sheet would have been reported as scanned. That is failure
class (b) exactly. `test_compressed_and_plain_streams_read_identically` is
the regression guard.

## 8 · NOT done in this branch [O]

Stated plainly rather than implied by silence:

* **The router / matrix INPUT kind is not wired.** `INPUT_KINDS` in
  `src/rvt/frontdoor/matrix.py` still spends the name `spec` on the
  building-spec JSON dialect, so a spec-sheet kind needs its own name
  (`specsheet`). Adding cells means declaring evidence that `verify_evidence()`
  will hold us to, and a matrix row claiming more than this branch proves
  would be failure class (a) at the product surface. Left for the follow-up
  that has #688's DONE text.
* **`manufacturer_claim`'s warning is not suppressed**, because
  `rvt.famgen.archetypes` does not exist on `main` at `ea6b875` — it arrives
  with PR #674, which is unmerged (no merge commit, no remote branch). The
  hook this lane offers is `SheetReading.backing_document()`; wiring the
  suppression to it is a one-liner once #674 lands.
* **No `nominal` tier was invented.** `Fact.kind` on `main` is
  `fact | assumed | derived | given | ours`; `nominal` arrives with the same
  archetype work. A field the sheet does not state is therefore **blank with
  a recorded reason**, which is the other half of the issue's own
  "`nominal` or blank".
* No `.rfa` was produced or validated by this branch — nothing here reaches
  the writer yet, so there is no output file to validate and nothing is
  staged for the viewer.

## BRANCH STATE

* Branch `eng/688-specsheet` from `origin/main` @ `ea6b875`, not rebased (no
  upstream movement during the branch); one issue, one PR (`Closes #688`).
* Files: NEW `src/rvt/specsheet/{__init__,pdftext,table,values,sheet,_backend}.py`;
  `pyproject.toml` (+`pdf` extra, `all` extended, extras comment);
  `tests/conftest.py` (+`build_specsheet_pdf`, +`zlib` import — the sheet
  builder lives once because two test modules build sheets, per #579/#670);
  NEW `tests/test_specsheet_values.py` (56 tests), NEW
  `tests/test_specsheet_read.py` (20 tests), NEW
  `tests/ci_shard.d/688-specsheet.txt`; mirrors
  `plugin/lib/src/rvt/specsheet/**` (6 files, byte-identical via
  `tools/sync_plugin.py`); NEW this record.
* Gates: `tests/test_specsheet_values.py` **56 passed** (0.08 s);
  `tests/test_specsheet_read.py` **20 passed** (0.12 s); together with
  `test_plugin_sync test_pyproject_extras test_conftest_scaffolding
  test_layout_law test_shard_list`: **142 passed, 0 failed** in 4.62 s.
  `tools/sync_plugin.py` rebuilt (6 files synced, deny-audit clean, identity
  scan == allowlist) + `--check` clean ("plugin in sync with source");
  `plugin/scripts/validate_plugin.py` **PASS** (25 assertions);
  `tools/dev/check_portable_paths.py` **ok** (3074 tracked paths, the 16 new
  files included).
  Full-suite run NOT done (`docs/inbox/SUITE-COORDINATION.md`: one canonical
  run at a time) — stream-local + the laws only.
* No `.rfa` produced, so no validator run and nothing staged for the viewer.
* **Claim/PR status:** this session had **no GitHub API access** — the API
  answers `GitHub access is not enabled for this session. An org admin must
  connect the Claude GitHub App for this organization.` (no `gh`, no GitHub
  MCP tools either). So #688 could not be read, could not be assigned, and
  carries **no 🔒 comment**, and the PR was not opened from here. Git over
  the proxy works, so the branch is pushed. A session with API access must
  verify nobody else holds #688 before this is merged — under
  S-2026-08-09-f the claim is the lock, and it was never taken.
