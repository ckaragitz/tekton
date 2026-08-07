# inbox — plugin-packager (2026-08-03)

Built `plugin/` at the repo root: the Claude Code plugin that ships the
whole toolbelt in one install. Structural validator passes; `pip install
./plugin/lib` into a fresh venv + `rvt.ecc` smoke test pass; the proven
V15/V18/V19 recipes are packaged as runnable, self-verifying scripts and
re-verified on the samples. Details, orchestrator actions and caveats:

## Findings the orchestrator should act on

1. **`src/rvt/` grew `commit.py` (another agent, aps-writer/cfb-writer) AFTER
   my snapshot.** `plugin/lib/src/rvt/` is a byte-identical copy of `src/rvt`
   as of packaging time and is fully verified working; it does not contain
   `commit.py`. Once that work is done, re-sync with:
   `rsync -a --exclude __pycache__ src/rvt/ plugin/lib/src/rvt/` and re-run
   `plugin/scripts/validate_plugin.py` + the smoke test. I did not chase an
   in-flight file.
2. **`plugin/docs/` was written into my output tree by another agent**
   (`HONEST-STATUS.md`, `JOB-TEMPLATES/*.md`, ~00:09–00:11). I read them
   (consistent with our honest-status framing) and left them untouched, and
   reference them in `plugin/README.md`. They contain **dangling
   references** to `PLAYBOOK-claude-code.md` and
   `plugin/docs/PLAYBOOK-claude-design.md`, which do not exist yet — that
   agent presumably still owes those files. My validator deliberately does
   not gate on `plugin/docs/`. Please assign ownership of `plugin/docs/`.
3. **`plugin/examples/` is a copy of `usecases/`** (the usecase-runner had
   already produced both bundles when I got there). Re-sync command is in
   `plugin/examples/README.md`. If the runner revises a bundle, re-copy.

## Engine portability — the honest finding baked into the rvt-native skill

- **Portable (file-driven, works after `pip install ./plugin/lib`):**
  `container.open_rvt(path)`, `ecc`, `partitions.StreamWalker/load_stream`,
  `objects.iter_records / ObjectDecoder(schema)`, `encode.ObjectEncoder`,
  `schema.parse(bytes)` (schema loads from the TARGET file's own
  `Formats/Latest` — verified: 496,597 B, 4,690 classes, so **no schema blob
  is bundled**), `writer.gzip_member`, `cfb_writer.write_cfb`,
  `roundtrip.read_entries`, `streams_edit`, `stream_encoders`.
- **Corpus-bound (dev machine only): `mutate.Document.load(project)`,
  `objects.load_segment(project)`, `elemtable.load_elemtable(project)`,
  `schema.load_schema()` with no args** — they name a sample project and use
  the hard-coded `ROOT = /Users/ck/dev/things/rev-revit` + `extracted/`.
  **The element-creation planner therefore cannot run on the brothers'
  machines.** Proposed follow-up task (D7 support): give `Document.load` a
  file-driven path (schema from the file, segments via `StreamWalker`,
  ElemTable via `stream_encoders.decode_elemtable`), removing the ROOT
  dependency. I did not modify `src/rvt` (out of scope for this slice).

## Marketplace note

The operative marketplace file is `plugin/.claude-plugin/marketplace.json`
(that is where `/plugin marketplace add ./plugin` reads; `source: "./"`
makes the plugin folder itself the marketplace root). `plugin/
marketplace.json` is an identical convenience copy per the task spec; the
validator asserts they stay identical. Install string:
`/plugin install revit-automation@rev-revit`.
