# Coverage harness — battle-hardening as a measured number

`tools/coverage.py` measures how much of the CRUD x category surface the
writer has actually PROVEN, cell by cell.  Nothing here is a claim: every
proven cell is backed by a proof `.rvt` that the Autodesk-free validator
(`rvt.validate`, all three layers) re-checks on every run, and a cell only
reaches CERTIFIED when the orchestrator's ledger says Autodesk's own reader
accepted that exact file.

## Files

| file | role | who edits |
|---|---|---|
| `matrix.json` | the DEFINITION (categories x verbs, each cell's implementing function, proof generator, proof file(s), read probe) **and** the last run's per-cell `result` + `summary` | definition: humans; `result`/`summary`: the runner |
| `matrix.md` | the rendered report — headline percentage, the glyph table, per-cell evidence, generator run log | the runner |
| `viewer-certified.json` | ledger of files Autodesk's viewer accepted | the orchestrator only |
| `README.md` | this file | humans |

## Running

```
.venv/bin/python tools/coverage.py run                 # regenerate + validate + report (~40 min)
.venv/bin/python tools/coverage.py run --validate-only # validate what is on disk (~6 min)
.venv/bin/python tools/coverage.py run --cells conduit:create wires:delete
.venv/bin/python tools/coverage.py report              # re-render matrix.md, no work
.venv/bin/python tools/coverage.py list                # cell inventory
```

Test: `.venv/bin/python -m pytest tests/test_coverage.py -q` (matrix
well-formedness + the runner on a 2-cell subset, ~7 s).

## What a run does

1. **Regenerate.** Every cell names a *generator* — a `make_*.py` driver
   that deterministically rebuilds its proof file(s).  The runner runs each
   distinct generator once as a subprocess (`PYTHONPATH=src`), after backing
   up its declared outputs; if the driver exits non-zero or an output is
   missing the backups are RESTORED, so a broken regenerator can never
   destroy a good proof (the failure is recorded, and the run exits 1).
   Generators that co-produce a **ledger-certified** file are **frozen** by
   default — certification applies to specific bytes, so the runner never
   overwrites them (`--force-regen` overrides for a deliberate rebuild).
2. **Validate.** Every referenced proof file goes through
   `rvt.validate.validate_file` (structure + consistency + semantic);
   `.rfa` proofs use `rvt.families.verify_rfa` (the project validator does
   not apply to families).  ZERO errors = pass.
3. **Probe (READ cells).** A read cell carries a probe against a real
   corpus file: `class_decode` (enumerate a class and decode N records),
   `category_decode` (count elements by BuiltInCategory) or `callable`
   (`pkg.mod:func(doc)` / `doc:method`).  A passing probe is a measured
   read, not an assertion.
4. **Resolve + report.** Statuses, row/overall percentages, `matrix.json`
   results and `matrix.md`.

## Statuses

| status | meaning |
|---|---|
| CERTIFIED | proof validates with 0 errors **and** the ledger records Autodesk-viewer acceptance |
| VALIDATES | proof validates with 0 errors; viewer certification pending |
| REGRESSED | a ledger-certified path whose current bytes now FAIL validation (alarm) |
| FAILS | proof file exists but the validator reports errors |
| UNPROVEN | an implementing function exists but no (passing) proof file |
| MISSING | no implementing function |
| BLOCKED | declared blocked by its stream (see the cell note) |
| NA | verb does not apply to the category — excluded from every percentage |

Headline = proven cells (CERTIFIED + VALIDATES) / applicable cells (all
non-NA).  Also reported: certified %, and regenerability (share of proven
cells with a registered regenerator — the static one-shot proofs
V22/V23-V31 are certified but have no checked-in driver).

## Adding a capability

Land the module + a proof driver, then add/edit the cell in `matrix.json`
(register a `generators` entry pointing at the driver and its outputs), and
rerun.  A cell with a function but no proof is UNPROVEN by design; the
number only moves when a proof file passes the validator.
