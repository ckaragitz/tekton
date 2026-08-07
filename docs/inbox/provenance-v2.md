# provenance-v2 — workstream record (PROVENANCE LEDGER v2, 2026-08-03)

Charter: fix the instrument the genesis auditor caught lying
(`docs/inbox/genesis-audit.md`: it reported "0 autodesk-sample" on
`experiments/genesis/G0.rvt`, a file ~94 % Autodesk BYTES, because it walked
only the ElemTable against ONE baseline). Extend `src/rvt/provenance.py` IN
PLACE — prior public API and all 11 v1 tests kept green — with a
STREAM-AWARE ledger, MULTI-BASELINE union, EMBEDDED-STRING provenance,
identity policy check, and an honestly recomputed G1. Territory touched
ONLY: `src/rvt/provenance.py`, `tools/provenance.py`,
`tests/test_provenance.py`, `docs/writer/provenance-ledger.md` (§0 v2
correction added; old element-only headlines marked superseded),
`experiments/genesis/provenance/{G0_v2.json,G0_v2.txt,.cache/}`, this
file. No other stream's file was edited; no core module changed.

## DONE = G0's honest byte-weighted, multi-baseline, stream-aware verdict

**MET.** The certified run:

```
.venv/bin/python tools/provenance.py experiments/genesis/G0.rvt \
    --baseline all --streams --json experiments/genesis/provenance/G0_v2.json
```
(exit 2; text output committed as `experiments/genesis/provenance/G0_v2.txt`;
cold run ~13 s indexing all six samples' 1.3 GB inflated into a ~29 MB
cached block index; cached re-run ~8 s). The published headline (also written into
`docs/writer/provenance-ledger.md` §0):

* Byte-weighted: of 2,218,218 inflated bytes, **94.91 % identical-to-
  baseline / 0.15 % modified-lineage / 4.94 % ours**; excluding the
  `Formats/Latest` schema stream (counsel C4), of 1,721,621 bytes **93.44 %
  identical / 0.20 % / 6.36 % ours** — the auditor's "~94 % / ~6 %",
  reproduced by the instrument.
* Stream table: `Global/Latest` (the ADocument) **1,586,254 / 1,586,254
  bytes byte-identical to rstbasicsampleproject** and expression-bearing →
  blocks G1; `Formats/Latest` 496,597 / 496,597 identical to all six samples
  → counsel C4 (not counted); `Global/History` 95.7 % / `DocumentIncrement
  Table` 86.4 % / `Global/PartitionTable` 100 % identical → lineage
  fingerprints (advisory); `Global/ElemTable`, `Global/ContentDocuments`,
  `ProjectInformation`, `TransmissionData`, `Partitions/21#host` (our 205
  records) → ours; **0 embedded family save units**.
* Multi-baseline (union over all six samples): **154 transitive-cloned / 51
  ours-created** (rst alone said 142/63); per baseline rst 142 · rme 130 ·
  racbasic 140 · racadv 129 · rstadv 126 · dach unmatched; of the 51
  "created", 26 have max-similarity < 0.40 everywhere (6 < 0.25) — the rest
  reproduce Autodesk product defaults. Instrument now names the audit's
  exhibits: `DBViewProject` 1500176 = 0.91 clone of **racbasic's** 230;
  `ElectricalSetting` 1500036 = 0.79 clone of **rme's** 639116 (and racadv/
  rstadv); `Viewer` 1500177 = 0.90 of racbasic 231; `BasePoint`s = 0.89–0.95
  of racadv/rme; three `DBViewType`s = 0.68–0.71 of racbasic.
* Autodesk resource refs (G1c): **7,438** in document content — 7,350 in
  `Global/Latest` (7,292 Forge typeIds), **88 inside OUR own records**
  (`assetlibrary_base.fbx` ×35, `%1!s!` load-label templates ×24, Forge
  typeIds ×21, `SunAndSky` ×8) across 20 host elements (15 `MaterialElem`).
* Identity: BasicFileInfo now ours (author/username `rvt-writer`, path
  `G0.rvt`, fresh GUID) — but the DIT still signs **22 of 23 save episodes
  with Autodesk employee usernames** (loboarch ×9, okapaw ×4, xuew ×3,
  youyi ×2, zhangg/gbs_subsuser6/campbes/hansonje). G0.rvt on disk predates
  the writer's V32 DIT scrub — regenerate it and this clears.
* **G1 v2 verdict: FAIL** — 150 derived elements + 1,586,254 identical
  expression-stream bytes + 7,438 resource refs + 1 identity violation; one
  counsel item (C4); five fingerprint advisories. `certifies_G1 = false`.

## What was built (all in `src/rvt/provenance.py`, ~700 new lines appended)

| capability | entry points | notes |
|---|---|---|
| Stream ledger (byte-weighted) | `content_units`, `stream_ledger`, `BaselineCorpus`, `build_baseline_corpus` | every OLE stream = 1 unit (prefix + all inflated members); every `Partitions/N` = `#host` unit + one `#uK`+GUID unit per embedded family save unit. Classification: whole-content sha1 identity (any baseline unit), exact same-named/same-GUID common prefix, and an **rsync-style block cover** — baselines indexed as aligned 4,096-B blocks (+256-B for OLE streams under 4 MB; partition units 4 KB only, keeping a 1.3 GB corpus index at ~29 MB) (weak checksum + blake2b), candidate scanned with a rolling weak hash at every offset (numpy prefix sums), strong-hash verified; low-entropy blocks excluded. Buckets partition each unit (identical + lineage-remainder + ours == inflated). Disk cache of baseline block indexes in `experiments/genesis/provenance/.cache/` (keyed size+mtime). |
| Multi-baseline union | `classify_elements_multi`, `provenance(doc, baselines=[...])`, CLI `--baseline` repeatable / `all` | v1 classifier per baseline; union precedence sample > modified > cloned > created > unmatched, tie-break by highest clone similarity; every verdict gets `attribution` + per-baseline `baselines` readings; report gains `multi_baseline_table` (per-baseline counts, derived-attribution histogram, created-max-similarity buckets). |
| Embedded-string provenance | `scan_resource_refs`, `resource_ref_report`, `RESOURCE_PATTERNS` | nine patterns (Forge `autodesk.*` typeIds, `forge-data-schema`, `autodesk.com`, `assetlibrary_base.fbx`, `SunAndSky`, `ADSK`, `%1!s!` MACH strings, `AREXContentGenerator` / `Revit Default DB Server`, bare `Autodesk`); NUL-collapsed buffer so ASCII + UTF-16LE hit in one pass; per stream/unit AND per host element; schema-stream hits tallied separately. |
| Identity policy | `identity_report`, `AUTODESK_EMPLOYEE_USERNAMES` | reads `rvt.identity` defaults: template author `Autodesk Revit` / `RevitApplication`, employee usernames (BFI or any DIT episode), template path in `last_save_path`, doc/episode GUID equal to any baseline's → blocking; non-product author → counsel-C1 advisory. |
| Honest G1 | `gate_G1` (extended), `GATE_LAYERS` | PASS iff zero derived elements ∧ zero identical bytes in EXPRESSION streams (`Global/Latest`, `Global/ContentDocuments`, save units) ∧ zero resource refs ∧ identity ours; `Formats/Latest` → `counsel` (C4), never a byte blocker; History/DIT/Contents/PartitionTable → `advisories`. `certifies_G1` true only when all four layers ran; an element-only PASS is labelled `NOT a G1 certification`. Element-layer blocking entries keep the v1 dict shape (no `layer` key) so v1 consumers/tests match exactly; the new layers carry `layer: streams|strings|identity`. |
| CLI | `tools/provenance.py FILE --baseline all --streams --json out.json` | `--streams --strings --identity` default ON (`--no-*` = v1 element-only); `--cache-dir`; exit `0` certified PASS / `2` FAIL / `3` partial-layer pass. Documented commands `--baseline all --streams` work verbatim. |
| Tests | `tests/test_provenance.py` | 22 (11 v1 unchanged + 11 v2): content-unit coverage (52 save units on rst, prefixed Latest), self-ledger = 100 % identical, bucket partition sums to 100 %, **G0 stream layer finds the sample ADocument** (Latest 1,586,254 identical, expression-bearing; schema separate; ~94 % excl. schema), resource scan ASCII+UTF-16, G0 refs > 5k Forge typeIds, identity flags rst's own template identity, G0's DIT username leak, multi-baseline union ≥ single + attribution, gate-v2 semantics (schema never blocks; partial layers don't certify; stream bytes / refs / identity each block), CLI multi-baseline e2e with cache. All green (~25 s). |

## Verification

* `.venv/bin/python -m pytest tests/test_provenance.py -q` → **22 passed**.
* Full suite `.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`
  → **531 passed, 1 failed** (10 min) — the ONE failure is the pre-existing
  one the auditor already recorded,
  `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`
  (plugin bundle drift on `lib/src/rvt/famgen/*` + `genesis/house_standard.py`
  — other streams' files; `tools/sync_plugin.py --check` confirms
  `provenance.py` is NOT in the drift list; fix = `python tools/sync_plugin.py`,
  outside my territory).
* This stream emits no `.rvt` (read-only instrument) → nothing for
  `tools/rvt_validate.py` to arbitrate; inputs are the existing genesis /
  sample files.
* No browser/viewer use (per orchestrator rules) — nothing here needs it.

## Diffs requested of other streams / the orchestrator

* **orchestrator:** run `python tools/sync_plugin.py` to clear the one
  failing (pre-existing) drift test — and note, per the auditor's B5, that
  what it bundles is a redistribution decision.
* **genesis-assembler:** regenerate `G0.rvt` through the current writer so
  its `Global/DocumentIncrementTable` is username-scrubbed (V32 mechanism)
  — the ledger will keep flagging the 22 employee usernames until then. Also
  the certified ledger run for every future G-milestone must be
  `--baseline all --streams` (the documented command), and the milestone's
  status doc should quote the byte-weighted headline, not the element count.
* **counsel list (via orchestrator):** C4 `Formats/Latest` byte-identical to
  all six samples (496,597 B); the 7,292 Forge `autodesk.unit/spec/…`
  typeIds + `forge-data-schema` corpus inside `Global/Latest` (leaves with
  the ADocument encoder, but the units-registry typeIds our OWN records emit
  (21) and `assetlibrary_base.fbx` / `SunAndSky` (43) are ours to decide);
  the `%1!s!` MACH load-label templates (24, Revit built-in UI resource
  strings) — interoperability-facts-vs-expression call.
* No exact-diff requested against any core module — v2 needed nothing
  outside `provenance.py` (it reads `container`, `partitions.StreamWalker` /
  `_inflate_member`, `stream_encoders.decode_*`, `identity.DEFAULT_AUTHOR`,
  `mutate.Document`, all read-only).

## Known limits (honest)

1. Block matching is 4 KB-granular for partition units (256 B for OLE
   streams < 4 MB): a shared byte-run shorter than one block that is not otherwise
   caught by whole-identity / common-prefix is not counted (under-count,
   never over-count). Whole-stream identity and ≥ 256 B same-named common
   prefixes are exact.
2. `identical_bytes` from block cover can include verbatim runs that are
   coincidentally common machinery (though low-entropy blocks are excluded);
   the `attribution` / `top_matched_units` fields let a reviewer check where
   each match came from.
3. Attribution for cloned elements picks the baseline with the HIGHEST
   similarity, which is the right answer for "whose product default did we
   reproduce" but is not necessarily the true-lineage baseline; both
   readings are kept per element (`baselines`).
4. The Autodesk-employee username list is the eight names observed in this
   corpus; another corpus would extend `AUTODESK_EMPLOYEE_USERNAMES`.
5. The resource-ref patterns are the audit's list plus close relatives; a
   G1c review should add any Autodesk artefact class counsel names.

## BRANCH STATE

* Repo is not git; files written this stream:
  `src/rvt/provenance.py` (v2 appended in place; v1 intact),
  `tools/provenance.py` (rewritten CLI, backward-compatible flags + old
  positional/`--baseline self` usage), `tests/test_provenance.py` (+11
  tests, 22 total, green), `docs/writer/provenance-ledger.md` (§0 v2
  correction; old headlines marked superseded),
  `experiments/genesis/provenance/G0_v2.json` + `G0_v2.txt` (the certified
  corrected run) + `.cache/` (baseline block indexes, ~regenerable),
  `docs/inbox/provenance-v2.md` (this record).
* G0's honest verdict: **G1 FAIL** on all four sub-gates — G1a 1,586,254 B
  ADocument stream blocker, G1b 154 clones + 25 high-similarity created,
  G1c 7,438 resource refs (88 in our records), identity 22 DIT usernames;
  **G1d (this instrument) DONE**. `certifies_G1=false` until an
  `--baseline all --streams` run reports zero on all four.
* No open blockers inside this stream's territory. STOP at READY.
