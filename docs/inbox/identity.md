# identity — the element-identity coupling, I1, birthright v4

Stream: **identity** (workstream agent, 2026-08-05, post-verdict-#47).
Territory: `tools/identity_probe.py`, `src/rvt/famgen/birthright.py` (v4
lanes), `experiments/identity/**`, `tests/test_identity.py`, this record.
Status: **STAGED (batch 55) — READY for upload; STOP at READY.**

Charter recap: #47 named the surviving axis — our-authored famdoc content
fails on REDUCED bases only (T1uG: same bytes PASS rst / FAIL G_ABPD),
born content passes everywhere, self-containment excludes references, so
the coupling is element-level identity/episode state.  This stream (1)
ran the commissioned forensics on the matched pair (TB0r-famdoc/TB0g PASS
vs T1u-famdoc/T1uG FAIL, same base, same lane) — BOTH halves: the famload
host-side write diff AND the element identity fields; (2) built **I1**
(T1u's famdoc, our 35 elements' identity fields — and only those —
normalized to the born convention, surgically machine-verified); (3)
wired **birthright v4** (the BORN IDENTITY lane) from the measured diff;
(4) built BX_v4 + DEMO v10 through it and staged all three behind one
G_ABPD control.

---

## 1. THE FORENSICS — `experiments/identity/identity_diff.json`

Instrument: `tools/identity_probe.py forensics` (fully machine-measured,
re-derivable in ~40 s).

### 1.1 Half 1 — the famload HOST-SIDE WRITE DIFF (TB0g vs T1uG)

| surface | measurement |
|---|---|
| Global/DocumentIncrementTable | **BYTE-IDENTICAL** between the PASS and the FAIL (both scrub every save-episode username to `''`; rows/ids/timestamps/counters verbatim) |
| Global/History | **untouched by both** (famload reuses the host's current episode) |
| Global/Latest (host ADocument) | **6 leaf diffs total**, all construction (unit GUID ×2, episode record count, surrogate id, 2 tracked-symbol sets) |
| host Global/ElemTable | added rows SHAPE-IDENTICAL (orig==id, all three episode columns = host episode 1016, partition 0); **zero base rows changed** in either |
| BasicFileInfo | identical modulo the output filename (both assert the writer's own author/client; the base's document GUID rides unchanged on both) |

**Verdict: host-side writes are identical ⇒ the coupling is inside the
famdoc elements** (the charter's pre-committed branch).

**The reduced-base premise CORRECTED by measurement:** G_ABPD carries
rst's Global/History entries (1,017/1,017 GUID-equal), rst's DIT rows
(all 22, usernames included) and every surviving ElemTable row
UNCHANGED.  Reduction rewrote the roster (−10,834 rows) and substituted
element content — NOT the host identity/episode surfaces.  The #47
framing "reduced bases' identity surfaces were rewritten during
reduction" is falsified at those three surfaces; what stands is the
coupling law itself, now located famdoc-side.

### 1.2 Half 2 — THE ELEMENT IDENTITY FIELDS (the ranked finite diff)

**RANK 1 — the family-parameter identity string**
`revit.local.family:<32-hex session><8-hex id>-1.0.0`
(`ParamElemFamily.m_pParamDef.m_typeId` — the m_seekItemId-style identity
the charter named).  THE MEASURED LAW: the 8-hex suffix records the id
the parameter had AT BIRTH and never re-derives.  Native containers ARE
their own birth container, so natively everything reads **SELF**
(suffix == current id: rst host 120/120, rst embedded units 243/243); a
REBASED transplant reads **OTHER** (the frozen birth id no longer equals
the current id).  On G_ABPD the four loaded-famdoc cells split EXACTLY:

| cell | param identity | verdict |
|---|---|---|
| T2a | 6/6 OTHER (shell birth ids 4208..5812) | PASS |
| TB0g | 3/3 OTHER (donor birth ids 1224270..) | PASS |
| T1uG | shell 6 OTHER + **ours 14 SELF** (wm-minted 1474542..55) | FAIL |
| SC1 | **14/14 SELF** (wm-minted 1472543..56) | FAIL |

Our params mint identity at the host-watermark current id — identity
coupled to the host's id/episode state; born params carry independent
frozen-birth identity.  The same SELF bytes pass on pristine rst (T1u) —
the coupling expresses on reduced substrates only, exactly the #47 law.

**RANK 2 — seq-101 `m_abFlags4Bytes`.**  Species-coherent per class in
every born famdoc (standalone carries 0x10, embedded drops it; measured
authority = the vendor .rfa == T2a's PASS bytes).  OUR elements mix
conventions inside one famdoc and stray off BOTH species: stray 0x800 on
DBViewType (2074 vs born 26), missing 0x2014 on SunAndShadowSettings
(10 vs born 8222), missing 0x10 on the datum/view classes (Level 2058 vs
2074, RefPlane, Viewer/Viewport/DBViewPlan/DBDrawing/SketchPlane/
ExtentElem/LevelAttributes).  All four cells separate on
flags-coherence too (T2a/TB0g coherent = PASS; T1uG/SC1 mixed = FAIL).
11 classes / 12 headers deviate among our 35.

**Recorded, NOT normalized in I1** (structure / doc-level, pre-committed
ledger items): (a) our ExtentElem + view-satellite SketchPlane
`m_parents.m_deletion` lists lack the leading self-Family root every
born twin carries; (b) the inline-ADocument elemArr episode columns —
T1uG's swapped born-wrapper table carries episode 0 where every
famload-authored table (T2a PASS, TB0g PASS, SC1 FAIL) carries the host
episode 1016 (non-separating alone, but the one doc-level surface still
splitting T1uG from TB0g).

**Measured EXONERATIONS** (equal / no-carrier / non-separating):
host-side writes (half 1); elemArr orig==id (everywhere) and episode
columns as element-level (uniform per famdoc, ours==shell);
m_createdPhaseId (−1 everywhere); m_regenHistory.m_historyMap (empty
everywhere); m_userId (self-consistent both sides); m_seekItemId
(Family-class only, no carrier in our 35); witness stamps
(Alignment/LinearDimString only, all False); GUID leaves (doc-level
classes only; PGUID maps empty); version counters (ours within born
range); session hex form (fresh-uuid4 style on ours AND born; born
sessions also absent host-side — T2a's 4 shell sessions unknown to
G_ABPD, passes).

## 2. birthright v4 (opt-in; v1/v2/v3 surfaces unchanged)

`src/rvt/famgen/birthright.py`: `_V4_LANES = _V3_LANES + ("identity",)`.

* `BORN_HEADER_FLAGS` — the born-standalone per-class flags table
  (measured on the vendor .rfa; test-pinned against it).
* `apply_born_identity(doc)` — POST-finalize: every ParamElemFamily's
  identity suffix re-minted as a FROZEN BIRTH id in the private small
  birth space (`BIRTH_SUFFIX_BASE` 4096+k, disjoint from the specimen's
  own param ids and every live id; session hex untouched); every covered
  header's `m_abFlags4Bytes` set to the born table.  Build-refusing on
  every unexpected shape (unfinalized doc, non-SELF prior mint, missing
  session identity, a DBView3d in the roster — the ExtentElem law is
  role-split there — missing flags key, birth-space overflow).
* `identity_census(doc)` — the machine gate: params all session-form,
  none SELF-minted, suffixes in the small birth space, covered flags on
  the born table.
* `apply_birthright_v4(doc, spec)` — full v3 (v2 lanes + hostsym) then
  the identity lane; REFUSES to emit on a red census.
* `enabled(spec, binds=…, version=4)` — routes products through v4;
  v3's loader hostsym patch carries over (`version >= 3`).  `version=2`
  default and `version=3` byte-behavior untouched (test-pinned).

Zero-donor line: the birth ids are OUR mint in a private id space; the
flags are per-class laws (adoptable shapes).  No donor bytes enter any
v4 surface.

## 3. The probes (all gates green; `experiments/identity/accounting.json`)

| probe | one thing it tests | vs | md5 | ids (sym/fam/inst) |
|---|---|---|---|---|
| **I1** | T1u's famdoc, our 35 elements' identity fields — and ONLY those — normalized to the born convention (14 suffixes → frozen birth ids 7675..7688 continuing the shell's 0..7674 space; 12 headers → the born flags table), famload + instance on **G_ABPD** | T1uG (FAIL) — the normalized identity field set is the single variable | `3d1cc2cd298cad8c9a1a2d671f781967` | 1474588 / 1474565 / 1474589 |
| **BX_v4** | B0's recipe (SC1's exact spec sha `00425e9d…` + binds, pinned) through birthright v4 on G_ABPD | BX_v3 (FAIL) — the element identity fields | `4d4ec8673a18d08bf97eac32324795f7` | 1474266 / 1474249 / 1474267 |
| **DEMO_250v_room_v10** | the user's exact prompt through rvt.frontdoor.run at version=4 | DEMO v9 (FAIL) | `78876fcfa472a6eb2d4cc912a1ea6890` | 6 families × 14 re-minted params, 6 instances |

Per-probe evidence, machine-verified at build (gates refuse otherwise):

* **I1** — the base state first re-proved byte-identical to `T1u.rvt`
  (segments 101/102/103 equal after the session-hex pin — T1uG's own
  proof), THEN the normalization, THEN the **surgical proof**: emitted
  segments differ from T1u's in EXACTLY the enumerated records — seq-103
  byte-identical, seq-102 diffs = the 14 param ids (1474542..55), seq-101
  diffs = the 12 covered headers (1474526..41), equal lengths, per-record
  containment.  References 31,054/31,054 in-unit; famload reproduced
  T1uG's exact host allocation (1474588/1474565/1474589 — the same three
  ids); the swapped born ADocument rides T1uG's lane verbatim; validator
  0; blob nonce verified; emitted unit identity census: 20 params, 0
  SELF.
* **BX_v4** — identity lane applied (14 suffixes → 4096..4109; flags 16
  headers covered / 15 changed); doc + file identity census green;
  hostsym applied; authored-vs-mined verify ok; walked binds
  self-contained; species census green (v3's gate intact); same spec
  sha + binds as SC1/BX_v3 (test-pinned single-variable claim).
* **DEMO v10** — 6 families × identity lane green (84 params re-minted,
  0 SELF across all 6 units); loader hostsym ×6; PP- symbol form ×6;
  species census green; validator 0; front-door status PROOF-ONLY.
  Walls: 0 — the known intent-grammar regression, still open, not this
  territory (fourth consecutive flag).

Gate summary (all three): validator 0 errors / 0 unexpected,
four-registry coherent, +1 unit on the load hop / +0 on the instance
hop, survivor law, identity gate PASS, blob-carrying with OUR
deterministic nonce, instance 0 dangling, **identity all-OTHER-form
REQUIRED everywhere**; I1 additionally REQUIRES base byte-identity +
the surgical containment; BX_v4/DEMO additionally REQUIRE the species
census.

## 4. The staged round + the decision table

**Batch 55** (`experiments/acceptance/batch_55.json`), staged via
probe_batch primitives, md5s re-verified, one control
(`CTRL_G_ABPD_b55.rvt`, byte-identical certified G_ABPD, md5
`1f1ff65b…`).  Reading order: **I1, BX_v4, DEMO_250v_room_v10.**

Decision table pre-committed in full in
`experiments/identity/probes.json` `reading_the_matrix`; headline rows:

* **I1 PASS + BX_v4 PASS + v10 PASS** ⇒ THE CLOSE: the identity law is
  confirmed — element identity minted against the host id space is what
  reduced bases reject; the fix is exactly the normalized field set
  (frozen-birth parameter identity + the born flags table).  Promote v4
  to the famgen emission default, rebuild acceptance.
* **I1 PASS + BX_v4 FAIL** ⇒ v4 authoring gap — diff BX_v4 against I1
  (finite); pre-identified candidates in order: (1) the
  parents-structure finding, (2) the born-roster true-up, (3) the
  born-wrapper ADocument.
* **I1 PASS + BX_v4 PASS + v10 FAIL** ⇒ famgen-loader lane gap —
  per-family bisect through BX_v4's famload lane.
* **I1 FAIL** ⇒ IDENTITY INSUFFICIENT — the honest remaining-axis
  ledger, recorded now: (a) the inline elemArr episode columns (T1uG
  ships 0 where every famload-authored PASS ships 1016 — the one
  doc-level surface still separating T1uG from TB0g), (b) the
  parents-structure finding, (c) content birth itself (#46's residual:
  no famdoc-side authoring closes it), (d) the container/envelope axes
  (terminal-diff territory).  The desktop-Revit check kit becomes the
  primary instrument; the compose-side repair (hr1 rank 1) re-ranks
  first.
* Control FAIL voids the round.

## 5. Findings for other streams (not this territory)

* **compose / genesis**: the b51 "G_ABPD carries an Autodesk username —
  scrub candidate" item should be re-read against §1.1: G_ABPD's
  History/DIT/BFI identity surfaces are byte-inherited from rst
  UNCHANGED, and the famload save path already scrubs DIT usernames +
  asserts our authorship in BFI on every emitted child.  A base-side
  scrub would not have separated the PASS from the FAIL cells.
* **famdoc_final / union machinery**: our view-satellite ExtentElem /
  SketchPlane headers omit the self-Family deletion root every born twin
  carries (§1.2 recorded item) — a candidate product fix independent of
  the verdicts.
* **famload**: authors host twins SELF-minted with a fresh session hex —
  measured native-coherent (rst host 120/120 SELF; T2a/TB0g pass with
  famload twins) — EXONERATED, no change wanted.
* **front door**: the demo prompt still derives 0 walls (fourth flag).
* **convert/extract streams**: identity strings freeze at birth — any
  extractor that rebases famdoc elements must NOT re-derive
  `revit.local.family:` suffixes (the born convention IS the stale
  suffix).
* **species stream (closed)**: `tests/test_species.py`'s
  unknown-version pin necessarily moved 4→5 when v4 came to exist —
  one-assertion mechanical edit, noted here (the species record itself
  is untouched).

## 6. Reproduction (repo root, `.venv/bin/python`)

```
tools/identity_probe.py forensics   # identity_diff.json (~40 s)
tools/identity_probe.py build       # I1, BX_v4, DEMO v10 + gates (~50 s)
tools/identity_probe.py census FILE [--unit N]   # the SELF/OTHER gate
tools/identity_probe.py verify      # re-run gates from accounting
tools/identity_probe.py stage       # batch (G_ABPD control, md5-verified)
.venv/bin/python -m pytest tests/test_identity.py -q   # 34 passed
```

## BRANCH STATE

* No VCS (working tree only).  Territory files written:
  `tools/identity_probe.py` (new), `src/rvt/famgen/birthright.py` (v4
  appended: `apply_born_identity`, `identity_census`,
  `apply_birthright_v4`, `_V4_LANES`, `BORN_HEADER_FLAGS`,
  `BORN_IDENTITY_LAW`, `BIRTH_SUFFIX_BASE`; `enabled` accepts
  `version=4`; versions 2/3 byte-behavior untouched),
  `tests/test_identity.py` (new, 34 passing),
  `experiments/identity/**` (3 probes + identity_diff.json +
  accounting.json + probes.json + _build/), staging copies + manifest
  `experiments/acceptance/batch_55.json`, this record.  One-assertion
  mechanical edit in `tests/test_species.py` (unknown-version 4→5 — the
  chartered v4's existence).  Plugin re-synced (`tools/sync_plugin.py`)
  after the birthright edit; validation passed.
* Targeted suites: test_identity 34 + test_species 36 + test_birthright
  + test_selfcontained + test_rft_probe + test_union_reconcile (123 in
  the combined adjacent run) + test_plugin_sync 7 — all passing.  NO
  full-suite run (charter).
* I1 embeds vendor-born content — PROOF-ONLY, quarantined under
  `experiments/`; BX_v4 + DEMO v10 carry zero donor bytes (authored
  birth + OUR minted identity in a private birth space, test-enforced).
  Zero donors in anything shipped.
* **Batch 55 is STAGED, gates green, md5-verified, control
  byte-identical to certified G_ABPD.  NOT uploaded — the orchestrator
  uploads (stage-only law).  STOP at READY.**
