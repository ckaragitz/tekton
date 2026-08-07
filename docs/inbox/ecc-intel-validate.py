"""Corpus-wide validation of the CRCIO ECC reproduction (ecc-intel)."""
import gc, glob, importlib.util, sys, time
spec = importlib.util.spec_from_file_location('crcio', 'docs/inbox/ecc-intel-crcio.py')
crcio = importlib.util.module_from_spec(spec); spec.loader.exec_module(crcio)
import olefile
PAGE_PAYLOAD, PAGE_STRIDE = 64_896, 65_249

def main(paths):
    full_ok = full_bad = tails_ok = 0
    unframed = []; tail_bad = []
    t0 = time.time()
    for path in paths:
        ole = olefile.OleFileIO(path)
        for parts in ole.listdir(streams=True, storages=False):
            name = "/".join(parts)
            raw = ole.openstream(parts).read()
            nfull = len(raw) // PAGE_STRIDE
            for k in range(nfull):
                page = raw[k*PAGE_STRIDE:k*PAGE_STRIDE+PAGE_PAYLOAD]
                tr = raw[k*PAGE_STRIDE+PAGE_PAYLOAD:(k+1)*PAGE_STRIDE]
                if crcio.page_trailer(page) == tr:
                    full_ok += 1
                else:
                    full_bad += 1
                    print("FULL-PAGE MISMATCH", path, name, k)
            tail = raw[nfull*PAGE_STRIDE:]
            if not tail:
                continue
            sol = None
            for L in range(len(tail), max(-1, len(tail) - 1000), -1):
                p = crcio.select_params(L)
                N = crcio.size_field_bits(p[2], p[3])
                if crcio.encoded_size(L, p[0], p[2], p[3], N) == len(tail):
                    if crcio.encode_block(tail[:L], p) == tail:
                        sol = (L, p); break
            if sol:
                tails_ok += 1
            elif nfull == 0:
                unframed.append((path.split('/')[-1], name, len(raw)))
            else:
                tail_bad.append((path.split('/')[-1], name, len(tail)))
            del raw
        ole.close(); gc.collect()
        print(f"[{time.time()-t0:6.1f}s] done {path}: full_ok={full_ok} full_bad={full_bad} tails_ok={tails_ok}", flush=True)
    print(f"\nfull pages: ok={full_ok} bad={full_bad}")
    print(f"final blocks reproduced: {tails_ok}")
    print(f"unframed (no CRCIO framing at all): {len(unframed)}")
    for u in unframed: print("   ", u)
    print(f"tail failures on framed streams: {tail_bad}")

if __name__ == '__main__':
    main(sys.argv[1:] or sorted(glob.glob('samples/*.rvt')))
