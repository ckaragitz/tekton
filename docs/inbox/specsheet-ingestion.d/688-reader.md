# specsheet-ingestion / #688 — the reader: positioned text, a layout layer, cited values

Fragment of the `specsheet-ingestion` stream (index:
`docs/inbox/specsheet-ingestion.md`, charter #688). Nobody else appends here.

Covers **DONE 2, 3, 4** and the reader half of **DONE 6**. DONE 1 (`route run
--pdf`, the `pdf` INPUT kind) and DONE 5 (identity parameters, the suppressed
`manufacturer_claim` warning) are the follow-up PR on this issue — this one is
`Refs #688`, not `Closes`.

## What was built

`src/rvt/specsheet/`, four layers, each checkable on its own:

| module | answers | depends on |
|---|---|---|
| `pdftext.py` | what was drawn, and **where** | stdlib only (`zlib`, `re`) |
| `layout.py` | which row / cell / column | `pdftext` |
| `vocab.py` | what a row label means | nothing |
| `sheet.py` | the cited value | all three |
| `_backend.py` | which extractor | optional `[pdf]` extra |

The split is the point. "What was drawn at x=300" is a **fact about the
file**; "the row labelled Depth is the family's depth" is an **inference**.
They are produced by different modules, and `ParsedSheet.report()` prints the
inference next to the fact it came from, which is #688 DONE 4 ("the
extraction is shown before it is trusted").

### `pdftext` — three decisions that are not optional for a table

1. **Objects are found by scanning `N G obj`, not from the xref.** Real vendor
   PDFs ship stale xrefs; every viewer has a reconstruct path, so we go
   straight to it. Measured below: this is the one case where our reader beats
   the mature library.
2. **The CTM is composed with the text matrix.** A producer that wraps a table
   in `q 1 0 0 1 72 640 cm … Q` puts every glyph 72pt right and 640pt up of
   where the text matrix alone says. Ignoring it does not corrupt the text —
   it moves the whole table, so any tolerance tuned on one file stops working
   on the next.
3. **The pen advances after every drawn run**, by the font's own `/Widths`
   (simple) or `/W` (Type0). Without it every run of one `TJ` array lands at
   the same x and a table row collapses into one cell.

`Glyph` therefore carries a **measured** `width`, not `0.5 em × len(text)`.
Where a font declares no widths at all, the estimate is used *and surfaced as
a page note* — see the sized gap below.

### `layout` — three named tolerances, no buried literals

`y_tol_em` 0.45 (a baseline), `space_em` 0.18 / `cell_em` 1.6 (one word / one
cell / two cells), `col_tol_em` 0.8 (one column). All in `layout.DEFAULTS`,
all overridable per call, and an unknown parameter name **raises** rather than
being ignored — a silently misspelled tolerance changes the parse and says
nothing.

Column clustering measures from each cluster's **leftmost** member, not its
running mean. Against a drifting mean, 12 left edges each 3pt right of the
last chain into one cluster 33pt wide and two real columns silently become
one. Measured: leftmost-anchored gives **4** clusters at an 8pt tolerance,
mean-anchored gives **1**.

### `vocab` — breadth as data (#685 / S-2026-08-11-c)

Row-label synonyms, per-field kind (`length` / `number` / `text`) and the
length-unit table are plain dicts. Adding a synonym or a field needs no new
branch anywhere. The synonyms are ordinary trade usage ("Catalog Number",
"Cat. No.", "Part Number") and carry **no manufacturer fact** — matching
"Height" to `height_in` says nothing about how tall anything is.

Matching is **exact on the normalised label**. Substring matching was tried
and rejected: "Enclosure Height" contains "enclosure", so a substring rule
reads a panel's height into the NEMA-type field *and cites the sheet while
doing it*. A wrong value wearing a citation is worse than no value.

### `sheet` — what is taken, and what is refused

A value is `fact`-tier only when it was read off the page, and it carries
file + page + row:

```
height_in      = 62.0 in            <- probe.pdf p1 r3 'Height' = '62.0 in'
width_in       = 20.5 in            <- probe.pdf p1 r4 'Width' = '20-1/2 in'
model          = PW-400-42-NEMA1    <- probe.pdf p1 r1 'Catalog Number' = 'PW-400-42-NEMA1'
```

Refused by name, each one line, none of them blocking delivery (hard rule 1):

| input | what it says |
|---|---|
| `"480Y/277 V"` in a numeric field | not a single quantity, the field is left unset |
| `"62"` in a length field | states no length unit — a unit taken from a column header would be an inference, not a reading |
| an unknown label | listed under *rows read but NOT used*, never dropped |
| image-only page | scanned, no OCR is attempted |
| `/LZWDecode` | names the filter and says FlateDecode is what is supported |
| encrypted | says so; no attempt |
| a field stated twice | first wins, **and** it becomes a question (`ParsedSheet.questions()`) |

Nothing is interpolated, no range is rounded into a number, and no rating is
converted (a 65 kA must not become 65000 A). A dual dimension `62.0 in (1575
mm)` keeps the first and **notes** the second rather than averaging them.

## Evidence

### 1. Cross-implementation agreement — the strongest evidence here

Both backends produce the same `Page`/`Glyph`, so they can be run against one
file and compared. pdfminer (under `pdfplumber`) is an independent
implementation of the same format by other people; where it agrees with
`pdftext` on a **coordinate**, that coordinate is very unlikely to be our bug.

Four producer habits, one fixture sheet, 9 fields the engine knows:

| PDF shape | stdlib values | pdfplumber values | agree | row grid agrees |
|---|---|---|---|---|
| absolute `Tm` per cell | 9 | 9 | **yes** | yes |
| one kerned `TJ` array per row | 9 | 9 | **yes** | yes |
| `q <translate> cm … Q` | 9 | 9 | **yes** | yes |
| Type0 2-byte CIDs + `/ToUnicode` + `/W` | 9 | 9 | **yes** | yes |
| uncompressed stream | 9 | 9 | **yes** | yes |
| `/Filter [/FlateDecode]` (array spelling) | 9 | 9 | **yes** | yes |
| **stale xref** | **9** | **0** | **no — ours wins** | — |

The stale-xref row is the design decision (1) above paying off: pdfminer
trusts the table and returns zero pages. The result is **not** silently
swapped for the one that worked — that would make one document read
differently on two machines — but the refusal names the switch:

> the pdfplumber backend found no pages in this PDF; the built-in stdlib
> reader DOES find text on 1 of its 1 pages — re-run with
> `RVT_PDF_STDLIB_FORCE=1` to use it

(`tests/test_specsheet_backend_688.py`, skipped without the `[pdf]` extra —
which CI does not install. Re-run with `pip install -e ".[pdf]"`.)

### 2. Single-variable mutants for the two matrix rules

Each rule was removed on its own and the probe re-run, `__pycache__` cleared
between runs. Each mutant is caught by exactly its own case and by neither
the other's — the fixture draws `"62.0 in"` at **(300, 700)**:

| mutant | `TJ` shape | `cm` shape |
|---|---|---|
| *(none — baseline)* | (300.0, 700.0) | (300.0, 700.0) |
| `M = tm` (no CTM composition) | (300.0, 700.0) | **(0.0, 0.0)** |
| pen never advances | **(264.0, 700.0)** | (300.0, 700.0) |

The 36pt `TJ` error is exactly the un-advanced width of the preceding cell
(`"Height"`, 6 chars × 6pt), which is what makes it a diagnosis and not just
a red test.

### 3. Six defects found by re-reading the module after writing it

Written, then read back cold before the PR left draft. Each fix is pinned by
its own test and each was confirmed by a mutant that reverts exactly that fix
— caught by its own test and by no other, `__pycache__` cleared between runs:

| # | defect | what it actually did | mutant fails |
|---|---|---|---|
| A | `/Filter` read only as `/Name`, never as `[/Name]` | the array spelling looked **unfiltered**, so compressed bytes were returned as the content stream, no text parsed out of deflate data, and a readable sheet was reported as *"probably a scanned image"* | `test_the_array_spelling_of_filter_is_read`, `…_filter_CHAIN_is_refused_by_its_full_name` |
| B | stream extent from `find(b"endstream")` | a payload whose bytes spell `endstream` truncated the page silently | `test_payload_bytes_that_spell_endstream_do_not_truncate_the_stream` |
| B′ | object extent from the **first** `endobj` | same failure one level up; the fix takes the **last** one inside the next object's extent | same test |
| C | `/Encrypt` matched anywhere in the file | a document merely containing the word was refused as encrypted; the spec requires the dictionary to be **indirect**, so `/Encrypt N G R` keeps every real case | `test_the_word_encrypt_in_a_stream_does_not_refuse_the_file` |
| D | unit lookup without stripping a trailing period | `"62.0 in."` — how a large share of sheets abbreviate it — came back as *"states no length unit"* | `test_an_abbreviated_unit_is_still_a_unit` |
| E | a non-positive length was accepted | `"0 in"` / `"-4 in"` built a degenerate solid our own validator still calls VALID | `test_a_non_positive_length_is_refused_by_name` |

**A is the one that matters.** It is not a crash and not a wrong number — it
is a *wrong refusal*, which sends the user looking for OCR for a document
that was never scanned. Measured on the fixture before the fix: the
single-name lookup returned `None` (= no filter) on a stream that carried
FlateDecode. `/Filter [/FlateDecode]` is now a shape in both parametrised
suites, so both backends are held to it.

Fixing A changed the refusal text for the *supported* case too (the filter
names lost their leading `/`), and the two existing refusal tests caught that
on the first run. Worth recording: the tests that paid off here were the ones
pinning a message, not a value.

### 4. The instrument, and the instrument bug found while using it

`tests/fixtures_pdf.py` **writes** every PDF the tests read — no vendor
document is or may be committed (hard rules 3 and 6), and a writer is the
better instrument anyway: each fixture states the coordinate it drew at, so a
test asserts the reader recovered *that*, not "something plausible". Every
glyph is declared 600/1000 em, so the x of the n-th character is arithmetic.

The first version named the font `/Helvetica` while declaring non-Helvetica
widths. pdfminer substitutes its built-in AFM metrics for a base-14 name and
ignores the declared `/Widths`, so the two backends disagreed on the `TJ`
shape: `"62.0 in"` at **292.9** instead of 300 — which is 72 + the *true*
Helvetica width of `"Height"` (28.9pt) + the kern, to the decimal. That is a
self-contradictory document no producer would emit, i.e. an instrument bug,
so the readings taken with it were void: the fixture now uses a subset name
(`/AAAAAA+ProbeMono`) and everything was re-measured. The table in §1 is the
re-measurement.

### 5. Gates

- `tests/test_specsheet_pdftext_688.py` — **32 passed**
- `tests/test_specsheet_sheet_688.py` — **53 passed**
- `tests/test_specsheet_backend_688.py` — **14 passed** (with the `[pdf]`
  extra installed; skips without it)
- **the full merged CI shard** (`tools/dev/shard_list.py --print`, 158 files)
  on this branch — **3645 passed, 134 skipped, 4 xfailed** in 6:49, exit 0
- `tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py`
  — **31 passed** (the product still works from a bare unzip)
- `tests/test_pyproject_extras.py` — **8 passed** (the `pdf` extra joins
  `EXPECTED_EXTRAS`)
- `tests/test_plugin_sync.py`, `tests/test_conftest_scaffolding.py` — green
- `tools/sync_plugin.py` re-run, `--check` clean, deny-audit clean, identity
  scan == allowlist; `plugin/scripts/validate_plugin.py` 25/25;
  `tools/dev/check_portable_paths.py` ok (3225 paths)
- drop-in `tests/ci_shard.d/688-specsheet-reader.txt` (3 files)

Fresh-clone safe: no `samples/`, no network, no vendor file.

## Findings not fixed here

- **Base-14 fonts with no `/Widths` are estimated, and the error is real.**
  When a producer names `/Helvetica` and omits `/Widths` (common in simple
  documents), we fall back to 0.5 em and say so in the page note. Measured on
  the fixture sheet: the value column lands **5–20pt left** of where it was
  drawn, varying per row with the label's length. The column tolerance is
  0.8 em = 8pt, so a 20pt error *does* split one column into two. The note
  fires and the values still parsed on this sheet because the label/value gap
  is wide, but a tight sheet would break. Fix = ship the 14 standard AFM
  width tables. **Filed as #788.**
- **No OCR, ever, in this module.** An image-only sheet is reported. If that
  turns out to be common in the beta, it is a separate optional-extra
  decision, not something to slip into the stdlib reader.
- **The vocabulary is electrical-leaning.** It covers the fields #688's own
  example needs plus obvious mechanical/lighting ones. Growing it is a data
  edit by design, and a category that has no synonym set should eventually
  say so the way #601's standard-parameter tables do.
- **Spanning cells, multi-line cells and rotated text** are named in
  `layout`'s docstring as out of scope. A wrapped value is two rows and the
  reader above decides; nothing here joins them.
- `_colon_split` is the one layout inference in `sheet` rather than `layout`:
  it only fires on a single-cell row whose head already names a known field,
  so "Note: see page 4" stays unused. Pinned by test.

## BRANCH STATE

- Branch: `cam/688-specsheet-reader`, cut from `main` @ `50a89ef`.
- Files written: `src/rvt/specsheet/{__init__,pdftext,layout,vocab,sheet,_backend}.py`,
  `tests/fixtures_pdf.py`, `tests/test_specsheet_{pdftext,sheet,backend}_688.py`,
  `tests/ci_shard.d/688-specsheet-reader.txt`, `pyproject.toml` (the `pdf`
  extra + its doc block), `tests/test_pyproject_extras.py` (one line:
  `pdf` joins `EXPECTED_EXTRAS`), this record and its index, and the
  `plugin/lib/src/rvt/specsheet/**` mirror (generated by `sync_plugin.py`).
- Shipped: the reader, gated as above.
- Staged, not shipped: nothing.
- Not done: DONE 1 (`route run --pdf`, the `pdf` INPUT kind in `matrix.py`)
  and DONE 5 (identity parameters + the suppressed `manufacturer_claim`
  warning) — the follow-up PR on #688, which is why this one says `Refs`.
  No viewer or desktop round: nothing here writes a file, so hard rule 4 does
  not yet apply to it — it will to the family the follow-up builds.
