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

### 3. The bug the independent review found, and why my own tests could not

The #688 review returned `changes` on one finding that matters more than
everything else in this record, so it goes first:

> a numeric-only string inside a `TJ` array is silently read as a kerning
> number, so a value is dropped or, worse, a WRONG value is emitted with a
> `fact`-tier citation.

A `TJ` array interleaves strings and kerning numbers — `[(a) -120 (b)]` —
and both arrive from the tokenizer as `bytes`. The reader decided which was
which by trying `float()`. That works until a string *is* numeric, which on
a spec sheet is the normal case, because the values **are** numbers:

| drawn | read | effect |
|---|---|---|
| `[(62.0)] TJ` | taken as a kern | the value **vanishes** |
| `[(6) 0 (2.0 in)] TJ` | `6` taken as a kern | `height_in = 2.0 in`, **cited to the user's own document** |

The second is the failure this module's whole docstring says cannot happen.
The reviewer measured both against pdfminer on the same bytes: pdfminer
reads `Height 62.0 in`, we read nothing or `2.0 in`.

**Why the cross-backend table in §1 did not catch it.** Every value in the
fixture's `SHEET_ROWS` contains a space — `"62.0 in"`, `"400 A"`, `"145 lb"`
— so `float()` always failed and the ambiguous branch was never reached. The
instrument could not produce the shape that breaks the reader. Six PDF
shapes agreeing across two implementations, and none of them could see it.
The same hand wrote the writer and the reader, and this is exactly the blind
spot that creates: not a wrong assertion, an **absent** one.

Fixed by tagging string operands (`pdftext._Str`) so the question is never
asked. Now pinned at all three layers by seven tests: reverting the tag
fails 2 glyph-level, 2 pipeline-level and 2 cross-backend cases plus the
kern-split case — and leaves the `Tm` cases passing, since the bug is
`TJ`-specific and the parametrisation says so.

The fixture gained the shape it was missing: `NUMERIC_ROWS` /
`numeric_sheet_draws()` hoist the unit into the row label so every value run
is a bare number, and `kern_split` breaks a run mid-number with a zero kern
— what real producers emit constantly.

That change surfaced a second, smaller thing worth having: a row labelled
`Height (in)` with a bare `62.0` is **the row stating its own unit**, which
is a reading, not the column-header guess this module refuses. It is now
read, with `unit 'in' read from the row's own label` in the note so the
report never presents it as anything else. Only a *unit* is stripped from a
label — `Enclosure (Height)` still matches nothing, and `Width (W)` still
means width rather than watts.

### 3b. Five more from the same review

| finding | what it did | fix |
|---|---|---|
| `_media_box` raised `ValueError` on `[. . . .]` / `[- - - -]` | broke `read_sheet`'s documented "never raises for a bad document" — a page size we cannot read losing the whole page. The reviewer fuzzed 1200 random corruptions + 180 truncations and got **exactly two** escapes, both here | fall back to US Letter |
| `_backend` folded `FileNotFoundError` into `UnreadablePdf` | with the extra installed a typo'd path returned a `ParsedSheet`; without it the same call raised — **the one thing `_backend` claims cannot happen** | re-raise `OSError` before the blanket catch |
| the declared unit in `FIELDS` was never read | `"90 kg"` became `weight_lb = 90`: a fact about the document and a lie about the product, invisible to a consumer reading the key by name | `vocab.UNIT_SPELLINGS` + `unit_matches`; a positive mismatch is refused by name, a *bare* rating is still recorded with a note (a rating is not a length — the 25x mm/in ambiguity that justifies refusing a bare length does not exist here) |
| `test_pyproject_extras` guarded only `ifcopenshell` | nothing stopped `pdfplumber` being added to `test` later, and DONE 2's whole claim rests on that | parametrised over both backends |
| `max_pages=64` truncated silently | pages 65+ of a 100-page submittal lost with no note, so `questions()` asks about a field the document answers on page 80 | a page note naming the cap |

### 3c. Four nits from the re-review, two of which were wrong values

The re-review of the fixed head returned `nits`, having verified all eight
prior findings independently — 4254 fuzz cases across six producer shapes
(0 unhandled exceptions), a faithful revert of the `_Str` tagging (7 failures
across all three layers, `Tm` cases still green), and agreement with
`pdfminer.extract_text` on the bare-numeric and kern-split sheets. Two of its
four nits were wrong values rather than tidiness, so all four are fixed:

| nit | what it did | fix |
|---|---|---|
| a single-letter unit in a label | `Height (M)` read as **metres**: 96 became **2440.944882 in** end-to-end. On a drawing table `(M)` is a dimension callout far more often than a unit | a single character is read only on a **non-length** field whose declared unit it matches — see §3d, because the first version of this fix was a blanket refusal and was worse than the bug |
| an assumed unit was marked only in prose | a weight column headed "kg" with a bare `90` gives `weight_lb = 90` — wrong by **2.2×** — separated from a read value by a free-text `note` a consumer cannot check | `SheetValue.unit_source` is now `cell` / `label` / `declared`, with `unit_assumed` and both in the JSON. This is the flag DONE 5's identity lane must read |
| a unitless field adopted a label unit | `Phase (A) \| 3` recorded as `phases = 3.0 unit='a'` — a bogus unit on a count | only adopt where the field declares a unit |
| `_media_box` took `objs` and ignored them | an indirect `/MediaBox 5 0 R` — what a producer emits when pages share a box — fell through to Letter | resolved through the objects it was already given |

**One of those four tests was vacuous on its first writing, and the mutant
caught it rather than me.** `test_a_unitless_field_does_not_adopt_a_label_unit`
used the reviewer's own `Phase (A)` — but the single-letter rule now refuses
that label outright, so the row never reached the branch under test and the
test asserted over an empty list. Removing the guard entirely left it green.
Rewritten with a multi-character unit (`Phases (lbs)`) and an assertion that
the row was actually read, it fails as it should. Mutants on all four:
5 / 1 / 1 / 1 failures, each caught by its own test and no other.

### 3d. Round 3: my round-2 fix was worse than the bug it fixed

The third review returned `changes` on the very fix described above, and it
was right. Refusing **every** single-letter parenthetical lost 14 real label
forms that had worked one commit earlier:

`Rated Current (A)` · `Amperes (A)` · `Current Rating (A)` · `Ampacity (A)` ·
`Color Temperature (K)` · `CCT (K)` · `Correlated Color Temperature (K)` ·
`Input Power (W)` · `Wattage (W)` · `Power (W)` · `Watts (W)` ·
`Ambient Temperature (C)` · `Operating Temperature (C)` · `Weight (#)`

And losing them was not merely a missing value. Measured by the reviewer: a
sheet with the headline `Rated Current (A) | 400` near the top and an
accessory `Amps | 20` further down gives

```
amps = 20.0   raw '20'   duplicates() == []
```

— a **20× wrong** `fact`-tier value carrying a citation, with the ambiguity
not even surfaced, because the only row that still resolved was the wrong
one. I had introduced the shadowing failure while fixing a conversion
failure.

**The fix is to make the gate field-aware**, which is what the danger was
always confined to: a *length*'s units differ by 25×, so a coin flip there
is a 25× error; a `number` field's declared unit constrains the letter. The
label is now resolved to its key **first**, and a single character is
accepted only when the field is not a length *and* the character is an
accepted spelling of that field's own declared unit. `(A)` on `amps` is a
reading; `(A)` on `height_in` is a refusal. All 14 forms back, all 7 length
cases still refused, 0 mismatches across 23 probed labels.

**And the comment I wrote was the real defect.** It said *"Nothing is lost by
refusing: the row is listed as unused."* That was an assertion with no
measurement behind it, checked into the source, in the exact place a later
session would go looking before re-testing. The reviewer measured it and it
was false. The comment now carries the numbers instead.

Two more from the same round:

| finding | what it did | fix |
|---|---|---|
| the label-unit probe fired even when the **cell** stated a unit | `Height (mm) \| 62 kg` resolved silently in the label's favour: `height_in = 2.440945 in`. A label and a cell that plainly contradict each other are a thing to refuse and show, never to pick between | probe only when the cell stated nothing; a non-length unit in the cell is now a named refusal |
| `/MediaBox` inheritance | the docstring named the indirect-reference case, but a shared page size is normally stated **once on the `/Pages` node** and inherited. A parent carrying `[0 0 1224 792]` gave 612×792 | the parent chain is walked, depth-bounded so a self-referential file cannot hang it |

### 3e. Round 4: the round-3 fix reached the trigger, not the mechanism

Round 3 measured a shadowing failure — a headline row refused, a lower row
silently taken — through one particular refusal reason (a label the
single-letter gate rejected), and I fixed **that reason**. Round 4 measured
the same failure through a different door:

```
Rated Current (A) | 400 V      <- refused: V is not an amps spelling
Amps              | 20
  ->  amps = 20.0, cited, duplicates() == {}
```

An ordinary data-entry typo, the same 20×, the same invisibility. The cause
was never the label gate: `by_key()` and `duplicates()` walked **accepted**
rows only, so any refused row vanished into `unmapped` where nothing could
see it. Five different refusal reasons reach it (a wrong unit, a range, an
unparseable cell, a non-positive length, a missing unit).

Fixed at the mechanism. A row that **names a field we know** and is then
refused is recorded as a refused *claim* — a `SheetValue` with `value=None`
and its reason in `refused` — kept in `ParsedSheet.refused`, out of
`values` so nothing can build from it, and folded back in by `claims()`,
`duplicates()` and the new `shadowed()`. `shadowed()` is the dangerous
subset: keys where an **earlier** claim was refused and a **later** one was
taken, which is exactly "the value you have is not the one the sheet leads
with". `questions()` names the refused row and its reason.

The value is still delivered — hard rule 1 — but the caveat is
machine-readable rather than absent. A genuine second row (nothing refused)
is a `duplicate` and **not** `shadowed`, both directions pinned, because
conflating them would make `shadowed()` fire on every ordinary multi-row
sheet and stop being read.

Round 4's second finding closed a hole in the round-3 gate itself:
`unit_matches` treats an empty declared unit as "anything goes", so every
letter a–z was accepted on `phases` and on all nine `text` fields — 300
accept decisions the docstring's contract does not describe, since there is
no spelling of "no unit". Harmless today (no caller reads a label unit for
those fields), a hole all the same. The gate now enumerates to **15**
accepts across all 24 fields, each defensible:

| field | accepted single characters |
|---|---|
| `amps` | `a` |
| `cct_k` | `k` |
| `temperature_c` | `c` |
| `watts` | `w` |
| `weight_lb` | `#` |
| the five length fields | `'` `"` |

The inch and foot marks are read on a **length** field and, by the same
argument, nowhere else — they used to be accepted on every field and were
harmless only because a later check refused them.

### 4. Six defects found by re-reading the module after writing it

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

### 5. The instrument, and the instrument bug found while using it

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

### 6. Gates

Every number below re-measured **as a section**, not line by line, on the
head it describes.

That distinction is the third staleness finding and the one worth keeping.
Round 3 named two stale items; I fixed those two and left a third — the
`test_specsheet_sheet_688.py` count — wrong in the same document, in this
same list, under a commit whose title was *"the round-2 fix was worse than
the bug"*. It had been wrong since round 3's head, while round 3's own PR
comment carried the right figure. Fixing what a reviewer names is not the
same as re-verifying what they were looking at, and the difference is
exactly one number nobody re-ran.

- `tests/test_specsheet_pdftext_688.py` — **32 passed**
- `tests/test_specsheet_sheet_688.py` — **114 passed**
- `tests/test_specsheet_backend_688.py` — **18 passed** (with the `[pdf]`
  extra installed; skips without it)
- `tests/test_pyproject_extras.py` — **9 passed**
- `tests/test_bootstrap.py test_coldstart.py test_surface_perf.py` — **31
  passed**; `test_plugin_sync test_records_layout
  test_conftest_scaffolding` — **34 passed**;
  `plugin/scripts/validate_plugin.py` — **25 assertions**
- the full merged CI shard and `check_portable_paths` counts belong on the
  PR, against the SHA they were measured on, rather than here — copying a shard
  count into a record is how it goes stale, which happened twice: the first
  draft printed 32 / 53 / 14 (pasted from two different runs; the review
  measured 28 / 55 / 14), and the second still carried the parent commit's
  shard number and a `test_pyproject_extras` count that predated
  parametrising it.
- `tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py`
  — **31 passed** (the product still works from a bare unzip)
- `tests/test_plugin_sync.py`, `tests/test_conftest_scaffolding.py` — green
- `tools/sync_plugin.py` re-run, `--check` clean, deny-audit clean, identity
  scan == allowlist; `plugin/scripts/validate_plugin.py` 25/25;
  `tools/dev/check_portable_paths.py` ok
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
  extra + its doc block), `tests/test_pyproject_extras.py` (the packaging
  guard, parametrised over both optional backends — it started as a one-line
  `EXPECTED_EXTRAS` edit and grew when round 1 pointed out the guard
  enforced the zero-install promise for `ifcopenshell` alone), this record
  and its index, and the
  `plugin/lib/src/rvt/specsheet/**` mirror (generated by `sync_plugin.py`).
- Shipped: the reader, gated as above.
- Staged, not shipped: nothing.
- Not done: DONE 1 (`route run --pdf`, the `pdf` INPUT kind in `matrix.py`)
  and DONE 5 (identity parameters + the suppressed `manufacturer_claim`
  warning) — the follow-up PR on #688, which is why this one says `Refs`.
  No viewer or desktop round: nothing here writes a file, so hard rule 4 does
  not yet apply to it — it will to the family the follow-up builds.
