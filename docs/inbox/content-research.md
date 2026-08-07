# Inbox: content-sourcing research → strategy

## Pass 2 (2026-08-03, second synthesis) — supersedes the strategy body

`docs/product/content-strategy.md` was rewritten. What changed vs. pass 1:

- **Electrical-distribution majors now covered** (Eaton, Schneider/Square D + LayoutFAST, Siemens
  BIMPOWER, ABB Electrification US, Legrand NA, Hubbell, Emerson/Appleton via CADENAS, nVent) —
  matrix rows 2–9. Headline: every website ToU is restrictive by default **but nearly all defer to
  per-download EULAs nobody has opened** (Eaton "Unless otherwise specified"; Siemens §4.1 switches
  off §§4.2–4.5 in favour of the App-Store/BIMPOWER EULA; Cooper §8 / Legrand / nVent carve-outs).
  The decisive documents are in-ZIP READMEs and product EULAs — unreadable by scraping; an
  authorized human must download and open them. New fact: **ABB terms version drift** (legacy
  terms at the same URL barred "commercial purposes"; which document governs the download host is
  unresolved).
- **Verifier corrections applied:** Focal Point *does* ban automated harvesting (row 15); RAB *does*
  have terms barring commercial use (row 18); Genlyte terms exist (Jan 2019, Signify template);
  Cooper §8 has an "Except as set forth in the applicable license agreement" lead-in; Finelite is a
  Legrand brand (parent terms unchecked); Hubbell says "express permission" not "written
  consent"; BIMobject §4.4(f) "Customer Contract" downgraded to speculative; BIMsmith/BIMobject
  downloaded-content redistribution downgraded to UNKNOWN (clauses govern the *Services*/site).
- **§1 verdict rewritten as conditional** and the doc now states the pass-1 critique's facts plainly:
  the shipping pipeline currently seeds from **Autodesk sample projects** (`seed.md`, rme 187/187
  Autodesk-authored symbols) — Tier A is aspirational until a cutover gate is met; and §5.1 is
  rebased on `docs/legal/provenance-memo.md` (Utility.dll analysis + independent math re-derivation
  + quarantine), including the §1201(a)(2)/(b) trafficking prong. Row 1 relabeled INFERRED (no
  "low risk"); Tier B and photometry-linking moved to UNKNOWN — NEEDS COUNSEL; ODA BimRv/APS
  downgraded to "candidate, terms unread"; Autodesk §8.1 marked cached-copy provenance.
- **New matrix rows / basis:** VA copyright policy caveat (Government may hold *assigned*
  copyrights — VA-hosted files not automatically free); GSA public-domain statement verified
  with its "determine for yourself" qualifier; USACE verified to have *no* license text anywhere;
  bSDD per-dictionary licensing; TM-32/LM-63 purchase licenses flagged UNREAD (all permissions
  INFERRED).

## Proposed new work (TRACKER) — pass 2 additions

1. ENG/OPS (P0) — **sample-seed cutover gate**: no deliverable ships while its element inventory
   contains any Autodesk-authored family; freeze/inventory what has shipped; hand to counsel.
2. LEGAL — extend the §5.1 brief with the §1201(a)(2)/(b) trafficking prong and the QA-seat
   privity fact; add "read ODA BimRv membership agreement + APS Automation-API terms."
3. HUMAN TASK (not automatable) — an authorized person downloads and opens: Eaton BIM ZIPs
   (README/EULA), Legrand/nVent/Hubbell/ABB/Signify family packages, Siemens BIMPOWER + Autodesk
   App Store EULA, Schneider LayoutFAST registration EULA, CADENAS PARTcommunity terms, BIMsmith
   Market EULA, MEPcontent registration terms, CSI EULA, IES webstore license, USAI Family User
   Guide. Record each verbatim.
4. RESEARCH — verbatim browser reads still owed: se.com ToU, Genlyte, RAB /legal, live Autodesk
   General Terms, bSDD per-dictionary licenses, GLDF MIT text; and re-verify BIMForum Part I vs
   Part II licenses + the PANYNJ ownership clause (verifier corrections not received in full).
5. RESEARCH — uncovered vendors (Vertiv, ASCO, Leviton, B-Line, Unistrut/Atkore, Legrand
   corporate; MODLAR, TraceParts, CADENAS, UNIFI, 3Dfindit) and owners (DoD UFC/UFGS, DDOT/DC
   public-works BIM standard, customer-side Revit EULA).

---

## Pass 1 record (retained)

The synthesized strategy is at `docs/product/content-strategy.md`. Orchestrator: fold these into
TRACKER.md / KNOWLEDGE.md.

Headline: no manufacturer/aggregator/public library grants a software vendor bundle/embed rights
in third-party family geometry (all verified terms are personal/non-commercial or own-project only;
silence = no permission). USACE UBOL is mixed-provenance (ARCAT copyright + Autodesk OOTB in its own
metadata) — NOT public-domain seed. Strategy = generate our own parametric families from
manufacturer *facts* (Feist), photometry linked not embedded, open standards (IFC/COBie/TM-32/GLDF)
for schema only, manufacturer .rfa only via customer download-on-demand, written mfr licenses as
the growth path.

Proposed new work (for TRACKER):
1. LEGAL — brief counsel on the two foundational risks: (a) our pure-Python .rvt/.rfa writer
   (RE/DMCA §1201(f)/EULA privity; evaluate ODA BimRv SDK or APS Automation API as replacements),
   (b) rename "rev-revit" (Autodesk mark in product name) before public launch.
2. ENG — provenance ledger + CI gate rejecting any untagged/third-party .rfa in our library.
3. ENG — spike ODA BimRv as the format layer in parallel with the legal review.
4. ENG — author the parametric master families (panelboard, switchboard, transformer,
   disconnect, breaker, troffer, downlight, conduit, tray, hangers, devices) with TM-32/COBie/IFC
   parameter mapping.
5. RESEARCH GAP — run the same terms audit on electrical-distribution manufacturer portals
   (Eaton, Schneider, Siemens, ABB/GE, Legrand, Leviton, Hubbell, B-Line, Unistrut, Atkore) plus
   MODLAR/CADENAS/TraceParts and MEPcontent's real terms; also CSI (MasterFormat/OmniClass) EULA
   scope for platforms. These were not covered by this pass.
6. RECONCILE — the "autodesk-licensing" and "family-formats" lens reports were absent from the
   synthesis input; reconcile §5.1 and §6 of the strategy against them when they land.

## Completeness critique

Adversarial read of `docs/product/content-strategy.md` against the verified research and the repo's
own inbox. Not legal advice. Four parts: (a) missing/unverified, (b) overconfidence, (c) what a
hostile Autodesk legal team seizes first, (d) one next research action per gap.

### (a) Missing or unverified sources / questions

- **The doc's Tier A premise is contradicted by the repo TODAY.** `docs/inbox/seed.md` shows the
  live pipeline seeding jobs from **Autodesk's own sample projects** (`rmebasicsampleproject.rvt`,
  `rstbasic`, `racbasic`) and cloning 187/187 Autodesk-authored family symbols out of them into the
  DDOT/Chicago-plenum deliverables. That is precisely the "ship/embed Autodesk sample content"
  constraint the strategy claims to honor. `genesis.md` (synthesize a valid .rvt from nothing) is
  research-stage, not shipping. So "GENERATE-OUR-OWN, ships day one" is an aspiration; the shipping
  reality is Autodesk-sample-derived. The strategy never states this gap or a cutover gate.
- **Format-knowledge provenance is not "unresolved" — it is documented.** `ecc-intel.md`: the CRCIO
  page-trailer was "recovered by disassembling the actual Autodesk binary" (`Utility.dll`), and the
  binary itself is checked into `docs/inbox/ecc-intel-Utility-2023_1_9.dll`. §5.1's hypothetical
  ("if rev-revit never accepts an Autodesk EULA and never uses Autodesk software/DLLs") is already
  falsified. The strategy must be re-based on the actual facts.
- **Electrical-distribution rights-holders — the product's core content — are entirely unassessed:**
  Eaton (the named DDOT/panelboard vendor), Schneider/Square D, Siemens, ABB/GE, Legrand,
  Leviton, Hubbell, Cooper B-Line, Unistrut, Atkore. All verified rows are lighting. The exec verdict
  generalizes lighting-mfr terms to switchgear vendors it never read.
- **The fact-extraction pipeline's own legal footprint is unaddressed.** Pipeline 2 reads cut sheets
  from the same sites whose ToU (Cree, Focal Point, CADdetails §11(i), NBS anti-mining, Acuity
  Collateral Policy) prohibit harvesting/downloading. "Facts are free" (Feist) does not answer
  "may we lawfully collect them from a site that bans automated collection." §5.5 gestures at
  this; §1 does not.
- **Open-standard rows 24–29 (IFC CC BY-ND, GLDF MIT, Penn State CC BY-SA, bSDD "FREE", LOD
  CC BY-NC) are labeled FOUND-IN-TERMS but their verification is not in the research handed to
  this critic** (input truncated at BIMForum). Treat as unverified until the verbatim reads are shown.
- **Verbatim reads still owed and now silently load-bearing:** Genlyte ToU (row 4), RAB /legal (row 8
  — cited as FOUND-IN-TERMS in the matrix while still summarizer-only), Focal Point harvesting
  clause, BIMobject §4.3, Autodesk General Terms (cached Feb-2024 copy; live page never read),
  Autodesk legacy LSA §2.1.1, BIMsmith Market EULA (bimsmith.com/eula.html), 3Dfindit, MEPcontent.
- **Untested legal theories the doc leans on without a source:** design patents / trade dress in
  fixture and enclosure *geometry* (Feist is a copyright case; it says nothing about a family that
  replicates a product's protected ornamental shape); compilation copyright in a manufacturer's
  catalog selection/arrangement; UK/EU database right (NBS is UK) if any customer or source is
  non-US; catalog numbers and "UL Listed"/NEMA marks as trademarks inside generated types.
- **ODA BimRv and APS are recommended as risk-collapsing without their terms being read.** ODA
  membership terms/cost/redistribution scope, ODA's own IP posture toward Autodesk, and the APS
  Automation-API-for-Revit terms and GA status are all UNKNOWN. A recommendation resting on
  unread terms is the doc's own anti-pattern.
- **Government coverage stops at USACE/VA/GSA/NAVFAC/PANYNJ.** Not researched: DoD UFC/UFGS BIM
  requirements, FAA, state DOTs, and the actual named customer owner (**DDOT / DC public-works BIM
  standard** for the bus-storage electrical rooms). CSI EULA scope unread (row 30 is UNKNOWN yet
  agency deliverables require it).
- **Customer-side EULA question never asked:** does the customer's own Autodesk agreement restrict
  opening/using project files not created by an Autodesk Offering, or third-party services that
  generate them? If yes, the risk lands on the customer we are selling to.
- **§1201 is analyzed only via the §1201(f) interoperability defense.** The trafficking prohibitions
  (§1201(a)(2)/(b)) and whether .rvt integrity/authenticity machinery (the CRCIO framing we
  reimplemented) constitutes a "technological measure" were not examined — and that is the prong a
  plaintiff pleads.

### (b) Claims stated more confidently than the evidence supports

- **The one-word verdict "Yes"** (§1) sits above two risks the same doc rates HIGH and
  *foundational* (format legality, product name) and above a Tier A that does not yet exist. The
  honest verdict is "not currently; achievable via own-authored generation once §5.1/§5.3 clear
  and the pipeline is off Autodesk sample seeds."
- **Row 1 "USE/BUNDLE/EMBED = YES … low risk."** Every other cell is FOUND-IN-TERMS or UNKNOWN;
  row 1 is a legal conclusion (Feist inference) presented as a matrix fact. Copyright is only one
  claim; design patent, trade dress, trademark-in-type-names, and how the facts were collected are
  all unassessed. "Low risk" is unearned.
- **Feist is overextended.** "Facts are not copyrightable, so a family … may lawfully *describe*
  an Eaton panelboard" converts a compilation-copyright holding into a clearance opinion on
  product geometry. INFERRED, and stated flatly in §1.
- **Tier B is the doc's own silence-as-permission error.** §3 says download-on-demand "keeps *us*
  outside every 'no redistribution' clause because we never possess the bytes." The EULAs are
  *silent* on a vendor tool that generates the placeholder, produces the procurement manifest,
  drives the customer to the download, then auto-swaps and remaps the file. The doc treats that
  silence as safe harbor while asserting everywhere else that silence is not permission.
  Inducement/contributory exposure is deferred to a §5.2 footnote; the exec verdict states Tier B
  as clear. It is UNKNOWN — NEEDS COUNSEL, same as every other silence.
- **"Photometry: LINK, don't embed" is presented as clean.** Verified terms cut against it: Cree
  bars even *linking* to its pages; Focal Point bars deep-linking/harvesting; RAB bars *any
  commercial use* of RAB Lighting Information — a link our commercial product writes into a
  deliverable pointing at their IES is plausibly commercial use. "Linked" ≠ "outside their terms."
- **"We are not a subscriber" (row 17)** is asserted as fact. If any engineer/QA seat runs licensed
  Revit to validate our output (the doc says deliverables are "opened in a licensed Revit seat for
  final QA"), the entity is a bound Autodesk licensee — the exact privity fact §5.1 needs and states
  as open.
- **ODA BimRv "may collapse this entire HIGH risk"** — stated as a strong recommendation on zero
  read of ODA's terms. Downgrade to "candidate; read the membership agreement first."
- **Autodesk §8.1 is cited in the matrix as FOUND-IN-TERMS** but was verified only against a
  cached Feb-2024 copy; the live terms were never fetched. Mark cached-copy provenance in the cell.
- **"Nominative fair use likely covers" mfr names** — no source, no case cited, and a full
  vendor-branded content library is exactly where nominative use gets tested. Flag as INFERRED.

### (c) What a hostile Autodesk legal team seizes on first (ranked)

1. **The repo is the exhibit.** `docs/inbox/ecc-intel-Utility-2023_1_9.dll` (Autodesk's shipped
   binary) plus `ecc-intel.md`'s admission the framing was "recovered by disassembling the actual
   Autodesk binary" and `ecc-intel-crcio.py` reimplementing it. That is (i) breach of the General
   Terms no-RE clause by a licensee (see the QA seat), (ii) a §1201 circumvention-trafficking theory
   if CRCIO/framing is pled as an integrity/technological measure, and (iii) potentially a
   trade-secret/copying claim over the DLL itself. Discovery starts and ends in `docs/inbox/`.
2. **Autodesk sample projects as the shipping seed.** `seed.md` proves deliverables are mutated
   `rmebasicsampleproject.rvt` files carrying Autodesk-authored families — direct infringement of
   Autodesk content in every .rvt shipped to date, contradicting the doc's own constraint.
3. **The product name.** "rev-revit" — mark-in-name is the cheapest, most certain C&D. (Correctly
   rated HIGH; it is the *first letter they send*, not the most damaging fact — items 1–2 are.)
4. **"Opens in Revit" marketing plus validation performed inside licensed Revit** — evidence the
   defendant is a licensee bound by the no-RE clause it was violating (kills the privity defense).

### (d) One next action per gap

- **Autodesk-sample seed (a1/c2):** orchestrator diff the shipped .rvt element inventory against
  the Autodesk sample's family/type list and freeze deliverables that carry any Autodesk-authored
  family; set an explicit cutover gate ("no Tier-A claim until genesis writes a family-free file
  our masters populate").
- **RE provenance (a2/c1/c4):** write a dated provenance memo of exactly how each format fact was
  learned (which binaries, who, on what machine, under what license), quarantine the checked-in
  DLL out of the repo, and hand the memo — not §5.1's hypotheticals — to counsel; ask counsel about
  a clean-room re-derivation and the §1201(a)(2)/(b) trafficking prong specifically.
- **Electrical majors (a3):** run the same verbatim-terms audit on Eaton, Schneider, Siemens, ABB,
  Legrand, Leviton, Hubbell, B-Line, Unistrut, Atkore before Pipeline 2 touches a panelboard.
- **Extraction-pipeline collection legality (a4):** for each spec-sheet source, record whether its
  ToU bans automated collection/download; default Pipeline 2 to manual entry until then.
- **Rows 24–29 verification (a5):** produce the verbatim license quotes (IFC, GLDF, Penn State
  incl. the "otherwise noted" carve-outs, bSDD per-dictionary, LOD) into the source catalog or
  downgrade those cells to unverified.
- **Owed verbatim reads (a6):** browser-read Genlyte, RAB /legal, Focal Point harvesting, BIMobject
  §4.3, live Autodesk General Terms + LSA, BIMsmith EULA, 3Dfindit, MEPcontent; strike or downgrade
  any matrix cell that still rests on a summarizer.
- **Geometry IP beyond copyright (a7/b2):** commission a design-patent + trade-dress screen on the
  first twelve master-family equipment classes and the naming convention (catalog numbers,
  UL/NEMA marks).
- **ODA/APS (a8/b8):** obtain the ODA BimRv membership agreement + quote and the APS
  Automation-API terms; re-rate the §5.1 recommendation only after reading them.
- **Government/DDOT + CSI (a9):** pull DDOT/DC public-works BIM standards for the named use case
  and read the CSI EULA (theconstructionstandard.com/eula) verbatim; add rows.
- **Customer-side Autodesk EULA (a10):** read the Revit end-user terms for any restriction on
  files/services not originating from an Autodesk Offering; add as a row.
- **§1201 trafficking (a11):** counsel question added to the blocking list: is any .rvt framing/
  integrity mechanism a "technological measure," and is our writer a circumvention *device*.
- **Verdict/Tier B/photometry-link/subscriber overconfidence (b1–b8):** rewrite §1's "Yes" as
  conditional, relabel row 1 cells INFERRED (drop "low risk"), move Tier B and "link don't
  embed" to UNKNOWN — NEEDS COUNSEL in the matrix, and mark row 17 §8.1 as cached-copy pending
  live verification.

## Completeness critique — pass 2 (2026-08-03)

Adversarial read of the rewritten `content-strategy.md` (definitive strategy, second synthesis)
against the verified electrical / lighting / aggregator research and the repo. The pass-1
critique's items were largely absorbed (conditional verdict, cutover gate, provenance memo, §1201
trafficking prong, electrical majors, row-1 relabel, Tier B → UNKNOWN, ABB drift, carve-outs).
This pass hunts what is *still* missing or still stated harder than its evidence carries. Not
legal advice; everything below is FOUND-IN-TERMS / INFERRED / UNKNOWN as labelled.

### (a) Missing or unverified sources / questions

- **The verdict's negative universal is drawn from the wrong document layer.** §1 states as a
  *finding* that "no license, from any source, grants a software vendor the right to harvest,
  bundle, redistribute, or server-side embed." But §1's own second paragraph and cross-cutting
  finding (2) say the decisive documents — in-ZIP EULAs (Eaton "Unless otherwise specified"),
  LayoutFAST / BIMPOWER / App-Store EULAs, CADENAS terms, the file EULAs under Cooper §8 /
  Legrand / nVent carve-outs — are UNREAD by anyone. The honest finding is "no *website ToU we
  could read* grants those rights." BIM-specific EULAs are precisely where a spec-driven
  manufacturer grants *more* (they want to be specified); the carve-outs cut both ways.
  → Next: state the finding at the layer actually read; promote the HUMAN TASK (open the
  packages/EULAs) to P0 with the cutover gate — it is the one item that can move the verdict.
- **How Tier A masters are authored is unaddressed, and it is a licensing question.** Pipeline 1
  says "hand-author ... geometry 100% ours" but names no tool; `genesis.md` is project-file work,
  and .rfa writing is even less mature. If any master is built in the Family Editor of a licensed
  Revit seat, the entity is a bound Autodesk licensee (the §5.1 privity fact), and the *license
  class* matters — trial / student / educational / developer-network output is contractually
  barred from commercial use (INFERRED from standard Autodesk licence classes; terms UNREAD).
  → Next: record per master the authoring tool + license class; add "authoring/QA-seat license
  terms" as a matrix row and to counsel Q1.
- **The cutover gate is under-scoped as "no Autodesk-authored *family*."** A project cloned from
  `rmebasicsampleproject.rvt` carries Autodesk-authored non-family expression the gate would pass:
  system-family types (conduit, cable tray, duct, wire — Pipeline 1 lists conduit/EMT/cable-tray as
  loadable masters, but in Revit these are *system families* whose types, routing preferences
  and fitting mappings live in the template), view templates, object styles, fill/line patterns,
  text/dimension styles, annotation symbols, shared-parameter definitions/GUIDs, keynote/
  load-classification settings. → Next: define the gate as an element-inventory diff against a
  family-free genesis baseline, not by family category; add settings/system-type provenance to
  the ledger; fix Pipeline 1 to distinguish loadable masters from system-type definitions we must
  also author.
- **What our writer stamps into the file's identity fields is unexamined.** `.rvt` carries
  `BasicFileInfo` (authoring application/build/username strings) — the direct analog of DWG's
  `TrustedDWG` authenticity string, which was the hook in Autodesk's suit against the Open Design
  Alliance (Lanham Act false designation). If our output asserts it was saved by "Autodesk Revit
  <build>", that is a trademark/false-origin exposure independent of copyright. → Next: dump the
  identity strings from a generated file; take the "what may the authoring string say and will
  Revit still open it" question to counsel.
- **Autodesk's litigation posture against format re-implementers is absent** (Autodesk v. ODA re
  DWG/TrustedDWG; RealDWG as the sanctioned licensing answer; whether any RealDWG-equivalent for
  .rvt exists) — the single most on-point precedent for §5.1, missing from the doc, the counsel
  list, and the ODA row *while the doc recommends spiking ODA BimRv*. → Next: add a §5.1
  precedent/posture note for counsel; ask ODA directly about Autodesk claims history over BimRv.
- **A lawful-content category is missing from the tiers: commercially licensed third-party
  family libraries / content services** (paid MEP-electrical-lighting family vendors and
  subscription catalogs that sell content *with* commercial licenses — several already sit
  unresearched in the "aggregators not researched" list). The tiers jump from A (generate) to C
  (manufacturer partnership) with nothing between; a licensed generic library may be the fastest
  lawful cover for plenum luminaires and gear while masters are authored. → Next: read the EULAs
  of 3–4 commercial family-library licensors specifically for embed-in-deliverable and
  redistribution rights; add rows.
- **Downstream contractual/commercial risk allocation is absent:** our own product terms toward
  customers (licensee-of-record framing, IP warranty on delivered .rvt, indemnity — government
  primes typically flow IP indemnity down to whoever supplies content) and IP/media-liability
  insurance. Every UNKNOWN cell is also a "who bears it" question. → Next: draft the product
  terms' IP/indemnity clauses with counsel before the first paid delivery; get an insurance quote
  conditioned on the content architecture.
- **Customer-supplied inputs beyond IES are unaddressed.** Pipelines 3–4 assume the customer
  supplies photometry, families and sometimes a firm template — which may itself be Autodesk-OOTB-
  or manufacturer-derived, and our tool then embeds and redelivers it inside a file *we* generate.
  The "won't export from a customer's Revit" constraint does not cover files the customer hands
  us. → Next: define the intake policy (accepted inputs, customer representation/warranty, whether
  we scan for Autodesk-authored content) and add "customer-supplied content" as a matrix row.
- **The only affirmative cells still lack shown verification.** Rows 31 (NIBS/COBie), 32 (IFC
  CC BY-ND 4.0 — and *which* IFC version we implement), 34 (Penn State CC BY-SA + "except where
  otherwise noted"), 36 (GLDF MIT) show YES with no "read verbatim on <date>" note; row 32's bSDD
  half is a search-summary read sharing a cell with the IFC text; row 33 is admittedly
  unreconciled. Cross-cutting finding (4) rests entirely on them. → Next: paste verbatim license
  clause + URL + read date for rows 31–36 into §7, split row 32, or downgrade to INFERRED.
- **Photometric *data* vs photometric *files* is unexamined.** The doc treats IES/GLDF as
  manufacturer property to be customer-supplied but never asks whether the numeric distribution
  (LM-63 payload) is measurement fact vs protectable authorship, nor whether deriving lumen/watt/CCT
  parameters from a customer-supplied IES is inside the manufacturer's/aggregator's terms — either
  answer changes Pipeline 3. → Next: add as a §5.5 counsel sub-question; do not extend the Feist
  reading to photometry until answered.
- **Owner-side market validity and coverage:** (i) *which* "DDOT" (Detroit vs DC — both run
  buses) and its BIM/CADD standard are unresolved, yet owner BIM manuals (USACE/VA/GSA cited)
  commonly mandate manufacturer-specific content or LOD that generic masters may not satisfy —
  Tier A's acceptability, not just legality, is unverified; (ii) Chicago-specific plenum
  requirements (Chicago Electrical Code / DOB, plenum-rating documentation) never enter; (iii) the
  device/controls/support brands the electrical rooms will actually spec (Leviton, Legrand P&S,
  Lutron, Atkore/Unistrut/B-Line strut and tray, busway makers) remain unresearched.
  → Next: resolve DDOT identity, pull its standard and the LOD/content requirements, and confirm
  a Tier-A model passes submittal before Pipeline 1's class list is frozen.
- **Autodesk-side AI/automation clause never read.** The doc records BIMobject §4.7(j) and
  Siemens' TDM/AI ban but has not read the *live* Autodesk General Terms (403 to fetch) for
  AI/ML-training and automated-access restrictions — relevant if any component learned from
  Autodesk sample files or licensee-created .rvt structure. → Next: browser-read the live General
  Terms + Terms of Use in full and record whether any learned component touched Autodesk-authored
  data.

### (b) Claims still stated more confidently than the evidence supports

- **§1 point 1: "We own what we author, so USE / BUNDLE / EMBED are clear for our own output"**
  — contradicts row 1 ("*Not* 'low risk' until §5.4–§5.5 screens clear") and §3 Tier A
  ("conditional on"). The exec verdict is where readers stop; reconcile it to the row.
- **Tier B "we never touch, host, or transmit the bytes" (§1) / "never possess or transmit"
  (Pipeline 4).** Pipeline 4's remapping means our software reads and edits the manufacturer's
  family/types in the model — squarely inside the "no modification / unaltered form" language
  of Legrand, Hubbell, ABB, RAB and BIMobject's derivative bans the doc itself quotes. "Never
  possess" may hold; "never touch" does not; and the modification prohibitions bind the *customer*
  our tool acts through. Say so.
- **"No license, from any source, grants ..."** — a finding about website ToUs presented as a
  finding about all sources (see (a) first bullet).
- **§5.7 "HIGH today, LOW once gated"** — LOW is unearned while §5.4/§5.5 (marks in type names,
  design patent/trade dress, collection legality) remain open; the gate removes Autodesk
  contamination only.
- **Pipeline 2 headline order.** "Facts are free" (Feist, INFERRED) leads and manual-entry-by-
  default trails as a subordinate clause; the automated-collection bans are FOUND-IN-TERMS and
  should be the headline, Feist the qualified reading.
- **"Opened in a licensed Revit seat for final QA"** (product framing) is treated as neutral in
  §6 while §5.1 says the same fact may make the entity a bound licensee — the pipelines assume
  in-house validation without stating whose seat/license; make it an explicit decision.

### (c) What a hostile Autodesk legal team seizes on first (re-ranked for the pass-2 record)

1. **The paper trail we are writing.** `docs/legal/provenance-memo.md`, `ecc-intel.md`, the
   quarantine note, `seed.md`, this strategy doc (which ranks Autodesk's best attacks and admits
   both the RE and the sample-seed shipping), and both critique passes are non-privileged repo
   documents authored without counsel — discoverable admissions with the plaintiff's analysis
   pre-written. → Retain counsel *before* expanding §5 further and move the provenance record
   and legal analysis under attorney direction (work-product).
2. **Sample-seed shipping and any already-delivered `.rvt`** — each is a timestamped
   infringement exhibit that a cutover gate does not undo. → Enumerate every deliverable ever
   handed to a customer + element inventory; keep "already-shipped remediation/notification"
   first in counsel Q3.
3. **`BasicFileInfo` / authoring-string false designation** — the ODA/TrustedDWG playbook
   Autodesk has actually run; cheap for them, unexamined by us (see (a)).
4. **§1201(a)(2)/(b) on a distributed commercial writer** reproducing CRCIO framing/checksums —
   the doc now names the prong, but the sales narrative ("valid .rvt, no Revit needed") is the
   plaintiff's demonstrative; the math re-derivation defends copyright originality, not
   trafficking.
5. **The name (§5.3)** — first letter, cheapest fix, still unrenamed.
6. **Licensed Revit used to build/validate a Revit-substituting product** — kills the no-privity
   story and invites General-Terms competitive-use / developer-license clauses (UNREAD).
7. **Any automated manufacturer-site collection** pairs Autodesk with a queue of co-complainants
   (Cree, Focal Point, ABB, NBS, CADdetails, BIMobject §4.7) — keep Pipeline 2 manual and say so.

### (d) Next actions, consolidated (one per gap)

- **P0 pair:** (i) redefine the cutover gate as a full element-inventory diff against a
  family-free genesis baseline; (ii) authorized human opens the vendor packages/EULAs and records
  them verbatim — these two, not counsel briefs, move the verdict this quarter.
- **Counsel intake before more docs:** retain counsel; continue §5 and the provenance record
  under privilege only.
- **New matrix rows:** customer-supplied content; commercially licensed family libraries;
  authoring/QA-seat license class; customer's own Revit EULA (promote from listed gap);
  `BasicFileInfo`/authoring string.
- **Reconcile internal contradictions:** §1 point 1 "clear" vs row 1; Tier B "never touch" vs
  Pipeline 4 remap; §5.7 LOW; Pipeline 2 headline order.
- **Rows 31–36:** verbatim clause + IFC version + read date, split row 32, or downgrade.
- **Read the unread terms that recommendations rest on:** ODA BimRv membership (plus ODA's
  Autodesk-litigation history), APS Automation-API terms, the license of every seat used to author
  or validate anything, live Autodesk General Terms including AI/automation clauses.
- **Owner/market validity:** resolve DDOT identity + owner BIM standard + LOD / manufacturer-
  specific-content requirements + Chicago plenum documentation before Pipeline 1's class list is
  frozen.
