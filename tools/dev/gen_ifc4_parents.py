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
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "src", "rvt", "ifc", "ifc4_parents.py")
SCHEMA = "IFC4"

HEADER = '''\
"""rvt.ifc.ifc4_parents -- the IFC4 entity hierarchy as a plain
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

FOOTER = "}\n"


def render() -> str:
    import ifcopenshell
    import ifcopenshell.ifcopenshell_wrapper as W

    schema = W.schema_by_name(SCHEMA)
    rows = []
    for decl in schema.declarations():
        if not isinstance(decl, W.entity):
            continue
        sup = decl.supertype()
        rows.append((decl.name(), sup.name() if sup is not None else None))
    body = "".join(f"    {name!r}: {parent!r},\n" for name, parent in rows)
    head = HEADER.format(schema=SCHEMA, version=ifcopenshell.version, count=len(rows))
    return head + body + FOOTER


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the module on disk differs")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        with open(OUT, encoding="utf-8") as fh:
            disk = fh.read()
        if disk == text:
            print(f"ok: {os.path.relpath(OUT, ROOT)} matches the {SCHEMA} declarations")
            return 0
        sys.stdout.writelines(difflib.unified_diff(
            disk.splitlines(True), text.splitlines(True), "on-disk", "generated", n=1))
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({text.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
