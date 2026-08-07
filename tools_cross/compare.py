#!/usr/bin/env python3
"""Cross-file structural comparison of the six Revit 2026 sample projects.

For every stream present in >=5 of the 6 files this script compares:

  * raw ``.bin`` heads (first 256 bytes) column-wise -> per-offset
    constancy report (identical in all files vs varying, and how varying
    little-endian fields correlate with file size / stream size / number
    of gzip blocks);
  * correctly *de-framed and re-inflated* payload heads (first 512 bytes)
    column-wise;
  * the 8-byte pre-gzip prefixes of the Global/* streams (prefix table);
  * the trailing data after each deflate payload (page-frame table,
    gzip-trailer validity, zero padding, final partial-page trailer);
  * the ``Contents`` stream wrapper layout (magic 0x05221962);
  * cross-file identity of Formats/Latest, Global/PartitionTable and
    Contents inflated payloads.

KEY DISCOVERY encoded here (see docs/streams/07-cross-file.md and
docs/inbox/cross-file.md): every OLE stream that carries compressed data
is stored as *pages*: 64,896 (0xFD80) bytes of logical stream content
followed by a 353-byte per-page trailer block, i.e. raw offsets
64896 + n*65249 hold 353 non-payload bytes.  These must be stripped
*before* inflating.  After de-framing, every gzip member has a standard,
VALID 8-byte gzip trailer (CRC32 + ISIZE).  Inflating the raw framed
stream (as tools/scan_gzip.py did) silently corrupts every payload larger
than ~64.9 KB compressed (Formats/Latest included).

Run:
    .venv/bin/python tools_cross/compare.py            # full report (all 6)
    .venv/bin/python tools_cross/compare.py --file racbasicsampleproject
"""
import os, sys, json, zlib, hashlib, struct, argparse
from collections import OrderedDict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, 'extracted')
FILES = ['dach-sample-project', 'racadvancedsampleproject', 'racbasicsampleproject',
         'rmebasicsampleproject', 'rstadvancedsampleproject', 'rstbasicsampleproject']

# ---------------------------------------------------------------------------
# Page-frame constants (verified on all streams incl. dach Partitions/84,
# 129 MB / 1,978 frames): the raw OLE stream = logical content in pages of
# PAGE_DATA bytes, each followed by a PAGE_TRAILER-byte block.
# ---------------------------------------------------------------------------
PAGE_DATA = 64896        # 0xFD80 bytes of logical stream per page
PAGE_TRAILER = 353       # bytes of per-page trailer ("junk") after each page
PAGE_STRIDE = PAGE_DATA + PAGE_TRAILER   # 65249


def deframe(raw: bytes) -> bytes:
    """Return the logical stream: raw bytes with every 353-byte page-trailer
    block (at raw offsets 64896 + n*65249) removed."""
    out = bytearray()
    pos = 0
    off = PAGE_DATA
    while off < len(raw):
        out += raw[pos:off]
        pos = off + PAGE_TRAILER
        off += PAGE_STRIDE
    out += raw[pos:]
    return bytes(out)


def frame_offsets(rawlen: int):
    """Raw offsets of the page-trailer blocks present in a stream."""
    offs = []
    off = PAGE_DATA
    while off + PAGE_TRAILER <= rawlen:
        offs.append(off)
        off += PAGE_STRIDE
    return offs


def inflate_member(logical: bytes, off: int):
    """Inflate the gzip member at ``off`` in a *de-framed* stream.

    Returns dict(payload, defl_end, crc_stored, isize_stored, crc_ok,
    isize_ok).  ``defl_end`` is the offset just past the deflate data
    (i.e. the gzip trailer starts there).
    """
    assert logical[off:off + 3] == b'\x1f\x8b\x08'
    flg = logical[off + 3]
    hdr = 10
    if flg & 0x04:
        xlen = struct.unpack_from('<H', logical, off + 10)[0]
        hdr += 2 + xlen
    dc = zlib.decompressobj(-15)
    payload = dc.decompress(logical[off + hdr:]) + dc.flush()
    defl_end = len(logical) - len(dc.unused_data)
    trailer = logical[defl_end:defl_end + 8]
    crc_stored = int.from_bytes(trailer[:4], 'little') if len(trailer) >= 4 else None
    isize_stored = int.from_bytes(trailer[4:8], 'little') if len(trailer) >= 8 else None
    crc = zlib.crc32(payload) & 0xffffffff
    return dict(payload=payload, defl_end=defl_end,
                crc_stored=crc_stored, isize_stored=isize_stored,
                crc_ok=(crc == crc_stored),
                isize_ok=(isize_stored == (len(payload) & 0xffffffff)),
                eof=dc.eof, hdr_len=hdr)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_manifest(fname):
    with open(os.path.join(EXTRACTED, fname, 'manifest.json')) as fh:
        return json.load(fh)


def stream_key(name):
    """Normalise per-file stream names to a cross-file key
    (Partitions/N -> Partitions/<N>)."""
    if name.startswith('Partitions/'):
        return 'Partitions/<N>'
    return name


def gather():
    """Return {key: {file: (stream_name, raw_bytes, manifest_entry)}}"""
    table = OrderedDict()
    filesize = {}
    for f in FILES:
        m = load_manifest(f)
        filesize[f] = m['size']
        for s in m['streams']:
            key = stream_key(s['name'])
            path = os.path.join(EXTRACTED, f, s['name'].replace('/', '__') + '.bin')
            raw = open(path, 'rb').read()
            table.setdefault(key, OrderedDict())
            # dach has two Partitions streams: keep the big one under the
            # canonical key, keep the small one under its own key
            if key in table and f in table[key] and key == 'Partitions/<N>':
                prev = table[key][f]
                if len(raw) < len(prev[1]):
                    table['Partitions/<extra>'] = OrderedDict()
                    table['Partitions/<extra>'][f] = (s['name'], raw, s)
                    continue
                else:
                    table.setdefault('Partitions/<extra>', OrderedDict())[f] = prev
            table[key][f] = (s['name'], raw, s)
    return table, filesize


def column_report(blobs, width, base=0):
    """Per-offset constancy over the first ``width`` bytes of each blob.
    Returns list of dicts {off, values, const}."""
    rows = []
    for i in range(width):
        vals = tuple((b[i] if i < len(b) else None) for b in blobs)
        present = [v for v in vals if v is not None]
        const = len(set(present)) == 1 and len(present) == len(vals)
        rows.append(dict(off=base + i, values=vals, const=const))
    return rows


def summarize_columns(rows, files, blobs, extra_metrics=None, label='',
                      corr_limit=None, only_hinted=False):
    """Print a compact constancy map + a table of varying offsets, plus
    correlation hints for varying little-endian u32 fields.

    corr_limit: only scan u32 fields at offsets < corr_limit (used to skip
    compressed bodies where columns are meaningless noise).
    only_hinted: print only u32 rows that carry a correlation hint.
    """
    n = len(rows)
    const = [r for r in rows if r['const']]
    print(f'    {label}constant offsets: {len(const)}/{n}')
    # constancy map, 64 columns per line: 'C' const, 'v' varying, '.' absent
    line = ''
    for i, r in enumerate(rows):
        c = 'C' if r['const'] else 'v'
        if all(v is None for v in r['values']):
            c = '.'
        line += c
        if len(line) == 64:
            print(f'      +{i - 63:04x} {line}')
            line = ''
    if line:
        print(f'      +{n - len(line):04x} {line}')
    # constant runs with their hex values (first blob)
    runs = []
    i = 0
    while i < n:
        if rows[i]['const']:
            j = i
            while j < n and rows[j]['const']:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    for a, b in runs[:12]:
        seg = blobs[0][a:b]
        h = seg[:24].hex() + ('...' if b - a > 24 else '')
        print(f'      const [{rows[a]["off"]:>4}..{rows[b-1]["off"]:>4}] ({b-a:3d} B): {h}')
    if len(runs) > 12:
        print(f'      ... {len(runs)-12} more constant runs')
    # varying u32 fields on 4-byte boundaries: correlate with metrics
    if extra_metrics:
        limit = n - 3 if corr_limit is None else min(n - 3, corr_limit)
        for off in range(0, limit, 4):
            if any(rows[k]['const'] for k in range(off, off + 4)):
                continue
            vals = []
            ok = True
            for b in blobs:
                if len(b) < off + 4:
                    ok = False
                    break
                vals.append(int.from_bytes(b[off:off + 4], 'little'))
            if not ok:
                continue
            hints = []
            for mname, mvals in extra_metrics.items():
                if vals == list(mvals):
                    hints.append('== ' + mname)
                elif all(m for m in mvals) and len(set(round(v / m, 4) for v, m in zip(vals, mvals))) == 1:
                    hints.append(f'x{vals[0]/mvals[0]:.3g} * {mname}')
                else:
                    r = pearson(vals, mvals)
                    if r is not None and abs(r) > 0.9:
                        hints.append(f'corr({mname})={r:+.2f}')
            if only_hinted and not hints:
                continue
            vs = ' '.join(str(v) for v in vals)
            print(f'      u32@{off:<4} {vs:60s} {"; ".join(hints)}')


def pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def hexdump(b, base=0, indent='      '):
    out = []
    for i in range(0, len(b), 16):
        c = b[i:i + 16]
        out.append(f'{indent}{base+i:06x}  ' + ' '.join(f'{x:02x}' for x in c).ljust(48)
                   + ' ' + ''.join(chr(x) if 32 <= x < 127 else '.' for x in c))
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------

GZIP_STREAMS = ['Formats/Latest', 'Global/Latest', 'Global/ContentDocuments',
                'Global/ElemTable', 'Global/History', 'Global/DocumentIncrementTable',
                'Global/PartitionTable', 'Contents']


def analysis_prefix_table(table):
    print('\n' + '=' * 78)
    print('1. 8-BYTE PRE-GZIP PREFIX on Global/* streams (u64 LE per file)')
    print('=' * 78)
    print(f'    {"stream":30s} ' + ' '.join(f'{f[:8]:>8s}' for f in FILES) + '   constant?')
    for key, per in table.items():
        if not key.startswith('Global/'):
            continue
        vals = []
        for f in FILES:
            if f in per:
                vals.append(int.from_bytes(per[f][1][:8], 'little'))
            else:
                vals.append(None)
        cst = len(set(v for v in vals if v is not None)) == 1
        print(f'    {key:30s} ' + ' '.join(f'{("-" if v is None else v):>8}' for v in vals)
              + f'   {"CONSTANT" if cst else "varies"}')
    print("""
    Observation: the prefix is a per-STREAM-NAME constant across all six
    files, never varying with file: Global/Latest=5, ContentDocuments=1,
    DocumentIncrementTable=1, History=1, ElemTable=0, PartitionTable=0.
    [hypothesis] It is the serialization *version/flags word of the object
    stored in that stream* (ADocument=5, the four sub-containers 0/1), i.e.
    a class/format version stamped by the writer, not a per-file value and
    not a size/count (it does not correlate with any size or count).""")


def analysis_frames_and_trailers(table):
    print('\n' + '=' * 78)
    print('2. TRAILING DATA after each deflate payload + PAGE-FRAME TABLE')
    print('=' * 78)
    print(f'    Page framing: raw stream = pages of {PAGE_DATA} logical bytes,'
          f' each followed by a {PAGE_TRAILER}-byte page-trailer block '
          f'(stride {PAGE_STRIDE}).')
    print('    After DE-FRAMING, the bytes after every deflate payload are the '
          'standard 8-byte gzip trailer\n    (CRC32 LE + ISIZE LE, both VALID), '
          'then zero padding, then the final partial page trailer.\n')
    hdr = (f'    {"file/stream":48s} {"raw":>10s} {"frames":>6s} {"logical":>10s} '
           f'{"deflEnd":>9s} {"isize":>10s} {"crc_ok"} {"isz_ok"} {"zeros":>6s} {"ftrail":>6s}')
    print(hdr)
    all_valid = True
    frame_rows = []
    for key in GZIP_STREAMS + ['Partitions/<N>']:
        per = table.get(key)
        if not per:
            continue
        for f in FILES:
            if f not in per:
                continue
            name, raw, ment = per[f]
            frames = frame_offsets(len(raw))
            logical = deframe(raw)
            # first gzip member
            gz = logical.find(b'\x1f\x8b\x08')
            if gz < 0:
                continue
            try:
                info = inflate_member(logical, gz)
            except Exception as e:
                print(f'    {f}/{name}: inflate error {e}')
                all_valid = False
                continue
            tail = logical[info['defl_end'] + 8:]
            z = 0
            while z < len(tail) and tail[z] == 0:
                z += 1
            ftrail = len(tail) - z
            crc_ok = info['crc_ok']
            isz_ok = info['isize_ok']
            all_valid &= (crc_ok and isz_ok)
            if key == 'Partitions/<N>':
                zs, fs = '   n/a', '   n/a'   # tail = further gzip members
            else:
                zs, fs = f'{z:>6d}', f'{ftrail:>6d}'
            print(f'    {(f+"/"+name)[:48]:48s} {len(raw):>10d} {len(frames):>6d} '
                  f'{len(logical):>10d} {info["defl_end"]:>9d} {info["isize_stored"]:>10d} '
                  f'{str(crc_ok):>6s} {str(isz_ok):>6s} {zs} {fs}')
            frame_rows.append((f, name, len(raw), len(frames), len(logical), z, ftrail))
    print(f'\n    => gzip trailers valid for ALL de-framed streams: {all_valid}')
    print("""
    Trailer layout after the deflate payload (de-framed coordinates):
      +0  4B  u32 LE   CRC32 of inflated payload      (standard gzip)
      +4  4B  u32 LE   ISIZE = payload length mod 2^32 (standard gzip)
      +8  N   0x00...  zero padding (0..~500 bytes)
      +8+N M  hi-entropy final partial-page trailer, M ~= 353*lastPage/65249
              for large streams (min ~37..91 bytes for small streams), always
              starts 0x00 and last byte in {0x00,0x01}. Deterministic per
              stream content (identical Formats/Latest across all 6 files
              carry identical trailer bytes). [hypothesis] per-page
              integrity / ECC block written by Revit's paged stream writer.

    NOTE the pre-existing extraction (tools/scan_gzip.py, extracted/*.gz)
    inflates the FRAMED raw stream: any member whose compressed extent
    crosses a raw offset 64896 + n*65249 is silently corrupted from that
    point (or raises 'invalid block type' / 'invalid code lengths set').
    In racbasicsampleproject/Partitions/15, 90 of 400 sampled members
    cross a frame; all 90 fail CRC as extracted and 89/90 verify after
    de-framing.""")
    return frame_rows


def analysis_contents(table):
    print('\n' + '=' * 78)
    print('3. Contents STREAM WRAPPER (magic 62 19 22 05 = 0x05221962 LE)')
    print('=' * 78)
    per = table['Contents']
    print(f'    {"file":26s} {"tot":>4s} {"[4]hdrSz":>8s} {"[8]cnt":>6s} {"[12]":>6s} '
          f'{"[20]u32":>8s} {"gz@":>4s} {"defl":>5s} {"isize":>5s} {"crc":>5s} {"zeros":>5s} {"junk":>5s}')
    inflated = {}
    for f in FILES:
        name, raw, ment = per[f]
        magic0 = raw[0:4].hex()
        h4, h8, h12 = struct.unpack_from('<III', raw, 4)
        magic1 = raw[16:20].hex()
        u20 = struct.unpack_from('<I', raw, 20)[0]
        gz = raw.find(b'\x1f\x8b\x08')
        info = inflate_member(deframe(raw), gz)
        tail = raw[info['defl_end'] + 8:]
        z = 0
        while z < len(tail) and tail[z] == 0:
            z += 1
        inflated[f] = info['payload']
        print(f'    {f:26s} {len(raw):>4d} {h4:>8d} {h8:>6d} {h12:>6d} {u20:>8d} {gz:>4d} '
              f'{info["defl_end"]-gz:>5d} {info["isize_stored"]:>5d} '
              f'{"OK" if info["crc_ok"] else "BAD":>5s} {z:>5d} {len(tail)-z:>5d}'
              f'   magics={magic0}/{magic1}')
    print("""
    Wrapper layout (all offsets little-endian u32 unless noted):
      0x00  4B  magic     62 19 22 05  (=0x05221962)   constant
      0x04  4B  0x1c=28   [hypothesis] container format version/header id  constant
      0x08  4B  1         [hypothesis] item count (RevitPreview4.0 also =1)  constant
      0x0C  4B  0         reserved                                             constant
      0x10  4B  magic     62 19 22 05  again = start of item record            constant
      0x14  4B  varies    per-file (183,430,213,424,264,178) [hypothesis] item
                          type/class-id word; on RevitPreview4.0 this is 0x800C
                          = 0x8000 flag | class 12 (A3PartyAImage, the
                          FilePreview's m_pAImage type) with an UNcompressed
                          payload; here the payload is gzipped. Meaning of
                          the Contents value unresolved.
      0x18  ..  gzip member (10-byte header, raw deflate, valid 8-byte
                trailer CRC32+ISIZE), then zero pad + ~42-byte final
                page-trailer (see section 2).
    Inflated payload begins with the Revit build string in UTF-16
    ('20250227_1515(x64)'), GUIDs shared with Global/PartitionTable, the
    document name 'GLOBAL' and (in worksharing files) the last-saved-by
    username -> the Contents payload is a small storage-manifest record.""")
    return inflated


def analysis_identity(table):
    print('\n' + '=' * 78)
    print('4. INFLATED PAYLOAD IDENTITY ACROSS FILES (sha256 of de-framed inflate)')
    print('=' * 78)
    for key in ['Formats/Latest', 'Global/PartitionTable', 'Contents']:
        per = table[key]
        print(f'    {key}:')
        hashes = {}
        payloads = {}
        for f in FILES:
            name, raw, _ = per[f]
            gz = deframe(raw).find(b'\x1f\x8b\x08')
            info = inflate_member(deframe(raw), gz)
            h = hashlib.sha256(info['payload']).hexdigest()[:16]
            hashes[f] = h
            payloads[f] = info['payload']
            print(f'      {f:26s} len={len(info["payload"]):>8d}  sha256={h}  '
                  f'crc_ok={info["crc_ok"]} isize_ok={info["isize_ok"]}')
        uniq = set(hashes.values())
        print(f'      => {"IDENTICAL across all files" if len(uniq) == 1 else str(len(uniq)) + " distinct payloads"}')
    print("""
    Formats/Latest: byte-identical everywhere, TRUE size 496,597 bytes
    (gzip ISIZE), CRC32 0x26852216 - NOT the 498,766-byte blob produced by
    inflating the framed stream (that decode diverges into LZ garbage at
    payload offset 138,858). Global/PartitionTable and Contents payloads
    differ per file (per-project data) but share large constant regions.""")


def analysis_heads(table, filesize):
    print('\n' + '=' * 78)
    print('5. RAW STREAM HEADS (first 256 bytes) column constancy')
    print('=' * 78)
    for key, per in table.items():
        present = [f for f in FILES if f in per]
        if len(present) < 5:
            continue
        blobs = [per[f][1][:256] for f in present]
        metrics = OrderedDict()
        metrics['file_size'] = [filesize[f] for f in present]
        metrics['stream_size'] = [len(per[f][1]) for f in present]
        metrics['frames'] = [len(frame_offsets(len(per[f][1]))) for f in present]
        metrics['stream_size/1024'] = [len(per[f][1]) // 1024 for f in present]
        # gzip block count from index.json if available
        counts = []
        for f in present:
            idxp = os.path.join(EXTRACTED, f, per[f][0].replace('/', '__') + '.gz', 'index.json')
            try:
                counts.append(len(json.load(open(idxp))['members']))
            except Exception:
                counts.append(0)
        metrics['gzip_members(raw scan)'] = counts
        # correlations only make sense in the uncompressed header region;
        # a gzip body (or the deflate blocks of Partitions) is column noise.
        gz = [b.find(b'\x1f\x8b\x08') for b in blobs]
        corr_limit = min(g for g in gz if g >= 0) if any(g >= 0 for g in gz) else 64
        print(f'\n  -- {key}  ({len(present)}/6 files)   [u32 correlation scan '
              f'limited to header offsets < {corr_limit}]')
        rows = column_report(blobs, min(256, max(len(b) for b in blobs)))
        summarize_columns(rows, present, blobs, metrics, label='raw ',
                          corr_limit=corr_limit)


def analysis_inflated_heads(table, filesize):
    print('\n' + '=' * 78)
    print('6. INFLATED (de-framed) PAYLOAD HEADS (first 512 bytes) column constancy')
    print('=' * 78)
    for key in GZIP_STREAMS:
        per = table.get(key)
        if not per:
            continue
        present = [f for f in FILES if f in per]
        if len(present) < 5:
            continue
        blobs = []
        sizes = []
        for f in present:
            name, raw, _ = per[f]
            logical = deframe(raw)
            gz = logical.find(b'\x1f\x8b\x08')
            info = inflate_member(logical, gz)
            blobs.append(info['payload'][:512])
            sizes.append(len(info['payload']))
        metrics = OrderedDict()
        metrics['file_size'] = [filesize[f] for f in present]
        metrics['stream_size'] = [len(per[f][1]) for f in present]
        metrics['inflated_size'] = sizes
        print(f'\n  -- {key}  inflated sizes: ' + ', '.join(f'{f[:8]}={s}' for f, s in zip(present, sizes)))
        rows = column_report(blobs, min(512, max(len(b) for b in blobs)))
        summarize_columns(rows, present, blobs, metrics, label='inflated ',
                          only_hinted=True)


def analysis_partitions_header(table, filesize):
    print('\n' + '=' * 78)
    print('7. Partitions/<N> binary header (first 24 bytes) decode across files')
    print('=' * 78)
    print(f'    {"file/stream":38s} {"raw":>10s} {"logical":>10s} {"1stgz@":>7s}  first 44 header bytes')
    for f in FILES:
        for key in ['Partitions/<N>', 'Partitions/<extra>']:
            per2 = table.get(key, {})
            if f not in per2:
                continue
            name, raw, _ = per2[f]
            logical = deframe(raw)
            gz = raw.find(b'\x1f\x8b\x08')
            print(f'    {(f+"/"+name)[:38]:38s} {len(raw):>10d} {len(logical):>10d} {gz:>7d}  '
                  f'{raw[:44].hex()}')
    print("""
    Constant bytes across files: [0..13] 09000000 00000000 a3030000 0000
    (u64 9 - cf. the Global prefixes 5/1/0/1 - then u32 0x3a3=931
    [hypothesis: partition object/format version]), [16..23] 0000280f
    04000000, and [34..53] up to the first gzip magic at 44. The varying
    16-bit/32-bit fields at [14..15], [24..27], [28..31] scale with the
    Partitions stream size (see section 5 correlations) [hypothesis: total
    element/data-object counts or byte offsets]. Semantic decode of this
    header belongs to the Partitions agent; recorded here only for
    constancy.""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', help='restrict per-file dumps to one file')
    args = ap.parse_args()
    table, filesize = gather()
    print('Cross-file structural comparison, Revit 2026 corpus')
    print('files: ' + ', '.join(FILES))
    print(f'page frame constants: PAGE_DATA={PAGE_DATA} PAGE_TRAILER={PAGE_TRAILER} '
          f'stride={PAGE_STRIDE}')
    print('streams present in >=5 files: ' +
          ', '.join(k for k, v in table.items() if len(v) >= 5))
    analysis_prefix_table(table)
    analysis_frames_and_trailers(table)
    analysis_contents(table)
    analysis_identity(table)
    analysis_heads(table, filesize)
    analysis_inflated_heads(table, filesize)
    analysis_partitions_header(table, filesize)


if __name__ == '__main__':
    main()
