#!/usr/bin/env python3
"""rvt_inspect.py -- read/introspect ANY .rvt (the fresh-machine entry point).

Loads the archive class schema straight from the TARGET FILE'S own
`Formats/Latest` stream (no bundled schema blob is needed -- every .rvt
carries its release's 496,597-byte class map), then reports the container,
the class map, and (optionally) decodes a sample of element records.

Usage:
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
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import ensure_rvt  # noqa: E402

ensure_rvt()

from rvt import schema as schema_mod  # noqa: E402
from rvt.container import open_rvt  # noqa: E402
from rvt.objects import ObjectDecoder, iter_records  # noqa: E402
from rvt.partitions import StreamWalker  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--classes", metavar="SUBSTR", help="list classes whose name contains SUBSTR")
    ap.add_argument("--records", type=int, default=0, metavar="N",
                    help="decode the first N seq-102 element records (schema-directed)")
    ap.add_argument("--dump-schema", metavar="OUT.json", help="write the parsed class map as JSON")
    a = ap.parse_args(argv)

    with open_rvt(a.path) as doc:
        streams = doc.streams()
        print(f"== {a.path} ==")
        print(f"streams ({len(streams)}):")
        for s in streams:
            print(f"  {s.name:34s} raw={s.size:>10,}")
        blob = doc.concat("Formats/Latest")
        sch = schema_mod.parse(blob, source=a.path)
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
            dec = ObjectDecoder(sch)
            names = doc.partition_streams()
            print(f"\ndecoding first {a.records} seq-102 records of {names}:")
            cnt = Counter()
            n = 0
            for pname in names:
                w = StreamWalker(doc.logical(pname), inflate=True, keep_data=True)
                seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.seq == 102)
                for rec in iter_records(seg, 102):
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
                    if n >= a.records:
                        break
                if n >= a.records:
                    break
            print(f"decode summary: {dict(cnt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
