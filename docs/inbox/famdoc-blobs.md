# famdoc-blobs — THE FAMDOC BISECTION RE-RUN WITH BLOBS (staged, batch 44)

Stream: **famdoc-blobs** (2026-08-05).  Charter: verdicts #36/#37 ended the
presence hunt (the audit requires the 64-byte `0x0f3f` unit footer blob to
be PRESENT on any instanced unit — content NOT verified, E1b random blob
passes) and voided batch 37's famdoc hybrid bisection for content
attribution (every hybrid carried an EMPTY blob, which alone fails any
instanced unit).  DEMO v5 — our famdoc content WITH blobs — still FAILS,
so the blob is necessary, not sufficient.  This stream REBUILDS the
bisection ladder through the FIXED writer, machine-verifies the blob on
every emitted unit, and stages it: whichever hybrid FAILS with a blob
names our guilty famdoc subtree.

**Territory touched ONLY:** `tools/famdoc_blobs.py` (new),
`experiments/famdoc_blobs/**` (new), `tests/test_famdoc_blobs.py` (new),
this record, and the staging copies `probe_batch` itself writes under
`experiments/acceptance/` (batch manifest + probes + controls — its
designed output).  `tools/famdoc_bisect.py` is IMPORTED with its output
dirs repointed into this stream's territory (module attrs only — the file
and the famdoc-bisect stream's emitted evidence are untouched; no
cross-voice writes).  No `src/**` edits.  No browser (STAGE only — the
orchestrator uploads); no Autodesk install dirs; zero donors in shipped
output (every probe PROOF-ONLY, quarantined); no full-suite runs
(SUITE-COORDINATION; canonical 1697/7/2 adopted).

## Result in one screen

* **THE BLOB-CARRYING LADDER IS BUILT, GATED AND STAGED AS BATCH 44** —
  8 probes (B7 + B0 + B1..B6), every one `rvt.validate` **VALID 0 errors /
  0 unexpected**, four-registry **coherent** (+1/+1/+1/+1 per load hop,
  instance hop registry-silent), survivor law **0 removed / 0 modified**,
  identity gate **PASS**, and — the round's ONE new gate — **every save
  unit of every probe and every intermediate load file carries the 64-byte
  `0x0f3f` blob** (B7/B1..B6: 54/54 units; B0: 2/2), with the ADDED unit's
  blob **byte-matching our deterministic nonce** recomputed independently
  from the unit's own seq-102 segment (`famdoc_adoc.build_footer` — sha512
  of our identity material, ZERO donor bytes).
* **The batch-37 voider is measured, not assumed**: the old
  `experiments/famdoc_bisect/H7.rvt` raw-scans as 53×64 B native + **our
  unit 0 B** — exactly the verdict-#36 failure condition; the rebuilt B7
  scans 54×64 B.  DEMO v5 was re-measured too: **all 7 units carry 64-B
  blobs and it still FAILED** — confirming the reframe this ladder tests.
* **Two controls, one batch** (the B0 rung lives on a different certified
  base): `CTRL_rstbasicsampleproject_b44` (md5 `b3235ad2…`, byte-identical
  untouched rst sample — gates B7/B1..B6) + `CTRL_G_ABPD_b44` (md5
  `1f1ff65b…`, byte-identical certified G_ABPD — gates B0).  Both
  md5-verified against their sources; every staged probe copy md5-verified
  against the manifest.  Batch number 44 — chosen collision-proof (the
  orchestrator's v5 round staged `CTRL_G_ABPD_b43` WITHOUT a
  `batch_43.json`, so the manifest-scanning counter alone would have
  reused 43; `tools/famdoc_blobs.next_batch_number` also scans staged
  `_b<n>` file tags).
* **B0 is the product-shape anchor the charter asked for**: the BXhf_f1i1
  recipe verbatim through the fixed writer — G_ABPD + ONE famgen
  panelboard family (the demo's PP-1, `famload_hostfix.corpus_symbol_form`)
  + ONE instance (product `FamilyInstanceConnectorManager`, read back from
  the emitted bytes), symbol-form gate re-asserted, 0 dangling refs.
* **Both loaders were confirmed to ride the fixed writer** before any
  build: `rvt.famload` (line 1166) and `rvt.famgen.loader` (line 1442)
  each call `factory.build_family_save_unit`, which now emits the nonce;
  the H6 adoc-swap path touches only `Global/ContentDocuments` (the
  partition unit rides through untouched — verified by the census).  No
  hybrid path splices raw unit bytes past the writer; the per-unit
  raw-scan + nonce equality is the machine proof, not an assumption.

## §1  The ladder (staged reading order = maximum information first)

All probes `experiments/famdoc_blobs/<rung>.rvt`, staged byte-identical to
`experiments/acceptance/`; manifest `experiments/acceptance/batch_44.json`.
Fresh GUIDs are minted per rebuild — re-hash after any rerun.

| # | rung | md5 | recipe (rebuilds) | the ONE thing it tests |
|--:|---|---|---|---|
| 1 | **B7** | `dd55928f` | batch-37 H7 | control-A **with blob**: the Autodesk column famdoc (id-rebased only) through famload + template instance.  E1b's law says presence is all the audit checks → **expected PASS**; batch 37's H7 FAIL is attributed to its empty blob |
| 2 | **B0** | `8e1bd459` | BXhf_f1i1 (b39) | control-B **with blob**: the PRODUCT shape — G_ABPD + ONE famgen family + ONE instance.  The product verdict rung |
| 3 | **B1** | `760a7332` | H1 | our GEOMETRY subtree (+7 elems: extrusion, sketch, 4 curves, plane).  Prime prior: `m_geomSteps`/`m_pGeomTable` differ on our OWN form elements (famdoc_diff.json) |
| 4 | **B2** | `68606f3a` | H2 | our PARAM/TYPE layer (+14 ParamElemFamily + four-surface rows) |
| 5 | **B3** | `7da3f9ab` | H3 | our REFERENCE/DATUM layer (+4) |
| 6 | **B4** | `329218c4` | H4 | our VIEW constellation (+8) |
| 7 | **B5** | `8b29d493` | H5 | our CONNECTOR layer (+3 incl. the apparent-load param) |
| 8 | **B6** | `e6a5495c` | H6 | control-A with the donor's OWN inline ADocument carried (131 populated registries; partition unit byte-identical in length to B7's) |

Element counts read back from the builds pin the axis multisets: 417
(B7/B6), 424/431/421/425/420 (B1/B2/B3/B4/B5) — donor + exactly the
declared axis set, same recipes as batch 37 (the hybrid machinery is
famdoc_bisect's own, imported).

**Reading the matrix** (full text in `probes.json → reading_the_matrix`):
either CTRL FAIL → its probes VOID.  **B7 PASS** → famload machinery
(authored host flavour + re-encode + rebase + registration) lawful WITH
the blob; B1..B6 carry clean one-axis content information; each Bn FAIL
independently convicts that axis (fix order B1 > B2 > B3 > B5 > B4; fix
spec = famdoc_diff.json's ranked entries).  **B7 FAIL** → even
blob-carrying, famload's own treatment poisons a lawful famdoc: B1..B6
content reads VOID; since the E-round proved the H12 byte-copy machinery
+ blob passes, the suspect space is exactly the delta famload authors vs
H12's byte-copies; B0 still reads alone (different loader).  **B0 PASS**
→ the product shape passes with the blob: rebuild DEMO v6 through
`tools/frontdoor.py` with the user's exact prompt, machine-verify blobs,
stage — v6 PASS closes the hunt; v6 FAIL localises to demo-scale
composition (multi-family/walls/feeders), bisected next by the demo's own
stages.  **B0 FAIL + B7 PASS + B1..B6 ALL PASS** → the defect lives in
what only B0 carries: whole-document composition (S0 skeleton, ordering,
registry singletons), the famgen-loader flavour (B0 is the only
famgen-loader rung), or an axis interaction — next ladder: our famdoc
through famload on rst (old H8 + blob) to split loader vs content, then
pairwise unions / inverse bisection.

## §2  The blob gate (machine, per file — the round's admission ticket)

Per probe AND its immediate parent (the load file / H6's adoc-swapped
file), `tools/famdoc_blobs.blob_proof`:

1. **Census**: walk every `Partitions/*` logical stream
   (`rvt.partitions.StreamWalker`); every unit's `0x0f3f` blob must be
   exactly 64 B (histogram recorded; any 0-length = build refusal — the
   verdict-#36 voiding condition).
2. **Added-unit identification** by GUID diff vs the probe's declared
   base (exactly ONE added unit per probe — also gated).
3. **Nonce equality**: rebuild the added unit's seq-102 segment from the
   walker's own inflated blocks and require
   `build_footer(guid, payload=seg102) == footer_blob` byte-for-byte —
   proving the blob came from OUR fixed writer (deterministic sha512 of
   product salt + unit GUID + payload digest; zero donor bytes), not from
   a stale splice or a donor copy.  Measured seg-102 sizes: B7/B6
   224,670 B, B1 229,942, B2 237,630, B3 227,385, B4 229,793, B5 227,000,
   B0 29,838.

`tests/test_famdoc_blobs.py` re-derives the census + nonce INDEPENDENTLY
(its own walker loop, not the tool's function) for all 8 probes.

## §3  Gates (all machine, per probe; no acceptance claim)

* `rvt.validate` **0 errors / 0 unexpected** (current validator incl. the
  loaded-content rules; 1 warning = the standing inherited
  RebarShape/DataStorage decoder gap present in the untouched sample).
* Four-registry census coherent; load hop +1/+1/+1/+1; instance hop
  registry-silent; survivor law 0/0 on both hops; identity gate PASS.
* Blob gate (§2) on probe + parent; added units = 1; nonce verified.
* Hybrids: schema-typed reference resolution **unresolved-anywhere = 0**
  (famdoc_bisect's dev-rfa RefDecoder pass, build-refusing).  B0:
  corpus-lawful symbol form re-asserted (`famload_hostfix
  .assert_symbol_form`), 0 dangling instance refs, product connector
  manager read back from the emitted bytes.
* Staging: `probe_batch` gate (bases resolve: rst → `sample`, G_ABPD →
  `certified`), TWO byte-identical controls, every staged copy
  md5-verified.

## §4  Honest limits

* B7 with a blob is E1's mechanism-question asked of the FAMLOAD flavour
  (E1/E1b rode H12's byte-copy machinery); a B7 FAIL would therefore be
  new information, not a contradiction of E1b.
* An axis PASS exonerates that subtree in ADD-form only (grammar
  lawfulness on a donor body); a defect requiring our subtree to be the
  document's SOLE content surfaces in B0 but not the hybrid — the
  pre-branched all-pass reading covers it.
* B0 rides the famgen loader on G_ABPD while B1..B7 ride famload on rst —
  deliberate (B0 is the product anchor), and the matrix reads the loader
  split explicitly (§1).
* The donor-path constants recorded for batch 37 carry over unchanged
  (famload twins every ParamElemFamily incl. the nested level-head
  'Radius'; donor resource refs resolve host-side; hybrids are
  project-hosted documents, dev `.rfa`s evidence-only).

## §5  Verification (how to re-run)

```
.venv/bin/python tools/famdoc_blobs.py build              # all 8 probes (~6.5 min)
.venv/bin/python tools/famdoc_blobs.py build --only B7,B0
.venv/bin/python tools/famdoc_blobs.py verify             # re-run every gate
.venv/bin/python tools/famdoc_blobs.py stage              # probe_batch + 2 controls
.venv/bin/python -m pytest tests/test_famdoc_blobs.py -q
```

Stream-local tests: **32 passed** — footer determinism/uniqueness, the
factory-source regression pin (build_family_save_unit must call
build_footer), per-probe independent census + nonce (8), gate greenness
(8), axis element counts (7), B0 recipe pins, B6 adoc-swap pin (131
populated slots), probes.json order/bases/md5s, decision-table branch
coverage, no stale `_h` manifest, staged-batch two-control + md5 pins.
Full suite: NOT run (SUITE-COORDINATION hard rule).

## BRANCH STATE

* **status: DONE — BLOB-CARRYING LADDER BUILT, GATED, STAGED (batch 44)
  WITH PER-PROBE BLOB PROOF + THE DECISION TABLE.**  STOPPED AT READY:
  nothing uploaded; the viewer queue is the orchestrator's.
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/famdoc_blobs.py` (new, ~740 lines; build/verify/stage),
  `tests/test_famdoc_blobs.py` (new, 32 pass),
  `experiments/famdoc_blobs/` {B7,B0,B1..B6}.rvt (md5s in §1),
  probes.json (decision table + per-probe blob proof), accounting.json
  (full gates incl. blob_proof per probe AND parent), `_build/B0_chain/**`
  (B0's famgen chain), `_h/_build/**` (the repointed famdoc_bisect
  per-rung evidence: load files, hybrid reports, dev rfas)}, this record,
  staging copies + `batch_44.json` + `CTRL_rstbasicsampleproject_b44.rvt`
  + `CTRL_G_ABPD_b44.rvt` under `experiments/acceptance/`.
* **gates**: every probe validator VALID 0/0, four-registry coherent,
  survivor 0/0, identity PASS, refs 0 unresolved-anywhere, **blob census
  64 B on every unit of every probe + parent, added-unit nonce
  byte-verified**, probe_batch ADMISSIBLE, both controls + all staged
  copies md5-verified.  `verify` re-run post-stage: 8/8 gates_ok.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (B1..B7
  sample-derived, quarantined, never bundled; B0 is G_ABPD-based product
  content but stays in the dev lane until certified).
* **next action (orchestrator)**: upload batch 44 in manifest order
  (both CTRLs first, then B7, B0, B1..B6), verdicts to
  `docs/coverage/viewer-certified.json`, read with `probes.json →
  reading_the_matrix`.  On **B0 PASS** this stream's standing follow-up
  applies: DEMO v6 via `tools/frontdoor.py author` with the user's exact
  prompt ("an electrical room rated for 250V with 6 panels"), blob-verify
  all units (`tools/famdoc_blobs.unit_footer_census`), stage for
  acceptance.  On an axis FAIL the fix spec starts at
  `experiments/famdoc_bisect/famdoc_diff.json`'s ranked entries for that
  axis.
