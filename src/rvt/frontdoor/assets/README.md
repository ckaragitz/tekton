# rvt.frontdoor assets

## `genesis_base.json` — the pinned DEFAULT genesis base

The front door authors every `.rvt` ON A BASE, and the DEFAULT base is our
composed genesis project `G_ABPD` (docs/inbox/genesis-audit.md, ORCHESTRATOR
VERDICTS #24: *GENESIS LOADS* — settings / style catalog / palette / datum /
views / residue layers all our constructors' output, composed by
`tools/genesis_compose.py` with NO Autodesk-authored base content, and the
Autodesk viewer opens it as a browsable model).

The base is registered by a **documented resolvable path + a sha256 pin**
(no ~580 KB binary is copied into the package, so the plugin ships no large
data). `rvt.frontdoor.base.resolve_base()` looks in order at:

1. an explicit `--base PATH` (user's authority; **an Autodesk sample is
   refused**; the file is provenance-ledgered and never asserted certified);
2. `$RVT_GENESIS_BASE` (a firm's own certified base);
3. the pinned repo path `experiments/genesis/subst_k4/compose/G_ABPD.rvt`;
4. `<plugin-root>/lib/genesis/G_ABPD.rvt` if a packager bundles it.

For (3)/(4) the file's sha256 MUST equal the pin
(`84173b8960b8cbba…d06df50`); a mismatch is REFUSED (the pin is what makes
"certified genesis base" true) — re-pin only after re-certification.

## Per-release slots (`releases`) — the `--target-version` registry

`genesis_base.json` also carries one slot per Revit release the front door
can be ASKED to target (`tools/frontdoor.py author --target-version N`).
`2026` is the certified default above; `2025` is the **B2025 lineage**
(`G_ABPD_2025`, docs/writer/genesis-2025-plan.md) and `2024` the **B2024
lineage** (`G_ABPD_2024`, the same recipe re-run on 2024 format data —
genesis-audit verdict #28 proved it transfers), each with `status: "pending
certification"` and NO sha256 until its campaign certifies. A slot resolves
ONLY when three sources agree — slot `status: certified`, slot sha256 pin,
and `rvt.versions.KNOWN_RELEASES[N].creation_certified` — anything less
raises `BaseNotCertified` and the front door DEGRADES HONESTLY: it delivers
the certified default build plus one clear line plus a version-agnostic IFC
addition (`rvt.frontdoor.ifc_out`), never a silent wrong-release file.

The same file also pins the SPECIMEN ANCESTOR `R5`
(`experiments/genesis/R5.rvt`): the family-free genesis base carries no wall
/ instance specimen, so `rvt.mutate` clones scaffolding from the certified
ancestor (same lineage, ids continuous). The specimen is a clone TEMPLATE and
is never emitted into an output.

## `../PROMPT_TO_IFC.md`

The IFC-authoring instructions any AI surface follows to turn the front
door's `scene-brief.json` (or a raw prompt) into a Three.js scene exported as
IFC4 with OUR tagging-contract Psets — the PRIMARY prompt path. Copied into
every prompt job's output directory next to `HANDOFF.md`.

## `../SKILL.frontdoor.md`

The ready-to-drop skill body for the plugin (`plugin/skills/frontdoor/
SKILL.md`) — kept beside the engine so the existing `src/rvt/**` → `plugin/
lib/src/rvt/**` sync carries it; the packager promotes it into
`plugin/skills/`.
