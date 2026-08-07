# REVIT CHECK KIT -- one desktop-Revit session, two files, ~10 minutes

**Why you are being asked.**  Autodesk's cloud viewer rejects our generated
files with an opaque "Processing failed" -- it never says WHY.  Desktop
Revit shows the SPECIFIC warning/error dialog.  One open attempt per file
below tells us more than another ten cloud probes.

**Files in this folder** (copies; originals under experiments/):

1. `BXhf_f1i1.rvt` -- OUR generated family + one placed instance (the
   product shape: what tekton actually ships).
2. `H12.rvt` -- the all-native-copy probe: an untouched Autodesk sample
   project plus ONE re-embedded copy of its own concrete-column family
   (famdoc bytes, inline registry document and host elements are literal
   byte-copies of Autodesk's own) plus one placed instance.  Every decoded
   record is native-shaped; only our container envelope + registration
   differ.  The cloud viewer rejects this file too -- the terminal mystery.

**What to do with EACH file (H12.rvt first):**

1. Open Revit (2026 if available; a newer release is fine -- it will
   offer to upgrade; an OLDER release cannot open these, stop there).
2. File > Open > the .rvt.  **Screenshot every dialog that appears**, in
   order, before clicking anything.  Then click through (OK / Close).
3. If it opens: Manage tab > Inquiry > **Warnings** -> Export or
   screenshot the full list.
4. Project Browser > Families > Structural Columns: does
   "M_Concrete-Square-Column H9 (or similar)" exist?  Open a 3D view: is
   a column visible near the origin?  Screenshot.
5. Try File > Save As (new name).  Screenshot any dialog.
6. If Revit CRASHES: screenshot the crash/journal dialog and grab the
   newest file from %LOCALAPPDATA%/Autodesk/Revit/<version>/Journals.

**What each outcome tells us:**

| outcome | reading |
|---|---|
| H12 opens clean, column visible | the cloud viewer's audit is stricter than Revit itself; the defect is a viewer-side ingest rule -- we chase the viewer, not file validity |
| H12 opens with a SPECIFIC warning dialog | that dialog names the audit's objection verbatim -- send the screenshot; it is the fix spec |
| H12 refuses with "file is corrupt" + detail | the detail line (element id / table name) localises the defect |
| H12 crashes | journal file names the failing subsystem |
| BXhf same-vs-different from H12 | same dialog => one shared root cause; different => our generated famdoc has an ADDITIONAL defect beyond the terminal one |
| both open clean in desktop Revit | ship-blocking only for cloud-viewer workflows; deliverable rule already stamps files -- record it |

**Safety / provenance**: both files are PROOF-ONLY dev probes derived from
Autodesk's own freely-downloadable sample (rstbasicsampleproject).  Do not
redistribute; delete after the check.  Nothing here touches your firm's
models or your Autodesk account beyond opening two local files.

**Send back**: the screenshots + (if any) the journal file + one line per
file: opened clean / warning dialog / corrupt dialog / crash.
