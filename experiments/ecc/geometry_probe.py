"""ecc-geometry: definitive final-block divisor probe.

For every final (partial-page) block of every stream in every available .rvt/
.rfa (six 2026 samples + vendor files), find ALL generators of the form
g(x) = h(x^I) — h a primitive trinomial of degree m (m in 2..11, plus
reciprocals) — that divide the whole final block viewed as a GF(2)
polynomial (bits LSB-first per byte, first bit = highest degree; leading
zero bytes are harmless high zero coefficients).  A genuine hit has
p_chance = 2^-(I*m), so any hit with I*m >= 60 is certain.  From the winning
(I,m) we derive the field length F = ceil(I*m/8) (+ the constraint P>=D) and
report the payload/field geometry exactly.
"""
from __future__ import annotations
import glob, sys, os, json
import numpy as np
sys.path.insert(0,'/Users/ck/dev/things/rev-revit/src')
from rvt.container import open_rvt, PAGE_PAYLOAD, PAGE_TRAILER, PAGE_STRIDE

ROOT='/Users/ck/dev/things/rev-revit'
TRI={  # primitive trinomials x^m + x^k + 1 (all k with k<=m/2), degree->list of k
 2:[1], 3:[1], 4:[1], 5:[2], 6:[1], 7:[1,3], 9:[4], 10:[3], 11:[2],
}
def poly(m,k): return (1<<m)|(1<<k)|1
def recip(p):
    m=p.bit_length()-1
    r=0
    for i in range(m+1):
        if p>>i&1: r|=1<<(m-i)
    return r
POLYS={}
for m,ks in TRI.items():
    s=set()
    for k in ks:
        s.add(poly(m,k)); s.add(recip(poly(m,k)))
    POLYS[m]=sorted(s)

def lane_regs(block: bytes, I: int, hpolys):
    """residues (mod h(y)) of the I lane polynomials, for each h in hpolys.
    Returns array (nh, I) of registers; zero everywhere => divisible by h(x^I)."""
    N=len(block)*8
    bits=np.unpackbits(np.frombuffer(block,np.uint8), bitorder='little')
    padn=(-N)%I
    if padn: bits=np.concatenate([np.zeros(padn,np.uint8),bits])
    M=bits.reshape(-1,I)
    ms=[h.bit_length()-1 for h in hpolys]
    nh=len(hpolys)
    reg=np.zeros((nh,I),np.uint32)
    hl=np.array([h & ((1<<m)-1) for h,m in zip(hpolys,ms)],np.uint32).reshape(nh,1)
    mm=np.array(ms,np.uint32).reshape(nh,1)
    mask=np.array([(1<<m)-1 for m in ms],np.uint32).reshape(nh,1)
    for row in M:
        reg=(reg<<np.uint32(1))|row.astype(np.uint32)
        over=(reg>>mm)&1
        reg=(reg&mask)^(over*hl)
    return reg

def final_blocks(files):
    for f in files:
        try: d=open_rvt(f)
        except Exception: continue
        fn=os.path.basename(f)
        for s in d.streams():
            raw=d.raw(s.name)
            nf=len(raw)//PAGE_STRIDE
            if nf and len(raw)==nf*PAGE_STRIDE:
                nf-=1
            rem=raw[nf*PAGE_STRIDE:]
            if len(rem)<20: continue
            ms=d.members(s.name)
            D=None
            if ms:
                end=ms[-1].offset+ms[-1].consumed
                D=end-nf*PAGE_PAYLOAD
            after=rem[D:] if D is not None else rem
            z=len(after)-len(after.lstrip(bytes(1)))
            nz=len(after)-z
            yield fn, s.name, len(ms), rem, D, nz

def probe_block(rem, nz, D):
    R=len(rem)
    # F window from structure
    Fmin=max(1,nz-3); Fmax=min(R-1,nz+10)
    hits=[]
    for m,plist in POLYS.items():
        Ilo=max(1,(8*Fmin-63)//m); Ihi=min(255,(8*Fmax)//m)
        for I in range(Ilo,Ihi+1):
            regs=lane_regs(rem,I,plist)
            for h,r in zip(plist,regs):
                if not r.any():
                    hits.append((I*m,I,m,h))
    return sorted(hits, reverse=True)

if __name__=='__main__':
    files=sorted(glob.glob(f'{ROOT}/samples/*.rvt'))+sorted(glob.glob(f'{ROOT}/vendor/**/*.rvt',recursive=True))+sorted(glob.glob(f'{ROOT}/vendor/**/*.rfa',recursive=True))
    rows=[]
    for fn, sn, nmem, rem, D, nz in final_blocks(files):
        R=len(rem)
        hits=probe_block(rem, nz, D)
        best=hits[0] if hits else None
        if best:
            IM,I,m,h=best
            F=-(-IM//8)
            # allow field to start earlier if leading bytes zero? report base bits
            P=R-F
            base=8*F-IM
            desc=f"BEST I={I} m={m} h=0x{h:x} I*m={IM} F={F} P={P} base={base} ok(P>=D)={D is None or P>=D}"
        else:
            desc="NO DIVISOR (unframed or rule outside search)"
        print(f"{fn[:28]:29s} {sn:28s} R={R:6d} D={str(D):>6s} nz={nz:4d} :: {desc} others={[(i,m,hex(h)) for _,i,m,h in hits[1:6]]}")
        sys.stdout.flush()
        rows.append(dict(file=fn,stream=sn,R=R,D=D,nz=nz,hits=[(i,m,h) for _,i,m,h in hits]))
    json.dump(rows, open('/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/geom/probe_all.json','w'))
