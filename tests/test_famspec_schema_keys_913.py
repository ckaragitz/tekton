"""spec/famspec.schema.json carries no duplicate object key.

json.load keeps the LAST of two equal keys silently, so a duplicated field
(two "drive" entries on one kind landed this way while stacking #931 and the
equipment drives) would hide one definition from every reader without any
test noticing.  The plugin's mirrored copy must stay byte-identical."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "spec", "famspec.schema.json")
MIRROR = os.path.join(ROOT, "plugin", "skills", "tekton-native", "examples",
                      "famspec.schema.json")


def _no_dups(pairs):
    keys = [k for k, _ in pairs]
    dups = sorted({k for k in keys if keys.count(k) > 1})
    assert not dups, f"duplicate key(s) {dups} in one object of famspec.schema.json"
    return dict(pairs)


def test_the_famspec_schema_has_no_duplicate_keys():
    with open(SCHEMA, encoding="utf-8") as fh:
        json.load(fh, object_pairs_hook=_no_dups)


def test_the_plugin_copy_is_the_same_bytes():
    if os.path.exists(MIRROR):
        assert open(MIRROR, "rb").read() == open(SCHEMA, "rb").read()
