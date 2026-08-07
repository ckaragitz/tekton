"""rvt.versions.parity -- the multi-version READ-PARITY harness.

Mechanized re-run of the whole read stack over any .rvt / .rfa, of any
release, producing one comparable row per file:

    version | streams | gzip (members, CRC-ok) | page/ECC framing (pages) |
    partition framing (blocks, walker errors) | schema (size, sha, classes,
    parse) | object decode (records, elements, clean %) | validator verdict

The point of the table is PARITY: a Revit 2024 / 2025 file must read as
cleanly as a 2026 one.  Every stage runs inside :func:`rvt.versions.reading`
so the file's OWN framing ordinals are in force (never the 2026 constants).

CLI::

    PYTHONPATH=src python -m rvt.versions.parity samples/*.rvt samples/2025/*.rvt \\
        samples/2024/*.rvt --json parity.json --md parity.md

The default file set (no args) is the phase-A parity corpus: the 2026
basics + every 2025/2024 sample + the third-party 2024 model + the
2024/2025 sample-family .rfa carried in vendor/.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import (KNOWN_RELEASES, describe, detect_release, ordinals_from_schema,
               reading, schema_of)

# streams a well-formed project (.rvt) carries; a family (.rfa) additionally
# has PartAtom.  Presence is reported, absence is not itself an error.
STANDARD_STREAMS = ("BasicFileInfo", "Contents", "Formats/Latest", "Global/Latest",
                    "Global/ElemTable", "Global/History", "Global/DocumentIncrementTable",
                    "Global/PartitionTable", "Global/ContentDocuments", "RevitPreview4.0",
                    "TransmissionData", "ProjectInformation")

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def default_files() -> List[str]:
    """The phase-A parity corpus (whatever of it exists locally)."""
    c = []
    for stem in ("rstbasicsampleproject", "racbasicsampleproject", "rmebasicsampleproject"):
        c.append(f"samples/{stem}.rvt")                       # 2026 baseline
    for yr in ("2025", "2024", "2023"):
        for stem in ("rstbasicsampleproject", "racbasicsampleproject", "rmebasicsampleproject",
                     "rstadvancedsampleproject", "racadvancedsampleproject",
                     "rmeadvancedsampleproject"):
            c.append(f"samples/{yr}/{stem}.rvt")
    c += ["vendor/magnetar-revit-test-datasets/Revit/2024_Core_Interior.rvt",
          "vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2025.rfa",
          "vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2024.rfa"]
    return [p for p in (os.path.join(ROOT, x) for x in c) if os.path.isfile(p)]


@dataclass
class ParityRow:
    path: str
    name: str
    release: Optional[int] = None
    kind: str = "?"                                  # rvt / rfa / rte
    streams: int = 0
    partitions: List[str] = field(default_factory=list)
    standard_present: str = ""                       # "n/12"
    gzip_members: int = 0
    gzip_crc_ok: int = 0
    pages_checked: int = 0
    partition_blocks: int = 0
    walker_errors: int = 0
    schema_size: int = 0
    schema_sha8: str = ""
    schema_classes: int = 0
    schema_fields: int = 0
    schema_unresolved: int = 0
    schema_parse: str = ""                           # OK / error text
    framing: Dict[str, int] = field(default_factory=dict)
    records: int = 0
    elements_decoded: int = 0
    decode_failures: int = 0
    decode_clean_pct: float = 0.0
    verdict: str = "?"
    v_errors: int = 0
    v_warnings: int = 0
    error_samples: List[str] = field(default_factory=list)
    seconds: float = 0.0
    fatal: str = ""

    def as_json(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["framing"] = {k: f"{v:#x}" for k, v in self.framing.items()}
        return d


def run_file(path: str, *, validate: bool = True, quiet: bool = True) -> ParityRow:
    """Run the whole read stack on one file and return its parity row."""
    from ..container import open_rvt
    from .. import validate as V
    from ..partitions import StreamWalker

    row = ParityRow(path=path, name=os.path.basename(path))
    t0 = time.time()
    try:
        row.kind = os.path.splitext(path)[1].lower().lstrip(".") or "?"
        row.release = detect_release(path)
        # --- container / streams / gzip flavour --------------------------------
        with open_rvt(path) as d:
            names = [s.name for s in d.streams()]
            row.streams = len(names)
            row.partitions = d.partition_streams()
            std = [s for s in STANDARD_STREAMS if s in names]
            row.standard_present = f"{len(std)}/{len(STANDARD_STREAMS)}"
            for n in names:                                    # every gzip member,
                for m in d.members(n):                          # CRC-verified
                    row.gzip_members += 1
                    row.gzip_crc_ok += int(m.crc_ok)
        # --- schema (release-independent grammar) -----------------------------
        try:
            sch = schema_of(path)
            st = sch.stats()
            row.schema_size = st["stream_size"]
            row.schema_sha8 = st["sha256"][:8]
            row.schema_classes = st["class_count"]
            row.schema_fields = st["field_count"]
            row.schema_unresolved = st["unresolved_refs"]
            row.schema_parse = "OK"
            row.framing = ordinals_from_schema(sch)
        except Exception as e:                                 # parser delta = a defect
            row.schema_parse = f"ERROR {type(e).__name__}: {e}"[:160]
            sch = None
        # --- everything else runs with the file's OWN framing in force -------
        # (plus, iff the schema declares 32-bit element ids -- Identifier v1,
        # Revit <= 2023 -- the records32 width layer: the 2023 record delta)
        from contextlib import ExitStack
        from . import records32
        with ExitStack() as _stack:
            _stack.enter_context(
                reading(path, schema=sch) if sch is not None else reading(path))
            if sch is not None and records32.is_ids32(sch):
                _stack.enter_context(records32.ids32())
            # partition framing walk (block count, walker resyncs) on the
            # de-paged logical streams; the per-page ECC check itself is
            # counted by the validator below (pages_checked)
            with open_rvt(path) as d:
                for pn in d.partition_streams():
                    try:
                        w = StreamWalker(d.logical(pn), inflate=False)
                        row.partition_blocks += len(w.blocks)
                        row.walker_errors += len(w.errors)
                    except Exception as e:
                        row.walker_errors += 1
                        row.error_samples.append(f"{pn}: walker {type(e).__name__}: {e}"[:140])
            # the layered validator: ECC framing + consistency + schema-directed decode
            if validate:
                rep = V.validate_file(path)
                s = rep.stats
                row.pages_checked = int(s.get("pages_checked", 0))
                row.records = int(s.get("records", 0))
                row.elements_decoded = int(s.get("elements_decoded", 0))
                row.decode_failures = int(s.get("decode_failures", 0))
                tot = row.elements_decoded + row.decode_failures
                # NB: validator's elements_decoded counts CLEAN seq-102 element
                # decodes; failures are the residue.
                row.decode_clean_pct = round(100.0 * row.elements_decoded / tot, 3) if tot else 0.0
                row.verdict = "VALID" if rep.ok else "INVALID"
                row.v_errors = len(rep.errors)
                row.v_warnings = len(rep.warnings)
                for f in rep.errors[:3]:
                    row.error_samples.append(f"[{f.layer}] {f.where}: {f.message}"[:160])
    except Exception as e:
        row.fatal = f"{type(e).__name__}: {e}"[:200]
        if not quiet:
            traceback.print_exc()
    row.seconds = round(time.time() - t0, 1)
    return row


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def markdown_table(rows: List[ParityRow]) -> str:
    hdr = ("| file | rel | streams | std | gzip (ok/tot) | pages | blocks(err) | "
           "schema size/classes | parse | decode clean | records | verdict (E/W) |")
    sep = "|" + "|".join(["---"] * 12) + "|"
    out = [hdr, sep]
    for r in rows:
        dec = (f"{r.decode_clean_pct:.2f}% ({r.elements_decoded:,}/"
               f"{r.elements_decoded + r.decode_failures:,})") if r.records else "-"
        out.append(
            f"| {r.name} | {r.release} | {r.streams} | {r.standard_present} | "
            f"{r.gzip_crc_ok}/{r.gzip_members} | {r.pages_checked} | "
            f"{r.partition_blocks}({r.walker_errors}) | "
            f"{r.schema_size:,}/{r.schema_classes:,} | {r.schema_parse[:12]} | {dec} | "
            f"{r.records:,} | {r.fatal or r.verdict} ({r.v_errors}/{r.v_warnings}) |")
    return "\n".join(out)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rvt.versions.parity",
                                 description="Multi-version read-parity table")
    ap.add_argument("paths", nargs="*", help="files (default: the phase-A parity corpus)")
    ap.add_argument("--json", help="write rows as JSON here")
    ap.add_argument("--md", help="write the markdown table here")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    paths = a.paths or default_files()
    rows = []
    for p in paths:
        print(f"... {p}", file=sys.stderr, flush=True)
        rows.append(run_file(p, validate=not a.no_validate))
    table = markdown_table(rows)
    print(table)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump([r.as_json() for r in rows], fh, indent=1)
    if a.md:
        with open(a.md, "w") as fh:
            fh.write(table + "\n")
    bad = [r for r in rows if r.fatal or r.verdict == "INVALID" or r.schema_parse != "OK"]
    for r in bad:
        for s in r.error_samples[:2]:
            print(f"  {r.name}: {s}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
