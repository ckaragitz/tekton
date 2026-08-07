# inbox — families (family-authoring reconnaissance)

Stream: FAMILY AUTHORING RECONNAISSANCE, 2026-08-03 (two passes). Territory
touched: `src/rvt/families.py`, `tests/test_families.py` (14 pass),
`experiments/families/*` (inventories, dumps, encoder round-trip, CD map,
F0/F1/F2 `.rfa` + reports), `docs/writer/family-authoring.md` (the plan).
No edits to protected modules (encode/commit/writer/ecc/cfb are only
imported).

## Findings (evidence in the plan + JSON dumps)

- Family storage SOLVED [V]: `Partitions/<N>` units 1..k = one embedded family
  document each; host `Family.m_oFamDoc.FamilyDocument.m_contentDocGUID` ==
  the unit separator GUID == the `Global/ContentDocuments` key
  (rme 147/159, rac 82/94 host families resolve; the rest are system /
  in-place families with no document). `m_big2SmallMap2` maps HOST ids
  (categories/styles/param elements) -> EMBEDDED ids. Nested families are
  further top-level units (rme: 305 units vs 147 host families). Ids are
  file-wide unique; separator counter == the unit's element-record count.
- A family document = a complete small Revit document, and it DECODES 100 %
  CLEAN with the existing decoder (605/605 recessed light, 551/551 panelboard,
  1992/1992 in a standalone .rfa): self-Family, "Ref. Level", CategoryElem/
  GStyleElem copies, views, RefPlanes, SketchPlane/VarSketch/CurveElem
  profile sketches, ExtrusionElem/Sweep/Blend forms each carrying a real
  GElement solid in seq 103, FamilyGeomCombination, ImposterLight,
  ParamElemFamily, ConnectorElem (ConnectorElemDomainElectrical: voltage,
  apparent load per phase, PF, poles, load classification).
- **Our encoder re-serializes family documents BYTE-IDENTICALLY** [V] — every
  record of all three seqs, incl. sentinels: sample .rfa 1,993/1,993 ×3,
  recessed light 606/606 ×3, panelboard 552/552 ×3
  (`experiments/families/encoder_roundtrip.json`). => F1/F2 fell out.
- **F1 BUILT + self-verified [V mechanism, H acceptance]:**
  `experiments/families/F1_rfa_full_reencode.rfa` (462,848 B) — the sample
  `racbasicsamplefamily-2026.rfa` re-emitted through the WHOLE pipeline:
  every seq-101/102/103 record decoded + re-encoded by `rvt.encode`, spliced
  at the original block boundaries, re-gzipped (level 3, sync-flush), every
  framed stream re-framed with REAL recomputed CRCIO ECC, unframed metadata
  (BasicFileInfo, TransmissionData, RevitPreview4.0, plain-XML PartAtom)
  copied, container by our CFB writer. Read-back: 18 gzip members / 0 CRC
  failures, 5 full pages / 0 ECC mismatch, walker clean, 1,993 records per
  seq, 1,992/1,992 clean decodes, element-id sequences == source, inflated
  Global/* + schema payloads == source (`F1_report.json`).
- **F2 BUILT [V mechanism, H acceptance]:**
  `experiments/families/F2_rfa_type_param_edit.rfa` = F1 + type
  `'0610 x 0160mm'` Length (user param 4253) 2.001312 ft (610 mm) → 3.0 ft
  (914.4 mm) inside the self-Family's `FamilyTypeTable`, record re-encoded
  with a recomputed adler32 stamp (3935391679 → 3522383392, 10 bytes changed,
  same length; the current type/cached solid untouched). Reads back 3.0 with a
  valid stamp (`F2_report.json`).
- **NEW: in a standalone .rfa the TYPES live inside the document** — the
  self-Family's `FamilyTypeTable` holds all 4 types (name + param sets; `m_idx`
  = current type; `m_familyParams` == the current type's set); user params
  are positive paramIds = the doc's ParamElemFamily ids (4208 Height / 4209
  Width / 4253 Length / 5812 Radius). In a project the types are host-side.
- **NEW: ContentDocuments entry grammar [V]** — every embedded document's
  ADocument is locatable by its separator GUID (305/305 rme): entry =
  `u32 X | a3 03 -1 a2 03 -1 (null lead pointers) | GUID | u32 adoc_len |
  ADocument (u16 0x1c lead)`, entries back-to-back at `adoc_len + 36`. The
  ADocument's `0x0ae9` slot = the doc's own self-Family id. Comparing lead
  bytes with the .rfa's `Global/Latest`: SAME ADocument field sequence, but
  the embedded copy INLINES `ElemTable` (0x5c9) + `History` (0x538) where the
  standalone file externalizes them to `Global/*`. => the F3b extraction
  route is a mechanical inline↔externalized transform once the ADocument
  field decoder (R3) exists (`experiments/families/cd_family_documents_rme.json`,
  `families.content_documents_by_guid` / `content_document_adoc`).
- `.rfa` == same CFB container + BYTE-IDENTICAL `Formats/Latest` schema
  (sha256 6459a9a9…) + one `Partitions/N` with ONE unit = the family document
  + the same `Global/*` streams with the same 8-byte prefixes + the same CRCIO
  page ECC + a plain unframed Atom-XML `PartAtom`. F0 (container round-trip,
  `--verify`) PASSES: `experiments/families/F0_rfa_container_roundtrip.rfa`.
- Verified electrical semantics inside the recessed lighting fixture doc:
  connector `m_dVoltage` 1291.67 = 120 V (÷0.3048²), family param `-1140004`
  688.89 = 64 W wattage, `-1150107` 4230 = CCT (K), dims Length/Width/Depth
  1200/300/150 mm as user params, IES web stored as UTF-16 text in
  `-1150142`, filename `-1140034`. This unit is the recessed-luminaire clone
  donor.

## Recommendation

First family target = a standalone `.rfa` (clone-and-mutate; closed graph,
no host coupling), then load into a project. F1 and F2 are now built and
green under self-verification; the immediate next step is the ACCEPTANCE
GATE (below). Experiment ladder F1..F7 in `docs/writer/family-authoring.md`
§6.

## Requests for the orchestrator

1. **VIEWER/REVIT-TEST these two files** (both self-verify green; both are
   variants of `vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa`,
   a Furniture "table end" family, Revit 2026):
   - `experiments/families/F1_rfa_full_reencode.rfa` — expectation: opens in
     the family editor / translates IDENTICAL to the original (the family T0;
     a pass proves encoder + framing + ECC + container on family files).
   - `experiments/families/F2_rfa_type_param_edit.rfa` — expectation: opens;
     Family Types dialog shows type `0610 x 0160mm` with **Length = 914.4 mm**
     (was 610 mm); other types unchanged (a pass proves edited + re-stamped
     family objects load).
2. **A standalone Autodesk lighting-fixture `.rfa` (Revit 2026)** dropped in
   `samples/` would let F3a–F5 run on the RIGHT domain donor (we only hold a
   2026 furniture .rfa). Any stock "Plain Recessed Lighting Fixture.rfa" the
   brothers can save from their Revit content library. (Alternative F3b —
   extracting the embedded recessed light — is now well understood; see the
   plan §2.1, but needs the ADocument field decoder.)
3. `src/rvt/content.py::scan_content_documents` (32/305 rme entries): my
   earlier diagnosis (non-null lead pointers) was WRONG — all 305 family
   entries carry NULL lead pointers `a303 -1 a203 -1`. The under-count has
   another cause (start position / its ascending-GUID filter). Not blocking
   anything (families.py locates entries by GUID directly); noted for that
   module's owner.
4. `rvt.validate` on ANY `.rfa` (including the untouched Autodesk sample)
   reports 5 project-calibrated "errors": missing `ProjectInformation`,
   `PartAtom` "not CRCIO-framed" + "no gzip member", `Global/ElemTable`
   ("GraveyardRec wire layout not observed"), `DocumentIncrementTable`
   truncated read. These are validator gaps for family files, not defects —
   worth an `.rfa` mode in `validate.py` (that module's owner). F1's
   validate output is IDENTICAL to the original's (30,353 refs checked, 0
   decode failures on both).
5. `KNOWLEDGE.md` "Streams stored with NO CRCIO paging" list should gain
   `PartAtom` (plain Atom XML in .rfa; F1 copied it unframed).

## Verification

- `.venv/bin/python -m rvt.families` regenerates everything under
  `experiments/families/`: `inventory_{rme,rac}.json`,
  `dump_rme_plain_recessed_light.json`, `dump_rme_panelboard_208v_mlo.json`,
  `encoder_roundtrip.json`, `cd_family_documents_rme.json`,
  `F1_rfa_full_reencode.rfa` + `F1_report.json`,
  `F2_rfa_type_param_edit.rfa` + `F2_report.json` (~8 s;
  `--no-experiments` for inventories/dumps only).
- `.venv/bin/python -m pytest tests/test_families.py -q` → **14 passed**
  (9 recon + 5 new: CD-entry grammar 305/305, encoder round-trip rfa +
  recessed light byte-identical, F1 emit + read-back invariants, F2 edit
  read-back + valid stamp + single-record diff).
- Full suite (`pytest tests/ -q --ignore=tests/oracle`): **264 passed, 1
  failed** — the failure is `tests/test_plugin_sync.py` (plugin drift on
  `lib/src/rvt/families.py` = my change, plus `manipulate.py` +
  `validate.py` = other in-flight streams). Left for the ORCHESTRATOR: run
  `tools/sync_plugin.py` once this tick's streams are integrated (running
  it now would bundle the other streams' unfinished files and re-zip the
  plugin — outside my territory and their call).

BRANCH STATE: no git repo (working tree); deliverables complete and
extended — src/rvt/families.py (inventory + dump + encoder_roundtrip +
content_documents_by_guid + emit_rfa/verify_rfa = F1/F2),
tests/test_families.py (14 pass), docs/writer/family-authoring.md,
experiments/families/{inventory_rme.json, inventory_rac.json,
dump_rme_plain_recessed_light.json, dump_rme_panelboard_208v_mlo.json,
encoder_roundtrip.json, cd_family_documents_rme.json,
F0_rfa_container_roundtrip.rfa, F1_rfa_full_reencode.rfa, F1_report.json,
F2_rfa_type_param_edit.rfa, F2_report.json}; READY — F1 + F2 await the
viewer/Revit acceptance gate; next code step after acceptance = F3a (lighting
donor) or F3b (ADocument field decoder for extraction), then F4/F5.
