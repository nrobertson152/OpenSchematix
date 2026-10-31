"""Robustness fuzz: degenerate / near-degenerate drawings. Checks that every
accepted region contains the pick, has a flattened area equal to its exact
area, and that other interior picks find the same region."""
import math, os, random, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from openschematix.model import Shape
from openschematix.boundary_fill import find_region
from openschematix import regions as rg

def L(i, a, b): return Shape(i, "line", pts=[a, b])
def A(i, c, r, s, e): return Shape(i, "arc", c=c, r=r, start=s, extent=e)
def C(i, c, r): return Shape(i, "circle", c=c, r=r)

def scen(kind, rnd):
    if kind == "big_radius":     # nearly straight arcs from huge circles
        sh = [A(i, (rnd.uniform(0, 100), 1e6 * rnd.choice([-1, 1])), 1e6 + rnd.uniform(-50, 50), rnd.choice([89.99, 269.99]), 0.02) for i in range(6)]
        sh += [L(10 + i, (rnd.uniform(0, 100), rnd.uniform(-150, 150)), (rnd.uniform(0, 100), rnd.uniform(-150, 150))) for i in range(10)]
        return sh, (0, 100, -150, 150)
    if kind == "tiny":           # features near the snap tolerance
        s = 0.05
        sh = [L(i, (rnd.uniform(0, 1), rnd.uniform(0, 1)), (rnd.uniform(0, 1), rnd.uniform(0, 1))) for i in range(12)]
        sh += [C(50 + i, (rnd.uniform(0, 1), rnd.uniform(0, 1)), rnd.uniform(s, 0.4)) for i in range(4)]
        return sh, (0, 1, 0, 1)
    if kind == "near_parallel":
        sh = []
        for i in range(12):
            a = rnd.uniform(-1e-4, 1e-4)
            y = rnd.uniform(0, 100)
            sh.append(L(i, (0, y), (100, y + 100 * math.tan(a))))
        sh += [L(100 + i, (x, -5), (x + rnd.uniform(-1, 1), 105)) for i, x in enumerate(rnd.sample(range(0, 100), 6))]
        return sh, (0, 100, 0, 100)
    if kind == "concurrent":     # many lines through one point, plus a ring
        sh = [L(i, (50 + 60 * math.cos(t), 50 + 60 * math.sin(t)), (50 - 60 * math.cos(t), 50 - 60 * math.sin(t)))
              for i, t in enumerate(rnd.uniform(0, math.pi) for _ in range(16))]
        sh += [C(100, (50, 50), 40), C(101, (50 + rnd.uniform(-1e-3, 1e-3), 50), 20)]
        return sh, (0, 100, 0, 100)
    if kind == "noisy_grid":     # grid geometry with sub-tolerance noise and duplicates
        n = lambda: rnd.uniform(-0.004, 0.004)
        sh = []
        for i in range(8):
            sh.append(L(i, (n(), i * 10 + n()), (70 + n(), i * 10 + n())))
            sh.append(L(20 + i, (i * 10 + n(), n()), (i * 10 + n(), 70 + n())))
        sh += [C(40 + i, (rnd.randrange(1, 7) * 10, rnd.randrange(1, 7) * 10), rnd.choice([5, 10, 15])) for i in range(5)]
        sh += [A(60 + i, (rnd.randrange(1, 7) * 10, rnd.randrange(1, 7) * 10), 10, rnd.choice([0, 90, 180, 270]), 90) for i in range(5)]
        return sh, (0, 70, 0, 70)
    if kind == "far_away":       # large coordinates
        o = 2.5e6
        sh = [L(i, (o + rnd.uniform(0, 300), o + rnd.uniform(0, 300)), (o + rnd.uniform(0, 300), o + rnd.uniform(0, 300))) for i in range(15)]
        sh += [C(50 + i, (o + rnd.uniform(0, 300), o + rnd.uniform(0, 300)), rnd.uniform(10, 80)) for i in range(5)]
        return sh, (o, o + 300, o, o + 300)
    if kind == "tangent_chains":
        sh = [C(i, (20 * i, 0), 10) for i in range(6)] + [C(10 + i, (20 * i + 10, 0), 10 * math.sqrt(2) - 10) for i in range(5)]
        sh += [L(30, (-20, -10), (120, -10)), L(31, (-20, 10), (120, 10))]
        return sh, (-10, 110, -10, 10)
    raise KeyError(kind)

KINDS = ["big_radius", "tiny", "near_parallel", "concurrent", "noisy_grid", "far_away", "tangent_chains"]

def run(seeds=30, verbose=True):
    bad = 0; checked = 0
    for kind in KINDS:
        for seed in range(seeds):
            rnd = random.Random(seed * 1000 + KINDS.index(kind))
            sh, (x0, x1, y0, y1) = scen(kind, rnd)
            for _ in range(12):
                p = (rnd.uniform(x0, x1), rnd.uniform(y0, y1))
                try:
                    res = find_region(sh, p)
                except Exception as e:  # noqa
                    bad += 1; print("EXC", kind, seed, p, type(e).__name__, e); continue
                if not res.ok: continue
                checked += 1
                ok = rg.point_in_rings(res.rings, p) and res.area > 0
                scale = max(1.0, (x1 - x0))
                tol = 1e-5 * scale
                fl = sum(rg.ring_area([(x, y, 0) for x, y in rg.flatten_ring(r, tol)]) for r in res.rings)
                if abs(fl - res.area) > max(1e-6 * scale * scale, 1e-3 * res.area):
                    ok = False; print("AREA", kind, seed, p, fl, res.area)
                b = rg.rings_bbox(res.rings); n = 0
                for _ in range(300):
                    q = (rnd.uniform(b[0], b[2]), rnd.uniform(b[1], b[3]))
                    if rg.point_in_rings(res.rings, q) and rg.boundary_distance(res.rings, q) > 0.02:
                        r2 = find_region(sh, q)
                        if not (r2.ok and abs(r2.area - res.area) <= 1e-6 * max(1, res.area)):
                            ok = False; print("INCONS", kind, seed, p, q, res.area, r2.area, r2.message); break
                        n += 1
                        if n == 3: break
                if not ok: bad += 1
    print("checked", checked, "bad", bad)
    return bad

if __name__ == "__main__":
    run()
