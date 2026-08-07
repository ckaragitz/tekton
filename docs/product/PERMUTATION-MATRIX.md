# The Permutation Matrix — what tekton can route today

**The mandate** (user, verbatim intent): *“we should be able to create rvt
and rfa files from a prompt alone OR take an ifc file and turn into rvt OR
take a prompt and turn into ifc and then turn into rvt OR … think of any
permutation. the goal is to be able to handle any and all situations.”*

The design answer is a **routing matrix over composable stages**, not
per-route code:

- **Inputs** — any subset of `{prompt, ifc, rvt, rfa, spec}`
  (`spec` = the building/room spec JSON, `spec/building.schema.json`
  dialect; `rfa` = a family request: a **famspec** JSON `{"kind": …}` —
  see the rfa rows for the honest input contract).
- **Outputs** — one of `{rvt, rfa, ifc}`.
- **Machine truth**: `src/rvt/frontdoor/matrix.py` (`CELLS`/`STAGES`/`CHAINS`).
  `tools/route.py matrix` prints the live table **and self-audits every
  evidence citation** (test paths exist; every `certified:` ref is really
  in `docs/coverage/viewer-certified.json`). `tests/test_router.py` fails
  the suite if any claim goes stale. This document is the rendered copy.
- **Router**: `rvt.frontdoor.router.route(inputs, output, **opts)`,
  CLI `tools/route.py run`. It composes the *existing* certified stages —
  it adds no authoring logic of its own. Anything not in the table comes
  back as **one clear line** (the matrix row + the closest supported
  route), never a traceback.
- **Deliverable rule**: gates are labels. Every route **delivers** its
  output file plus *every* intermediate (intent JSON, IFC, families,
  underlying manifests) plus a route manifest (`route.json` / `ROUTE.md`)
  with stamps, caveats and the evidence cited — caveats ride **after**
  delivery, never instead of it.

Status vocabulary — honest per cell:

- **works** — runnable end-to-end today; runnable evidence cited.
- **partial** — the mechanism runs with a *named* caveat/scope gap.
- **missing** — not implemented; the router answers with the clear line.

## Single inputs (all 15 cells enumerated)

| in → out | status | route (stages) | evidence (cited by the machine matrix) | honest caveats |
|---|---|---|---|---|
| prompt → rvt | **works** | `prompt_to_rvt` (prompt→intent, handoff, intent→rvt on the certified genesis base) | worked `experiments/frontdoor/prompt-electrical-room/`; `tests/test_frontdoor.py`; certified walls-only + `stage_L8_lp4` shapes | walls+families in one file = OPEN BUG (r2): combined file **stamped**, `--strict` splits into two certified-shape files; circuits are a named blocker (plan delivered, never faked); PROOF-ONLY until G2/G3 |
| prompt → ifc | **works** | `prompt_to_ifc` (prompt→intent, intent→ifc) | `tests/test_target2025.py` round-trips the emitter against our own resolver | IFC is version-agnostic; re-enters via `--ifc` |
| prompt → rfa | **works** | `prompt_to_rfa` (prompt→intent, intent→rfa) | worked families dir; `tests/test_famgen_factory.py` | catalog-backed kinds only (panelboard / transformer / luminaire / honest house switchboard); anything without facts is refused by name |
| ifc → rvt | **works** | `ifc_to_rvt` (ifc→intent, intent→rvt) | **certified** `V25_room_from_ifc.rvt`, `V26_room_from_ifc_with_walls.rvt`; worked `ifc-electrical-room-2500a/` | same open-bug/circuits/PROOF-ONLY caveats; a *product* IFC auto-falls back to the family chain (below) |
| ifc → ifc | **works** | `ifc_normalize` (ifc→intent, intent→ifc) | `tests/test_target2025.py`, `tests/test_ifc_intent.py` | normalisation into our tagging-contract dialect; content outside the resolved intent does not survive |
| ifc → rfa | **works** | `ifc_to_rfa` (room: intent→rfa; product: ifc→facts→rfa) | **certified** `L_downlight_loaded.rvt`; `tests/test_ifc_family.py` | room IFCs → catalog families for tagged equipment; product IFCs → the measured **downlight archetype** (the one facts→rfa archetype wired) |
| rvt → rvt | *missing* | — | — | an .rvt alone is a no-op copy; an edit needs instructions → use **prompt+rvt** |
| rvt → ifc | *missing* | — | — | no RVT→intent resolver yet (we read/inventory .rvt, we don’t lift geometry back to intent); inspect with `tools/rvt_edit.py info` |
| rvt → rfa | *missing* | — | — | family extraction not implemented — and extracting third-party families would redistribute vendor bytes (content rule); our families are regenerable from plans |
| rfa → rvt | **works** | `famspec_load` (facts→rfa, four-registry load) | **certified** `L1a_rstbasic_loaded_levelhead.rvt`, `L_downlight_loaded.rvt`; `tests/test_famload.py` | **input contract**: a famspec JSON (`{"kind": "downlight", …}`) — the family is *rebuilt by its constructor* and loaded; a bare foreign `.rfa` path is refused with this row (no .rfa-from-disk reload yet); default host = the loader-certified rst host |
| rfa → ifc | *missing* | — | — | no family→IFC emitter; author the product IFC from facts instead |
| rfa → rfa | *missing* | — | — | family modification needs instructions and no family-edit pipeline exists (see prompt+rfa) |
| spec → rvt | **works** | `spec_to_rvt` (**chain** spec→ifc→intent→rvt on the genesis base) | **certified** `V23_electrical_room.rvt` (legacy direct); worked `usecases/chicago-plenum…/generated.ifc`; `tests/test_job.py` | the legacy direct build (`tools/rvt_job.py create --spec`, template project) remains as **spec+rvt**; open-bug/PROOF-ONLY caveats ride |
| spec → ifc | **works** | `spec_to_ifc` (deterministic generator) | worked `usecases/…/generated.ifc`; `skills/tekton-ifc/tests` | identical spec → byte-identical IFC |
| spec → rfa | **works** | `spec_to_rfa` (chain spec→ifc→intent→rfa) | worked families dir; `tests/test_famgen_factory.py` | the spec’s *tagged* equipment maps to catalog family plans; catalog scope as above |

## Combinations

| in → out | status | route | evidence | honest caveats |
|---|---|---|---|---|
| prompt + rvt → rvt | **works** | `rvt_edit` (the certified edit pipeline: modify / move / retype / delete / cascade, NL or ops.json) | **certified** `M3_modify`, `M4_move_retype`, `M2_delete_cascade`, `M2_delete_cascade_rac` (foreign file); worked `rvt-edit-room/` | the prompt is the *edit*; an authoring-shaped prompt falls back to building **on your .rvt as base** — that branch is *partial* (gates run, no viewer certification on arbitrary bases). Known blocker: rename/set-mark on *our created* instances (no param rows yet) |
| ifc + rvt → rvt | *partial* | `ifc_onto_rvt` (merge: the IFC intent built with your .rvt as base) | stage evidence + `tests/test_frontdoor.py` | certified stage code + all gates run on *your* base; viewer certification exists only for the genesis base; Autodesk samples refused |
| prompt + rfa → rfa | *missing* | — | — | family modification (open an .rfa, apply a prompt, re-emit) is not built; regenerate from changed facts: prompt→rfa |
| rfa + rvt → rvt | *partial* | `famspec_load` (load into **your** project) | **certified** L1a / L_downlight (rst host), `stage_L8_lp4` (genesis lineage) | four-registry mechanism + census/validator gates run on arbitrary hosts *without* viewer evidence; famspec contract as above (`downlight` wired; catalog kinds load via the room pipeline) |
| prompt + ifc → rvt | *partial* | `ifc_build_then_edit` (build the IFC, then apply the prompt as an edit) | composition of two proven stages | a non-edit prompt cannot merge into the IFC’s intent yet (intent-level merge unbuilt) — the route fails with the edit grammar rather than guessing |
| spec + rvt → rvt | **works** | `spec_on_rvt_seed` (`tools/rvt_job.py create --spec --base`) | **certified** `V23_electrical_room.rvt`; `tests/test_job.py` | your .rvt is the seed/template: seed audit + hard gates; output ledgered against that seed (PROOF-ONLY vs what you supply) |

**Anything else** (e.g. `prompt+spec → rvt`, `rvt → ifc`, any output for an
unlisted combination): the router returns the matrix row and the closest
supported route in one line, exit code 4 — never a traceback.

## Chains (selectable with `--via`, or implicit)

| chain | status | how | evidence |
|---|---|---|---|
| prompt → ifc → rvt | **works** | `route --output rvt --prompt … --via ifc` — the handoff round trip run in-process (intent → our IFC → re-resolved → build) | `tests/test_target2025.py` + demo `experiments/routes/demo3-prompt-via-ifc-rvt/` |
| spec → ifc → rvt | **works** | the canonical `spec → rvt` route | see spec→rvt row |
| ifc → rfa → loaded-rvt | **works** | `--via family` on ifc→rvt, and the automatic product-IFC fallback | **certified** `L_downlight_loaded.rvt` |
| prompt → rfa → loaded-rvt | **works** | the F/L stages *inside* prompt→rvt (families generated, loaded, placed) | **certified** `stage_L8_lp4.rvt` |

## Demonstrated end-to-end (2026-08-04, this stream)

All five live under `experiments/routes/` with `route.json` + `ROUTE.md`:

1. `demo1-prompt-to-rfa` — prompt → **2 .rfa** (validator VALID, provenance ok), 3 s.
2. `demo2-spec-to-ifc` — room-spec → IFC4 (657 entities, deterministic), 0.3 s.
3. `demo3-prompt-via-ifc-rvt` — **the chain** prompt → IFC → .rvt on the
   genesis base (open-bug stamp riding the combined file), 23 s.
4. `demo4-rfa-loaded-rvt` — **the combination** famspec → .rfa → four-registry
   **loaded** .rvt (project validates 0 errors), 35 s.
5. `demo5-prompt-rvt-edit` — prompt+rvt edit (move + cascade delete), hard
   gates PASSED, 1.8 s.

## The named gaps (what would flip cells)

> In flight at time of writing: the `rvt.convert` streams
> (`docs/inbox/convert-b.md`) are landing implementations for several of
> these gaps (add-into-project, ifc merge, family modify, rvt→ifc,
> family extract, .rfa reload). Cells flip here — with their evidence
> cited and self-audited — when those records close; until then the
> statuses below are the proven truth.

- **RVT→intent resolver** — unlocks rvt→ifc, rvt→rvt re-authoring, true
  ifc+rvt merge semantics, prompt+ifc intent merge.
- **.rfa-from-disk reload** (.rfa → FamilyDoc reconstitution) — unlocks
  bare-.rfa loads and the family-edit pipeline (prompt+rfa).
- **Standalone catalog-kind loads** (famload for panelboard/transformer/
  luminaire outside the room pipeline) — flips rfa cells from scoped to full.
- **Open bug r2** (walls+families in one file) — removes the stamp from
  every combined build.
- **Instance param rows on created instances** — unlocks rename/set-mark
  edits on our own output.
- **G2/G3 gates** — flip PROOF-ONLY to DELIVERABLE everywhere.
