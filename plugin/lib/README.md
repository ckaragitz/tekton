# `rvt` — the bundled native-`.rvt` engine

This directory is a pip-installable copy of the tekton `src/rvt` Python
package: the reverse-engineered, Autodesk-Viewer-proven reader/writer for
Autodesk Revit `.rvt` files. The `tekton` plugin's
`tekton-native` skill drives it. Install it once per machine / sandbox:

```bash
# from the plugin root (or any absolute path to plugin/lib):
pip install ./lib                 # inside plugin/  ->  installs package "rvt"
# or, with uv:
uv pip install --python .venv/bin/python ./lib
# verify:
python -c "import rvt.ecc, rvt.container, rvt.cfb_writer; print('rvt engine OK')"
```

The only dependency is `olefile`. No compiler, no native code — pure
Python, so it installs the same way in the Cowork / claude.ai Linux
code-execution sandbox as it does in Claude Code.

## What is portable vs. what is corpus-bound

The engine has two layers. Know which one you are using:

- **File-driven API (portable — use these in jobs).** Given only a path to a
  real `.rvt`, these work on any machine after `pip install ./lib`:
  `rvt.container.open_rvt(path)` (de-paging, CRC-verified members,
  `logical()/inflate()/concat()`), `rvt.ecc` (page ECC framing,
  `frame_stream / unframe_stream / page_trailer`), `rvt.partitions`
  (`StreamWalker`, `load_stream`, record framing), `rvt.objects.iter_records`
  + `ObjectDecoder(schema)`, `rvt.encode.ObjectEncoder(schema)`,
  `rvt.schema.parse(bytes)` (the schema comes from the target file itself —
  see below), `rvt.writer.gzip_member` (zlib level 3 + sync-flush),
  `rvt.cfb_writer.write_cfb`, `rvt.roundtrip.read_entries`,
  `rvt.streams_edit` (record-save bookkeeping over decoded models),
  `rvt.stream_encoders`, `rvt.elemtable.parse_elemtable(bytes)`.

- **Corpus-driven convenience API (developer-machine only).** A handful of
  helpers name a sample *project* (`"racbasicsampleproject"`) and read the
  pre-extracted research corpus under a hard-coded repo path
  (`ROOT = /Users/ck/dev/things/tekton`, `extracted/<project>/`):
  `rvt.mutate.Document.load(project)`, `rvt.objects.load_segment(project)`,
  `rvt.elemtable.load_elemtable(project)`, `rvt.schema.load_schema()` with no
  argument. On a fresh machine these do not resolve. The `tekton-native` skill
  gives the file-driven equivalent for each (e.g. build the schema from the
  target file, walk the partition segments with `StreamWalker` instead of
  `load_segment`). The element-creation *planner* (`mutate.py`) is the
  research surface for milestone D7 and is intentionally documented as
  in-progress — see the skill's status box.

## The schema (Formats/Latest) — no bundled blob needed

Every Revit 2026 file carries the same 496,597-byte archive class map in
its own `Formats/Latest` stream, and the engine reads it straight from the
target file:

```python
from rvt.container import open_rvt
from rvt import schema
from rvt.objects import ObjectDecoder
with open_rvt("some-model.rvt") as doc:
    sch = schema.parse(doc.concat("Formats/Latest"))   # 4,690 classes
dec = ObjectDecoder(sch)                                # schema-directed codec
```

So nothing large ships here. (A file from a *different Revit release* has
a different schema and is parsed by the same call — the grammar is
release-independent.) The optional one-time repo command that dumps the map
to JSON for browsing is `python -m rvt.schema` — it writes to the developer
tree (`extracted/_schema/`) and is not needed at runtime.
