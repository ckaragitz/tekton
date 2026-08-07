# Manufacturer facts store — the DATA that drives family generation

Stream: `facts-store` (2026-08-03). Code: `src/rvt/famgen/catalog.py`.
Data: `src/rvt/famgen/facts/**` (+ `LICENSE_NOTES.md`). Tests:
`tests/test_famgen_catalog.py` (28 pass). Confidence tags: **[V]**
value read from a published document this session, **[H]** inferred /
summary-only / convention (flagged `assumed` in the data), **[D]** design
decision. Companions: `docs/product/content-strategy.md` (THE RULE:
generate-our-own families driven by FACTS — Pipeline 2), and
`docs/writer/family-authoring.md` / `src/rvt/genesis/*` (the field-by-field
"no cloned payload" discipline this store feeds).

## 0 · TL;DR

The user says *"build me an Eaton panel with X and Y and a room rated for
250 V"* and the platform must CREATE the Revit assets (families), not just
the project. The families are OURS — geometry and parameters authored field
by field — but they are dimensioned and rated by **published FACTS** about
real products. This store is where those facts live:

* one JSON record per product line, `facts/<vendor>/<line>.json`;
* every figure carries its **source** (URL, document, date accessed) and a
  per-field **provenance flag** — `fact` (read from a document this session)
  or `assumed` (inferred / derived / search-summary / not-yet-sourced);
* a null value means **NOT SOURCED** — the loader refuses to invent it;
* `catalog.py` is the loader / selector / validator the family generator
  calls (`get_variant(vendor, line, **selector)`).

Facts are not copyrightable (*Feist*); we store no manufacturer file, drawing
or prose, and reference photometry by URL only (`LICENSE_NOTES.md`, §5).

## 1 · What is in the store [V unless flagged]

| record | contents | primary basis |
|---|---|---|
| `eaton/pow-r-line-panelboards.json` | legacy 1a + Xpert 1X/2X/3X/3E/4X: box W/D (20.00 W × 5.75 D standard, 28 W option), box heights 36/42/48/60/72/90 with the **PRL1X circuits→height table** by mains (100/225/400/600 A), voltage classes 240 / 480Y-277 / 480 / 600 Vac, MLO / main-device amps, interrupting kA (fully & series rated), gutters, NEMA 1/2/3R/4/4X/12, surface/flush, PRL4X boxes (BX24/36/44 × 57/73.5/90, 11.31 D) | Eaton catalog **CA08100003E Vol 2 Tab 3, June 2020** + **RP01400001E Apr 2021** + Eaton Arabia 1a technical page |
| `square-d/nq-nf-iline-panelboards.json` | NQ (240 Vac/48 Vdc; mains 100/225/400/600 A; 18–84 pole spaces; 20 W × 5.75 D box, 8.75 D & 26 W & 14 W options; MHxx heights 26…86 with the MLO spaces→height rows), NF (600Y/347 max, 480Y/277; mains to 800 A; column-width 8.625/9.69 W × 5.625 D), I-Line (600 Vac / 250 Vdc) | Schneider **Digest 178 (0100CT1901) §9 Panelboards, 9/1/2023** |
| `eaton/dry-type-transformers.json` | DOE 2016 DT-3 480Δ→208Y/120 Al: kVA 15…500 → frame → weight (lb/kg) → catalog #; **frame dims** FR939…FR945 (H/W/D in & mm); NEMA 2 std / 3R w/ weathershield kits; 2 in side/rear clearance; 150/115/80 °C rise; NEMA ST-20 sound | Eaton **CA08100003E Vol 2 Tab 2, Aug 2017** |
| `hps/sentinel-g-transformers.json` | second vendor: 75 kVA point (H 36 / W 28.3 / D 27 in, DH3-N3R, 98.6 %) [V]; 30 kVA point + range statement [H, `assumed`] | distributor listing [V]; HPS site unread |
| `lithonia/blt-led-troffer.json` | 2BLT4: 47.75 L × 23.75 W × 2.375 H in, 38 W, ~4600 lm, 4000 K, CRI 82, 120–277 V, damp [V]; 2BLT2 [H]; **IES referenced by URL, never stored** | distributor listing [V]; Acuity pages **deliberately not fetched** |
| `lithonia/ldn6-led-downlight.json` | flagship archetype ("Chicago Plenum" CP option, 6 in, lumen packages 500…5000, MVOLT, non-IC) — **all `assumed`, housing dims null** | search summaries only (honesty demo) |
| `generic/devices-and-mounting.json` | ADA §308 reach envelope (15–48 in) [V], NEC 314.16 4 in sq × 1½ in = 21.0 in³ [V]; 5-15R/5-20R/switch/4-in box records — conventions `assumed` | ADA 2010 §308, NEC 314.16 (search-corroborated) |

Sourced vs. requested (the stream brief's checklist):

| requested | status |
|---|---|
| Eaton Pow-R-Line widths (typ. 20") | **[V]** 20.00 in standard, 28 in option |
| box heights by circuit count | **[V]** for 15/18/27/30/39/42 branch circuits per 20-in section (36–90 in). **The 54/66/84-space single boxes in the user's spec are NOT tabulated** — a section tops out at 42 branch circuits; larger counts are multi-section. NQ *does* tabulate 54/72/84-space single boxes (56/44/50/68-in). No dimension was invented. |
| depths (typ. 5.75") | **[V]** 5.75 in (146.1 mm) |
| mains 100/125/225/400/600 A | **[V]** 100/225/400/600 A families; 125 A appears in the NF/PRL3E ranges |
| voltage 240 / 480Y/277 / 600 V | **[V]** |
| MCB vs MLO, gutters, surface/flush | **[V]** (gutters 5.5 top-bottom / 4 side; PRL4X 10.63 / 5–8) |
| NEMA enclosure types | **[V]** 1, 2, 3R, 4, 4X, 12 (1a page) |
| weight where given | **NOT PUBLISHED** in the panelboard sections read → null, flagged, no weight parameter |
| transformer kVA 15…500, V classes, W/H/D by kVA, weights, clearances | **[V]** 15…300 with W/H/D + weights; **500 kVA reads "Contact Eaton"** → null; 2-in clearance [V] |
| troffer housing dims, aperture, plenum flag, W / lm / CCT, 120–277 V, driver, mounting, IES by URL | 2BLT4 dims/W/lm/CCT/V **[V]**; plenum & mounting [H]; LDN6 (the plenum-rated downlight) **all [H]**, dims null; IES = URL reference only |

## 2 · The schema [D]

One file per product line: `facts/<vendor>/<line>.json`.

```jsonc
{
  "schema_version": 1,
  "vendor": "eaton", "line": "dry-type-transformers",
  "product_line": "...", "category": "panelboard|transformer|luminaire|device",
  "revit_category": "OST_ElectricalEquipment",        // target Revit category
  "license_note": "...",
  "collection_posture": {"summary": "...", "primary_reachable": false, "method": "..."},
  "sources": { "S1": {"url": "...", "canonical_url": "...", "doc": "...",
                      "publisher": "...", "doc_date": "...", "accessed": "2026-08-03",
                      "verification": "VERIFIED|UNVERIFIED|SEARCH-SUMMARY", "note": "..."} },
  "line_facts": { "<field>": {"value": ..., "unit": "in",
                              "provenance": "fact|assumed", "source": "S1", "note": "..."} },
  "frames": { ... },                                    // optional shared tables
  "variants": [ {
      "model": "V48M28T7516", "aliases": [...], "role": "...",
      "ratings": { "kva": 75, "primary_v": "480 delta", ... },
      "dims_in": { "w": 30.50, "h": 43.00, "d": 24.00 },  // inches; null = NOT SOURCED,
                                                          // "VARIABLE" = chosen from h_options
      "options": { ... },
      "source":  { "url": "...", "doc": "...", "accessed": "2026-08-03" },
      "field_provenance": { "ratings.kva": "fact", "dims_in.w": "fact", ... },
      "notes": "..."
  } ]
}
```

Rules the validator enforces (`validate_line`): required top-level keys;
every source has `url`/`doc`/`accessed`/`verification` (verification in the
known set); every variant has `model`/`ratings`/`dims_in`/`source`/
`field_provenance`, `dims_in` has `w`/`h`/`d` keys, `source` has
`url`/`doc`/`accessed`, and **every tracked leaf field (top-level keys of
`ratings`, `dims_in`, `options`) has a `fact`/`assumed` flag** — no field
escapes a provenance decision. Tests additionally assert: null values are
never flagged `fact`; every manufacturer line rests on ≥1 `VERIFIED`
source; VERIFIED sources carry an accessed date; the store holds both flags
(it genuinely distinguishes verified from assumed); no `.ies` payload exists
anywhere in the store.

Provenance semantics [D]:

* `fact` — read **directly from a document this session** (manufacturer
  catalog / spec sheet, an authorized distributor's republication of it, or
  a code text corroborated by search) listed in `sources`.
* `assumed` — inferred (a width decoded from a catalog number), derived (an
  efficacy we computed), seen only in a search-engine summary, a design
  convention (typical mounting height), or a **null placeholder**.
* `null` value = **NOT SOURCED — never invent.** `"VARIABLE"` = a height
  legitimately chosen from `h_options` by circuit count (a fact, not a gap).

## 3 · The loader `rvt.famgen.catalog` [V]

```python
from rvt.famgen import catalog as cat
cat.list_lines()                                      # [(vendor, line), ...]
doc = cat.load_line("eaton", "pow-r-line-panelboards")
v = cat.get_variant("eaton", "pow-r-line-panelboards", model="Pow-R-Line Xpert 3X")  # alias ok
v = cat.get_variant("eaton", "dry-type-transformers", kva=75)          # by rating
cat.find_variants("square-d", "nq-nf-iline-panelboards", voltage_max_ac_v=600)  # NF + I-Line
cat.find_variants("eaton", "pow-r-line-panelboards", bus_current_range_a=225)  # range match
cat.dims_feet(v)                    # inches -> feet; None / "VARIABLE" preserved
cat.require(v, "dims_in.w")                    # value, or CatalogError if null
cat.require(v, "dims_in.w", fact_only=True)    # ...and reject 'assumed'
cat.assumed_fields(v); cat.unsourced_fields(v) # what to surface as unverified
cat.provenance_report(vendor, line)            # fact/assumed/null/source-level audit
cat.validate_line(doc); cat.validate_all()
```

`get_variant` returns **exactly one** match or raises listing candidates —
never a silent guess. Selectors: `model` (matches model or any alias,
case-insensitive), any `ratings`/`options`/`dims_in` key by bare name, or a
dotted path (`ratings.temp_rise_c=150`); a numeric selector matches inside
a two-number `[lo, hi]` range. `require(..., fact_only=True)` is the
mechanism that enforces the brief's rule *never invent a dimension without
flagging 'assumed'*: the generator asks the catalog to require the figure
and gets an exception, not a fabricated number.

CLI: `python -m rvt.famgen.catalog list | show <v> <l> | get <v> <l> k=v… |
validate` (validate prints per-line provenance audits; exits non-zero on any
problem).

## 4 · Provenance audit (2026-08-03, `catalog validate`)

| line | variants | fact | assumed | null | sources |
|---|---:|---:|---:|---:|---|
| eaton/pow-r-line-panelboards | 6 | 93 | 4 | 6 | 3 VERIFIED, 1 UNVERIFIED |
| square-d/nq-nf-iline-panelboards | 3 | 45 | 7 | 3 | 1 VERIFIED, 2 UNVERIFIED |
| eaton/dry-type-transformers | 9 | 145 | 6 | 7 | 1 VERIFIED |
| hps/sentinel-g-transformers | 2 | 11 | 11 | 1 | 1 VERIFIED, 1 UNVERIFIED, 1 SEARCH-SUMMARY |
| lithonia/blt-led-troffer | 2 | 11 | 9 | 2 | 1 VERIFIED, 1 UNVERIFIED |
| lithonia/ldn6-led-downlight | 1 | 0 | 11 | 3 | 1 UNVERIFIED, 2 SEARCH-SUMMARY |
| generic/devices-and-mounting | 4 | 4 | 30 | 0 | 2 SEARCH-SUMMARY, 1 UNVERIFIED |

(Counts are per-variant leaf fields; run `catalog validate` for live
numbers — they move as records are promoted from `assumed` to `fact`.)

## 5 · Collection posture — what was and was not done [V]

`docs/product/content-strategy.md` §5.2 governs: facts are free, the
*collection method* is a separate question, and several manufacturers ban
automated harvesting. What this stream did, per source:

* **One manual-equivalent read per document, transcribed by hand — no
  crawling, no scraping loop.** Nine documents/pages total across all
  vendors; no bulk enumeration of any portal.
* **eaton.com and se.com are unreadable by scripted clients** (timeouts /
  403). Eaton and Schneider figures were read from *their own catalogs*
  (CA08100003E; Digest 178) as republished by authorized electrical
  distributors; canonical vendor URLs kept alongside as `UNVERIFIED`.
* **Acuity (Lithonia) pages were deliberately not fetched** — its terms are
  among the corpus's most restrictive on non-personal / automated use
  (content-strategy row 10). Lighting facts came from an independent
  distributor listing plus search summaries; Acuity URLs are recorded for a
  human to read in their own browser. Fields resting only on summaries are
  `assumed`.
* **HPS terms were never reviewed** → treated restrictive-by-default; the
  record is deliberately thin and flagged.
* **Photometry: referenced, never redistributed.** No `.ies`/GLDF payload is
  stored (a test enforces this); luminaires carry the manufacturer download
  URL as a reference the customer follows under their own license.

**Not resolved by this stream (still NEEDS COUNSEL, content-strategy §5.2 /
§5.4 / §5.5):** the per-source collection legality; whether generated family /
type NAMES may carry manufacturer names or catalog numbers (this store uses
them only as data identifiers); design-patent / trade-dress screen on the
master families' shapes.

## 6 · How the generator uses it [D]

```
spec sentence  --> genesis / famgen constructor
                        |  get_variant("eaton", "pow-r-line-panelboards",
                        |              model="PRL2X")           # or by rating
                        |  require(v, "dims_in.w")  -> 20.00 in
                        |  in_to_ft(...)            -> feet (Revit internal)
                        |  assumed_fields(v)        -> surface as unverified params
                        v
             family document (rvt.famgen.skeleton): OUR geometry from
             these dimensions; ratings as parameters (BusRating, MainsRating,
             Voltage, NumberOfCircuits ... = the shared-parameters bridge in
             samples/design-ifc/panelboard-shared-parameters.txt)
```

Panelboard height: the family exposes `NumberOfCircuits`; the constructor
looks up `options.box_height_by_circuits` (Eaton) or
`options.mlo_box_height_single_phase_3wire` (NQ) for the box height and
`dims_in.w`/`d` for width/depth. Transformer: `dims_in` per kVA is complete
15…300 kVA; 500 kVA is null → constructor must be given the figure.
Luminaire: 2BLT4 dims are facts; the LDN6 (Chicago-plenum downlight)
housing is null → the flagship downlight keeps OUR OWN parametric housing
envelope until a spec sheet is read by a human. Every `assumed` figure
flows into the family as an editable parameter marked unverified in its
description.

## 7 · Confidence / unknowns

| claim | status |
|---|---|
| Eaton panelboard box family (20/28 W, 5.75 D, 36–90 H) and PRL1X sizing rows | **V** (CA08100003E June 2020, read) |
| legacy 1a/2a/3a/4B share the Xpert box widths | **V** (RP01400001E) |
| Schneider NQ/NF box family, MLO rows, kAIC summary | **V** (Digest 178 §9, 9/1/2023) |
| I-Line enclosure W/H | **H** (decoded from HC-series catalog numbers; the enclosure-dimension page not read) |
| Eaton transformer frames FR939–FR945, weights, catalog #s | **V** (CA08100003E Aug 2017) |
| Eaton 500 kVA dims / weights | **not published** ("Contact Eaton") — null |
| HPS 75 kVA point | **V** (distributor); 30 kVA + ranges **H** |
| 2BLT4 dims / W / lm / CCT / V | **V** (distributor listing) |
| LDN6 Chicago-plenum downlight (the flagship archetype) | **H throughout**, housing dims **not sourced** |
| ADA reach envelope, NEC 21.0 in³ | **V** (search-corroborated code figures) |
| panelboard / luminaire weights | **not published** in what was read |
| catalog editions match the *current* products (June 2020 / Aug 2017 / 2023 editions) | **H** — newer editions may revise figures; `doc_date` recorded per source |

Unknowns / next: read the Acuity spec sheets (BLT, LDN6-CP) by a human →
promote LDN6 to facts; read the HPS selection guide (S2, >10 MB) → real
second-vendor dims/weights; the I-Line enclosure dimension table; Eaton
1a-specific sizing (54/66/84-space multi-section rules) and panelboard
weights (a different catalog section); a receptacle/switch record read
verbatim from NEMA WD 6; and the counsel questions in §5.

## 8 · Reproduction

```
.venv/bin/python -m rvt.famgen.catalog list
.venv/bin/python -m rvt.famgen.catalog validate      # schema + provenance audit
.venv/bin/python -m rvt.famgen.catalog get eaton dry-type-transformers kva=112.5
.venv/bin/python -m rvt.famgen.catalog get eaton pow-r-line-panelboards model=PRL1X
.venv/bin/python -m pytest tests/test_famgen_catalog.py -q       # 28 passed
```
