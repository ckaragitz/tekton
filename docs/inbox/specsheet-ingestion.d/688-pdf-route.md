# 688-pdf-route — the `pdf` INPUT, and the identity lane

PR fragment for **#688 DONE 1 and DONE 5** (+ **#797**, folded in as that
issue asked). The reader landed in #789; this is the route that uses it.

## What was built

**`pdf` is a real INPUT kind**, not a cell bolted onto an existing one:
`matrix.INPUT_KINDS` gains it, all three single-input cells are enumerated
(`pdf → rfa` works, `pdf → rvt` and `pdf → ifc` missing with a reason and a
`closest` that itself works), and `pdf + prompt → rfa` is the one
combination. `tools/route.py` gains `--pdf`, and `router._r_pdf_to_rfa` is
the handler.

**The lane, in order.** Read the sheet → write the parse *before* trusting it
(`sheet.json`, `sheet-table.txt`, `sheet-plan.json`) → map it to a
`generic_model` famspec → build through the same `_famspec_rfa` block every
other family uses → if the sheet could not size a body, fall through to the
archetype lane so something is still delivered.

**What the prompt may do, and may not.** Beside a `--pdf` the prompt supplies
the words for the archetype fallback and nothing else. It does not override a
dimension the sheet states — a sheet-read number is the fact this lane exists
to deliver, and a typed number quietly winning would end up wearing a
citation to the user's own document. Pinned by
`test_a_prompt_beside_the_pdf_NEVER_overrides_a_stated_dimension`.

**`manufacturer_claim` suppression (DONE 5) is structural, not a flag.** A
sheet that sized the body is built by `make_generic_model` carrying the
sheet's own identity, and that path never consults the archetype resolver at
all. Where the sheet could *not* size a body and the archetype stands in, the
claim warning fires as usual — because there it is true: the named product is
not what was built.

## The bug this stream had to fix to meet DONE 5

`make_generic_model` accepted `identity`, `text_params` and `numeric_params`
in its signature, documented them, and — **on the single-prism path** — wrote
none of them. Only `_make_generic_multipart` (the `parts=` path) consumed
them. A spec sheet reaches the single-prism path by construction (height +
width + depth from a table is one prism), so DONE 5's identity had nothing to
land on.

Measured before the fix, on `make_generic_model(identity={'Manufacturer':
'Probeworks', 'Model': 'PW-400'}, text_params={'Voltage': '480Y/277 V'},
numeric_params={'Amps': 400.0})`:

```
parameters: ['Depth', 'Finish', 'Height', 'Material', 'Weight', 'Width']
```

and after:

```
parameters: ['Amps', 'Depth', 'Enclosure Rating', 'Finish', 'Height',
             'Material', 'SCCR', 'Voltage', 'Weight', 'Width']
row: Manufacturer='Probeworks Industries', Model='PW-400-42', Voltage='480Y/277 V',
     Amps=400.0, SCCR=65.0, Weight=65.77089365
```

The fix is two shared helpers (`_author_caller_params`, `_caller_param_row`)
extracted from the multi-part path *verbatim* and called from both, so the
two paths cannot drift again. The multi-part path's behaviour is byte-for-byte
unchanged — `test_ifc_assembly.py` is the control and stayed green.

**Weight is the one reading that does not go through `numeric_params`.** The
#601 standards table already authors `Weight` as a `mass` on this category,
and authoring a second parameter of that name would win the race and demote a
mass to a bare number. So `weight_lb` routes through `standard_values`, whose
contract is internal units, with the factory's own exact `pounds()` (the
pound's definition, `KG_PER_LB = 0.45359237`) doing the conversion: 145 lb →
65.77089365 kg on the type row. That is the only unit conversion this lane
performs, and it is named rather than implied — every other reading is stored
as the sheet stated it, because these are the document's numbers and a silent
conversion would put a different number behind its citation.

## Evidence

End to end, on a fixture sheet written by `tests/fixtures_pdf.py` (no vendor
PDF may be committed — hard rules 3 and 6):

```
probeworks-pw400.pdf  ->  PW-400-42-NEMA1.rfa
  validate     family-mode VALID, 0 errors
  provenance   ok=True, identity_is_ours=True
  dimensions   height_in 62.0 / width_in 20.5 / depth_in 5.75
               all provenance=fact, source='spec sheet: probeworks-pw400.pdf'
  citations    height_ft <- p1 r3 'Height' = '62.0 in'  (and 8 more)
  parameters   Amps, Enclosure Rating, SCCR, Voltage + the category standards
  identity     Model=PW-400-42-NEMA1 on the type row
  determinism  two runs, byte-identical
```

With a real vendor name in the identity block (`Eaton Corporation`) the
provenance scan stays clean and `identity_is_ours` stays true: the maker
rides as a parameter *value* (content-strategy 5.4), never as our author
string.

**The tests are mutation-checked, not just green.** Three mutants were run
against `tests/test_specsheet_route_688.py`:

| mutant | dies in |
|---|---|
| `dim_provenance = "fact"` → `"given"` | 2 tests (the fact-tier assertion and the prompt-override one) |
| single-prism path drops `_caller_param_row` again | 2 tests (identity on the type row, and the values) |

The second mutant is why one test was rewritten mid-stream: its first form
asserted only that the captions existed, and a family that *authored* the
parameters and wrote none of their values walked straight through it. A blank
`Voltage` is not the sheet's voltage; it is a parameter that lost its reading.

## #797, folded in as that issue asked

`vocab._known_unit` normalises with `.strip().lower().rstrip(".")` and none
of the three steps was exercised by any of the 176 tests #789 shipped —
verified by mutating each one out and watching all three modules stay green.
Now:

| step deleted | tests that fail |
|---|---|
| `.rstrip(".")` | exactly the 4 new `Height (in.)` / `Amperes (A.)` / `Weight (lbs.)` cases |
| `.strip()` | exactly the 2 new `Height ( in )` cases |
| `.lower()` | **none, and that is reported rather than papered over** |

`.lower()` is an equivalent mutant through the public API: its one caller
receives a string `_norm` has already lowercased, and on the single-character
path the comparison goes through `unit_matches`, which lowercases again. The
test named for it asserts the *reason* — that the public entry point
lowercases — so if that ever stops being true, it fails and the mutant
becomes testable. Same verdict #797 itself reached about case-sensitising
`unit_matches`.

## Open questions

- **The archetype fallback picks its words from the file stem** when there is
  no `--prompt` and the sheet is unreadable. `scan.pdf` names no product, so
  the route ends honestly — but a sheet named `eaton-prl1a-panelboard.pdf`
  would route on its filename, which is a weaker signal than a prompt. Worth
  deciding whether a filename should be allowed to choose an archetype at
  all, or only ever narrow one the user named.
- **No desktop verdict.** A sheet-built `.rfa` is validator-gated and
  PROOF-ONLY like every other family we generate (hard rule 4). #687's
  "functional" bar — constraints, visibility, tags — is untouched by this PR.
- **Nine of the sheet's readings are used; two rows are not.** The fixture's
  banner lines ("PROBEWORKS INDUSTRIES", "Specifications") name no field, and
  are reported as unused rather than dropped. On real sheets that list will
  be much longer, and it is the first place to look for vocabulary gaps.

## BRANCH STATE

Branch `cam/688-pdf-route`, `Refs #688`, `Closes #797`.

Files written:

- `src/rvt/frontdoor/router.py` — `_r_pdf_to_rfa`, `_side_file`, `pdf` in
  `_norm_inputs`, the route-table entry
- `src/rvt/frontdoor/matrix.py` — `pdf` in `INPUT_KINDS`, the `pdf->sheet`
  and `sheet->famspec` stages, four cells, three shared caveats
- `src/rvt/famgen/factory.py` — `_author_caller_params` /
  `_caller_param_row` shared by both generic-model paths (the DONE 5 bug fix)
- `src/rvt/specsheet/famspec_from_sheet.py` — `_STANDARD_VALUES`,
  `_to_internal`, `standard_values` in the plan and its JSON
- `tools/route.py` — `--pdf`
- `tests/test_specsheet_route_688.py` (new), `tests/test_specsheet_sheet_688.py`
  (#797's probes), `tests/test_router.py` (the pinned kinds tuple),
  `tests/ci_shard.d/688-pdf-route.txt`
- `docs/product/PERMUTATION-MATRIX.md` — the four new rows and the census

Gates: recorded on the PR's CI comment, pinned to the head SHA — counts in a
record go stale inside the commit that writes them.

Staged, not shipped: nothing. Everything here is on the default path.
