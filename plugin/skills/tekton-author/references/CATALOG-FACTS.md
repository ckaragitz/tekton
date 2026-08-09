# CATALOG-FACTS — the manufacturer facts store that drives family generation

tekton generates real, parametric Revit families from **published product
FACTS** (dimensions, ratings, options), not from third-party geometry and
not from guesses. The facts live in the engine at
`lib/src/rvt/famgen/facts/<vendor>/<line>.json` and are queried through
`rvt.famgen.catalog`. Read this before promising a family for any product.

## 1. The rules (why the store is conservative)

- **A fact is a figure read from a cited document.** Every leaf value in
  `ratings` / `dims_in` / `options` carries a `field_provenance` flag:
  `'fact'` (read from the source, with URL / document / date accessed) or
  `'assumed'` (inferred, derived, summary-only, or not yet sourced).
- **Never fabricated.** A `null` fact stays `None`;
  `catalog.require(...)` RAISES rather than guessing. A generator that hits a
  gap surfaces the `assumed` figure as an *editable, unverified parameter*
  in the delivery report — the licensed engineer confirms it.
- **Selection is explicit, never fuzzy**: by model / alias / rating value
  (`kva=150`, `voltage_max_ac_v=240`), including range membership. An
  ambiguous or absent match is a `CatalogError`, which tekton reports
  verbatim (e.g. the 2500 A switchboard refusal below).
- **Legal basis** (`lib/src/rvt/famgen/facts/LICENSE_NOTES.md`): facts are
  not copyrightable; the store holds no manufacturer files, drawings or
  copied text — only figures with citations. Geometry is authored by OUR
  constructors from those figures (`references/GENESIS-BASE.md` explains
  the same posture for the project base).

## 2. What is in the store today

`python -m rvt.famgen.catalog list` (needs the engine importable — see
the skill's Setup):

| vendor / line | variants | category | what it is |
|---|---|---|---|
| `eaton/pow-r-line-panelboards` | 6 (PRL1a, PRL1X, PRL2X, PRL3X, PRL3E, PRL4X) | panelboard | Pow-R-Line legacy + Xpert panelboards: box W 20 in, D 5.75 in, height by pole spaces (36/48/60/72/90 in); PRL4X is the 36 in-wide power panelboard |
| `eaton/dry-type-transformers` | 9 (V48M28T1516 … T5516) | transformer | 600 V class DOE 2016 ventilated dry-type, aluminum, 480 delta → 208Y/120; 15 … 500 kVA with W/H/D, weight, frame (one 500 kVA row still unsourced) |
| `hps/sentinel-g-transformers` | 2 | transformer | Hammond Sentinel G low-voltage distribution transformers |
| `square-d/nq-nf-iline-panelboards` | 3 (NQ, NF, I-Line) | panelboard | NQ (240 Vac), NF (600Y/347), I-Line (600 V) — heights by branch spaces |
| `lithonia/blt-led-troffer` | 2 (2BLT4-38W, 2BLT2) | luminaire | BLT recessed LED troffer (2×4, 2×2) |
| `lithonia/ldn6-led-downlight` | 1 (LDN6-35/15-CP) | luminaire | 6 in LED downlight with the Chicago-plenum option (dims unsourced → `assumed`) |
| `generic/devices-and-mounting` | 4 | device (Electrical Fixtures) | NEMA 5-15R / 5-20R duplex receptacles, single-pole toggle switch, 4 in square box: device-box + faceplate modelling envelopes (`assumed`), the 180 VA NEC 220.14(I) receptacle unit load, typical mounting heights (18 in receptacle / 48 in switch, `assumed` conventions) inside the ADA 308.2.1 reach envelope 15..48 in (`fact`) |

Query one member (the CLI is the fastest way to see the exact facts a
family will be built from):

```bash
python -m rvt.famgen.catalog show eaton pow-r-line-panelboards
python -m rvt.famgen.catalog get  eaton dry-type-transformers kva=150     # -> V48M28T4916, W 34.5 H 51 D 31.5 in, 1239 lb
python -m rvt.famgen.catalog get  eaton pow-r-line-panelboards model=PRL2X
python -m rvt.famgen.catalog validate                                       # every line's provenance completeness
```

## 3. How a fact becomes a family (the resolver's job)

`rvt.ifc.intent.plan_families()` (and the front door's build step) maps
an equipment item's tagging contract (`references/TAGGING-CONTRACT.md`)
onto ONE constructor and runs the facts resolver:

| kind | constructor | catalog selection |
|---|---|---|
| distribution / lighting / receptacle panelboard | `rvt.famgen.factory.make_panelboard(vendor, line, amps, spaces, mcb=…, mounting=…)` | the Pow-R-Line member whose ampacity + space rows cover `BusRating` / `NumberOfCircuits`, voltage class by `Voltage` |
| dry-type transformer | `rvt.famgen.factory.make_transformer(kva, vendor, primary, secondary)` | the DOE 2016 row for that kVA (dims + weight facts) |
| 2500 A switchboard | `rvt.ifc.intent.make_house_switchboard(...)` | NO catalog member (panelboards tabulate 100/225/400/600 A mains): the factory REFUSES with `FactoryError`, and the house switchboard is composed from OUR OWN IFC-modeled lineup extents with the pset ratings as parameter VALUES; the manufacturer / model strings ride as *ifc-declared identity*, not as catalog facts |
| downlight / troffer | `rvt.famgen.factory.make_luminaire(...)` / `rvt.ifc.famfrom_ifc.make_downlight` (via the IFC-family path) | the Lithonia member |
| duplex receptacle / switch / junction box (`receptacle_device`, prompt: “N duplex receptacles”, IFC: `IfcOutlet`) | `rvt.famgen.factory.make_device(kind, mounting_height_in=None, voltage=120, va=180)` — repo CLI `tools/make_family.py device --kind duplex-receptacle|switch|junction-box`; from this plugin call the constructor through the engine (`F.make_device('duplex-receptacle').write('out/duplex.rfa')`) until the famspec kind `device` lands (issue #361) | the `generic/devices-and-mounting` member: faceplate `plate` + device `box` at the record’s envelopes, ONE 1-pole 120 V primary connector (180 VA booked, bound to `Voltage` / `Load`), `MountingHeight` from the facts. **Honest status:** family-mode VALID + provenance clean and it LOADS unplaced (`make_family.py load-device`, four-registry, category Electrical Fixtures, project validator 0 errors); the room build PLANS + lays the devices out at the ADA/NEC height but does not load/place them yet (issue #359) — the manifest says so per device |

The delivery report must repeat, per generated family, which figures are
`fact` (cited) and which are `assumed` (to be confirmed), plus every
`CatalogError` refusal verbatim. That table IS the honesty guarantee.

## 4. Adding a product (extending the store)

1. Author `<vendor>/<line>.json` under the facts directory following an
   existing line as the template (`schema_version`, `sources` with URL /
   document / accessed date / `verification`, `variants[]` each with
   `ratings`, `dims_in`, `options`, `field_provenance` per leaf).
2. Every leaf you fill must have a `field_provenance` entry (`fact` needs
   a source citation; use `assumed` and say why in `notes` otherwise).
3. `python -m rvt.famgen.catalog validate` must report zero problems for
   the new line, then extend the constructor's selector table if the
   product is a new kind.
4. In this plugin build the facts directory is `lib/src/rvt/famgen/facts/`
   inside the bundled engine source (see the Setup note in `SKILL.md`: use
   the editable install / `PYTHONPATH` route so the JSON store is found —
   a plain non-editable `pip install ./lib` currently omits the data files).
