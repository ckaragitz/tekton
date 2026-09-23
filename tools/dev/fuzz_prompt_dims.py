"""Fuzz the prompt -> dimension resolver against a per-prompt oracle (#812).

Every generated prompt carries what it states: each phrase's parameter and
value, restatements (same value), contradictions (either value is fine),
bare aliases (an alias with no number, which must NOT come back ``given``),
an "N x N" cross-dimension right before the noun, a count ("3 x 10 ft
long"), and the noun first / last / in the middle / absent.  Units, fractions,
hyphenated forms, connectors and separators are varied too.  A prompt passes
when every stated value is bound to its own phrase as ``given`` and nothing
unstated is ``given`` (a ``Param.follows`` follower of a stated leader is
``given`` by design).

The point is the COMPARISON, because the oracle is only as good as the
generator (a bare alias next to a number is often genuinely ambiguous):

    PYTHONPATH=<tree A>/src python -B tools/dev/fuzz_prompt_dims.py 1 20000 a.json
    PYTHONPATH=<tree B>/src python -B tools/dev/fuzz_prompt_dims.py 1 20000 b.json
    python tools/dev/fuzz_prompt_dims.py --compare a.json b.json

prints, per class, how many prompts B gets wrong that A got right.  Print
``rvt.__file__`` (it goes to stderr) and check it: ``tests/conftest.py``
puts its own tree first, so run this, not pytest, to compare trees.

Three rounds of #828 each shipped a regression that the author's own sweeps
could not produce, because every one of those sweeps shared a shape (noun
first; no cross with a restatement; no 'x' used as a separator).  This file is
the generator that found the fourth before a reviewer did; add a shape to it
whenever a review finds one it could not make.
"""
import collections
import json
import random
import sys


def _generate(seed, n_prompts, out):
    from rvt.famgen import archetypes as AR
    print("rvt", AR.__file__, file=sys.stderr)
    R = random.Random(seed)
    units = {"in": ["in", "inch", "inches", '"', "in."], "ft": ["ft", "feet", "foot", "'"]}
    conn = ["", "", "", "of ", "= ", ": ", "is "]
    seps = [" ", " ", ", ", " and ", "; ", " - ", " with ", ",", " that is ", " x ", " by "]

    def fmt(v):
        k = R.random()
        if k < 0.15 and v >= 2:
            n = R.choice([1, 3, 5, 7])
            return (f"{int(v)}-{n}/8" if R.random() < .5 else f"{int(v)} {n}/8"), int(v) + n / 8
        if k < 0.25:
            n, d = R.choice([(1, 2), (3, 4), (5, 8), (13, 16), (7, 16)])
            return f"{n}/{d}", n / d
        if k < 0.4:
            x = round(v + R.choice([0.25, 0.5, 0.75]), 2)
            return f"{x}", x
        return f"{int(v)}", float(int(v))

    def value_for(p):
        if p.unit == "ft":
            if R.random() < 0.8:
                t, v = fmt(R.randint(2, 20))
                return t, R.choice(units["ft"]), v
            t, v = fmt(R.randint(24, 120))
            return t, R.choice(units["in"]), v / 12
        lo = max(1, int(p.minimum) + 1)
        if R.random() < 0.1:
            t, v = fmt(R.randint(25, 300))
            return t, "mm", v / 25.4
        t, v = fmt(R.randint(lo, lo + 30))
        return t, R.choice(units["in"]), v

    def phrase(al, t, u):
        glue = "" if u in ('"', "'") else " "
        st = R.random()
        if st < 0.45:
            return f"{t}{glue}{u} {al}"
        if st < 0.55 and u in ("in", "ft", "inch", "foot"):
            return f"{t}-{u}-{al}"
        return f"{al} {R.choice(conn)}{t}{glue}{u}"

    def one(a):
        noun = a.title.split(" - ")[0].lower()
        ps = [p for p in a.params if p.aliases and p.unit in ("in", "ft")]
        R.shuffle(ps)
        k = R.randint(1, min(4, len(ps)))
        stated, bare = ps[:k], ps[k:k + R.choice([0, 0, 1])]
        cross_keys = [c for c in ("width_in", "height_in", "depth_in")
                      if any(p.key == c for p in a.params)]
        use_cross = len(cross_keys) >= 2 and R.random() < 0.3
        if use_cross:
            stated = [p for p in stated if p.key not in cross_keys]
        want, loose, parts = {}, {}, []
        for p in stated:
            t, u, v = value_for(p)
            ph = phrase(R.choice(p.aliases), t, u)
            if R.random() < 0.08 and ph[0].isdigit():
                ph = f"{R.randint(2, 6)} x {ph}"
            parts.append(ph)
            want[p.key] = v
            r = R.random()
            if r < 0.2:
                parts.insert(R.randint(0, len(parts)), phrase(R.choice(p.aliases), t, u))
            elif r < 0.3:
                t2, u2, v2 = value_for(p)
                parts.insert(R.randint(0, len(parts)), phrase(R.choice(p.aliases), t2, u2))
                loose[p.key] = (v, v2)
                del want[p.key]
        for p in bare:
            parts.insert(R.randint(0, len(parts)), R.choice(p.aliases))
        sep = R.choice(seps)
        cross_txt = ""
        if use_cross:
            vs = [R.randint(2, 30) for _ in range(R.choice([2, 3]) if len(cross_keys) >= 3 else 2)]
            cross_txt = " x ".join(str(x) for x in vs) + R.choice(["", " in", "in", '"', " inch"])
            if R.random() < .3:
                cross_txt = cross_txt.replace(" x ", "x")
            for c, x in zip(cross_keys, vs):
                want[c] = float(x)
        where = R.choice(["last", "middle"] if use_cross else ["first", "last", "middle", "absent"])
        art = R.choice(["a ", "an ", "", "the "])
        cx = cross_txt + " " if cross_txt else ""
        if where == "first":
            pr = f"{noun} {sep.join(parts)}"
        elif where == "absent":
            pr = sep.join(parts)
        elif where == "last":
            pr = f"{art}{sep.join(parts)} {cx}{noun}"
        else:
            cut = len(parts) // 2
            pr = f"{art}{sep.join(parts[:cut])} {cx}{noun} {sep.join(parts[cut:])}"
        cls = "+".join(x for x, f in (("cross", use_cross), ("bare", bool(bare)),
                                       ("contra", bool(loose)), ("noun-" + where, True)) if f)
        return " ".join(pr.split()), want, loose, cls

    def check(a, r, want, loose):
        for k, v in want.items():
            if r.provenance[k] != "given" or abs(r.values[k] - v) > 1e-3 * max(1, v):
                return False
        for k, vs in loose.items():
            if r.provenance[k] != "given" or min(abs(r.values[k] - v) for v in vs) > 1e-3 * max(1, max(vs)):
                return False
        ok = set(want) | set(loose)
        for k, pv in r.provenance.items():
            if pv == "given" and k not in ok:
                f = a.param(k).follows
                if not (f and f in ok and abs(r.values[k] - r.values[f]) < 1e-6):
                    return False
        return True

    res, keys = {}, list(AR.ARCHETYPES)
    while len(res) < n_prompts:
        key = R.choice(keys)
        a = AR.archetype(key)
        pr, want, loose, cls = one(a)
        if not want and not loose:
            continue
        try:
            ok = check(a, AR.resolve_prompt(pr, product=key), want, loose)
        except Exception as e:                       # noqa: BLE001 -- a crash is a finding
            ok, cls = False, cls + "+EXC:" + type(e).__name__
        res[pr + "|" + key] = [ok, cls]
    json.dump(res, open(out, "w", encoding="utf-8"))
    print(len(res), "prompts,", sum(not v[0] for v in res.values()), "wrong")


def _compare(a_path, b_path):
    a = json.load(open(a_path, encoding="utf-8"))
    b = json.load(open(b_path, encoding="utf-8"))
    worse = [k for k in a if a[k][0] and not b[k][0]]
    better = [k for k in a if not a[k][0] and b[k][0]]
    by = collections.Counter(b[k][1].split("+noun")[0] or "plain" for k in worse)
    print(f"A wrong {sum(not v[0] for v in a.values())}, B wrong {sum(not v[0] for v in b.values())}; "
          f"B worse than A on {len(worse)} {dict(by)}, better on {len(better)}")
    for k in worse[:10]:
        print("   ", k)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--compare"]:
        _compare(sys.argv[2], sys.argv[3])
    else:
        _generate(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
