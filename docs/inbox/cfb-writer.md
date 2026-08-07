# inbox — cfb-writer agent (container layer)

Out-of-scope observations made while building `src/rvt/cfb_writer.py` /
`src/rvt/roundtrip.py`. Not acted on; for the orchestrator.

1. **`experiments/roundtrip/*.rvt` are large untracked binaries** (six files,
   ~230 MB total, one is 139 MB). `.gitignore` covers `samples/` and
   `extracted/` but not `experiments/roundtrip/`. Suggest adding it.

2. **`rvt` is not installed into the venv** — every `python -m rvt.*` needs
   `PYTHONPATH=src` (tests add `src` via `tests/conftest.py`). A tiny
   `pyproject.toml` + `uv pip install -e .` (or a `.pth` in site-packages)
   would make `python -m rvt.roundtrip` work as the task statement spells it.

3. **KNOWLEDGE.md nit**: "Stream inventory is small and stable (12–14
   streams)" — with the root and the three storages the *directory* holds
   16–18 entries (rstbasic 16, dach 18). Full per-sample tables are in
   `docs/streams/00-cfb-container.md` §2 if you want to reference exact
   counts.

4. **Slack-byte leakage in the originals (forensics, not format).** Revit's
   writer leaves uninitialised buffer bytes in the last sector of each
   stream. In `rstadvancedsampleproject`, the 4,052 slack bytes after
   `TransmissionData` contain a **UTF-16 XML fragment** (`<?xml versi…`),
   i.e. remnants of an earlier serialisation of that stream in the same
   allocation. Others show `06 00 00 ac 06 00 00 ad …` counter-like runs and
   `ff` fills. None of it is inside any stream, but it is a source of
   "phantom" strings if anyone greps raw file bytes instead of extracted
   streams. Our writer zero-fills, so round-tripped files are cleaner than
   originals.

5. **A byte-identical writer is deliberately not attempted.** It would need
   an emulation of Windows Structured Storage's on-demand FAT growth (FAT
   sector #2 lands at sector 50-ish), its red-black insertion order and its
   slack garbage. If Track D ("lossless byte round-trip") is meant literally,
   the container layer alone makes that ill-defined — recommend redefining
   D1 as **stream-level lossless** (which now passes for all six).

6. **`compoundfiles` (already in the venv) is a good second reader** for the
   verify harness (independent implementation, warns on FAT/DIFAT/header
   irregularities). `verify_pair()` uses it automatically when importable.

7. Possible follow-up for `container.py` (orchestrator-owned, so untouched):
   expose per-entry directory metadata (sid, clsid, state bits, FILETIMEs) so
   readers don't need to reach into `olefile.direntries` the way
   `roundtrip.catalog()` does.
