"""rvt.convert.rfa_assemble -- assemble a STANDALONE ``.rfa`` from a family
document's RAW RECORDS.

The famgen emitters (``skeleton.emit_family_rfa`` / ``famdoc_adoc.
emit_family_rfa_v2``) write ``.rfa`` files from a constructive
:class:`~rvt.famgen.skeleton.FamilyDoc`.  Extraction starts from the other
end -- the per-seq record byte strings of an EXISTING family document (an
embedded project unit, or an ``.rfa``'s own unit 0) -- so this module is the
same assembly recipe re-based on segments:

* the family document's records ride VERBATIM (byte-faithful content);
* every scaffolding stream is re-authored by the proven writers:
  partition framing (``skeleton.build_partition_stream`` + our unit footer
  nonce + the decoded end record), the six coordinated Global table streams
  (``genesis.skeleton.minimal_globals`` -- single-episode invariants by
  construction), the standalone ``Global/Latest`` ADocument
  (``famdoc_adoc.author_family_adocument`` over the document's OWN
  inventory, archetype = the bundled certified genesis base -- the same
  zero-donor path the production family writer uses), identity through
  ``rvt.identity``, ``PartAtom`` from our Atom writer, and the CFB
  container by our writer;
* ``Formats/Latest`` is carried from the SOURCE file itself (every ``.rvt``
  and ``.rfa`` embeds the per-release schema constant -- format, not
  content).

Used by :mod:`rvt.convert.extract_family` (RVT -> RFA).  Territory:
``src/rvt/convert/`` (convert-a stream).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

__all__ = ["UnitElement", "UnitDoc", "assemble_rfa"]

PRODUCT_NAME = "rvt-writer"


@dataclass
class UnitElement:
    """One element of the family document, decoded: the SkelElement-shaped
    facts the inventory / ElemTable builders need (records stay verbatim)."""
    elem_id: int
    class_name: str
    obj: Dict[str, Any] = dc_field(default_factory=dict)
    owner_id: int = -1
    original_id: Optional[int] = None

    def elemrec_row(self, episode: int = 0) -> tuple:
        from ..genesis.skeleton import NO_OWNER
        owner = self.owner_id if self.owner_id >= 0 else NO_OWNER
        orig = self.original_id if self.original_id is not None else self.elem_id
        return (orig, episode, episode, episode, self.elem_id, owner, 0)


class UnitDoc:
    """A FamilyDoc-shaped view over decoded unit records -- exactly the
    protocol ``famdoc_adoc.derive_family_inventory`` (constructive branch)
    and the ElemTable builder read."""

    finalized = True

    def __init__(self, *, elements: List[UnitElement], self_family: UnitElement,
                 document_guid: str, name: str, category_id: int,
                 part_type: int = 0, types: Optional[List[tuple]] = None):
        self.elements = elements
        self.self_family = self_family
        self.document_guid = document_guid
        self.name = name
        self.category_id = int(category_id)
        self.part_type = int(part_type)
        self.types = list(types or [])
        self.current_type = 0

    def finalize(self) -> "UnitDoc":
        return self


def assemble_rfa(segs: Dict[int, bytes], doc: UnitDoc, out_path: str, *,
                 formats_raw: bytes,
                 adoc_archetype: Optional[str] = None,
                 adoc_mode: str = "candidate",
                 username: str = PRODUCT_NAME,
                 product_name: str = PRODUCT_NAME,
                 timestamp: Optional[int] = None,
                 category_label: Optional[str] = None) -> Dict[str, Any]:
    """Write the standalone ``.rfa`` at ``out_path``.

    ``segs``          the family document's per-seq (101/102/103) record byte
                      strings INCLUDING sentinels (``rvt.families.
                      unit_segments`` shape) -- carried verbatim;
    ``doc``           the :class:`UnitDoc` facts over the same records;
    ``formats_raw``   the SOURCE file's raw ``Formats/Latest`` stream;
    ``adoc_archetype``the ADocument shape source (default: the bundled
                      certified genesis base -- zero donors).

    Returns the assembly report incl. ``verify`` (:func:`rvt.famgen.
    skeleton.verify_family_rfa`).  Callers run the family-mode validator on
    top (:func:`rvt.famgen.famdoc_adoc.validate_family_file`).
    """
    from .. import ecc
    from .. import identity as ID
    from .. import stream_encoders as se
    from .. import adocument as A
    from ..cfb_writer import CfbEntry, write_cfb
    from ..writer import gzip_member
    from ..famgen import famdoc_adoc as FA
    from ..famgen import skeleton as SK
    from ..genesis import skeleton as GSK

    if adoc_archetype is None:
        from ..frontdoor.standalone import bundled_base_path
        adoc_archetype = bundled_base_path()
    ts = int(timestamp if timestamp is not None else FA.TIMESTAMP)

    # --- the standalone ADocument over the document's OWN inventory --------
    ad = FA.author_family_adocument(doc, mode=adoc_mode, donor=adoc_archetype)
    latest_logical = A.latest_logical_stream(ad["payload"], level=3)

    # --- the six coordinated Global table streams ---------------------------
    gm = GSK.minimal_globals(doc.elements, document_guid=doc.document_guid or None,
                             username=username, out_path=out_path, timestamp=ts)
    enc = GSK.encode_minimal_globals(gm)
    dit_model = gm["DocumentIncrementTable"]
    part_name = SK._partition_stream_name(dit_model)
    et_count = len(gm["ElemTable"]["records"])
    doc_guid = str(gm["_ids"]["document_guid"])

    # --- the partition stream: records verbatim, our framing ----------------
    digest_material = b"".join(segs.get(s, b"") for s in (101, 102, 103))
    footer_blob = FA.build_footer(guid=doc_guid, payload=digest_material,
                                  mode="nonce")
    logical_part = SK.build_partition_stream(segs, elem_table_count=et_count,
                                             footer_blob=footer_blob,
                                             end_record=FA.FAMILY_END_RECORD)

    streams: Dict[str, bytes] = {}
    streams[part_name] = ecc.frame_stream(logical_part)
    for n in ("ElemTable", "History", "DocumentIncrementTable", "PartitionTable"):
        payload_n = enc[n]
        if n == "DocumentIncrementTable":
            payload_n = ID.own_increment_table_payload(payload_n, username=username)
        streams[f"Global/{n}"] = ecc.frame_stream(
            se.global_prefix(n) + gzip_member(payload_n, level=3, sync_flush=True))
    streams["Global/ContentDocuments"] = ecc.frame_stream(
        se.global_prefix("ContentDocuments")
        + gzip_member(enc["ContentDocuments"], level=3, sync_flush=True))
    streams["Global/Latest"] = ecc.frame_stream(latest_logical)
    pro = se.encode_contents_prologue(gm["ContentsPrologue"])
    streams["Contents"] = ecc.frame_stream(
        pro + gzip_member(enc["Contents"], level=3, sync_flush=True))
    ep_guid = str(gm["_ids"]["episode_guid"])
    bfi_model = ID.own_identity_model(dict(gm["BasicFileInfo"]), out_path=out_path,
                                      username=username, document_guid=ep_guid,
                                      author=ID.DEFAULT_AUTHOR,
                                      client_app_name=ID.DEFAULT_CLIENT_APP)
    streams["BasicFileInfo"] = se.encode_basic_file_info(bfi_model,
                                                         regenerate_mirror=True)
    streams["TransmissionData"] = SK.our_transmission_data()
    label = category_label or SK.category_label(doc.category_id)
    streams["PartAtom"] = SK.build_part_atom(doc.name, label,
                                             type_names=[n for n, _v in doc.types],
                                             product_name=product_name)
    streams["Formats/Latest"] = formats_raw

    entries = [CfbEntry(path="", entry_type="root")]
    for storage in ("Formats", "Global", "Partitions"):
        entries.append(CfbEntry(path=storage, entry_type="storage"))
    order = ["BasicFileInfo", "Contents", "Formats/Latest",
             "Global/ContentDocuments", "Global/DocumentIncrementTable",
             "Global/ElemTable", "Global/History", "Global/Latest",
             "Global/PartitionTable", "PartAtom", part_name, "TransmissionData"]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    write_cfb(out_path, [*entries,
                         *(CfbEntry(path=n, entry_type="stream", data=streams[n])
                           for n in order)])

    rep: Dict[str, Any] = {
        "path": out_path, "size": os.path.getsize(out_path),
        "partition_stream": part_name, "elements": et_count,
        "document_guid": doc_guid, "episode_guid": ep_guid,
        "adoc_mode": adoc_mode,
        "adoc_archetype": adoc_archetype,
        "adoc_bytes": len(ad["payload"]),
        "streams": {k: len(v) for k, v in streams.items()},
        "ours": ["partition framing + unit footer nonce + end record",
                 "Global/{ElemTable,History,DocumentIncrementTable,"
                 "PartitionTable,ContentDocuments,Latest}", "Contents",
                 "BasicFileInfo (rvt.identity)", "TransmissionData", "PartAtom",
                 "CFB container / gzip / CRCIO framing"],
        "carried": ["the family document's OWN records (verbatim; the content "
                    "being extracted)",
                    "Formats/Latest from the SOURCE file (per-release schema "
                    "constant -- format, not content)"],
    }
    rep["verify"] = SK.verify_family_rfa(out_path)
    return rep
