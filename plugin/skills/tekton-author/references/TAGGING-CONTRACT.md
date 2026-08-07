# TAGGING-CONTRACT — the Pset join key between an IFC and OUR content

Every panelboard / switchboard / transformer that tekton generates is
matched to one of OUR family constructors by **the property names on its
IFC property set** — not by the geometry, not by the object name. Those
property names are the *tagging contract*: the join key that
`rvt.ifc.intent.normalize_contract()` reads and `plan_families()` acts on.
Get the names right at authoring time and the mapping is automatic; get
them wrong and the item degrades to "unmapped" with a stated reason.

The contract is the same one the `tekton-ifc` skill installs into a
Claude Design model (`skills/tekton-ifc/references/tagging-contract.md`
documents the *authoring* side: how `userData.ifc.psets` becomes an
`IfcPropertySet`). This file documents the *consuming* side: what tekton
reads back out and what each key drives.

## 1. The contract keys (join key)

`rvt.ifc.intent.CONTRACT_KEYS` — read from ANY pset the product carries
(`PanelSchedule`, `SwitchboardSchedule`, `TransformerSchedule`,
`Pset_ManufacturerTypeInformation`, ...); the pset *name* is recorded as
provenance but does not affect the join:

| Key | Type / example | What it drives |
|---|---|---|
| `PanelName` | label, `'DP-1'` | The equipment tag: family/type naming, the panel schedule identity, the placed instance's mark. Defaults to the IFC `Tag` (then the leading name token) when absent. |
| `Voltage` | `'480Y/277 V'` or a number | Parsed by `parse_voltage()` into line-to-line / line-to-neutral / phase count / wire count / system label. Selects the catalog voltage class (a `480Y/277` board maps to the 480 V panelboard line; `208Y/120` to the 240 V class). |
| `Phases` | `3` | Derived from `Voltage` when absent (a `Y/` system is 3-phase). Rides onto the family as a parameter VALUE. |
| `Wires` | `4` | Derived from `Voltage` when absent (a `Y/` system is 4-wire). Parameter value. |
| `BusRating` | `400` (amps) | THE PRIMARY CATALOG SELECTOR: the constructor picks the catalog member whose ampacity rows cover this rating. Also fills `MainsRating` for single-rating devices. Absent => scraped from the name text `(\d+)\s*A`. |
| `MainsType` | `'Main breaker'` / `'Main lugs only'` | Selects the MCB vs MLO variant of the panelboard family. Alias `MainDevice` folds in (`'breaker'` in its text => `Main breaker`). Absent => scraped from `MLO` / `MB` / `MCB` tokens in the name. |
| `MainsRating` | `400` | The main device rating; defaults to `BusRating` (single-rating device). |
| `ShortCircuitRatingkA` | `65` | Parameter value (SCCR); catalog facts may cap it. |
| `Mounting` | `'surface'` / `'flush'` / `'floor'` | The mounting disposition: WALL kinds (panelboards, ground bus) resolve an UPRIGHT work-plane frame (family +Z = the front normal); FLOOR kinds (switchboard, transformer) resolve a yaw frame. |
| `NumberOfCircuits` | `42` | Selects the pole-space count of the panelboard variant (30 / 42 spaces ...). Absent => scraped from `NN space` / `NN circuit` name text. |
| `NeutralRating` | `200` (%) or amps | Parameter value. |
| `FedFrom` | `'MSB'` (an upstream tag) | Builds the FEEDER TREE: one directed edge `<FedFrom tag> -> <this tag>`, each edge = one planned feeder circuit (panel -> load, rating, poles, voltage). Corroborated against the `conduit_<from>_<to>` named conduit solids when the IFC carries them. |
| `FeederEntry` | `'top'` / `'bottom'` | Parameter value; records where the feeder lands on the enclosure. |
| `MainDevice` | free text | Alias source for `MainsType` (see above). |
| `Sections` | `4` | Switchboard section count (drives the house-switchboard lineup composition when no catalog member covers the ampacity). |

Aliases also read when present: `RatingkVA`, `Primary`, `Secondary`,
`ImpedancePercent`, `TemperatureRise` (transformers); `Manufacturer`,
`ModelLabel`, `RoomName`; the clearance keys `ClearWidth` / `ClearDepth` /
`ClearHeight` / `Egress`; support keys `StrutSize` / `RodSize` /
`MaxSpacingM` / `AttachTo`.

## 2. Every value carries its provenance

`normalize_contract()` records where each value came from, so the
delivery report can tell FACT from INFERENCE:

| provenance string | meaning |
|---|---|
| `pset:PanelSchedule.BusRating` | read directly from that pset property |
| `pset:<name>.MainDevice` | folded from an alias key |
| `tag` / `name` | defaulted from the IFC Tag / Name |
| `name-text (NNN A)` | scraped from the name / object-type text by regex |
| `derived from voltage system` | Phases / Wires computed from the `Y/` voltage |
| `= BusRating (single-rating device)` | MainsRating defaulted |

Say this in every report: an `assumed` or text-scraped value is an
EDITABLE parameter the licensed engineer reviews — never a fact tekton
asserts.

## 3. What the join produces (worked, from the electrical-room IFC)

`examples/electrical-room-2500a.ifc` (our own three-d-stage authoring)
resolves to this family plan (`python scripts/ifc_intent.py intent
examples/electrical-room-2500a.ifc`):

| tag | pset (join key) | constructor | catalog member |
|---|---|---|---|
| DP-1, DP-2 | PanelSchedule 400 A, MB, 42 sp, 480Y/277 | `famgen.factory.make_panelboard` | Eaton PRL2X |
| LP-1..3 | 100 A MLO, 30 sp, 480Y/277 | `make_panelboard(mcb=False)` | Eaton PRL2X |
| LP-4 | 225 A MB, 42 sp, 208Y/120 | `make_panelboard` (240 V class) | Eaton PRL1X |
| T1 | TransformerSchedule 150 kVA 480 delta -> 208Y/120 | `make_transformer` | Eaton V48M28T4916 |
| MSB | SwitchboardSchedule 2500 A, 480Y/277, 65 kA, 4-section | `make_house_switchboard` — the panelboard resolver is asked FIRST and REFUSES honestly (`FactoryError: no sizing rows for 2500 A mains; tabulated: [100, 225, 400, 600]`); no catalog line covers a 2500 A switchboard, so the house family is composed from our own IFC-modeled lineup extents with the pset ratings as parameter values | (house) |
| TMGB, conduits, hangers, clearances | — | unmapped, each with a stated reason (ground-bus family follow-up; `rvt.mep.conduit` over the recorded runs; detailing; annotation) | — |

The refusal is the point: a rating the catalog does not cover is REFUSED
and routed to a house/parametric family that carries the ratings as
values — tekton never fabricates a manufacturer fact. See
`references/CATALOG-FACTS.md`.

## 4. Authoring rules that keep the join clean

1. **Put schedule data in psets, not in geometry or names.** Names are a
   fallback scraped by regex; a `480Y/277 V` in the name works, but
   `Voltage` in the pset is deterministic.
2. **One product per real component**, tagged with `ifcClass` =
   `IfcElectricDistributionBoard` (panelboards, switchboards),
   `IfcTransformer`, `IfcSwitchingDevice` (switchgear),
   `IfcCableCarrierSegment` (conduit runs, named `conduit_<from>_<to>`),
   `IfcDiscreteAccessory` (supports). A `IfcBuildingElementProxy` is a
   proxy — it maps only if its name/psets classify it.
3. **`FedFrom` names the upstream product's `PanelName`/tag** — that is
   how the feeder tree links; a `FedFrom` naming a tag not in the file is
   recorded as an EXTERNAL root (e.g. `UTILITY`).
4. **Clearances are data, not solid gear**: name the working-clearance
   volume `clearance_<tag>` (or exclude it) and put the dims in psets
   (`ClearWidth` / `ClearDepth` / `ClearHeight`); tekton records each as a
   NEC 110.26 zone tied to its equipment and OMITS it from the model with a
   stated reason (annotation, not a family).
5. **Property names are case-sensitive** and should equal the firm's
   Revit shared-parameter names when they have a shared-parameters file
   (`skills/tekton-ifc/references/shared-parameters-mapping.md`), so the
   same names flow through IFC psets, our family parameters, and the firm's
   schedules.
