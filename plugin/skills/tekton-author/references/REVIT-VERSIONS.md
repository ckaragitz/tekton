# REVIT-VERSIONS — target release first: what each year honestly gets

Load this only when the user's answer to *"Which Revit year will open
this?"* is not one of the plain cases in `SKILL.md` step 0, or when they
ask why the year matters.

## The one-way rule (why the skill asks first)

A `.rvt` / `.rfa` opens in the Revit release that saved it **or a newer
one — never an older one**, and there is no "save as previous version".
So the recipient's year decides which base tekton builds on. Point
releases (2025.1 vs 2025.3) do not matter; the annual release does. If a
firm has mixed installs, **the oldest install wins**. IFC has no such
constraint (any Revit 2019+ links our IFC4), which is why an IFC is always
offered as an *addition* when the year is a problem — never as a silent
replacement for a requested `.rvt`.

## Per-release status (what `result.release.target_support` means)

| Year asked | `--target-version` | Built on | Honest status to state |
|---|---|---|---|
| **2026** | `2026` | `assets/genesis/G_ABPD.rvt` (certified, pinned) | `certified-base`: the composed base is certified by Autodesk's reader (ledger entry, verdict #24). THIS output: our validator 0 errors = *validated, not itself Autodesk-certified* until the recipient opens it. Opens in 2026+. |
| **2025** | `2025` | `assets/genesis/G_ABPD_2025.rvt` (certified, pinned) | `certified-base`, built natively in 2025 framing/schema inside the release context. Same two tiers. Opens in 2025 and 2026. Placed equipment carries the same open instance-audit residual as 2026 (stated in `build.degradations`). |
| **2024** | `2024` | `assets/genesis/G_ABPD_2024.rvt` (certified, pinned) | as 2025. Opens in 2024, 2025, 2026. **The safe default when a firm is unsure or mixed** — every supported Revit opens it. |
| **2023** | `2023` | — (format known: files read; no certified creation base yet) | `known-not-certified`: the run still DELIVERS the default-release build + `result.release.line` (relay verbatim: their Revit 2023 cannot open it) + a version-agnostic IFC beside it. Offer: the IFC now; a native 2023 `.rvt` when that base certifies. |
| **2022 or older / unknown** | the year as given | — | `not-supported`: same delivery as 2023 (default build + line + IFC). Say plainly that no supported target opens in their Revit; the IFC is the usable deliverable; `nearest_supported` in the result is only useful if *someone* on their side runs that year or newer. |
| **not stated** | omit the flag | default (2026) | `result.release.ask` reminds you: state "this file is Revit 2026; it will not open in an older Revit" and ask before promising. Prefer asking up front. |

The tool owns this table at runtime (`rvt.versions` + the pin registry):
if a release certifies later, the same command resolves its base and
`target_support` flips by itself — trust the JSON over this file.

## Existing files (`--rvt`, tekton-edit, extraction)

The release is **auto-detected** from the file (`go.inputs[].revit_release`
and `result.release.input_release`) and **kept**: an edit never up- or
down-grades. So the only question for the user is whether *they* can open
the input they gave you. Today the edit engine opens Revit **2026** project
files; a 2025/2024 input is detected and reported but the edit itself
fails with one clear line (release-aware editing is tracked as its own
issue) — say so, hand back nothing false, offer the create route at their
year instead.

## What to say, compactly

- match: "Built for Revit {output}; opens in {output} and newer. Base
  certified by Autodesk's reader; this file passed our validator (0
  errors) — please open it in your Revit / the free Autodesk Viewer to
  confirm acceptance."
- fallback: relay `result.release.line` **verbatim**, hand over the `.rvt`
  AND the `.ifc`, then the offer (IFC now / nearest supported year if
  anyone has it).
- Two tiers, always separate: *our validator PASS* vs *accepted by
  Autodesk* (only after they open it).
