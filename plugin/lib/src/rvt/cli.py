"""rvtinspect — interactive inspector over the container spine.

Usage:
  python -m rvt.cli ls FILE
  python -m rvt.cli hexdump FILE STREAM [--member N] [--offset O] [--len L]
  python -m rvt.cli dump FILE STREAM [--member N] [--out PATH]
  python -m rvt.cli strings FILE STREAM [--member N] [--min N] [--utf16]
"""
from __future__ import annotations

import argparse
import re
import sys

from .container import open_rvt


def _payload(doc, stream: str, member: int | None) -> bytes:
    if member is None:
        return doc.raw(stream)
    return doc.inflate(stream, member)


def _hexdump(b: bytes, base: int = 0) -> str:
    lines = []
    for i in range(0, len(b), 16):
        chunk = b[i : i + 16]
        hx = " ".join(f"{c:02x}" for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        lines.append(f"{base + i:08x}  {hx:<47}  {asc}")
    return "\n".join(lines)


def cmd_ls(a) -> int:
    with open_rvt(a.file) as doc:
        print(doc.describe())
    return 0


def cmd_hexdump(a) -> int:
    with open_rvt(a.file) as doc:
        b = _payload(doc, a.stream, a.member)
        b = b[a.offset : a.offset + a.len]
        print(_hexdump(b, a.offset))
    return 0


def cmd_dump(a) -> int:
    with open_rvt(a.file) as doc:
        b = _payload(doc, a.stream, a.member)
    if a.out:
        with open(a.out, "wb") as fh:
            fh.write(b)
        print(f"wrote {len(b):,} bytes -> {a.out}")
    else:
        sys.stdout.buffer.write(b)
    return 0


def cmd_strings(a) -> int:
    with open_rvt(a.file) as doc:
        b = _payload(doc, a.stream, a.member)
    n = a.min
    if a.utf16:
        pat = re.compile((rb"(?:[\x20-\x7e]\x00){%d,}" % n))
        for m in pat.finditer(b):
            print(f"{m.start():08x}  {m.group().decode('utf-16-le')}")
    else:
        pat = re.compile(rb"[\x20-\x7e]{%d,}" % n)
        for m in pat.finditer(b):
            print(f"{m.start():08x}  {m.group().decode('ascii')}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rvtinspect")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ls"); s.add_argument("file"); s.set_defaults(fn=cmd_ls)

    s = sub.add_parser("hexdump")
    s.add_argument("file"); s.add_argument("stream")
    s.add_argument("--member", type=int, default=None)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--len", type=int, default=256)
    s.set_defaults(fn=cmd_hexdump)

    s = sub.add_parser("dump")
    s.add_argument("file"); s.add_argument("stream")
    s.add_argument("--member", type=int, default=None)
    s.add_argument("--out", default=None)
    s.set_defaults(fn=cmd_dump)

    s = sub.add_parser("strings")
    s.add_argument("file"); s.add_argument("stream")
    s.add_argument("--member", type=int, default=None)
    s.add_argument("--min", type=int, default=6)
    s.add_argument("--utf16", action="store_true")
    s.set_defaults(fn=cmd_strings)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
