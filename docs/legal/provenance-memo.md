# PROVENANCE MEMO — the rev-revit .rvt reader/writer  (DRAFT FOR COUNSEL)

Status: DRAFT prepared 2026-08-03 for review by qualified counsel. This is a
factual record, NOT legal advice and NOT a legal conclusion. Every statement
below is drawn from the project's contemporaneous engineering logs
(KNOWLEDGE.md, docs/acceptance-log.md, docs/ecc-brief.md, docs/inbox/*.md).

## 1. What the software does
A pure-Python library that reads and writes the Autodesk Revit `.rvt` file
format, developed 2026-08-02..03 for INTEROPERABILITY: enabling
third-party/AI tools to author files that Revit — the industry's system of
record — can open, so end deliverables remain `.rvt` as AEC/government
contracts require.

## 2. How the format knowledge was obtained (in the order it happened)
1. Six publicly-obtained Revit sample project files were analysed as data
   (container structure, streams, records) — file-format analysis of files
   in our lawful possession; no Autodesk software was executed.
2. The stream page-checksum ("ECC") was FIRST characterised empirically from
   the sample files alone (paging geometry, then a search over CRC
   polynomials/geometries), producing candidate parameters.
3. To confirm the checksum algorithm, `Utility.dll` (Revit 2023.1.9) was
   extracted from Autodesk's PUBLICLY DOWNLOADABLE Revit update package
   (no Revit installation, and to the operator's understanding no
   click-through license was presented/accepted for the extracted DLL —
   COUNSEL TO CONFIRM THE ACQUISITION TERMS OF THE UPDATE PACKAGE). The
   relevant checksum routine (`CRCIO`) was analysed. This CONFIRMED the
   parameters.
4. The checksum was then INDEPENDENTLY RE-DERIVED by pure mathematics from
   the sample files alone (255-lane bit-interleaved CRC-11, polynomial and
   geometry recovered by search) and validated byte-exact across a corpus of
   files spanning Revit 2016–2026 — i.e. a clean, non-DLL derivation exists
   and reproduces every observed checksum. The shipping implementation
   (`src/rvt/ecc.py`) is our own code implementing the mathematically-derived
   algorithm; it contains no Autodesk code.
5. No Autodesk source code was accessed at any point.

## 3. Disposition of the Autodesk binary (2026-08-03)
The extracted `Utility.dll` was REMOVED from the project repository and moved
to a preserved, non-distributed quarantine directory
(`/Users/ck/dev/things/rev-revit-quarantine/`). It is not part of any build,
package, plugin, or deliverable. A note remains at
`docs/inbox/ecc-intel-Utility-2023_1_9.QUARANTINED.md`. Decision on
retention vs destruction is deferred to counsel (preservation vs
non-possession trade-off).

## 4. Facts bearing on privity / EULA
- The reverse-engineering work was performed WITHOUT installing Revit and, to
  the operator's understanding, without agreeing to Autodesk's software
  license agreement in that process. COUNSEL TO CONFIRM.
- The commercial workflow contemplates the CUSTOMER opening deliverables in
  THEIR licensed Revit seat for QA. Whether that customer-side licensing
  creates any obligation binding the vendor entity is a question for counsel
  (raised by internal review as a "privity" issue).
- Customers, not this project, would be the parties bound by Autodesk's
  terms for their Revit use.

## 5. Questions for counsel (from internal adversarial review)
1. Interoperability reverse-engineering: applicable exceptions and their
   scope (e.g. 17 U.S.C. §1201(f) and any EULA-privity analysis); is the page
   checksum a "technological measure" or an integrity/error-correction code
   (it verifies AND repairs single-bit errors — evidence it is ECC, not access
   control)?
2. Effect of the DLL confirmation step given an independent clean-room
   mathematical derivation exists and is what ships; whether a documented
   clean-room re-implementation (separate deriver/implementer) is advisable.
3. Retention vs destruction of the quarantined DLL.
4. Trademark: use of "Revit"/".rvt" in a product name (the working name
   contains the mark) and in descriptive marketing.
5. Whether an ODA (Open Design Alliance) BimRv membership or Autodesk APS
   licence changes the risk posture, and their terms.

