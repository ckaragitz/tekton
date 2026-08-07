#!/usr/bin/env python3
"""Extract every OLE stream from each sample .rvt into extracted/<file>/,
writing raw stream bytes plus a manifest.json with size, sha256, and the
first 64 bytes as hex + a naive magic classification.

This is the shared corpus every downstream analysis agent works from.
"""
import olefile, os, sys, json, hashlib

SAMPLES = os.path.join(os.path.dirname(__file__), '..', 'samples')
OUT = os.path.join(os.path.dirname(__file__), '..', 'extracted')

MAGICS = [
    (b'\x1f\x8b\x08', 'gzip'),
    (b'PK\x03\x04', 'zip'),
    (b'\x89PNG\r\n\x1a\n', 'png'),
    (b'<\x00?\x00x\x00m\x00l\x00', 'utf16-xml'),
]


def classify(head: bytes) -> str:
    for sig, name in MAGICS:
        if head.startswith(sig):
            return name
    # gzip after a short header (8 bytes) is the common Global/* layout
    if head[8:11] == b'\x1f\x8b\x08':
        return 'hdr8+gzip'
    if head[4:14] == b'<\x00?\x00x\x00m\x00l\x00':
        return 'hdr4+utf16-xml'
    if head[:4] == b'\x62\x19\x22\x05':
        return 'magic-05221962'
    return 'unknown'


def safe(name: str) -> str:
    return name.replace('/', '__')


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in sorted(os.listdir(SAMPLES)):
        if not f.lower().endswith('.rvt'):
            continue
        base = os.path.splitext(f)[0]
        d = os.path.join(OUT, base)
        os.makedirs(d, exist_ok=True)
        ole = olefile.OleFileIO(os.path.join(SAMPLES, f))
        manifest = {'file': f, 'size': os.path.getsize(os.path.join(SAMPLES, f)), 'streams': []}
        for parts in ole.listdir(streams=True, storages=False):
            name = '/'.join(parts)
            data = ole.openstream(parts).read()
            with open(os.path.join(d, safe(name) + '.bin'), 'wb') as fh:
                fh.write(data)
            manifest['streams'].append({
                'name': name,
                'size': len(data),
                'sha256': hashlib.sha256(data).hexdigest(),
                'head_hex': data[:64].hex(),
                'kind': classify(data[:64]),
            })
        ole.close()
        with open(os.path.join(d, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=2)
        print(f"{base}: {len(manifest['streams'])} streams -> {d}")


if __name__ == '__main__':
    main()
