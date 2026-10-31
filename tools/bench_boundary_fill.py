"""Boundary-fill benchmarks. Usage: python tools/bench_boundary_fill.py [repo_dir]  (prints median seconds per case)."""
import math, os, random, statistics, sys, time
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from openschematix.model import Shape
from openschematix.boundary_fill import find_region

def L(i, a, b): return Shape(i, "line", pts=[a, b])
def C(i, c, r): return Shape(i, "circle", c=c, r=r)
def A(i, c, r, s, e): return Shape(i, "arc", c=c, r=r, start=s, extent=e)

def grid(n):
    return [L(i, (0, i * 10), (n * 10, i * 10)) for i in range(n + 1)] + [L(1000 + i, (i * 10, 0), (i * 10, n * 10)) for i in range(n + 1)], (n * 5 + 5, n * 5 + 5)

def crossing_lines_arcs(n):
    random.seed(1)
    sh = [L(i, (random.uniform(0, 1000), random.uniform(0, 1000)), (random.uniform(0, 1000), random.uniform(0, 1000))) for i in range(n)]
    sh += [A(10000 + i, (random.uniform(0, 1000), random.uniform(0, 1000)), random.uniform(20, 300), random.uniform(0, 360), random.uniform(30, 330)) for i in range(n)]
    return sh, (500, 500)

def circles(n):
    random.seed(2)
    return [C(i, (random.uniform(0, 1000), random.uniform(0, 1000)), random.uniform(10, 80)) for i in range(n)], (500, 500)

def sparse_schematic(n):
    random.seed(0)
    sh = [Shape(1, "rect", pts=[(0, 0), (4000, 0), (4000, 3000), (0, 3000)])]
    for i in range(n // 10):
        x, y = random.uniform(50, 3900), random.uniform(50, 2900)
        sh.append(Shape(10 + i, "rect", pts=[(x, y), (x + 30, y), (x + 30, y + 20), (x, y + 20)]))
    for i in range(n):
        x, y = random.uniform(50, 3950), random.uniform(50, 2950)
        sh.append(L(100000 + i, (x, y), (x + random.uniform(-20, 20), y + random.uniform(-20, 20))))
    return sh, (10, 10)

CASES = [
    ("grid 41x41 lines", lambda: grid(40), {}),
    ("grid 81x81 lines", lambda: grid(80), {}),
    ("200 lines + 200 arcs, dense crossings", lambda: crossing_lines_arcs(200), {}),
    ("600 overlapping circles", lambda: circles(600), {}),
    ("sparse schematic 3000 stubs + 300 boxes", lambda: sparse_schematic(3000), {}),
    ("sparse schematic, gap 1 mm", lambda: sparse_schematic(3000), {"gap": 4}),
    ("grid 41x41, gap 1 mm", lambda: grid(40), {"gap": 4}),
]

def run(reps=3):
    out = {}
    for name, make, kw in CASES:
        sh, p = make()
        times = []
        for _ in range(reps):
            t = time.perf_counter(); r = find_region(sh, p, **kw); times.append(time.perf_counter() - t)
        out[name] = (statistics.median(times), r.ok, round(r.area, 6), r.holes)
        print(f"{name:45s} {statistics.median(times):8.3f} s  ok={r.ok} area={r.area:.6f} holes={r.holes}", flush=True)
    return out

if __name__ == "__main__":
    run()
