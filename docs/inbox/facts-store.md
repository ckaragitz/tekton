# inbox — facts-store stream (manufacturer FACTS that drive family generation)

Date: 2026-08-03. Owner: facts-store workstream. Record for the
orchestrator; merge into KNOWLEDGE.md / TRACKER.md at will. Full spec:
`docs/writer/facts-store.md`. Data: `src/rvt/famgen/facts/**`. Code:
`src/rvt/famgen/catalog.py`. Tests: `tests/test_famgen_catalog.py`.

## What was done

Built the **catalog-facts store** (content-strategy Pipeline 2): the lawful
DATA layer that dimensions and rates the families `rvt.famgen` generates.
Facts are not copyrightable (*Feist*); every figure is a fact read from a
published document, tagged with its source (URL / doc / date accessed) and a
per-field `fact` / `assumed` provenance flag. No manufacturer .rfa / CAD /
drawing / prose / photometric file is stored — photometry is referenced by
manufacturer URL only. `LICENSE_NOTES.md` states the basis.

Deliverables (all in territory):

* `src/rvt/famgen/facts/LICENSE_NOTES.md` — facts-not-expression basis, the
  no-manufacturer-files rule, the provenance-flag semantics, collection
  posture, trademark caveat.
* `facts/eaton/pow-r-line-panelboards.json` — legacy 1a + Xpert
  1X/2X/3X/3E/4X: 20.00 W (28 opt) × 5.75 D boxes, heights 36…90 with the
  PRL1X circuits→height table by mains 100/225/400/600 A, voltages
  240/480Y-277/480/600, MLO / main-device amps, kAIC (fully + series),
  gutters, NEMA 1/2/3R/4/4X/12, surface/flush, PRL4X box catalog.
* `facts/square-d/nq-nf-iline-panelboards.json` — NQ / NF / I-Line, from
  Schneider Digest 178 §9 (2023): NQ 20 W × 5.75 D (8.75 D, 26 W, 14 W
  options), MHxx heights 26…86 with MLO spaces→height rows, NF 600Y/347
  max + column-width dims, I-Line 600 Vac/250 Vdc (enclosure dims flagged
  `assumed`).
* `facts/eaton/dry-type-transformers.json` — DOE 2016 DT-3 480Δ→208Y/120
  Al: kVA 15…300 → frame → W/H/D (FR939…FR945 table, in + mm) → weight
  (lb/kg) → catalog #; NEMA 2 std / 3R w/ weathershield; 2-in side/rear
  clearance; 500 kVA reads "Contact Eaton" → null (never invented).
* `facts/hps/sentinel-g-transformers.json` — second vendor proving
  generalisation: 75 kVA point verified (36 H / 28.3 W / 27 D in, DH3-N3R);
  30 kVA + range statement `assumed`.
* `facts/lithonia/blt-led-troffer.json` — 2BLT4 troffer: 47.75 × 23.75 ×
  2.375 in, 38 W, ~4600 lm, 4000 K, CRI 82, 120–277 V, damp (verified via
  distributor); IES referenced by URL, never stored.
* `facts/lithonia/ldn6-led-downlight.json` — the flagship "Chicago plenum
  recessed light" archetype (LDN6 with CP option): **entirely `assumed`,
  housing dims null** — the honesty demonstration; the generator keeps OUR
  parametric housing until a human reads the spec sheet.
* `facts/generic/devices-and-mounting.json` — ADA §308 reach envelope
  (15–48 in) and NEC 314.16 4-in-square = 21.0 in³ (facts); 5-15R / 5-20R
  / switch / box records as `assumed` conventions.
* `src/rvt/famgen/catalog.py` — loader/selector/validator:
  `list_lines`, `load_line`, `get_variant(vendor, line, **selector)`
  (model/alias/rating/dotted-path/range selectors, exactly-one or raise),
  `find_variants`, `require(..., fact_only=)` (the never-fabricate guard),
  `assumed_fields`, `unsourced_fields`, `dims_feet`, `provenance_report`,
  `validate_line/validate_all`, CLI.
* `tests/test_famgen_catalog.py` — 28 tests: presence, license notes,
  schema validity, source citations, provenance flag on EVERY field, nulls
  never `fact`, selectors, `require` guards, unit conversion, provenance
  audit, no-`.ies`-payload, data-drift sentinels.

## Test count

`.venv/bin/python -m pytest tests/test_famgen_catalog.py -q` → **28 passed**.
Full suite: see the report at the end of this file (run at close).

## Findings for the orchestrator

1. **eaton.com and se.com are unreadable by automated fetch** (timeout /
   403). Their own catalogs (Eaton CA08100003E; Schneider Digest 178) are
   readable as PDFs republished by authorized electrical distributors — the
   facts are the manufacturer's; the canonical vendor URL is kept as
   `UNVERIFIED`. Any future "read the vendor page" task must plan for a
   human browser read, not a fetch.
2. **The user's 54/66/84-space single-box Eaton heights do not exist in the
   catalog read** — a Pow-R-Line 20-in section tops out at 42 branch
   circuits (larger = multi-section). Square D NQ *does* tabulate 54/72/84
   single boxes. The panel constructor must model >42-circuit Eaton panels
   as multi-section (or ask), never invent a taller single box.
3. **Panelboard and luminaire weights are not published in the sections read**;
   only transformer weights are (Eaton, 15…300 kVA). Do not emit a Weight
   parameter for panels/troffers.
4. **Acuity (Lithonia) primaries were deliberately not fetched** (restrictive
   ToU, content-strategy §5.2 / row 10). The flagship LDN6-CP downlight is
   therefore all-`assumed` with null housing dims. Highest-leverage human
   action: a designer opens the LDN6-CP + 2BLT spec sheets in a browser and
   the record is promoted to facts (five minutes' work).
5. **Collection legality per source is still a counsel item** — this stream
   kept the surface to nine manual-equivalent reads with a recorded posture
   each; it does not answer §5.2, it minimises it.
6. **Family/type NAMING with manufacturer names or catalog numbers is
   unsettled** (content-strategy §5.4) — the store uses them only as data
   identifiers; the generator should default to names WITHOUT catalog
   numbers (mfr/model as parameter *values*) until counsel rules.

## Proposed follow-ups (for TRACKER)

* Wire `catalog.get_variant`/`require` into the `famgen` constructors
  (panelboard, transformer, troffer) so `assumed` fields surface as
  unverified family parameters and nulls raise instead of zero-filling.
* Human read: Acuity BLT + LDN6-CP spec sheets → promote lithonia records.
* Read the HPS selection guide (S2, >10 MB — needs a manual download) →
  real second-vendor W/H/D + weights.
* Read the Eaton panelboard weight table + 1a multi-section rules; the
  I-Line enclosure-dimension page; NEMA WD 6 verbatim for the device
  records.
* Add a CI gate: `python -m rvt.famgen.catalog validate` (schema +
  provenance) alongside the family provenance ledger.
* Extend to the strategy's next equipment classes (switchboard, disconnect,
  ATS, cable tray / strut) with the same discipline.

## Verification pass — 2026-08-03 (second session, this stream)

A follow-up session re-audited the store rather than re-collecting it:

* `pytest tests/test_famgen_catalog.py -q` → **28 passed**.
* `python -m rvt.famgen.catalog validate` → **all 7 records OK**, exit 0;
  provenance audit: 0 fields missing a flag anywhere; nulls remain nulls
  (Eaton 500 kVA "Contact Eaton", LDN6 housing dims, HPS one point) —
  nothing zero-filled or invented.
* Brief-specific facts confirmed present: Eaton PRL1X circuits→box-height
  table (18/30/42 spaces per 20-in section, heights 36…90 in by mains
  100/225/400/600 and MLO/MCB config — the >42-circuit = multi-section
  finding stands, no invented tall single box); transformer kVA 15…300 with
  500 = null; IES photometry referenced by URL only — grep confirms **no
  `.ies` payload anywhere in the repo**; `LICENSE_NOTES.md` states the
  *Feist* facts-not-expression basis.
* The flagship LDN6-CP downlight was **deliberately left all-`assumed`**:
  re-read of `docs/product/content-strategy.md` (row 10 Acuity, row 11
  Cooper, §5.2) confirms automated fetch of acuitybrands.com /
  cooperlighting.com is barred, so promotion to `fact` remains a **human
  browser read** (finding 4 above), not something this stream may automate.
* **Full suite** (`pytest -q -x`): **473 passed, then 1 FAILED and the run
  stopped** — the failure is `tests/test_plugin_sync.py::
  test_plugin_is_in_sync_with_source`, a **cross-stream drift, not this
  stream's**: the family-geometry stream fixed the ISIZE-counter defect in
  `src/rvt/famgen/geometry.py` (18:06) after `plugin/lib/...` was last
  synced (16:12) and did not re-run the sync. `geometry.py` and `plugin/`
  are both outside facts-store territory, so it is NOT fixed here.
  **Remedy for the orchestrator: run `python tools/sync_plugin.py`** (a
  mechanical resync; `--check` shows exactly 1 drifted file, a 17-line
  diff = the ISIZE fix). A full non-`-x` count is pending that resync; the
  facts-store deliverables themselves are all green.

BRANCH STATE: facts-store COMPLETE — 7 facts records (Eaton panelboards + transformers, Square D panelboards, HPS transformers, Lithonia troffer + LDN6 downlight, generic devices) + LICENSE_NOTES.md + rvt.famgen.catalog loader/validator + 28 passing tests + docs/writer/facts-store.md; all writes confined to src/rvt/famgen/facts/**, src/rvt/famgen/catalog.py, tests/test_famgen_catalog.py, docs/writer/facts-store.md, docs/inbox/facts-store.md; no existing rvt module or test touched; suite status: catalog tests 28/28 green, validator 7/7 records OK, full suite 473 passed + 1 cross-stream failure (plugin/geometry.py sync drift owned by family-geometry — fix = `python tools/sync_plugin.py`), see verification pass above.
