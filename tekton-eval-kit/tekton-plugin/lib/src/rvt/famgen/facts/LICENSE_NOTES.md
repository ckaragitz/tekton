# Manufacturer facts store — license and provenance notes

This directory is the **catalog-facts store** of `rvt.famgen` (docs/product/
content-strategy.md, Pipeline 2). It drives family generation with published
FACTS about real products. It is data, not content: no third-party model,
drawing, prose or photometric file lives here, ever.

**This is not legal advice.** The posture below implements the operating
rules of `docs/product/content-strategy.md` (the definitive strategy) and
must be re-read against it. Items the strategy marks NEEDS COUNSEL remain
NEEDS COUNSEL here.

## 1 · The basis: facts, not expression

Every value in `facts/**/*.json` is a fact about a product — a dimension,
a rating, a catalog number, an option code — read from a document the
manufacturer (or an authorized distributor republishing the manufacturer's
figures) published, or from a public code / standard. Facts are not
copyrightable (*Feist Publications v. Rural Telephone*, 499 U.S. 340 (1991));
we own everything we author *from* those facts. Concretely, this store:

* stores **numbers, codes and short factual labels only** — never a
  manufacturer's drawing, dimensioned artwork, photograph, catalog page,
  descriptive prose, or the selection/arrangement of a whole catalog table
  beyond the specific figures we need;
* **never stores or redistributes a manufacturer's CAD / BIM / .rfa file
  or a photometric (.ies / GLDF) payload.** Photometry is *referenced by
  the manufacturer's own URL* (`photometry_reference` fields); the customer
  obtains the file under their own license (content-strategy §3, Pipeline 3);
* regenerates all **geometry from dimensions** in `rvt.famgen` — nothing is
  traced, rasterized or copied from a cut sheet; families model the
  functional envelope, not ornamental styling (content-strategy §5.5,
  design-patent / trade-dress screen still owed);
* keeps a **provenance ledger per fact** — every record carries
  `source: {url, doc, accessed}` and every field a `field_provenance` flag,
  so any deliverable can be audited back to its published figure.

`Feist` is a *copyright* case. It says nothing about design patents,
trade dress, trademark use of a manufacturer's name / catalog number in a
family or type name (content-strategy §5.4), or the *collection* method
(§5.2). Those remain open counsel items and are not answered by this store.

## 2 · Field provenance flags

Every leaf field a variant exposes (`ratings.*`, `dims_in.*`, `options.*`)
has an entry in that variant's `field_provenance` map:

* `fact` — the figure was **read directly from a document this session**
  (a manufacturer catalog / spec sheet, an authorized distributor's
  republication of it, or a code / standard text corroborated by search),
  and that document is listed under `sources` with `verification:
  VERIFIED` (or `SEARCH-SUMMARY` for a code figure corroborated only by
  search snippets — noted per source).
* `assumed` — anything else: a value **inferred** (e.g. an enclosure width
  decoded from a catalog number), **derived** (an efficacy we computed),
  seen **only in a search-engine summary**, a **design convention**
  (typical mounting height), or a **null placeholder** for a figure not
  yet sourced. `assumed` values never masquerade as facts and the generator
  should surface them as editable, unverified parameters.

A `null` value with an `assumed` flag means **NOT SOURCED — do not
invent.** The catalog loader (`rvt.famgen.catalog`) refuses to fabricate
these; generation must ask for the figure or leave the parameter blank.

Source-level `verification` values: `VERIFIED` (document read),
`UNVERIFIED` (URL recorded for a human — unreadable / deliberately not
fetched), `SEARCH-SUMMARY` (only a search snippet seen).

## 3 · Collection posture (content-strategy §5.2)

*"Facts are free" does not answer "may we collect them from a site that
bans automated collection."* Each record's `collection_posture` states how
its figures were obtained. Rules applied:

* **One manual-equivalent read per document, no crawling.** Each source is a
  single fetch of one published document; figures were transcribed by hand.
  No bulk harvesting, no scraping loop, no AI/ML training on the material
  (BIMobject-style §4.7(j) clauses noted).
* **Where a site's terms restrict automated collection or non-personal
  use, its pages are not fetched.** Acuity Brands (Lithonia) is the live
  example (content-strategy row 10, §5.2): `lithonia/*` records were built
  from independent distributor listings and search summaries only; the
  Acuity pages are recorded `UNVERIFIED` / `primary_deliberately_not_fetched`
  for a human to read in their own browser. Fields sourced only from
  summaries are `assumed`.
* **Unreachable primaries are recorded, not guessed.** `eaton.com` and
  `se.com` block scripted clients; Eaton and Schneider figures were read
  from their *own* catalogs (CA08100003E; Schneider Digest 178 / 0100CT1901)
  as republished by authorized electrical distributors, with the canonical
  vendor URL kept alongside as `UNVERIFIED`.
* **Vendors whose terms were never reviewed** (Hammond Power Solutions) are
  treated as restrictive-by-default; their records are deliberately thin
  and flagged.

The extraction pipeline's collection legality per source is itself a
**NEEDS COUNSEL** item (content-strategy §5.2, §5.5, consolidated question
4). This store's discipline is designed to keep that question small — a
handful of manual-equivalent reads of published spec sheets — not to
pre-empt the answer.

## 4 · Trademarks and names (content-strategy §5.4)

Manufacturer and product-line names (`Eaton`, `Pow-R-Line`, `Square D`,
`I-Line`, `Lithonia`, `Sentinel G`, `LDN6`, …) appear here as **factual
identifiers of the product a fact is about**, in `vendor` / `product_line`
/ `model` / `aliases` fields. That is data-store nomenclature, not a family
naming decision. Whether generated FAMILY / TYPE **names** may carry a
manufacturer name or catalog number — versus carrying them only as
parameter *values* — is an open counsel question and a generator-level
policy switch, not settled by this store.

## 5 · What each vendor directory contains

| dir | line | basis |
|---|---|---|
| `eaton/` | Pow-R-Line panelboards (legacy 1a/2a/3a/4B ↔ Xpert 1X/2X/3X/4X); DOE 2016 general-purpose dry-type transformers | Eaton catalogs CA08100003E (Vol 2 Tab 3 June 2020; Tab 2 Aug 2017), RP01400001E, and the Eaton Arabia technical page — VERIFIED reads |
| `square-d/` | NQ / NF / I-Line panelboards | Schneider Digest 178 (0100CT1901) Section 9, 9/1/2023 — VERIFIED read |
| `hps/` | Sentinel G transformers (second-vendor proof) | one distributor listing (VERIFIED) + search summaries (`assumed`) |
| `lithonia/` | BLT LED troffer, LDN6 downlight (flagship archetype) | distributor listing (VERIFIED for 2BLT4) + search summaries; Acuity primaries deliberately not fetched; IES referenced by URL only |
| `generic/` | NEMA devices, box sizes, ADA / NEC mounting facts | ADA 2010 §308, NEC 314.16 (search-corroborated); conventions `assumed` |
