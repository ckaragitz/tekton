# adoc-landmarks — workstream record (2026-08-03)

Charter: the NON-OBJECT landmark regions inside `Global/Latest` (the
serialized ADocument): (1) the Forge JSON corpus — locate, extract,
characterize, decide (a) identical / (b) project-specific / (c) regenerable
from public sources + licence; (2) the string tables — project vs product
data; (3) the ElementId-reference regions — cluster and classify the registry
kind of G0's dangling ids. Deliverables: `tools/latest_map.py`,
`experiments/genesis/latest/map_<sample>.json` ×6, `tests/test_latest_map.py`,
`docs/writer/latest-regions.md` (the spec + the three determinations).
Territory touched ONLY: those five paths + this record. No `src/rvt/*` edits;
no browser tools; only public web reads (Autodesk help / API docs / the
schema portal probe).

## Result (see docs/writer/latest-regions.md for the evidence)

1. **JSON corpus = IDENTICAL product data (a).** Two tables — 893 unit
   documents (796,206 B) + 422 spec/parameter-group documents (537,134 B),
   1,333,340 bytes, **byte-identical (sha-256) in all six samples**; the only
   per-file field is table 1's owning-element id. It is Autodesk's installed
   **Revit Unit Schemas** (`RevitUnitSchemas.msi` → `Common Files\Autodesk
   Shared\Revit Schemas <yr> Release`), the same typeids the public Revit API
   enumerates (`UnitTypeId`/`SpecTypeId`/`GroupTypeId`). **(c) is FALSE as
   stated:** no autodesk-forge / GitHub repository publishes these documents,
   the public schema portal (schema.autodesk.com) is login-gated, and no
   licence text is embedded — so it is a counsel item (same class as
   `Formats/Latest`), with two engineering routes: emit the identical
   product-constant bytes, or source them from the customer's own install.
2. **Strings:** project-authored strings (must become ours) = view/sheet/
   assembly names, room/space names, colour-scheme names + range labels,
   two structural material names, the `LB_*` reconcile map (103 rows keyed
   to sample element ids), usernames ('macalis', 'liqi'). Everything else is
   product (build list, Forge docs, secondary-data class names, numbering
   partitions, `Rbs*` system pairs, updaters, DB-server descriptor,
   browser-folder defaults, MEP naming tokens). Per-cluster
   product/project/ambiguous counts are in each map JSON.
3. **G0's dangling ids: 10,002 references / 6,405 distinct rstbasic ids, 0
   references to our 205 ids; NOT a deletion registry.** They sit in the
   ADocument's LIVE indexes: id-maps 4,167 ids (BuiltInCategory→category/
   style tables, category↔GStyle pairs, ParamElem→ParamBinding registry,
   Rebar numbering), id-arrays 2,724 ids (per-class element-id indexes:
   instances, materials, patterns, appearance assets, sun settings, view
   list, MEP/electrical catalogs, default-type registry), 143 scattered in
   colour-fill/sketch entries. The ADocument enumerates the deleted
   inventory and does not know our skeleton exists — the strongest single
   predictor that G0 will not open, and the encoder's real job statement:
   REGENERATE the element index + category catalogue over our ids, not
   "drop dead pointers".
4. **Correction to prior knowledge:** `docs/streams/03-global-latest.md`'s
   "0.5–1 MB opaque LZ-compressed continuation of the units dictionary" was
   the wave-1 page-framing artefact — on the de-paged payload the corpus is
   plain UTF-16 text end to end; there is no second codec. (Its offsets /
   inflated sizes are stale too.) Suggest KNOWLEDGE.md note this.
5. Map coverage: racbasic 98.5 %, rstbasic 98.1 %, racadv 98.9 %, rstadv
   98.9 %, rme 96.9 %, dach 51.9 % (dach's ~2.3 MB high-entropy residue =
   workshared/ES payloads absent from the other five; not framed).

## Files
| item | path |
|---|---|
| tool (`latest_map`, corpus/string/id analysers, CLI, `--dangling`) | `tools/latest_map.py` |
| per-sample maps (+ coverage + json-table facts + region list) | `experiments/genesis/latest/map_<sample>.json` (6) |
| tests (8: framing, classification, periodic merge, corpus identity, coverage) | `tests/test_latest_map.py` |
| spec + determinations | `docs/writer/latest-regions.md` |

## For the orchestrator
* No `.rvt` files emitted by this stream (analysis only) — nothing to
  viewer-test from here.
* KNOWLEDGE.md merge candidates: (i) the corpus identity + provenance facts
  (§1 above); (ii) the LZ-continuation retraction (§4); (iii) the ADocument
  registry inventory (§3) — the concrete list of tables the ADocument
  encoder must produce; (iv) the ES-schema list sits BETWEEN the two Forge
  tables (u32 count + GUID-keyed descriptors; 0 racbasic / 175 dach), the
  runtime schema table the object decoder is missing for `ESEntity.m_blob`.
* Counsel list addition: the Revit Unit Schemas corpus (C4-class), with the
  two sourcing options; no in-file licence text exists to quote.
* Diffs requested outside my territory: none required. Suggestion for the
  `docs/streams/03-global-latest.md` owner: mark §4.7/§4.8 (units dictionary
  "compressed continuation") superseded by `docs/writer/latest-regions.md`.

## Reproduce
```
.venv/bin/python tools/latest_map.py --all          # ~3 s, six map JSONs
.venv/bin/python tools/latest_map.py --identity     # corpus byte-identity
.venv/bin/python tools/latest_map.py --dangling     # G0 registry study
.venv/bin/python -m pytest tests/test_latest_map.py -q   # 8 passed
```

BRANCH STATE: no VCS (plain directory); uncommitted new files
`tools/latest_map.py`, `tests/test_latest_map.py`,
`docs/writer/latest-regions.md`, `docs/inbox/adoc-landmarks.md`,
`experiments/genesis/latest/map_{racbasic,rstbasic,racadv,rstadv,rme,dach}sampleproject.json`.
No existing source, doc, or orchestrator file modified. Full suite at
handoff (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
614 s): **494 passed, 1 failed** — the failure is the pre-existing
`tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` (plugin
bundle stale vs a parallel stream's `src/rvt/genesis/*`; fix =
`python tools/sync_plugin.py`, not my territory). My 8 tests pass. READY.
