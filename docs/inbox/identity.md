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

---

## eng #388 — 2026-08-10 — the v4 lane accepts our own DBView3d (ExtentElem role split); refusal retired

Stream: `eng388` (engineer session under the tech-lead session; branch
`cam/388-birthright-v4-dbview3d`).  Closes #388.  Refs #381 / #383 (every
generated family now carries the ceiling plan + the "View 1" `DBView3d`
constellation).  The identity axis stays **exonerated** for the open cell
(verdict #48) — nothing below is a viewer/Revit claim; it repairs a lane
that raised on every product.

### 1. The break (measured on `main` @ 2b87024)

`with birthright.enabled(spec, version=4): make_panelboard / make_luminaire /
make_transformer(start_id=3000)` — all three:

```
ValueError: birthright v4 identity: document authors a DBView3d -- the ExtentElem
flags law is role-split there and this lane only knows the plan/section shape; refuse
```

(v2/v3 unaffected; `tests/test_identity.py` used toy documents and *pinned*
the refusal, so no test caught it — the #383 reviewer did.)

### 2. The change (`src/rvt/famgen/birthright.py`, ~25 lines)

* The role split the module already documented, now resolved per element:
  `born_header_flags(el, view3d_ids)` = the `BORN_HEADER_FLAGS` table value,
  except an `ExtentElem` whose `obj["m_dbViewId"]` names a `DBView3d`
  carries `BORN_EXTENT_FLAGS_3D = 10`; plan/section satellites keep 26.
  Authority unchanged: `identity_diff.json` born-standalone `ExtentElem
  {26: 6, 10: 1}` = 2 plan + 4 section + 1 3D view of the vendor .rfa.
* `apply_born_identity` and `identity_census` both go through it (a 3D
  satellite left at 26 is a census `flags_off`, so the lane and its gate
  cannot disagree); `_extent_view_id(el)` is the one place `m_dbViewId` is
  read; the report gains `extent_roles` (`{"plan_section": n, "view3d": m}`,
  tallied from the same predicate, not back-derived from the value).
* `apply_host_family_table_law` gains an explicit `native: bool` verdict
  (see §3, the identity_probe adjustment) — additive key, v3 behaviour and
  every existing assertion unchanged.
* The DBView3d refusal is **removed**; in its place the lane refuses only an
  `ExtentElem` naming a view id the document does not carry (role
  undecidable) — the "refuse loudly on a shape it does not understand" law,
  narrowed to the actually-undecidable case.
* Classes the 3D constellation adds that the table never covered
  (`DBView3d` 65562, `Viewer3d` 18744, `ModelClipBox`, `LightSchemeElement`
  in the specimen) stay **untouched**, exactly as the table's contract says
  ("classes absent from the table are left untouched") — widening the table
  is a separate, single-variable decision, not this fix.

### 3. Evidence (this VM: cloud session, no `samples/` / `vendor/`)

After, same call as §1 (bundled `experiments/birthright/template_birth.json`):

| product | builds | version | n_added | verify | identity_ok | suffixes re-minted | flags changed | ExtentElem (view class → flags) |
|---|---|---|---|---|---|---|---|---|
| make_panelboard | ✅ | 4 | 1683 | ok | True | 14 | 31 | DBViewPlan 26, DBViewPlan 26, **DBView3d 10** |
| make_luminaire | ✅ | 4 | 1683 | ok | True | 8 | 31 | DBViewPlan 26, DBViewPlan 26, **DBView3d 10** |
| make_transformer | ✅ | 4 | 1683 | ok | True | 11 | 27 | DBViewPlan 26, DBViewPlan 26, **DBView3d 10** |

One v4-lane product emitted through the product's own `write()`
(`make_panelboard` → `panelboard_v4.rfa`, 1,770 elements, scratch dir):
`tools/rvt_validate.py … --family` → **VALID (no errors); warnings=0**;
`tools/make_family.py provenance` → **PROVENANCE-CLEAN** (all 11 checks
true: zero donor ADocument bytes / ids / names, identity ours, footer ours).

`tools/identity_probe.py build` on the post-#383 tree (G_ABPD supplied
locally as a byte-identical copy of the plugin pin, md5 `1f1ff65b…` = the
compose manifest's):

```
[identity] BX_v4 BUILT -> experiments/identity/BX_v4.rvt (md5 adf457ab, 2.2s)
[identity] BX_v4: validator 0 err (unexpected 0), coherent True, identity-form True, species True, gates_ok True
[identity] DEMO_250v_room_v10 BUILT -> experiments/identity/DEMO_250v_room_v10.rvt (md5 8c8e4eab, 15.0s)
[identity] DEMO_250v_room_v10: validator 0 err (unexpected 0), coherent True, identity-form True, species True, gates_ok False
[identity] I1 FAILED: FileNotFoundError: /home/user/tekton/samples/rstbasicsampleproject.rvt
```

* **BX_v4** (SC1's recipe at v4: famload + one instance on G_ABPD): builds,
  every gate green — identity lane applied (14 suffixes, 33 headers covered,
  31 changed), doc-side census green, hostsym applied, verify ok, walked
  binds self-contained, file-level census all-OTHER-form, species ok.
* **DEMO v10** (the prompt through `rvt.frontdoor.run` at v4): builds — 6
  families, identity census green on every one, validator 0, species ok.
  Its `gates_ok False` is **one pre-existing, unrelated axis**:
  `survivor_law_ok False` = host survivor **49504 `ProjectInfo`** modified in
  seq-102 (`Building Name 'Genesis Base' → ''` etc.) — the front door's
  deliberate per-job ProjectInfo identity write from **#148**
  (`docs/inbox/projectinfo-identity.md`), which postdates this probe's
  byte-identical-survivor gate (`bisect_instance_bug.account`).  Not caused
  by #381/#383/#388 and not birthright's; filed as a follow-up (below)
  rather than loosened here.
* **I1** is sample-gated by construction (T1u's famdoc = `samples/
  rstbasicsampleproject.rvt` + the vendor .rfa) — the one step a cloud VM
  cannot run; it never touches the v4 lane (I1 normalizes T1u's fields
  directly), so it is unaffected by this change.
* `tools/identity_probe.py` needed **one adjustment to build DEMO v10 at
  all**, independent of #383: its "loader-half hostsym applied on every
  family" check has been dead since **#10** (the product loader authors the
  native single-leading-blank table itself, so `apply_host_family_table_law`
  is a verifier reporting `applied: False` — its own docstring and
  `test_hostsym_product::test_birthright_v3_loader_half_is_now_a_noop` say
  so).  Fixed at the contract, not by inference: `apply_host_family_table_law`
  (birthright, in territory) now states the shape verdict positively —
  `native: bool` on all three return paths (False only on the two off-shape
  early returns that also carry `why`) — and the probe keys on
  `all(native)`; one changed condition + comment in the probe, said here as
  the charter asks.  `tools/species_probe.py:1245` (DEMO v9) still carries
  the identical dead `all(applied)` check — out of territory, same one-line
  fix when that probe is next run.
* BX_v4 / DEMO md5s differ run to run (`adf457ab`/`63b5402b`,
  `8c8e4eab`/`8cea5b7d`) with no source change between runs — pre-existing
  build nondeterminism (#9's territory), not introduced here.
* The regenerated `experiments/identity/accounting.json` / `probes.json` /
  `_build/**` from these local runs are **not** committed: the tracked
  copies are the owner-machine batch-55 evidence the layer-3 tests pin, and
  a cloud rebuild (I1 absent, DEMO gate red on #148) would only degrade
  them.  Numbers above are from the scratch copy.

### 4. Tests

`tests/test_identity.py`: `test_refuses_dbview3d` → **`test_accepts_dbview3d_and_splits_extent_role`**
(toy doc: plan satellite → 26, 3D satellite → 10, DBView3d header untouched,
`extent_roles`, census green; census flags a 3D satellite left at 26) +
`test_refuses_extent_naming_absent_view` +
`test_loader_half_states_native_verdict`; new **`TestV4LaneOnRealProducts`**
(bundled spec, fresh-clone safe, ~0.4 s): the v4 lane over the real
`make_panelboard` / `make_luminaire` / `make_transformer` (version 4,
identity applied, census green, verify ok) and the panelboard's ExtentElem
roles `{DBViewPlan: {26}, DBView3d: {10}}`, `extent_roles {plan_section 2,
view3d 1}`, every other covered class uniform at the table value.  Against
`main`'s `birthright.py` these are 2 failed + 4 errors; with the change
**37 passed, 3 skipped** (vendor .rfa absent / BX_v4 absent / staged
binaries absent).  The file joins the CI shard via
`tests/ci_shard.d/388-birthright-v4-dbview3d.txt` (whole file is
fresh-clone safe: layers 2–3 read tracked JSON and self-skip on absent
binaries).  Adjacent: test_identity + test_plugin_sync + test_species +
test_birthright + test_hostsym_product + test_shard_list = **145 passed, 5
skipped**.

### 5. Follow-ups (filed, `Refs #388`)

* **#413** — identity_probe / bisect survivor gate vs the #148 ProjectInfo write: the
  DEMO-lane accounting should treat the front door's *declared* ProjectInfo
  identity write (element 49504, seq-102 string params only) as lawful — or
  diff against a ProjectInfo-normalised parent — instead of reading it as a
  survivor-law violation; until then every front-door-built probe's
  `survivor_law_ok` is False by design.
* (noted, not filed — belongs to the #381 campaign's own sequencing) the
  born table does not cover the 3D constellation's own classes
  (`DBView3d`/`Viewer3d`/`ModelClipBox`/`LightSchemeElement`); if the
  identity axis is ever re-opened with new evidence, that is the next
  single variable, with the specimen values already in `identity_diff.json`.

### BRANCH STATE (eng #388)

* Branch `cam/388-birthright-v4-dbview3d` from `main` @ 2b87024.  Files:
  `src/rvt/famgen/birthright.py` (+ mirror `plugin/lib/src/rvt/famgen/
  birthright.py` via `tools/sync_plugin.py`), `tests/test_identity.py`,
  `tests/ci_shard.d/388-birthright-v4-dbview3d.txt` (new),
  `tools/identity_probe.py` (the DEMO v10 hostsym-check condition, §3),
  this section.  `/simplify` ran (4 angles; applied: single-site
  `m_dbViewId` read, predicate-keyed role tally, explicit `native` verdict
  instead of inferring from `why`).  Nothing under `skeleton.py` / factory bodies / hot
  files.
* Gates: test_identity 37 passed / 3 skipped; adjacent run (identity,
  plugin_sync, species, birthright, hostsym_product, shard_list) 145 passed /
  5 skipped; `tools/sync_plugin.py` synced 1 file, `--check` clean (deny-audit
  clean, identity scan == allowlist, assets verified);
  `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok; `tests/test_shard_list.py` 23
  passed.  No full-suite run (charter).
* Nothing staged for the viewer; no certification claim.  Zero donor bytes:
  the change is a per-element choice between two already-tabled scalar law
  values.
