# rft-probes — THE BIRTH-STATE PROBE LADDER (2026-08-05)

THE LEAD (the user's field testers, career Revit users): desktop Revit
cannot create a family EXCEPT from an `.rft` template — every genuine
famdoc is BORN with template inheritance.  That maps exactly onto the
campaign's terminal finding (genesis-audit verdicts #36–#42): a
donor-DERIVED famdoc reduced to our exact content PASSES the instance
audit (SUB_ALL), our from-scratch assembly FAILS (BX_conj, all 12 corpus
separators flipped).  The audit checks something inherited AT BIRTH that
no content diff exposed — and the birth-state is unmeasured (we have
never seen an `.rft`).  This stream builds the ladder that measures it.

Tool: `tools/rft_probe.py` (poll / census / build / verify / stage /
selftest).  Module: `src/rvt/famgen/birthright.py` (opt-in).  Tests:
`tests/test_rft_probe.py` (24, all passing).  Decision table:
`experiments/rftprobe/probes.json`.

## STAGED (awaiting viewer)

**Batch 49** (`experiments/acceptance/batch_49.json`) — controls FIRST
(racadvanced sample, rst sample, G_ABPD), then:

- **TB0** — the corpus-smallest MODEL-instanceable Autodesk-born famdoc
  (M_RPC Female, racadvanced unit 33, 381 records) famload-loaded into
  its OWN host + one uniform template instance (the H7/B7 recipe).  New
  vs certified B7: the famdoc + the host.
- **TB0r** — the smallest model-instanceable famdoc of rst basic itself
  (M_Pile-Steel Pipe, unit 41, 414 records) through B7's exact
  host+path.  SINGLE-VARIABLE famdoc swap against certified B7 (the
  417-record column).
- **T0** — OUR famgen famdoc (PP-1) via famload + uniform template
  instance on G_ABPD.  The T-ladder's FAIL anchor (H8B lineage
  transplanted to this ladder's base+path); the exact substrate T3
  augments.

**Batch 50** (`experiments/acceptance/batch_50.json`) — G_ABPD control +

- **T2a** — T2's dress rehearsal: the **Revit-BORN standalone .rfa**
  famdoc (vendor `racbasicsamplefamily-2026.rfa`, 1,992 elements)
  UNMODIFIED via famload + one instance on G_ABPD.  Provenance measured:
  Autodesk build string `20250227_1515(x64)E`, a real user save path,
  64-byte unit blob — a genuine desktop-Revit-saved family file.  The
  ONE thing vs T0: the famdoc is BORN.

All probes: validator 0 unexpected errors, coherent four-registry
census, survivor law OK, every unit blob-carrying with the ADDED unit's
blob byte-matching OUR deterministic nonce (machine-verified), instance
references fully resolved.  Reading table in probes.json; headline:

- T2a PASS ⇒ birth-inheritance extends to standalone-born bodies on
  G_ABPD; the T2 pipeline is fully proven before any `.rft` is spent.
- TB0r FAIL ⇒ REOPENS machinery (single variable vs certified B7).
- T0 PASS would be a SURPRISE that re-frames the campaign (our famdoc
  passing famload+template placement on G_ABPD while failing B0/H8B).

## WAITING ON the acquire stream (poll wired)

- `samples/rft/*.rft` → unlocks **T2** (template famdoc unmodified +
  famload + instance on G_ABPD — the pure-birth control, the `.rft`
  equivalent of H7) and **T1** (THE DECISION RUNG: template-born SHELL +
  our 35-element content union registered in the template self-Family —
  famdoc_final's U16 add-form with the template body as the donor).
  `build` auto-detects; `--rft PATH` overrides; electrical templates
  preferred (matches our panelboard content's category — wishlist:
  **Metric Electrical Equipment.rft** first, then Generic Model).
- `experiments/rft/template_birth.json` → unlocks **T3** (our famdoc +
  birthright-AUTHORED birth features, zero donor bytes).  The input
  CONTRACT is documented in `src/rvt/famgen/birthright.py` (tolerant
  parse; minimum viable = the template famdoc's `class_histogram`;
  highest-value extras = `self_family_fields` + `self_family_header` —
  the SUB_ALL/F1 16-record residue lives in the self-Family record +
  header — and `layout`).

The T2/T1 plumbing is PROVEN END-TO-END without an .rft: `selftest`
emits OUR own famgen famdoc as a standalone .rfa (zero donor), reads it
back through the exact .rft reader (41/41 roster + owner roundtrip),
famloads onto G_ABPD, places an instance — validator 0, blobs verified
(`experiments/rftprobe/selftest.json`).  When the .rft lands, the only
untested surface is the .rft species itself.

## MEASURED FINDINGS (this session)

1. **The annotation confound** (`experiments/rftprobe/corpus_census.json`,
   511 famdocs): the corpus's absolutely smallest famdocs (199–233
   records: diffuser tags, view titles, grid heads) are annotation
   families whose native "instances" are `IndependentTag` elements or
   VIEW-OWNED FamilyInstances (`m_ownerDBViewId` set, no level/phase).
   The proven placement path produces the level+phase MODEL form — an
   annotation-symbol instance through it would be a shape no native file
   exhibits (a confound, not a datum).  TB0 is therefore the smallest
   famdoc with MODEL-form native instances.  Follow-up proposed:
   view-owned placement grammar to reach the 199-record frontier.
2. **Standalone ownership law**: a standalone family file's
   `Global/Latest` ADocument carries an EMPTY `m_elemTable` (measured on
   the vendor-born .rfa AND our own v2-emitted .rfa); owner ids live in
   the `Global/ElemTable` STREAM.  Projects keep the embedded famdoc's
   owners in the inline ContentDocuments ADocument — the two species
   differ exactly there.  `load_rft_elements` reads the stream (and
   flags a populated ADocument table as a species finding).
3. **The small-id aliasing hazard** (would have corrupted every .rft
   probe): standalone-born famdocs use SMALL element ids (3..~2500 — a
   fresh document id space), so the proven blind int-walk rebase
   (`_walk_replace_ids`, sound for project-embedded donors at ~1.4M)
   aliases ordinary small integers — flags, enum values, weakref
   indices — into the id block.  First symptom: `GeomStepList.m_flags`
   encode overflow.  Fix shipped in the tool: a **schema-TYPED
   decode-time remap** (the validator's `_RefDecoder` hook) that
   substitutes exactly the values the schema types as ElementId.
   Embedded-donor rungs (TB0/TB0r) keep the proven blind walk.
4. **Blank-pair host symbol**: the born famdoc's type table opens with
   the corpus blank pair `' '` (types5 law confirmed on a standalone
   file); naming the famload HOST symbol after it would author a
   `' '`-named FamilySymbol — a shape no native host exhibits.  The
   tool picks the first NON-BLANK type name (`0610 x 0160mm`).
5. **What birth looks like** (prior for birthright): the Revit-saved
   standalone famdoc carries the FULL style catalog at birth — 1,477
   GStyleElem + 70 CategoryElem + materials/appearance assets/fonts/line
   patterns in 1,992 elements.  If `.rft` templates look the same, the
   birth roster is dominated by the catalog layer, which the genesis
   constructors already author project-side.  NOTE against over-reading:
   SUB_ALL proved the audit does NOT require those elements PRESENT in
   an embedded famdoc — the birth question is what their DERIVATION
   leaves behind (self-Family/header residues, layout), which is why
   birthright's `fields` lane exists.

## birthright (the product-fix scaffold, opt-in)

`src/rvt/famgen/birthright.py`: `read_birth_spec` (tolerant contract
parse) → `birth_delta` (roster diff + self-Family field/header deltas +
authorable/unauthorable split) → `apply_birthright` (three lanes: roster
via the CONSTRUCTORS registry — EMPTY in v1 on purpose, the unauthorable
list IS the author spec; fields via adopt-or-author — the zero-donor
line `adoptable()` adopts laws/shapes (enums, counters, flags, ids) and
AUTHORS equivalents for identity/content (GUIDs → fresh uuid4, long
strings, blobs); layout reserved for `layout_law`).  T3 refuses — writing
`experiments/rftprobe/birthright_author_spec.json` — rather than fake an
unauthorable birth set.

## DEVIATIONS from charter (declared)

- TB0 is 381 records (M_RPC Female), not the absolute smallest famdoc
  (199) — the smaller ones are unreachable without the unproven
  view-owned instance form (finding #1).  The census records the whole
  frontier; TB0r added as the tight single-variable pair vs B7.
- T0 and T2a added beyond the charter's T1/T2/T3/TB0 — T0 anchors the
  T-ladder (every T-rung differs from it by one thing), T2a converts
  dead waiting time into a staged birth datum.

## BRANCH STATE

- Working tree only (no git repo).  Territory files:
  `tools/rft_probe.py`, `src/rvt/famgen/birthright.py`,
  `tests/test_rft_probe.py` (24 passing), `docs/inbox/rft-probes.md`,
  `experiments/rftprobe/**` (probes + census + selftest + accounting +
  probes.json), staged copies + manifests `experiments/acceptance/
  batch_49.json` (TB0, TB0r, T0 + 3 controls) and `batch_50.json` (T2a
  + G_ABPD control).
- Nothing shipped; all donor-embedding probes quarantined under
  `experiments/`.  No shared files edited (famdoc_bisect/blobs/final
  imported with output dirs repointed).
- NEXT (any session): run `poll`; when `samples/rft/` lands → `build
  --only T2,T1` then `stage --only T2,T1`; when `template_birth.json`
  lands → `build --only T3` (or read the refusal's author spec, register
  constructors, rebuild).  After viewer verdicts: record in probes.json
  order TB0 → TB0r → T0 → T2a → T2 → T1 → T3 against
  `reading_the_matrix`.
