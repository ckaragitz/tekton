#!/usr/bin/env python3
"""rvt_inspect.py -- read/introspect ANY .rvt (the fresh-machine entry point).

Loads the archive class schema straight from the TARGET FILE'S own
`Formats/Latest` stream (no bundled schema blob is needed -- every .rvt
carries its release's 496,597-byte class map), then reports the container,
the class map, and (optionally) decodes a sample of element records.

The record walk (``--records``) reads the file under ITS OWN release
(issue #533): a Revit 2025/2024 project's Partitions/<N> streams are walked
with that release's container class and block/trailer tags, and its records
framed with that release's id width, all read from the engine modules at
call time -- the instrument ladder ``rvt.global_framing.enter_own_release``
that rvt_analyze / seed_audit / provenance enter, so any release the engine
can READ is walked, not only the ones it can author.  A native file (every
partition header already parses with the natively bound container class)
enters no context and imports nothing extra; a partition that cannot be
walked at all (damaged header, unknown release) is reported on its own line
and counted as ``unwalkable`` in the decode summary -- exit 1, never a
traceback.  The stream listing, schema summary, ``--classes`` and
``--dump-schema`` are release-agnostic and never enter a context.

Exit codes: 0 = inspected; 1 = something asked for could not be read (the
schema stream does not parse, a partition cannot be walked); 2 = not a
readable .rvt / CFB container.

Usage (in the plugin: ``python <skill>/scripts/_bootstrap.py run rvt_inspect.py ...``):
    python rvt_inspect.py file.rvt                 # container + schema summary
    python rvt_inspect.py file.rvt --classes Wall  # find classes by substring
    python rvt_inspect.py file.rvt --records 20    # decode the first N seq-102 records
    python rvt_inspect.py file.rvt --dump-schema schema.json   # write the class map

This is the file-driven equivalent of the developer-tree helpers
(rvt.schema.load_schema() with no args, rvt.objects.load_segment(project)),
which name a sample project and only resolve inside the research repo.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "src"))     # plugin layout

from rvt import objects as O  # noqa: E402  -- iter_records via the module: the <=2023 id layer rebinds it
from rvt import partitions as P  # noqa: E402
from rvt import schema as schema_mod  # noqa: E402
from rvt.container import open_rvt  # noqa: E402


def natively_framed(doc) -> bool:
    """True when every Partitions/<N> header already parses with the
    container class bound in ``rvt.partitions`` right now -- a native-release
    file: nothing to enter, nothing more to import.  Anything else -- a
    foreign release, a damaged header -- asks the version model."""
    try:
        for name in doc.partition_streams():
            P.parse_stream_header(doc.logical(name))     # raises on any other container class
    except Exception:  # noqa: BLE001
        return False
    return True


def enter_files_release(stack: contextlib.ExitStack, doc, path: str) -> str | None:
    """Put ``path``'s own release in force on ``stack`` when it is not the
    native one; None when nothing had to be said, else the one sentence
    naming the rung the file is read on instead (reported, never raised)."""
    if natively_framed(doc):
        return None
    from rvt.global_framing import enter_own_release   # foreign files only: keep the native path light
    return enter_own_release(stack, path)


def print_records(doc, dec: O.ObjectDecoder, limit: int) -> int:
    """Decode and print the first ``limit`` seq-102 element records of every
    Partitions/<N> stream, walked with whatever release is in force.  Returns
    the number of partitions that could not be walked (each reported on its
    own line and in the summary) -- 0 on a healthy file."""
    names = doc.partition_streams()
    print(f"\ndecoding first {limit} seq-102 records of {names}:")
    cnt = Counter()
    n = 0
    for pname in names:
        try:
            w = P.StreamWalker(doc.logical(pname), inflate=True, keep_data=True)
        except Exception as e:  # noqa: BLE001 -- an unwalkable partition is the finding, not a crash
            print(f"  {pname}: cannot be walked ({type(e).__name__}: {e})")
            cnt["unwalkable"] += 1
            continue
        seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.seq == 102)
        for rec in O.iter_records(seg, 102):
            if rec.elem_id == -1:
                continue
            try:
                obj = dec.decode_record(rec.class_id, rec.payload)
                status = "clean" if obj.clean else f"partial({obj.consumed}/{obj.total})"
                cls = obj.class_name
            except Exception as e:  # keep going; report the failure
                status, cls = f"ERR:{type(e).__name__}", f"0x{rec.class_id:x}"
            cnt[status if status.startswith(("clean", "ERR")) else "partial"] += 1
            print(f"  id={rec.elem_id:>9}  class={cls:34s} psize={rec.body_size:>7}  {status}")
            n += 1
            if n >= limit:
                break
        if n >= limit:
            break
    print(f"decode summary: {dict(cnt)}")
    return cnt["unwalkable"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--classes", metavar="SUBSTR", help="list classes whose name contains SUBSTR")
    ap.add_argument("--records", type=int, default=0, metavar="N",
                    help="decode the first N seq-102 element records (schema-directed)")
    ap.add_argument("--dump-schema", metavar="OUT.json", help="write the parsed class map as JSON")
    a = ap.parse_args(argv)

    if not os.path.exists(a.path):
        print(f"ERROR: no such file: {a.path}", file=sys.stderr)
        return 2
    try:
        doc = open_rvt(a.path)
    except Exception as e:  # not CFB / not readable
        print(f"ERROR: cannot open as an .rvt container: {e}", file=sys.stderr)
        return 2

    with doc:
        streams = doc.streams()
        print(f"== {a.path} ==")
        print(f"streams ({len(streams)}):")
        for s in streams:
            print(f"  {s.name:34s} raw={s.size:>10,}")
        try:
            blob = doc.concat("Formats/Latest")
            sch = schema_mod.parse(blob, source=a.path)
            if not sch.classes:                          # a truncated file inflates to nothing
                raise ValueError(f"no classes in {len(blob):,} inflated bytes")   # parse() should raise itself: #569
        except Exception as e:  # noqa: BLE001 -- a schema stream that does not read IS the finding
            print(f"\nschema (Formats/Latest): unreadable ({type(e).__name__}: {e}) "
                  "-- nothing below the stream listing can be reported")
            return 1
        st = sch.stats()
        print(f"\nschema (Formats/Latest, {len(blob):,} bytes inflated): "
              f"{st['class_count']} classes, sha256 {st['sha256'][:16]}...")
        print(f"  ADocument type id: 0x{sch.by_name['ADocument'].type_id:x}"
              if 'ADocument' in sch.by_name else "  (no ADocument?)")

        if a.classes:
            hits = [c for c in sch.classes if a.classes.lower() in c.name.lower()]
            print(f"\nclasses matching {a.classes!r}: {len(hits)}")
            for c in hits[:60]:
                print(f"  0x{c.type_id:04x}  {c.name}")
            if len(hits) > 60:
                print(f"  ... ({len(hits) - 60} more)")

        if a.dump_schema:
            with open(a.dump_schema, "w") as fh:
                json.dump(sch.to_json(), fh, indent=1)
            print(f"\nclass map written: {a.dump_schema}")

        if a.records:
            # walk under the FILE's own release; a file whose release cannot be
            # resolved is still walked (on the rung the note names) and reported honestly
            with contextlib.ExitStack() as stack:
                note = enter_files_release(stack, doc, a.path)
                if note:
                    print(f"warning: {note}", file=sys.stderr)
                if print_records(doc, O.ObjectDecoder(sch), a.records):
                    return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
