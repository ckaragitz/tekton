---
name: tekton-native
description: "Author, edit, inspect and validate NATIVE Autodesk Revit .rvt files with the bundled reverse-engineered `rvt` engine (pure Python; install once with `pip install ./lib` from the plugin root). Use whenever the user has an actual .rvt (not IFC) and wants to open/inspect it (streams, class schema, elements, tables), make a proven content edit (e.g. change text such as a title, panel name or note and re-emit a file Autodesk still opens), re-write a .rvt end-to-end, or run the mandatory pre-delivery self-checks (gzip CRC, per-page ECC, block walker, record stamps) before an Autodesk-Viewer acceptance test. Also the entry point for the in-progress element-creation API (add_wall / add_family_instance). For IFC authoring/validation/hardening use the sibling tekton-ifc skill instead. Always states which capabilities are viewer-proven vs in-progress and never overclaims."
---

# tekton-native — read, edit and validate native `.rvt` files

The engine-level skill over the bundled **`rvt` engine** (pure Python;
Autodesk-proven reader/writer). `<plugin>` below means this plugin's root
(the folder containing `.claude-plugin/`); this file is
`<plugin>/skills/tekton-native/SKILL.md`. Despite the description's
install note, NO pip install is needed: the launcher below puts the
bundled engine on the path by itself. For CREATING a new project/room from
a prompt, IFC or spec, the flagship route is the **tekton-author** front
door; for surgical element edits, **tekton-edit**; for QA,
**tekton-inspect**. This skill is for engine-level work on a real `.rvt`:
stream/schema/record inspection, the proven size-preserving text edit, and
the four self-checks.

## THE DELIVERABLE RULE (non-negotiable)

When the user asks for a `.rvt` or `.rfa` and one can be produced, **write
it and hand it to the user — always.** Self-check results, PROOF-ONLY
stamps and status labels ride WITH the file, **never as refusal logic**:
deliver first, then state the caveats plainly. The only acceptable
non-delivery is a job that is genuinely impossible, reported as ONE clear
line naming the single missing input. Never substitute IFC for a requested
`.rvt` — offer IFC as an addition, not a replacement.

## Version reality — ask FIRST on any creation request

**"Which Revit year will open this — 2026, 2025, 2024, or older?"** — ask
before any new `.rvt` is made (Revit cannot open a file saved by a newer
release) and pass the answer as `--target-version YEAR` to the
**tekton-author** front door: 2026 / 2025 / 2024 build natively on that
year's certified base (opens in that year and newer); an older year still
DELIVERS the default build plus one clear line and a version-agnostic IFC
addition — never a silent substitute. An EDITED or inspected file keeps
its input's release (never up-/down-graded); `go` auto-detects it
(`go.inputs[].revit_release`) — state it with every result.

## Step 1 — readiness (ONE command, <2 s)

```bash
python <plugin>/skills/tekton-native/scripts/_bootstrap.py
```

`tekton: READY | …` → proceed straight to the job. `NOT READY` → relay the
line verbatim. No pip install, no venv, no `eval`, no task boards, no
exploratory shell. Never read, probe, list, or request access to any
Autodesk installation directory (the Windows program / program-data
Autodesk trees, /Applications/Autodesk, Autodesk family-template folders);
any donor/template file comes from the plugin's own assets or from the user.

## Step 2 — the job (ONE command; its output IS your report)

```bash
# what is in this file: streams, schema summary, decoded records
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run rvt_inspect.py \
    model.rvt [--classes Wall] [--records 20] [--dump-schema out/schema.json]

# the PROVEN size-preserving content edit (title, panel name, note …)
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run rvt_edit_text.py \
    in.rvt --old "OLD TEXT" --new "NEW TEXT" -o out/edited.rvt
#   --new must be the SAME byte length as --old (the script refuses otherwise);
#   --utf16 for UTF-16LE strings (most Revit names/notes; auto-fallback tries both)

# the four self-checks — MANDATORY on every .rvt before it leaves your hands
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run rvt_selfcheck.py \
    out/edited.rvt --json out/selfcheck.json     # exit 0 PASS · 1 FAIL · 2 not a .rvt

# the full 3-layer validation gate / element edits / seed audit / schedules
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run rvt_validate.py out/edited.rvt
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run rvt_edit.py in.rvt info
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run seed_audit.py template.rvt --job job-spec.json
python <plugin>/skills/tekton-native/scripts/_bootstrap.py run panel_schedule.py --spec electrical-job.json --out schedules/
```

Relay the command's printed report as the deliverable summary. For
`rvt_edit_text.py`: deliver on `SELF-CHECK PASS`, then say "the file passed
our self-checks; the next gate is opening it in the Autodesk Viewer / your
Revit — please confirm." For `rvt_selfcheck.py`: all four failure counts
must be zero (gzip CRC · page ECC · block walker · record stamps); a single
ECC mismatch means Autodesk's reader will reject the file.

## Capability status (say it plainly, with the delivery)

- **PROVEN** (accepted by Autodesk's own reading pipeline): read/decompose
  any `.rvt`; whole-file re-write with real ECC; size-preserving content
  edits (our text renders on Autodesk's title sheet); element creation
  proofs V20–V22 (created column, batch, wall); element edit/move/retype/
  delete on real files.
- **VERIFIED** (byte-exact against real files): schema-from-file (the
  class map parses from ANY release's `Formats/Latest`), object codec
  (99.69% of corpus records; 100% on electrical/MEP), small-table codecs.
- **In progress**: wall render (LOAD vs RENDER); circuits on pre-existing
  elements. Full creation runs from bundled assets alone — the family
  container and the wall/instance templates come from the bundled genesis
  base; families are self-generated, no donor or specimen file is
  needed (`--specimens` is an expert override). State the caveats WITH
  the file, never as a reason to hand over nothing.

## Engine facts for programmatic work (the load-bearing rules)

- Always decode from `doc.logical(name)` (de-paged) — raw streams are
  64,896-byte pages each followed by a 353-byte ECC trailer.
- Element data: `Partitions/<N>`, three parallel record streams (seq 101
  header / 102 object / 103 geometry), keyed by ElementId;
  `Global/ElemTable` is the index; History/DocumentIncrementTable/
  BasicFileInfo carry save bookkeeping.
- After touching any record: recompute the stamp
  (`adler32(u16 class_id + object)`), recompress with
  `gzip_member(level=3, sync_flush=True)`, keep block `B` fields and the
  `0x0f21` mirror consistent, re-frame with `ecc.frame_stream` (never
  copy/zero trailers), rebuild the CFB with `write_cfb`.
- Never ECC-frame the raw metadata streams (`BasicFileInfo`,
  `ProjectInformation`, `RevitPreview4.0`, `TransmissionData`).
- Keep the sentinel record last; seqs 101/102/103 carry identical
  ElementId sets.
- Never overwrite the input file; write to a new path.
- Schema-from-file: `schema.parse(doc.concat("Formats/Latest"))` — no
  schema blob ships; every file carries its own.

## Reference

| Path (under `skills/tekton-native/`) | What |
|---|---|
| `scripts/_bootstrap.py` | readiness line · `run <script> …` launcher · `doctor` |
| `scripts/rvt_inspect.py` | container + schema-from-file + decoded record sample |
| `scripts/rvt_edit_text.py` | the proven size-preserving edit pipeline, self-verifying |
| `scripts/rvt_selfcheck.py` | the four self-checks; the pre-delivery gate |
| `scripts/rvt_validate.py` · `scripts/rvt_edit.py` | full validation gate · element edit CLI |
| `scripts/seed_audit.py` · `scripts/panel_schedule.py` · `scripts/spec_to_rvt.py` | seed readiness · schedules/load calcs · spec→rvt |
| `<plugin>/lib/` (`rvt` package) + `lib/README.md` | the engine and its API map |
| `references/status-and-evidence.md` | the acceptance ledger (what each proof proved) |
| sibling skills | **tekton-author** (create) · **tekton-edit** (edit) · **tekton-inspect** (QA) · **tekton-ifc** (IFC) |
