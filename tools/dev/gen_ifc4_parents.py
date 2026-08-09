#!/usr/bin/env python3
"""One-off GENERATOR for src/rvt/ifc/ifc4_parents.py (issue #155).

steplite (rvt.ifc.steplite, the stdlib-only IFC reader the plugin ships)
hand-transcribes attribute rows for the entity subset the read paths use.
To keep entities OUTSIDE that subset inside the right ``by_type`` / ``is_a``
closures it also needs the plain "class -> supertype" relation of the whole
IFC4 entity hierarchy.  That relation is a fact of buildingSMART's PUBLIC
IFC4 (ADD2 TC1) EXPRESS schema; this script reads it out of a locally
installed ifcopenshell (``ifcopenshell_wrapper.schema_by_name("IFC4")``)
and writes it down as OUR OWN python text: one ``"IfcChild": "IfcParent"``
line per entity, nothing else (no attribute lists, no vendor file bytes).

ifcopenshell is a DEV-TIME input of this generator only -- the generated
module imports nothing and steplite stays stdlib-only at runtime.

    .venv/bin/python tools/dev/gen_ifc4_parents.py            # rewrite the module
    .venv/bin/python tools/dev/gen_ifc4_parents.py --check    # exit 1 on drift
    .venv/bin/python tools/dev/gen_ifc4_parents.py --schema IFC2X3   # -> ifc2x3_parents.py
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def out_path(schema: str) -> str:
    return os.path.join(ROOT, "src", "rvt", "ifc", f"{schema.lower()}_parents.py")


HEADER = '''\
"""rvt.ifc.{module} -- the {schema} entity hierarchy as a plain
class-name -> supertype-name table (issue #155).

GENERATED TEXT, OUR OWN: written by ``tools/dev/gen_ifc4_parents.py`` from
the entity declarations of buildingSMART's public {schema} EXPRESS schema as
exposed by ifcopenshell {version} (``ifcopenshell_wrapper.schema_by_name(
"{schema}")``: ``entity.name()`` -> ``entity.supertype().name()``).  It records
schema FACTS (which class specialises which), carries no attribute lists and
no bytes of any vendor file, and imports nothing -- ``rvt.ifc.steplite``
reads it so that entity classes outside its hand-transcribed attribute
subset still land in the correct ``by_type`` / ``is_a`` closures (an
``IfcDoor`` is an ``IfcBuildingElement`` is an ``IfcElement`` is an
``IfcProduct`` ...) exactly as the real library reports them.

Do not edit by hand: re-run the generator (``--check`` reports drift).
{count} entities; roots map to ``None``; rows in the schema's declaration
order (case-insensitive alphabetical).  NOTE: that is NOT the sibling order
``by_type`` walks -- ifcopenshell's ``entity.subtypes()`` are CamelCase names
sorted case-SENSITIVELY (``IfcCShapeProfileDef`` before
``IfcCircleProfileDef``); steplite sorts siblings itself accordingly.
"""
from typing import Dict, Optional

SCHEMA = "{schema}"

#: CamelCase entity name -> CamelCase direct supertype name (None for roots)
PARENT: Dict[str, Optional[str]] = {{
'''


def render(schema_name: str) -> str:
    import ifcopenshell
    import ifcopenshell.ifcopenshell_wrapper as W

    schema = W.schema_by_name(schema_name)
    rows = []
    for decl in schema.declarations():
        if not isinstance(decl, W.entity):
            continue
        sup = decl.supertype()
        rows.append((decl.name(), sup.name() if sup is not None else None))
    module = os.path.splitext(os.path.basename(out_path(schema_name)))[0]
    head = HEADER.format(module=module, schema=schema_name,
                         version=ifcopenshell.version, count=len(rows))
    return head + "".join(f"    {name!r}: {parent!r},\n" for name, parent in rows) + "}\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--schema", default="IFC4",
                    help="ifcopenshell schema name (default IFC4; steplite reads ifc4_parents)")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the module on disk differs")
    args = ap.parse_args(argv)
    out = out_path(args.schema)
    text = render(args.schema)
    if args.check:
        with open(out, encoding="utf-8") as fh:
            disk = fh.read()
        if disk == text:
            print(f"ok: {os.path.relpath(out, ROOT)} matches the {args.schema} declarations")
            return 0
        sys.stdout.writelines(difflib.unified_diff(
            disk.splitlines(True), text.splitlines(True), "on-disk", "generated", n=1))
        return 1
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(out, ROOT)} ({text.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
