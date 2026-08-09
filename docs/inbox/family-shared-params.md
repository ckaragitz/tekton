# family-shared-params — tagging-contract parameters as SHARED family parameters at OUR file's GUIDs (#165)

Stream: **family-shared-params** (engineer session eng165, 2026-08-09, issue #165, P1,
area:famgen / area:docs, refs steer #108). Territory: `src/rvt/famgen/skeleton.py`,
`src/rvt/famgen/factory.py`, `tools/make_family.py`, `src/rvt/famload.py` +
`src/rvt/famgen/loader.py` (twin typeId propagation only), `skills/tekton-ifc/references/shared-parameters-mapping.md`
(root copy; plugin mirror regenerated), `docs/writer/asset-factory.md` §6 row 8,
`tests/test_famgen_skeleton.py`, `tests/test_famgen_factory.py`, this record, regenerated
`plugin/lib` mirrors. No hot file touched.
Status: **SHIPPED as a PR — family-mode VALID 0 errors, PROVENANCE-CLEAN, GUIDs decode back
verbatim; NO loads / certification claim (rule 4). Family-side `ParamElemExternal` is listed
below as a candidate variable for a later certification batch; nothing staged for the viewer.**

## 1. Why

Schedules and tags in a firm's project bind SHARED parameters by GUID, not by name. Our
generated families carried the eleven tagging-contract names only as LOCAL
`revit.local.family:` parameters (asset-factory honest limit #8), so a `PanelName` column
keyed on our own published GUID file stayed empty after load; and every local parameter's
identity carried a fresh per-build `uuid4` (a determinism smell, cf. #9). The GUID policy
("copy verbatim, never regenerate") was written in the tekton-ifc reference but not
implemented family-side. Our shared-parameter file with its eleven real GUIDs is tracked at
`usecases/eaton-panelboard/panelboard-shared-parameters.txt`.

## 2. What was built

* **`skeleton.new_shared_parameter(elem_id, self_family_id, caption, guid, *, spec_type_id,
  group_type_id, kind='ParamDefValue', …)`** + **`FamilyDoc.add_shared_parameter(caption,
  guid, spec, group)`** — a `ParamElemExternal` (a *shared* family parameter). The object is
  built by OUR [VERIFIED project-side, 466/466] constructor `rvt.genesis.residue_b.shared_parameter`
  (`m_externalParamKey.m_guidValue = guid`, `m_pParamDef.m_typeId = 'revit.local.shared:<32hex guid>-1.0.0'`,
  `m_paramElemId == m_id`, `m_bindingIds []`, `m_userModifiable T`, `m_hideWhenNoValue F`)
  overlaid with the two family-document conventions every element of ours carries
  (`m_famId` = the self-Family, `m_designOptionId` −4); header = the `ParamElemFamily`
  header shape (family id, deletion `[family, self]`, flags 8218 / −32768). It registers in
  `doc.params[caption]`, so type-table rows, the current-type set, the parameter-order cell
  and the locked-ids list key on its element id exactly like a local parameter
  ("type-table values still keyed correctly" — asserted). `kind=` selects the ParamDef
  storage class; the default `ParamDefValue` keeps the definition block byte-for-byte the
  shape our certified-lineage local parameters carry (spec id + restriction 1 + boundless F),
  so the shared variant differs from the local one in **element class + GUID identity only**
  (single-variable discipline); the project-side census law (text → `ParamDefString`,
  integer → `ParamDefInt`) is the documented alternative (`SHARED_PARAM_DEFAULT_KIND`).
* **The policy lives in the document, not the factory** — `skeleton.read_shared_parameter_file(path)`
  parses OUR Revit shared-parameter TXT by its documented tab-separated grammar (`#`
  comments; `*KIND col…` header rows naming the columns of the `KIND value…` rows that
  follow — META / GROUP / PARAM; UTF-8 or Revit's UTF-16-with-BOM) into
  `{name: SharedParamDef(guid, name, datatype, group, description, visible)}` (malformed
  GUID / duplicate name / headerless row → `ValueError`); `new_family_document(...,
  shared_params=None | path | rows)` stores the rows on `FamilyDoc.shared_params`; and
  **`FamilyDoc.add_family_parameter` itself routes**: a caption present in the file whose
  DATATYPE agrees with the requested spec (`shared_datatype_matches` /
  `SHARED_DATATYPE_SPECS`, version-agnostic) is authored SHARED at the row's GUID
  (description carried); a datatype disagreement, or an instance/formula shared request, is
  refused (`ValueError`, never a second GUID); every other caption stays local. So EVERY
  `add_family_parameter` caller (factory, `ifc/intent`, `ifc/famfrom_ifc`, heads) gets the
  policy by passing `shared_params=` once — no per-call threading.
* **Deterministic LOCAL identities** — `local_param_guid(family_name, caption) =
  our_guid("family.parameters", family, caption)` (the repo's canonical uuid5 derivation
  from #9: namespace `uuid5(NAMESPACE_DNS, "rvt-writer.gen.family.parameters")`, purpose
  constant `LOCAL_PARAM_PURPOSE`, documented in the reference §1.3).
  `new_family_parameter(..., family_name=)` defaults its 32-hex session part to that guid
  (the `<8-hex element id>-1.0.0` suffix law is untouched, so `layout_law` / `birthright`
  keep working); `FamilyDoc.family_guid` is now `Optional[str] = None` = "per-parameter
  deterministic identity" (an explicit GUID still gives the one-session-GUID form).
  `shared_param_type_id(guid)` / `param_type_id(guid, id)` are the two identity helpers.
* **`factory.make_panelboard / make_transformer / make_luminaire(shared_params=None | path |
  rows)`** — pass-through to `new_family_document`; `DEFAULT_SHARED_PARAMS` = the tracked
  file's path; `FamilyProduct.shared_parameters()` / report `family.shared_parameters` =
  caption → GUID; a product note says it out loud incl. "no loads claim". Panelboard + our
  file ⇒ the eleven contract parameters shared, Width/Height/Depth local; transformer ⇒
  `Phases`; luminaire ⇒ `Voltage`.
* **`tools/make_family.py {panelboard,transformer,luminaire} --shared-params FILE`** (+ usage
  text, a `shared :` line in the human report; refusals print "factory refused the job").
* **Loaders (twin identity propagation only)** — one rule for both: `skeleton.PARAM_TWIN_CLASSES`
  + `skeleton.retarget_param_twin(obj, twin_id, host_family_id, session_hex)` (id /
  `m_paramElemId` / `m_famId` rewrites; identity re-homed BY SCHEME: `revit.local.family:`
  → host session + id, `revit.local.shared:<guid>` + `m_externalParamKey` **kept
  verbatim**). `famgen.loader.author_param_twins` and `famload.author_param_twins` both call
  it and twin a `ParamElemExternal` as its own class (`HDR_FLAGS` gained the class, same
  words as `ParamElemFamily` in each loader) — the two copies of the rewrite are gone.
* **Docs** — reference §1.3 "GUID identity policy for GENERATED families" (root
  `skills/tekton-ifc/…`, mirrored by sync) incl. the corrected statement that the literal
  file IS tracked in this repo; `docs/writer/asset-factory.md` limit #8 rewritten (built,
  uncertified, what stays open).
* **Provenance whitelist** — `factory._FORGE_VOCAB` already whitelisted
  `revit\.local\.(family|shared)[:.]`; nothing to extend, asserted in a test and re-proven on
  the file (PROVENANCE-CLEAN below).

## 3. Evidence (this clone: fresh, no `samples/`, bundled genesis base only)

### 3.1 The eleven GUIDs, decoded back from the written `.rfa` vs OUR file

`tools/make_family.py panelboard --mains 400 --spaces 42 --voltage 480Y/277 --mcb
--shared-params usecases/eaton-panelboard/panelboard-shared-parameters.txt -o …/panel.rfa`
→ `verify ok, decode 45/45; validate VALID (0 errors, 0 warnings); provenance ok=True (all 11
checks)`; `tools/rvt_validate.py … --family` → `VALID (no errors); warnings=0`.
Decoded `ParamElemExternal` records (unit 0):

| id | caption | `m_externalParamKey.m_guidValue` (decoded) | file GUID | `m_typeId` | spec |
|---|---|---|---|---|---|
| 1025 | PanelName | d2cce9ee-8e62-44ff-b5ab-12ead03922b8 | d2cce9ee-8e62-44ff-b5ab-12ead03922b8 | revit.local.shared:d2cce9ee8e6244ffb5ab12ead03922b8-1.0.0 | spec.string |
| 1026 | Voltage | 002b1533-731c-41b3-b1a5-20f6b1ee035a | 002b1533-731c-41b3-b1a5-20f6b1ee035a | revit.local.shared:002b1533731c41b3b1a520f6b1ee035a-1.0.0 | electrical:potential |
| 1027 | Phases | 1816cd3d-3644-40b9-8188-9f9bee361411 | 1816cd3d-3644-40b9-8188-9f9bee361411 | revit.local.shared:1816cd3d364440b981889f9bee361411-1.0.0 | spec.int64 |
| 1028 | Wires | c3611f34-2603-40b9-8dc6-08a736656a6f | c3611f34-2603-40b9-8dc6-08a736656a6f | revit.local.shared:c3611f34260340b98dc608a736656a6f-1.0.0 | spec.int64 |
| 1029 | BusRating | ea6b58a3-d06a-43c6-82f2-83e88a5348e0 | ea6b58a3-d06a-43c6-82f2-83e88a5348e0 | revit.local.shared:ea6b58a3d06a43c682f283e88a5348e0-1.0.0 | electrical:current |
| 1030 | MainsType | 65863827-d986-49c3-b257-4fcc1d7e8337 | 65863827-d986-49c3-b257-4fcc1d7e8337 | revit.local.shared:65863827d98649c3b2574fcc1d7e8337-1.0.0 | spec.string |
| 1031 | MainsRating | 32a6688e-cda7-4884-b635-10e1ad2da190 | 32a6688e-cda7-4884-b635-10e1ad2da190 | revit.local.shared:32a6688ecda74884b63510e1ad2da190-1.0.0 | electrical:current |
| 1032 | ShortCircuitRatingkA | 95713ca1-2c46-40a7-9e6e-ea3a59ca834f | 95713ca1-2c46-40a7-9e6e-ea3a59ca834f | revit.local.shared:95713ca12c4640a79e6eea3a59ca834f-1.0.0 | aec:number |
| 1033 | Mounting | ea7d916a-5caf-4069-a3f1-5a5f6df75fba | ea7d916a-5caf-4069-a3f1-5a5f6df75fba | revit.local.shared:ea7d916a5caf4069a3f15a5f6df75fba-1.0.0 | spec.string |
| 1034 | NumberOfCircuits | 9aeb45cc-a05e-4cd2-9f5d-fc101a841b3c | 9aeb45cc-a05e-4cd2-9f5d-fc101a841b3c | revit.local.shared:9aeb45cca05e4cd29f5dfc101a841b3c-1.0.0 | spec.int64 |
| 1035 | NeutralRating | 0c2e8d22-6ff6-4049-b265-f93fae7afc64 | 0c2e8d22-6ff6-4049-b265-f93fae7afc64 | revit.local.shared:0c2e8d226ff64049b265f93fae7afc64-1.0.0 | spec.string |

11/11 equal; Width/Height/Depth (1022–1024) stay `ParamElemFamily` with `revit.local.family:`
identities. Transformer `--shared-params` ⇒ `Phases` shared (VALID 0 errors, provenance ok);
luminaire ⇒ `Voltage` shared (VALID 0 errors, provenance ok).

### 3.2 DEFAULT (no flag) output structurally unchanged — byte-level before/after

Method: build panelboard / transformer / luminaire with NO flag twice on untouched `main`
(950d4b6) = the per-build noise baseline, then twice on this branch; decode every stream
digest + every family-document record (seq 101/102/103) + BasicFileInfo + PartAtom and diff
leaf-by-leaf (scratch instrument `rfadump.py`, not committed).

* **Pre-existing per-build noise, identified** (main~main): panel 25 / xfmr 22 / lum 18
  differing leaves = (a) the document GUID (`uuid4` in `new_family_document`) →
  `BasicFileInfo` unique/central GUID + mirror text, `PartAtom`, and the digests of
  `Contents`, `Global/History`, `Global/PartitionTable`, `Partitions/0` (unit GUID inside;
  its gzip length wobbles by a few bytes with the GUID bytes); (b) the family session GUID
  (`uuid4`) → the 32-hex part of every local parameter's `m_typeId` (14 / 11 / 8 leaves).
* **main~branch (no flag):** panel 25 / xfmr 22 / lum 19 differing leaves and the SET of
  differing paths == the noise set exactly (lum's +1 = `Partitions/0.len`, the gzip-length
  wobble of class (a)). Same 45 / 43 / 39 records, same classes and ids, same stream list,
  every stream length equal except `Partitions/0`. ⇒ apart from the identified noise,
  expected differences = **none**.
* **branch~branch (no flag):** 10 / 10 / 10 leaves — class (b) is GONE (local identities are
  now deterministic); only the document-GUID noise (a) remains (out of this issue's scope;
  see follow-ups).

### 3.3 Gates

* `pytest tests/test_famgen_skeleton.py tests/test_famgen_factory.py tests/test_famgen_geometry.py
  tests/test_famgen_adoc.py tests/test_famload_batch.py tests/test_bare_family_validate.py
  tests/test_famgen_loader.py tests/test_layout_law.py tests/test_identity.py
  tests/test_birthright.py tests/test_union_reconcile.py -q -rs` → **214 passed, 49 skipped
  (sample-gated), 0 failed**; plus `test_famload.py test_famload_2025.py test_famdoc_scan_fp.py
  test_famdoc_final.py test_hostsym_product.py test_frontdoor_standalone.py
  test_required_settings.py test_geo_site_determinism.py test_rfa_load.py test_target2025.py`
  → **113 passed, 34 skipped**; the full CI shard (`tests/ci_shard.txt`) → see PR body.
* New tests (fresh-clone, all executed here): skeleton — deterministic local guid + the
  documented namespace, `new_shared_parameter` layout, `add_shared_parameter` keys type
  values, `new_family_document(shared_params=)` routes `add_family_parameter` (datatype
  clash / instance refused), `retarget_param_twin` re-homes local / keeps shared;
  factory — file parser on OUR tracked TXT (11 GUIDs verbatim, order = contract, datatypes
  agree with the contract specs), grammar edges (UTF-16, bad GUID, duplicate, headerless),
  the flag makes exactly the eleven shared / rest local / values keyed / datatype clash
  refused, default build unchanged + deterministic, **the written `.rfa` is VALID +
  provenance-clean and its 11 `ParamElemExternal` GUIDs decode == the file's**, and **both
  loaders' twins keep the shared typeId + GUID** (host = the bundled `G_ABPD.rvt`).
* `tools/sync_plugin.py` → synced 5 files, deny-audit clean, validation passed; `--check`
  clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2780 paths).

## 4. Findings

1. The provenance whitelist needed no change: `_FORGE_VOCAB` has carried
   `revit.local.shared` since the residue-B work; the GUID strings themselves match no
   suspect pattern.
2. `famdoc_adoc.FAMILY_DATA_CACHES` deliberately EMPTIES the family ADocument's
   `ExternalParamTracking.m_keyDataMap` / `m_companyNameMap`. Project-side the shared GUID is
   the KEY of that map (`second.m_paramId` = the element id, genesis-residue-B finding 1). A
   Revit-born family with a shared parameter very probably registers it there too — we have
   no such specimen. This is the most likely reason a desktop load could complain, and it is
   outside this issue's territory (`famdoc_adoc.py`).
3. Host side, a real load into a firm's project must REUSE an existing `ParamElemExternal` of
   the same GUID (that is the whole point of binding by GUID) or register ours in the host's
   `ExternalParamTracking`; today's twin allocates a fresh host id and registers nothing
   (typeId propagation only, per charter).

## 5. Candidate variables for a later certification batch (NOT a loads claim)

One variable per probe, each with a byte-identical control on a certified base:
(v1) family-side `ParamElemExternal` as built (kind `ParamDefValue`); (v2) the storage-kind
law instead (`kind=` text → `ParamDefString`, integer → `ParamDefInt`); (v3) v1 + the
family ADocument's `ExternalParamTracking.m_keyDataMap` populated with our 11 GUIDs;
(v4) load into `G_ABPD` with the twin as built vs. registered in the host's map.

## 6. Follow-ups (searched first; filed as task issues, `Refs #165`)

* Register shared-parameter GUIDs in the family ADocument's `ExternalParamTracking` and, on
  load, reuse-by-GUID / register in the host's map (findings 2–3; territory `famdoc_adoc.py`,
  loaders) — then STAGE v1/v3/v4.
* Deterministic document GUID for factory builds (the remaining class-(a) per-build noise;
  `new_family_document(document_guid=None)` → uuid4), same policy as #9.

## BRANCH STATE

* Branch `cam/165-shared-param-guids` from `origin/main` 950d4b6; commits: skeleton
  (shared constructor + deterministic local identities), factory + CLI (`shared_params=` /
  `--shared-params`, TXT parser), loaders (twin propagation), tests, docs (reference §1.3,
  asset-factory row 8, this record), plugin mirrors
  (`plugin/lib/src/rvt/{famgen/skeleton.py,famgen/factory.py,famgen/loader.py,famload.py}`,
  `plugin/skills/tekton-ifc/references/shared-parameters-mapping.md`).
* Gates: all of §3.3 green in this clone; NO full-suite run (charter).
* Shipped vs staged: code + CLI + tests + docs shipped in the PR; **nothing staged for the
  viewer, no loads / certification claim**; no `.rfa` outputs committed (scratch only, each
  VALID 0 errors / provenance ok).
* Hot files: none touched.
