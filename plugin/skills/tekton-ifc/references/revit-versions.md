# Revit version compatibility — the rules, the checks, and the free validation options

Evidence tags: **[docs]** Autodesk help / IFC Manual / KB; **[src]** the
open-source IFC add-in; **[aps]** Autodesk Platform Services docs;
**[unverified]** could not confirm — do not assert to users.

---

## TL;DR

1. **A `.rvt` opens only in the Revit release that saved it or a NEWER one.
   Never older.** There is no "save as previous version" — Autodesk states
   Revit "does not have a feature to save to older version data formats or
   work with the newer RVT file format in an older version". Opening in a
   newer release *upgrades* the file (one-way). [docs]
2. **Therefore any `.rvt` we generate must target a release ≤ the brothers'
   installed Revit.** Their version is still `[open]` (samples/schema here are
   2026). Ask before ever shipping a `.rvt`.
3. **IFC has no such constraint.** Any supported Revit release links our IFC,
   and the intermediate `<name>.ifc.RVT` is created *by their own Revit*, so
   it is automatically their version. This is the primary reason IFC is the
   default deliverable. [docs]
4. **Schema support:** *Open IFC* = IFC2x3/2x2/2x only; *Link IFC* = those +
   IFC4 (all releases here) + IFC4.3 (experimental 2023.1/2024, proper from
   2025). We export IFC4 — always linkable, never openable natively. [docs]
5. **No-Revit validators:** Autodesk Viewer web (free, accepts IFC + RVT) and
   the APS Model Derivative API prove the file parses/renders in Autodesk's
   toolchain — they do **not** prove Revit-native categories, parameter typing
   or editability. Only Revit (a 30-day trial, or the brothers' seat) proves
   the Revit-specific behaviour; Revit's free *viewer mode* can review but has
   save/export blocked. [docs; aps]

---

## 1. The one-way version rule

- "While Revit can open older version files, Revit cannot open a model that
  was saved by a newer version (for example a model saved in Revit 2022 cannot
  be opened in Revit 2021)." The error is *"The file … was saved in a later
  version of Revit and cannot be retrieved in this version."* [docs KB]
- "If a model is created, saved or modified using the current release … it
  cannot be opened or converted or downgraded to a previous Revit version."
  [docs KB "Is it possible to convert or downgrade an RVT file"]
- Practical corollaries for us:
  - The **`.ifc.RVT`** the link importer creates is written by the *user's*
    Revit ⇒ always their version ⇒ never a compatibility problem. Do not ship
    one we generated on a newer release.
  - The **firm's oldest install wins**: if anyone in the office is a release
    behind, coordination `.rvt`s must not be saved forward past it (they can
    no longer open the upgraded file). State this in every delivery report.
  - Point releases (2024.2 vs 2024.3) are compatible with each other; the
    breaking boundary is the annual major release.
  - Downgrade "workarounds" all lose data (IFC round-trip, DWG, etc.) — never
    promise one; the only clean path is having the right release.

## 2. How to tell which release saved a file

- **Without opening Revit:** every `.rvt`/`.rfa` stores a UTF-16
  `BasicFileInfo` stream in its OLE container. Open the file in Notepad and
  search for `F o r m a t` (or `B u i l d`) — the wide-char text
  `Format: 2026` / `Build: 20250227_1515(x64)` is the answer. [docs KB "How
  to check from which version a Revit file comes from before opening it";
  KNOWLEDGE.md — our corpus files read `Format: 2026`]
- **With our tooling:** `rvt` already parses `BasicFileInfo` (`src/rvt/meta.py`,
  the `--params` report) — build the "which release is this?" check into the
  skill so users never guess.
- **In Revit:** attempting to open an older file shows a *"Model Upgrade"*
  dialog naming the source release; opening a newer one shows the error above.
  Revit's *Help ▸ About* tells you the *installed* release/point-update (this
  is what to ask the brothers for). [docs]
- **In the cloud:** APS/BIM 360 report the model's Revit version via the
  Automation API / Model Derivative metadata. [aps blog]

## 3. IFC schema support by Revit release (import side)

Autodesk's wording, identical in the 2023 and 2026 help: "For import (to open
or link an IFC file), Revit supports IFC files based on … IFC2x3, IFC2x2, and
IFC2x. For import (link only), Revit also supports … IFC4." [docs "About
Revit and IFC"] Plus the IFC Manual on 4.3.

| Schema | Open IFC (native conversion) | Link IFC | Notes |
|---|---|---|---|
| IFC2x / IFC2x2 | ✅ all releases | ✅ | Legacy; do not author. |
| **IFC2x3** (CV2.0) | ✅ all releases | ✅ | The only schema the Open route fully supports. |
| **IFC4** (RV / DTV) | ❌ (opens with `IFCPartialSchemaSupport` warning; effectively unsupported) [src `IFCImportFile.Import`] | ✅ all releases 2019–2026 | **What we export.** Link-only by design. |
| IFC4x1 / 4x2 (alignment RCs) | ❌ | recognised by the importer's schema enum [src `IFCSchemaVersion.cs`] | Infrastructure candidates; irrelevant to us. |
| **IFC4.3** (ADD2 = ISO 16739-1:2024) | ❌ "Opening IFC 4.3 Files in Revit is NOT supported" | 2023.1/2024: *experimental* — `IFC4X3_ADD2` headers can fail in 2024 (workaround: latest IFC add-in from GitHub, or edit the header to `IFC4X3_RC4`); **2025+: supported** ("Revit 2025 can read the IFC4X3_ADD2 format and link the file properly") | [docs IFC Manual "IFC 4.3 Support"; KB "Unable to link IFC 4x3 file into Revit"]. We stay on IFC4 — no reason to touch 4.3. |

Export side (for reference): IFC2x2, IFC2x3 (Coordination View 2.0 —
certified), IFC4 (Reference View — certified; Design Transfer View), IFC4.3
(experimental 2023.1+, official ADD2 export from 2025). "Revit provides fully
certified IFC import and export based on buildingSMART® IFC data exchange
standards." [docs "About Revit and IFC"; docs "Exporting to IFC"]

The IFC engine is a **separately-updatable add-in** ("IFC for Revit 20xx",
Autodesk Desktop App / GitHub `Autodesk/revit-ifc` releases). Autodesk
supports "the most current annual version and two previous versions" with
fixes [src README]. If a user hits an import bug, updating the add-in (not
Revit) is the first fix — worth a line in the delivery report.

Import-engine differences across our four target releases (all still
DirectShape-based; see `revit-import-fidelity.md`):

| Release | Link IFC engine | Notable |
|---|---|---|
| 2023 | Legacy open-source importer | IFC4.3 link experimental from 2023.1. |
| 2024 | Legacy by default; **2024.1+** switches to the new AnyCAD-assisted processor by default (`Revit.ini [ImportIFC] LinkProcessor=Legacy` reverts) | "more advanced geometric fidelity and stability, but may reduce performance" [docs "Link an IFC File"; Revit API `ImportIFCOptions.LinkProcessor`: Default/Legacy/AnyCAD] |
| 2025 | New processor default; IFC4.3 ADD2 link supported; ~50 % faster IFC export; `IfcMaterial` shared parameter on Open; export Category Mapping templates dialog | [docs IFC Manual "New in Revit 2025"] |
| 2026 | Up to 50 % faster linking; **link positioning options** (Auto - Origin to Origin default, By Shared Coordinates); large-coordinate handling | [docs IFC Manual "New in Revit 2026"; docs "Link an IFC File"] |

## 4. Validation options that don't need a paid Revit seat

### 4.1 Revit itself, free, two ways

- **30-day free trial** — full functionality, expires after 30 days, not
  extendable, generally no credit card. This is the only free way to *prove*
  the full round trip (link, categories, parameter typing, schedules, tags)
  yourself. [docs autodesk.com/products/revit/free-trial]
- **Revit viewer mode** — launched from the Start-menu "Revit Viewer"
  shortcut or `Revit.exe /viewer`; runs with no licence. It "allows you to
  open and review models" and print, but **Save/Save As and all data exports
  (DWG/IFC/gbXML/family types) are disabled**, and print/DWF export also lock
  once you modify anything. [docs "About Revit Viewer"] For us: it can *open*
  an existing `.rvt` and inspect what an import produced, and read the
  `.ifc.log.html`; but **Link IFC in viewer mode is [unverified]** — linking
  must create and save the intermediate `.ifc.RVT`, which the save block likely
  prevents. Assume the trial (or the brothers' seat) is needed for the import
  test itself; use viewer mode only to review a `.rvt` someone else produced.
- (Revit LT also links and opens IFC — its help pages carry the same Link IFC
  topic — should the brothers turn out to run LT.) [docs]

### 4.2 Autodesk Viewer (web) — `viewer.autodesk.com`

- Free with an Autodesk account; upload up to ~50–80 file types including
  **`IFC` and `RVT` (Revit 2015 or later)**; view, measure, section, share,
  comment; uploads are stored 30 days by default. [docs Autodesk Viewer
  "Supported File Types"; docs Viewer landing/KB — free tier confirmed]
- **What it proves:** the IFC parses and translates in Autodesk's cloud
  toolchain (the same Model Derivative pipeline that backs the AnyCAD import
  engine); geometry, placements and the spatial tree look right; property
  panel shows the psets. Great smoke test before bothering anyone with Revit.
- **What it does NOT prove:** Revit category assignment, DirectShape vs
  native, parameter data types, shared-parameter binding, schedules/tags,
  editability, MEP behaviour. It is a viewer, not Revit.

### 4.3 APS Model Derivative API (programmatic translation)

- Translates IFC/RVT (and 60+ formats) to the SVF/SVF2 viewing format plus a
  property database — i.e. an automatable version of the Viewer smoke test
  (script it into the harden pipeline; parse the manifest/properties to
  assert element counts, class names and pset presence). [aps]
- **Cost — current model (effective 8 Dec 2025):** Model Derivative is one of
  four "rated" (metered) APIs. Charged in Flex **tokens per translation
  job — 0.5 token per "complex" job, 0.1 per "simple" job — and RVT/IFC
  translations count as complex**; non-translation API calls ≈ 1 token per
  300 000 calls. Every rated API includes a **free monthly tier** before
  charges apply; beyond it you buy Flex tokens (prepaid, minimum purchase 100,
  expiring in a year) or Pay-As-You-Go in select regions. [aps "APS Business
  Model Evolution" blog + pricing explainer]
  **Exact free-tier allowance and the USD price of a token were not
  retrievable from the pricing page — verify at aps.autodesk.com/pricing
  before quoting any number to the user.** For our volume (a handful of
  translations per project) the free tier is very likely sufficient
  [unverified — check the current allowance].
- Requires an APS app (Client ID/secret) — the brothers' work Autodesk account
  or ours; storage via OSS bucket. Subject to their IT policy.

### 4.4 APS Design Automation for Revit (Automation API) — the headless *Revit*

- Runs real Revit engines in the cloud with our add-in bundle: the sanctioned
  headless route both for **producing a genuine `.rvt`** (Tier 2: place
  families, set shared parameters, build circuits) and for **running the real
  IFC importer** without a desktop seat.
- **Version targeting is explicit:** you choose the engine
  (`Autodesk.Revit+2023` / `+2024` / `+2025` / `+2026`), so we can emit a `.rvt`
  in exactly the brothers' release once we know it — the version rule (§1)
  is solved by engine choice.
- Also a rated API (charged by processing time under the new model); needs
  the same APS credentials. [aps]

## 5. What to tell the user, every time

- "IFC works with any Revit 2019+. The `.ifc.RVT` your Revit creates is your
  version automatically."
- "If you ever want a real `.rvt` instead: tell us your exact release
  (Help ▸ About), and remember it can't be opened by anyone on an older
  release."
- "You can check any Revit file's version without Revit: open it in Notepad,
  search `F o r m a t`." (Or run our tool.)
- "Free ways to check our output before it hits your model: Autodesk Viewer
  (upload the IFC) for geometry/data, or a 30-day Revit trial for the full
  test."

---

## Sources

- Backward compatibility / no save-down [docs, Autodesk KB — bodies 403 to our
  fetcher, statements quoted from search results]:
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Backwards-compatibility-of-Revit-with-earlier-releases-of-the-software.html ;
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/The-file-filename-rvt-was-saved-in-a-later-version-of-Revit-and-cannot-be-retrieved-in-this-version-when-opening-a-Revit-model.html ;
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Convertion-or-downgrade-of-file-into-older-former-version-of-Revit.html
- Check a file's version without opening (Notepad "Format"/"Build";
  BasicFileInfo): https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-check-from-which-version-Revit-file-comes-from-before-open-it.html ;
  https://revitiq.com/check-revit-file-version/ ;
  Jeremy Tammik (Autodesk), RVT version via BasicFileInfo:
  https://jeremytammik.github.io/tbc/a/1570_rvt_version_py.html ;
  APS blog: https://aps.autodesk.com/blog/check-version-revit-file-using-design-automation-api
- Supported IFC schemas import/export (2023 & 2026, identical text):
  https://help.autodesk.com/cloudhelp/2023/ENU/Revit-DocumentPresent/files/GUID-6708CFD6-0AD7-461F-ADE8-6527423EC895.htm ;
  https://help.autodesk.com/cloudhelp/2026/ENU/Revit-DocumentPresent/files/GUID-6708CFD6-0AD7-461F-ADE8-6527423EC895.htm
- IFC 4.3 support & workarounds: https://autodesk.ifc-manual.com/revit/advanced-topics-and-best-practices/ifc-4.3-support ;
  KB "Unable to link IFC 4x3 file into Revit"
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Unable-to-link-IFC-4x3-file-into-Revit.html
- New link processor (2024.1+) & positioning (2026): "Link an IFC File" 2026
  https://help.autodesk.com/cloudhelp/2026/ENU/Revit-Model/files/GUID-DE8B322A-A507-4E03-93EC-AA21F354E43B.htm ;
  Revit API `ImportIFCOptions.LinkProcessor`
  https://www.revitapidocs.com/2025.3/898d7fa7-94d7-0010-1148-2de2d741fa1c.htm ;
  IFC Manual "New in Revit 2025/2026"
  https://autodesk.ifc-manual.com/revit/new-in-revit-2025 ,
  https://autodesk.ifc-manual.com/revit/new-in-revit-2026
- Open-source importer schema enum & Open-route partial-schema warning [src]:
  https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Import/Enums/IFCSchemaVersion.cs ;
  https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Import/Data/IFCImportFile.cs ;
  README support policy: https://github.com/Autodesk/revit-ifc#readme
- Revit trial: https://www.autodesk.com/products/revit/free-trial
- Revit viewer mode: https://help.autodesk.com/cloudhelp/2022/ENU/Revit-GetStarted/files/GUID-9577CB78-34FD-4AFB-8E92-3C8E2890CCB4.htm ;
  KB "How to use Revit in Viewer Mode"
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-use-Revit-Viewer-Mode.html
- Autodesk Viewer supported types (IFC + RVT 2015+):
  https://help.autodesk.com/cloudhelp/ENU/ADSKVIEWER-Help/files/ADSKVIEWER_Help_SupportedFileTypes_html.html ;
  https://viewer.autodesk.com/
- APS business model & Model Derivative token charging (0.5/0.1 tokens per
  complex/simple job; RVT/IFC = complex; free monthly tier; effective
  8 Dec 2025): https://aps.autodesk.com/blog/aps-business-model-evolution ;
  pricing page (verify allowances/token price): https://aps.autodesk.com/pricing
