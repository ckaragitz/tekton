# Learned: the donor-less host-ADocument law (#480), and why no test saw it coming

One-line context: for a whole campaign every generated `.rfa` the owner
desktop-confirmed had been built with `family_donor=<the owner's own .rfa>`,
while every install without that file took a different, untested code path
and produced families Revit rejected. Written from `docs/inbox/rfa-revit-api-compat.md`
(iteration 13), `docs/inbox/donorless-ifc.md` and PRs #480 / #505, for
KNOWLEDGE.md when the tech-lead loop folds it (issue #511 wrote the note; it
does not touch KNOWLEDGE.md itself).

1. **The bug.** With no donor the emitter takes the CONSTRUCTIVE path
   (`constructive_family_host_tree`), whose `AppInfoManager` carried **0 of
   239 manager slots** (a Revit-born famdoc fills 133). Every registry the
   famdoc laws wire -- `UniqueElementsTracking` [10]/[60]/[64]/[65]/[85],
   `PenWidthTableInfo`, `SymbolIdMgr` key 10, `BrowserOrganizationTracking`
   -- was guarded by `if isinstance(body, dict)` and therefore **silently
   no-opped**. Host `Global/Latest` shipped at **252 bytes** (donor path:
   65,249) -- the stub Revit rejects with `Failed to load elemStream#0`.
   User-facing severity: families worked on nobody's machine but the owner's.
2. **Why no test caught it.** Every famgen test read the ELEMENT records
   (unit 0, seq 101/102/103). *Nothing read the host ADocument*, so the
   element half of each law passed while its registry half was missing.
   The first test that opens the host document,
   `test_donorless_host_document_wires_every_registry` (>130 slots, UET
   length 93, all five UET ids set, pen table / symbol map / browser orgs
   wired), landed with the fix. **Law for future famgen work: a famdoc law
   has two halves -- the element and its registration in the host
   ADocument -- and a guard test must read both; a law asserted only on
   `Partitions/*` records is half a test.**
3. **The misfiled early sighting.** Desktop round 14 had already produced the
   252-byte host (probe M) and blamed it on calling `prod.write()` instead of
   `standalone_family_write` -- an "instrument error". It was this product
   bug: the donor-less path yields the same stub through either entry point.
   Rule this cost: when a probe differs from its siblings by 65 KB in one
   stream, that is a reading to explain, not an instrument to distrust --
   re-run the *same* recipe donor-free before reinterpreting.
4. **The fix, zero donor bytes.** `_populate_appinfo_managers` fills the
   constructive tree's slots from a measured index->class map
   (`src/rvt/famgen/assets/famdoc_appinfo_slots.json`, 133 entries -- class
   names and slot positions only), each a schema-blank of its class with
   `m_pADoc` weakref 1; `UniqueElementsTracking.m_elemIds` is sized to the 93
   positional slots so the id writes land. Donor-less output: 133/133 slots,
   all four registries wired, `Global/Latest` a real document.
5. **The process consequence (#505, steer #498 / S-2026-08-10-c).** Because a
   donor on the owner's machine had masked the bug for 28 rounds, the
   implicit donor was removed outright: `FamilyProduct.write` no longer reads
   `$RVT_FAMILY_DONOR`; a donor survives only as the explicit
   `standalone_family_write(family_donor=...)` argument for format-parity
   experiments, and the shipped plugin text no longer offers one (#511).
   Corollary for every desktop round from here on: **the probe a human opens
   must be built the way a stranger's install builds it** (bare unzip, no
   env overrides) or its verdict certifies a path nobody ships.
6. **Evidence status, stated no higher than the records.** `donorless-ifc.md`
   records the constructive path as "desktop-verified on two machines";
   #480's own donor-free pair (`donorless_fixed.rfa` / `donorless_troffer.rfa`)
   is logged "desktop verdict pending"; `ifc-assembly-rfa.md` records the
   owner's desktop open of a 103-solid donor-free `generic_model` ("it opened
   and all the slots for the channel are in"). None of this is in
   `docs/coverage/viewer-certified.json` -- no standalone `.rfa` of ours is
   in the ledger -- so generated families stay validator-gated + PROOF-ONLY
   in the matrix.
