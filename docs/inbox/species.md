# species — the species cells, the CD/registration forensics, birthright v3

Stream: **species** (workstream agent, 2026-08-05, post-verdict-#46).
Territory: `tools/species_probe.py`, `src/rvt/famgen/birthright.py` (v3
lanes), `experiments/species/**`, `tests/test_species.py`, this record.
Status: **STAGED (batch 54) — READY for upload; STOP at READY.**

Charter recap: #46 left the map "pristine rst accepts every species;
reduced bases accept exactly ONE — T2a, the standalone-born famdoc" with
three untested decisive cells.  This stream (1) ran the T2a-vs-SC1
registration forensics byte-for-byte across EVERY surface, (2) built the
two species cells as byte-identical transplants (T1uG, TB0g), (3) wired
**birthright v3** from the measured delta list, (4) built BX_v3 + DEMO
v9 through it, and staged all four behind one G_ABPD control.

---

## 1. THE FORENSICS — T2a (PASS) vs SC1 (FAIL), every registration surface

Instrument: `tools/species_probe.py forensics` →
`experiments/species/cd_forensics.json` (0.7 s, fully machine-measured).
Both files appended ONE unit to G_ABPD's rebuilt-empty ContentDocuments
stream through the same famload lane; the diff is therefore exactly the
species delta.

### 1.1 Measured EXONERATIONS (surfaces that do NOT separate PASS from FAIL)

| surface | measurement |
|---|---|
| CD stream framing | one entry each; identical 12-byte 0x3a3 separator prologue, identical 14-byte end record, byte-equal tail |
| **inline ADocument** | **7 diff paths TOTAL, all identity/count** (4 history GUIDs = own unit GUID in BOTH; m_ownerFamilyId = own self-Family; elem rows).  Both ship the authored embedded form: m_elemTable POPULATED inline, m_pHostDocument weakref 1, ContentRecSet 0, **0/239 AppInfo registries**, storedByRevitBuild [] |
| ContentTable record | shape-identical (guid + episode count differ) |
| FamilyMgr entry | shape-identical (surrogate id + guid) |
| host Global/ElemTable rows | shape-identical owner law (twins→Family; surrogates/symbols/instance ownerless; original_id==id; partition 0) |
| partition separator | counter=n_records + unit GUID + first_block 14, both |
| id policy | both register contiguous wm+1.. (**current-id policy stands**); T2a's small-id rep aliases are unremapped BORN residue (HR1: 45 typed), tolerated, not a shape to author |
| self-Family form | obj/header key sets IDENTICAL; every shape diff count-driven (familyIds rows, type pairs, locked, params); m_bShared True both |

**The charter-hypothesized "standalone inline-ADocument form" (m_elemTable
NULL, owners in the ElemTable stream, NO history GUIDs) is FALSIFIED as a
registered shape** — that is the standalone FILE's `Global/Latest` form;
the registered entry is famload's authored embedded form on the PASS and
the FAIL alike.  Cross-evidence already on record: U16g shipped the BORN
wrapper (independent identity, 131/239 registries, donor build strings)
and FAILED on G_ABPD.  The ADocument axis is dead on reduced bases; v3
deliberately changes nothing there.

### 1.2 THE MEASURED DELTA LIST (ranked; = the v3 spec)

1. **THE HOST SYMBOL TABLE (authorable — v3's hostsym lane).**
   SC1 registered TWO FamSymSurrogate+FamilySymbol pairs, the FIRST named
   `' '` (blank), **and bound the placed instance to the blank pair's
   symbol**; T2a registered exactly ONE pair (`'0610 x 0160mm'`, the
   first non-blank type name), instance bound to it.  Native law
   (measured, 36 rstbasic host Family rows): **zero** rows with more than
   one blank, **zero** rows whose m_idx names a blank when real pairs
   exist.  Root cause: birthright v2's types lane prepends the blank pair
   to `doc.types`; famload authors one host pair per `doc.types` entry
   and `plan.symbol_id` = the first.
   **Bonus measured leak (famgen-loader lane):** DEMO v8's six host
   Family rows carry a DOUBLE-blank type table `[' ', ' ', '225A MLO
   42ckt']` with **m_idx=1 pointing at a blank row** — the loader copies
   the baked unit table and prepends its OWN blank current-values row.
2. **Unit roster** — T2a carries **+268 elements across 50 classes**
   (the overlapping-class shortfall the spec records + the
   reference-closure dropped set + the loaded-family registration block:
   the vendor .rfa's roster includes a 2nd Family `'Level Head -
   Upgrade'` + FamilySurrogate + FamilySymbol + FamSymSurrogate
   IN-UNIT).  **Deferred, with cause:** T1v — the FULL born roster + our
   35 elements, clean symbol table, authored-empty ADocument — FAILED on
   G_ABPD (b51), so roster parity is measured NOT SUFFICIENT with
   ours-content present.  It is the first pre-committed lane of the
   BX_v3-FAIL branch (§5).
3. **Unit content authorship** — born vs authored.  Not authorable by
   definition; this is the residual axis T1uG and TB0g split.

New species datum from the build (recorded in the census): the
**embedded-born famdoc carries an EMPTY unit-side type table** (types
live host-side; TB0r/TB0g pairs `[]`, m_idx −1) while the
standalone-born species — and ours — carry the blank-pair-first table
in-unit (T2a `[' ', …]` m_idx 2; ours `[' ', '225A MLO 42ckt']` m_idx
1).  Our famdocs already sit on the standalone side of that axis.

---

## 2. birthright v3 (opt-in; v1/v2 surfaces unchanged)

`src/rvt/famgen/birthright.py`: `_V3_LANES = _V2_LANES + ("hostsym",)`.

* `apply_host_symbol_law(doc)` — POST-finalize, strips blank pairs from
  the famload-facing `doc.types` (recomputing `current_type`); the BAKED
  unit-side table keeps the born blank-pair-first form.  Build-refusing
  on drift (unfinalized doc, blank current type, unit table not
  blank-first, baked m_idx on a blank).
* `apply_host_family_table_law(el)` — the famgen-loader half: on an
  authored host Family element, drops blank-named rows copied from the
  unit table, keeping the loader's own single leading blank; m_idx on
  the first real pair (the native `[' ', 'Notch']` m_idx-1 shape).
* `apply_birthright_v3(doc, spec)` — the full v2 pipeline (roster /
  topology / types / re-finalize / fields+indices) then hostsym.
* `enabled(spec, binds=…, version=3)` — routes products through v3 AND
  live-patches `rvt.famgen.loader.author_host_family` for the with-block
  (corpus_symbol_form precedent; restored on exit; reports in the
  yielded dict's `hostsym_loader`).  `version=2` (default) is
  byte-for-byte the previous behavior — SC1/DEMO v8 reproducibility
  untouched.

The lane is **subtractive-only** (test-enforced): it never adds a value,
so v2's zero-donor line carries over verbatim.  What v3 deliberately
does NOT change, each with its measured reason: the registered
ADocument form (§1.1 — the only reduced-base PASS ships the current
authored form; the born wrapper failed as U16g), the id policy
(current-id — both sides register wm+1..), the roster (T1v insufficiency
— §1.2 rank 2).

## 3. The probes (all gates green; `experiments/species/accounting.json`)

| probe | one thing it tests | vs | md5 | ids (sym/fam/inst) |
|---|---|---|---|---|
| **T1uG** | T1u's byte-identical famdoc (standalone shell + our 35, famdoc_final machinery, born-ADocument wrapper) on **G_ABPD** | T1u (PASS, rst) — pure base axis; T1v (FAIL, G_ABPD) — the machinery/wrapper/offset form | `de51f469d7a99b5f0e3acb4ba6d643d9` | 1474588 / 1474565 / 1474589 |
| **TB0g** | TB0r's byte-identical embedded-born famdoc on **G_ABPD** | TB0r (PASS, rst) — pure base axis | `dab626e2ba53a5e65ebab934d2a5f261` | 1472945 / 1472939 / 1472946 |
| **BX_v3** | our famdoc through birthright v3 (famload lane) on G_ABPD | SC1 (FAIL) — **single registered surface: the host symbol table** | `832463fd2c6fcbd9440946b28ccd1fcc` | 1474266 / 1474249 / 1474267 |
| **DEMO_250v_room_v9** | the user's exact prompt through v3 (frontdoor lane) | DEMO v8 (FAIL) — the loader-half hostsym repair | `885d5e0add335fc85b92657ef28f3cb2` | 6 families × 1,724-record units, 6 instances |

Per-probe evidence, machine-verified at build (gates refuse otherwise):

* **T1uG** — segments 101/102/103 byte-equal to `T1u.rvt` unit
  `7218d5e4…` (session hex pinned fresh→`8217b592…`, U16's, 14
  substitutions — T1u's own pin); famload reproduced T1u's exact rst
  host allocation on G_ABPD (1474588/1474565/1474589); the swapped born
  ADocument equals T1u's shipped entry modulo exactly the four history
  identity GUIDs; references **31,054/31,054 in-unit** (the same
  fully-self-contained figure as T2a — our content rides fully
  self-contained inside the standalone shell); validator 0; blob nonce
  verified.
* **TB0g** — segments byte-equal to `TB0r.rvt` unit `54c84546…` with NO
  pinning (the three `revit.local.family:` strings are the DONOR's own
  and ride verbatim — measured, hex sets equal); refs 6,189 typed / 32
  host-resident / 0 unresolved (the embedded species' signature, cf.
  U16g's 29); validator 0; blob nonce verified.
* **BX_v3** — hostsym applied (doc.types `[' ', '225A MLO 42ckt']` →
  `['225A MLO 42ckt']`; unit table KEPT blank-pair-first m_idx 1);
  famload plan type_names non-blank; **unit class histogram IDENTICAL to
  SC1's; host-side delta exactly {FamSymSurrogate −1 blank, FamilySymbol
  −1} + the instance binding** (measured, §7 of cd_forensics + this
  build); four-surface census 0 host-resident, walked binds in-unit;
  authored-vs-mined verify 0 mismatches; same spec sha + binds as SC1
  (test-pinned); species census green.
* **DEMO v9** — 6 families, hostsym product-half applied ×6, loader-half
  applied ×6 (each dropped exactly 1 blank row); host Family tables now
  `[' ', '225A MLO 42ckt']` m_idx 1 (native shape; v8 shipped
  `[' ', ' ', …]` m_idx-on-blank); PP- symbol form asserted ×6;
  four-surface self-contained; validator 0; front-door status PROOF-ONLY
  (self-checks PASS).  Walls: 0 — the known intent-grammar regression,
  still open, not this territory (third consecutive flag).

Gate summary (all four): validator 0 errors / 0 unexpected, four-registry
coherent, +1 unit on the load hop / +0 on the instance hop (loaders),
survivor law, identity PASS, every unit blob-carrying with OUR
deterministic nonce on the added unit, instance 0 dangling; byte-identity
REQUIRED for T1uG/TB0g; species census REQUIRED for BX_v3/v9.

## 4. Declared deviation (TB0g's famdoc source)

The charter named "TB0's embedded-born famdoc verbatim".  Measured:
racadvanced's watermark is **438,567** vs G_ABPD's **1,472,524** — TB0's
rebased famdoc ids (438,568..438,948) alias LIVE G_ABPD host ids, so a
byte-identical transplant from that host is arithmetically impossible.
TB0g therefore carries **TB0r's famdoc** (rst unit 41, M_Pile-Steel Pipe,
414 records): the same embedded-born species, on the watermark-equal host
(rst wm == G_ABPD wm — the b52 transplant law), whose TB0r cell is the
certified PASS baseline, making TB0g a pure single-variable base swap.
The species cell the charter wanted (embedded-born × reduced) is filled
exactly; only the specimen changed, for a measured mechanical reason.

## 5. The staged round + the decision table

**Batch 54** (`experiments/acceptance/batch_54.json`), staged via
probe_batch primitives, md5s re-verified, one control
(`CTRL_G_ABPD_b54.rvt`, byte-identical certified G_ABPD).  Reading
order: **T1uG, TB0g, BX_v3, DEMO_250v_room_v9.**

Decision table pre-committed in full in
`experiments/species/probes.json` `reading_the_matrix`; headline rows:

* **T1uG PASS + BX_v3 PASS + v9 PASS** ⇒ THE CLOSE: the standalone
  species shape is the law on reduced bases, our content is fine inside
  it, v3 authors it — promote v3 to the famgen emission default,
  rebuild acceptance.
* **T1uG PASS + BX_v3 FAIL** ⇒ v3 authoring gap — re-run the forensic
  instrument on the (T1uG, BX_v3) pair; pre-identified candidates in
  order: (1) the born-roster true-up (+268 layer incl. the
  loaded-family block), (2) the born-wrapper ADocument (authored
  registries + independent identity + build strings, zero donor).
* **T1uG FAIL + TB0g PASS** ⇒ CONTENT BIRTH is the axis (reduced bases
  accept only fully-born unit content) — no famdoc-side authoring
  closes it; route to the compose-side repair (hr1 rank 1) + the
  desktop-Revit kit.
* **T1uG FAIL + TB0g FAIL** ⇒ the acceptance boundary is the T2a bytes
  themselves — suspicion moves to the reduced base's registration
  substrate; compose territory + escalation.
* Control FAIL voids the round.

## 6. Findings for other streams (not this territory)

* **famgen loader (shared famgen)**: `author_host_family` authors a
  DOUBLE-blank host type table whenever the unit table is
  blank-pair-first (v2 or any born-shaped doc) — m_idx lands on a blank.
  v3's opt-in patch fixes it inside the with-block only; if any verdict
  confirms the hostsym lane, the loader deserves the fix product-side
  (one-line: skip blank-named pairs when copying).
* **famload**: authors one host symbol pair per `doc.types` entry
  including blanks — same product-side candidate after verdicts.
* **front door**: the demo prompt still derives 0 walls (v3 had 4) —
  the previously-flagged grammar regression stands (third flag).
* **rft-probes stream**: the embedded-born empty-unit-type-table datum
  (§1.2 tail) belongs in the species notes of the .rft reader (its
  species finding hook already flags populated inline tables; the
  empty-table side is now measured too).

## 7. Reproduction (repo root, `.venv/bin/python`)

```
tools/species_probe.py forensics    # cd_forensics.json (0.7 s)
tools/species_probe.py build        # T1uG, TB0g, BX_v3, DEMO v9 + gates
tools/species_probe.py census FILE [--born]   # the species-shape gate
tools/species_probe.py verify       # re-run gates from accounting
tools/species_probe.py stage        # batch (G_ABPD control, md5-verified)
.venv/bin/python -m pytest tests/test_species.py -q   # 36 passed
```

## BRANCH STATE

* No VCS (working tree only).  Territory files written:
  `tools/species_probe.py` (new), `src/rvt/famgen/birthright.py` (v3
  appended: `apply_host_symbol_law`, `apply_host_family_table_law`,
  `apply_birthright_v3`, `_V3_LANES`, `HOST_SYMBOL_LAW`; `enabled` gains
  the optional `version=` kw, default 2 = previous behavior byte-for-
  byte), `tests/test_species.py` (new, 36 passing),
  `experiments/species/**` (4 probes + cd_forensics.json +
  accounting.json + probes.json + _build/), staging copies + manifest
  `experiments/acceptance/batch_54.json`, this record.  Plugin re-synced
  (`tools/sync_plugin.py`) after the birthright edit.
* Targeted suites: test_species 36 + test_birthright 19 +
  test_selfcontained 24 + test_union_reconcile 20 + test_rft_probe 24 +
  test_plugin_sync 7 — all passing.  NO full-suite run (charter).
* T1uG + TB0g embed vendor-born / Autodesk-sample content — PROOF-ONLY,
  quarantined under `experiments/`; BX_v3 + DEMO v9 carry zero donor
  bytes (same spec+binds as SC1, sha-pinned; the v3 lane is
  subtractive-only, test-enforced).  Zero donors in anything shipped.
* **Batch 54 is STAGED, gates green, md5-verified.  NOT uploaded — the
  orchestrator uploads (stage-only law).  STOP at READY.**
