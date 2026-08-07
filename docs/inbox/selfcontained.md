# selfcontained — THE CLOSE: HR1 + SC1 + the base ladder + DEMO v8

Stream: **selfcontained** (workstream agent, 2026-08-05, post-verdict-#45).
Territory: `tools/selfcontained.py`, `src/rvt/famgen/birthright.py` (v2
self-contained lanes), `experiments/selfcontained/**`,
`tests/test_selfcontained.py`, this record.
Status: **STAGED (batch 53) — READY for upload; STOP at READY.**

Charter recap: #45 convicted **G_ABPD × loaded-famdoc** (machinery and
species exonerated: T1r = T1v's exact bytes PASS on rst; U16g = U16's
proven famdoc FAIL on G_ABPD; T2a = the self-contained born standalone
PASS on G_ABPD). This stream (1) enumerated the famdoc→host reference
surface and diffed every target rst-vs-G_ABPD (HR1), (2) built OUR
content fully self-contained + one instance on G_ABPD (SC1), (3) split
the base conviction (ladder below; the charter's 2025 cell is blocked by
a measured gap, §4), (4) pre-built DEMO v8 through the same recipe, and
staged all four behind three certified controls.

---

## 1. HR1 — the enumeration, the diffs, and what they falsify

Instrument: `tools/selfcontained.py` `famdoc_census` — the **four-surface
host-resident census** of an added famdoc unit (seq-101 headers typed,
seq-102 objects typed, seq-103 rep id-walk, inline-ADocument typed) plus
the **walked-bind census** (the instanced form's style/material bind
slots). Full data: `experiments/selfcontained/hr1_report.json`.

### 1.1 Per-probe anatomy (measured this session)

| famdoc (base) | verdict | host-resident refs (101/102/103/adoc) | walked binds |
|---|---|---|---|
| T2a (G_ABPD) | PASS | 0 / 0 / 5* / 0 | **in-unit** (solid→own GStyle, faces→own material) — `self_contained` |
| T1v (G_ABPD) | FAIL | 0 / 0 / 5* / 0 | born forms bound; **OUR form −1 ×7** (1 solid + 6 face renders) |
| T1r = T1v bytes (rst) | PASS | same bytes | same (−1 tolerated on rst) |
| B0 / BX_birth (G_ABPD) | FAIL | **0 / 0 / 0 / 0** | **−1 ×7** (nothing bound at all) |
| U16g (G_ABPD) | FAIL | **23 / 29 / 51** / 0 | donor solid→**host 7845**, faces→**host material 1177727**; 18 foreign |
| U16 = U16g bytes (rst) | PASS | same bytes (targets born) | same host binds (landing born) |

\* T2a/T1v's 45 non-in-unit rep ids (5 aliasing host rows incl. GStyle
51/81/82/87/88 + one **deleted** target 3644, 40 resolving nowhere) are
**unremapped born-internal ids** — every one exists in the .rfa's own
3..7674 id space; the T-lane's schema-typed rebase does not walk those
rep slots. T2a PASSES carrying them ⇒ they calibrate the ranking:
**off-walk residue, even aliased onto substituted/deleted host rows, is
not fatal.** (T-lane finding, flagged in §6.)

### 1.2 What the enumeration falsifies and what survives

* **Falsified (as a blanket law): "any famdoc→host ref onto a
  substituted element is the objection."** T2a references substituted
  GStyles from its reps, its host Family row binds substituted GStyle 78,
  its instance binds substituted Level 311 + Phase 86961 — and passes.
  A category with **zero** style rows on G_ABPD (−2001265) and a
  **deleted** aliased target (3644) are also tolerated.
* **Falsified: the inline-ADocument flavour axis.** T2a ships the SAME
  authored-empty form as T1v (0/239 AppInfo registries, history GUID =
  unit GUID) and passes; U16g ships the born 131/239 form and fails.
* **Falsified: the host-row / lane axis.** T2a/T1v/U16g all carry dummy
  (SerializedDummy) host symbol/instance/family reps; hop accounting
  identical.
* **The ONE measured separator left standing: the walked-bind surface.**
  The born law (mined from the specimen + its T2a embedding): the
  instanced form's solid Geometry `GInfo.m_categoryId` → the famdoc's
  OWN GStyle row (born 4087), every face `m_pGFilling.GInfo` → own
  fill style (5564), sketch curves → own sketch style (4123), every face
  `m_renderStyleId` + `ExtrusionElem.m_materialId` → an **in-unit**
  MaterialElem (5265/5264) whose appearance asset is itself in-unit.
  OUR famgen emits **−1** on every one of those slots; the embedded
  donor species (U16g) binds **host** rows. Either way the walked style
  resolution LEAVES THE UNIT — on rst it lands on born rows; on G_ABPD
  every landing row is ours-substituted (or a hole). T2a — the only
  G_ABPD famdoc whose walk stays in-unit — is the only G_ABPD PASS.

### 1.3 The target diff, rst vs G_ABPD (field-by-field; every ref target)

All 22 present targets: **same class, same seq-101 header bytes,
value-level diffs only** (the substitution preserved identity/shape and
replaced values). Notables, ranked by walk proximity:

| target | class | on the walk? | what differs on G_ABPD |
|---|---|---|---|
| 1177727 | MaterialElem | **yes** (6 face renders + m_materialId + 7 Family refs) | **appearance asset stripped**: `m_appearanceAssetId` −1, asset property list 56→0, materialPathMap emptied; cellList→None (17 leaf diffs / 652) |
| 7845 | GStyleElem | **yes** (solid style) | color 0→2105440, pen 1→2, cellList→None |
| 12632 / 429 | GStyleElem / FillPatternElem | **yes** (face fillings) | house color / linePatternId −1→−3000010; pattern grids 3→1 + angle/deltas |
| 311 / 86961 | Level / ProjectPhase | instance row (T2a-exonerated) | bubble 30→40, isBuildingStory F→T, envelope; name 'New Construction'→'New Work' |
| 201 / 55150 / 69 / 111 / 193 / 23795 / 3 / 16 / 6473 | view styles/patterns | off-walk | house colors/pens/names ('GEN …'), cellList→None |
| 3644 | GStyleElem | off-walk alias | **MISSING** (deleted by D_all) |

### 1.4 THE RANKED OBJECTION LIST (per-ref; the record's deliverable)

1. **Face `m_renderStyleId` / `m_materialId` → substituted MaterialElem
   1177727 with a stripped appearance asset** (asset −1, 0 properties) —
   the walk renders faces through an assetless material; the most
   violent target diff on the walk surface (U16g's cell).
2. **Solid/fill style binds → substituted GStyle 7845 / 12632 +
   FillPattern 429** (house values; born rows carry a CellList, ours
   None) — the rest of U16g's walk surface.
3. **OUR unbound (−1) walk binds** — B0/T0/T1v/BX_birth/DEMO v5–v7 give
   the walk no in-unit answer at all; the resolution falls through to
   the host's category catalog. This is the axis SC1 flips.
4. **Host-side loader rows** (Family→category GStyle 78/124, corpus
   symbol GElement→124, instance→Level/Phase): T2a passes with the
   Family/instance shape and the dummy symbol ⇒ ranked low; SC1's
   T-lane drops the corpus GElement anyway.
5. **Off-walk refs** (RetouchTable 201/55150, sketch/annot styles,
   patterns, header `m_parents.m_deletion` lists, the 45 unremapped
   born-internal ids): T2a's tolerated aliases + the missing 3644
   calibrate these non-fatal.

**The G_ABPD-side compose ALTERNATIVE (per charter):** instead of (or
alongside) self-containment, repair the substituted rows the walk lands
on: (a) author a real in-file appearance asset for substituted
MaterialElem rows; (b) author `m_cellList` on substituted
style/pattern/material rows (born rows carry it; our writer drops it);
(c) close the deleted-style holes left referenced (GStyle 3644, category
−2001265's rows). Compose territory; the diff table above is the exact
repair spec. The ladder (§3) tells whether this route is even necessary.

---

## 2. SC1 — our content, fully self-contained, on G_ABPD

**Variant chosen (charter asked us to state it): authored in-unit locals
via the birthright lanes + the born render-bind law, loaded by the
T2a-EXACT lane.** Not the "carry the born shell's locals and repoint"
variant — T1v already carried the full born shell (catalog included)
around our content and FAILED; its measured gap vs T2a is exactly the
unbound walk binds of OUR form. Binding our form to authored in-unit
rows is the single untested content variable, and it is the zero-donor
recipe DEMO v8 needs anyway.

Recipe (all machine-verified, `experiments/selfcontained/accounting.json`):

* famdoc = our 41-element famgen panelboard + the **authored birth set**
  (1,683 elements; authored-vs-mined diff 0 mismatches) + the **render
  binds**: solid Geometry → authored(4087) = in-unit GStyle 1472607;
  6 faces `m_renderStyleId` + `m_materialId` → authored(5265) = in-unit
  MaterialElem 1472815 (whose `m_appearanceAssetId` → in-unit authored
  AppearanceAssetElem 1473783 — born parity: the born 5265 also carries
  0 inline props + an in-unit asset ref); 4 sketch curves → authored
  (4123) = in-unit GStyle 1472641. Bind targets mined into
  `experiments/selfcontained/render_binds.json` (born ids only, zero
  identity, test-enforced).
* lane = **T2a/T0's exact famload path** (`FL.load_family_documents`
  with a builder + `place_one`), dummy host symbol, authored inline
  ADocument, ONE uniform instance on G_ABPD.
* gates (all green): validator 0 errors / 0 unexpected; four-registry
  coherent; +1 unit on the load hop / +0 on the instance hop; survivor
  law; identity PASS; every unit blob-carrying, added nonce verified;
  instance 0 dangling; **four-surface census: 0 host-resident refs**
  (stricter than T2a itself, which carries 5 tolerated aliases);
  **walked binds self-contained** (0 foreign, 0 unbound).

| | |
|---|---|
| file | `experiments/selfcontained/SC1.rvt`, md5 `d3ad392346e022f9a2c93c2a1928f657` |
| ids | symbol 1474266 / family 1474249 / instance 1474269; part_type 14; category −2001040 |
| the ONE thing vs T2a (PASS) | the unit's content is OURS (authored, not born) |
| vs T0 (FAIL) | + birth set + binds (same lane, same base) |
| vs BX_birth (FAIL) | + binds, − corpus-symbol host bind (lane) |

---

## 3. The base ladder — U16's byte-identical famdoc across the compose stack

The charter's U16g25 is **blocked by a measured gap** (§4). The base
split ships instead WITHIN this lineage, same format, proven machinery
(`union_reconcile.build_u16g` verbatim with the base swapped; its own
gates all run):

| rung | base (certified) | famdoc→host targets land on | md5 |
|---|---|---|---|
| U16gK4 | `experiments/genesis/triage/K4.rvt` (the substrate: Autodesk empty skeleton) | **BORN rows** (measured: every target byte == rst's) | `2812846c901bb49190d9e620b8a57902` |
| U16gABP | `…/compose/G_ABP.rvt` (substitutions IN, deletions OUT) | **OUR substituted rows** (every target byte == G_ABPD's, != rst's) | `8128bf848e9b7af9d88483f2305ba12d` |
| U16g (b52) | G_ABPD (substitutions + 240 deletions) | substituted + holes | FAILED (known cell) |

Watermark law held (K4 == G_ABP == G_ABPD == rst == 1472524), so all
three cells carry U16's **byte-identical famdoc segments** (machine-
pinned) AND land on U16g's exact host ids (symbol 1474584 / family
1474565 / instance 1474585) — a pure base split. Reference resolution on
both rungs: 29 host-resident / 0 unresolved (the same 29 as U16g).

## 4. The 2025 cell — measured blocker, recorded follow-up

"U16g's exact recipe on G_ABPD_2025" cannot ship this round because,
measured: (a) **famload cannot walk 2025 framing** — the known gap B of
the 2025 build stream (`docs/inbox/compose-2025.md`: `unexpected
Partitions header: v=9 cls=0x391`); (b) 4 of the famdoc's 77 classes
have different 2025 layouts (BrowserOrganization, DBViewDrafting,
StructSettingsElem, Viewport) so "U16's famdoc bytes" cannot ride
verbatim; (c) the inline ADocument needs the port2025 adapt. A 2025
famload/instance lane is a real port, and a probe built on an untested
port would confound base-vs-machinery. Follow-up (owner: 2025/port
stream): port famload + the instance path under `context_2025`, then
re-run `U16g` there — `tools/selfcontained.py build_u16g_on` takes any
base once the lane exists.

---

## 5. DEMO v8 — the user's prompt through self-contained authoring

`"an electrical room rated for 250V with 6 panels"` end-to-end through
`rvt.frontdoor.run` with `birthright.enabled(spec, binds=…)` — the v7
recipe + the render-bind lane. 6 families × **1,724-record units, every
unit machine-verified: 0 host-resident refs on all four surfaces, walked
binds fully in-unit**; 6 instances; validator 0 errors; every unit
blob-carrying; PP- symbol form asserted on all 6; front-door status
PROOF-ONLY (self-checks PASS). Walls: 0 — the known intent-grammar
regression (flagged by the birthright stream, still open; not this
stream's territory). md5 `1741344f7777902fef81b7694efcc071`.

vs v7 (FAIL): the binds (single content variable).
vs SC1: the product loader lane (famgen chain + corpus symbol form,
which binds host GStyle 124 on the HOST-side symbol rep) and
multi-family — pre-committed in the decision table.

---

## 6. The staged round + the decision table

**Batch 53** (`experiments/acceptance/batch_53.json`), staged via
probe_batch primitives, all md5s re-verified. **THREE controls**, one
per base, each a byte-identical certified copy: `CTRL_G_ABPD_b53` (gates
SC1 + DEMO v8), `CTRL_K4_b53` (gates U16gK4), `CTRL_G_ABP_b53` (gates
U16gABP). Reading order: **SC1, U16gK4, U16gABP, DEMO_250v_room_v8**.

Decision table (full text `experiments/selfcontained/probes.json`
`reading_the_matrix`):

* **SC1 PASS** ⇒ the law is confirmed: the composed base accepts our
  famdoc once the walked style resolution stays in-unit; birthright v2
  self-contained authoring is the specified fix. Read DEMO v8: PASS ⇒
  the campaign closes (promote `birthright.enabled(spec, binds)` to the
  famgen emission default, rebuild acceptance); FAIL ⇒ enumerated lane
  deltas (famgen loader vs famload; corpus symbol GElement→host GStyle
  124; multi-family; walls) — bisect v8 through the T-lane first.
* **SC1 FAIL** ⇒ self-containment is insufficient; with T2a the passing
  shape, the residual delta is unit-content AUTHORSHIP × base. The
  ladder then carries the round:
  * **U16gK4 PASS + U16gABP FAIL** ⇒ substitution-layer conviction at
    the famdoc→host surface; the §1.4 compose-side repair (rank 1: the
    stripped material asset) is the fix spec.
  * **U16gK4 PASS + U16gABP PASS** ⇒ deletion-layer conviction (only
    the deletion set's holes separate U16gABP from b52's U16g FAIL);
    fix = don't delete referenced style rows / close the holes.
  * **U16gK4 FAIL** ⇒ lineage conviction independent of our
    substitutions — the composed skeleton itself rejects a loaded-
    famdoc recipe rst accepts byte-identically; escalate to the
    desktop-Revit kit + the 2025 lane port.
* Any control FAIL voids its own base's probes only.

**Findings for other streams** (not this territory):

* **T-lane rebase gap**: seq-103 rep id slots are not remapped by the
  schema-typed rebase (45 born-internal ids ride into every T-probe;
  tolerated by the viewer, but they alias host ids — rft-probes stream).
* **Compose**: G_ABPD's substituted rows are value-impoverished where
  the walk can land (§1.4 alternative — material asset, cellList,
  deleted-style holes). `hr1_report.json` carries the per-field spec.
* **Front door**: the demo prompt still derives 0 walls (v3 had 4) —
  the previously-flagged grammar regression stands.

## 7. Reproduction (repo root, `.venv/bin/python`)

```
tools/selfcontained.py mine-binds     # render_binds.json (4087/5564/4123/5265)
tools/selfcontained.py hr1            # hr1_report.json (censuses + diffs)
tools/selfcontained.py build          # SC1, U16gK4, U16gABP, DEMO v8 + gates
tools/selfcontained.py stage          # batch 53 (3 controls, md5-verified)
tools/selfcontained.py census FILE --base BASE   # the four-surface gate
.venv/bin/python -m pytest tests/test_selfcontained.py -q   # 24 passed
```

## BRANCH STATE

* No VCS (working tree only). Territory files written:
  `tools/selfcontained.py` (new), `src/rvt/famgen/birthright.py`
  (render-bind lanes appended: `read_bind_spec`, `apply_render_binds`,
  `walked_bind_census`, `enabled(..., binds=)`; v1/v2 surfaces
  unchanged), `tests/test_selfcontained.py` (new, 24 passing),
  `experiments/selfcontained/**` (4 probes + render_binds.json +
  hr1_report.json + accounting.json + probes.json + _build/), staging
  copies + manifest `experiments/acceptance/batch_53.json`, this record.
  Plugin re-synced (`tools/sync_plugin.py`) after the birthright edit.
* Targeted suites: test_selfcontained 24 + test_birthright 19 +
  test_rft_probe 24 + test_union_reconcile 20 + test_plugin_sync — all
  passing. NO full-suite run (charter).
* U16gK4/U16gABP embed the rst donor famdoc — PROOF-ONLY, quarantined
  under `experiments/`; SC1/DEMO v8 carry zero donor bytes (authored
  birth + symbolic-id binds, test-enforced). Zero donors in anything
  shipped.
* **Batch 53 is STAGED, gates green, md5-verified. NOT uploaded — the
  orchestrator uploads (stage-only law). STOP at READY.**
