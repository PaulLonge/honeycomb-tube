"""Place every station in its own hexagon, near its real position, with lines running through neighbouring cells.

1. Project each station's latitude and longitude onto a plane centred on Charing Cross, stretched east-west
   (London is wider than it is tall) and fisheyed, so zone 1 gets room and the long branches are pulled in.
2. Snap stations to the nearest free hex cell, centre outwards.
3. Improve the placement by simulated annealing, moving one station at a time (or swapping two). The cost adds:
     --edge   linked stations should sit in touching cells
     --pos    a station should stay near where it really is
     --turn   lines should run straight through a station
     --dir    a link should point the way it really goes (east stays east); high values stop lines folding back
4. Write {station id: [q, r]} in axial hex coordinates.

The published map (data/cells.json) is:
    python layout.py --seed 3 --edge 4 --pos 1.2 --turn 2.0 --dir 10
which leaves 5 links pointing against the real geography. With --dir 0 the map is straighter but folds: the
Elizabeth line ends up running Taplow, Maidenhead, Twyford, Reading from west to east.

    python layout.py [--seed N] [--edge W] [--pos W] [--turn W] [--dir W] [--steps N] [--out data/cells.json]
"""
import argparse, collections, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--seed', type=int, default=3)
ap.add_argument('--edge', type=float, default=4.0)
ap.add_argument('--pos', type=float, default=1.2)
ap.add_argument('--turn', type=float, default=2.0)
ap.add_argument('--dir', type=float, default=10.0)
ap.add_argument('--steps', type=int, default=1_500_000)
ap.add_argument('--network', default=os.path.join(HERE, 'data', 'network.json'))
ap.add_argument('--out', default=os.path.join(HERE, 'data', 'cells.json'))
A = ap.parse_args()
W_EDGE, W_POS, W_TURN, W_DIR = A.edge, A.pos, A.turn, A.dir
random.seed(A.seed)

net = json.load(open(A.network, encoding='utf-8'))
N = net['nodes']
E = [(a, b, ls) for a, b, ls in net['edges']]
ids = sorted(N)

# 1. Projection: Charing Cross at the origin, kilometres, stretched and fisheyed.
C = (51.5080, -0.1247)
ASPECT = 1.35
POW = 0.5


def plane(la, lo):
    x = (lo - C[1]) * math.cos(math.radians(C[0])) * 111.3
    y = (C[0] - la) * 111.3
    d = math.hypot(x, y) or 1e-9
    k = d ** POW / d
    return x * k * ASPECT, y * k


P = {s: plane(N[s]['lat'], N[s]['lon']) for s in ids}
SCALE = 1.28
S3 = math.sqrt(3)
T = {s: ((S3 / 3 * P[s][0] - P[s][1] / 3) / SCALE, (2 / 3 * P[s][1]) / SCALE) for s in ids}   # target, axial


def hd(a, b):              # hex distance
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[0] + a[1] - b[0] - b[1])) // 2


def xy(c):                 # axial -> plane
    return (S3 * (c[0] + c[1] / 2), 1.5 * c[1])


DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def cube_round(q, r):
    x, z = q, r; y = -x - z
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz: rx = -ry - rz
    elif dy > dz: ry = -rx - rz
    else: rz = -rx - ry
    return rx, rz


# 2. Greedy start: centre outwards, each station to the nearest free cell.
cell, occ = {}, {}
for s in sorted(ids, key=lambda s: math.hypot(*P[s])):
    c0 = cube_round(*T[s]); seen, frontier = {c0}, [c0]
    while True:
        free = [c for c in frontier if c not in occ]
        if free:
            best = min(free, key=lambda c: (c[0] - T[s][0]) ** 2 + (c[1] - T[s][1]) ** 2); break
        nxt = []
        for c in frontier:
            for d in DIRS:
                n = (c[0] + d[0], c[1] + d[1])
                if n not in seen: seen.add(n); nxt.append(n)
        frontier = nxt
    cell[s] = best; occ[best] = s

adj = collections.defaultdict(list)
per_line = collections.defaultdict(lambda: collections.defaultdict(set))
for a, b, ls in E:
    adj[a].append(b); adj[b].append(a)
    for l in ls:
        per_line[l][a].add(b); per_line[l][b].add(a)
triples = set()            # (a, s, b): s sits between a and b on one line
for l, g in per_line.items():
    for s, nb in g.items():
        nb = sorted(nb)
        if len(nb) == 2:
            triples.add((nb[0], s, nb[1]))
tri_of = collections.defaultdict(list)
for t in triples:
    for m in t: tri_of[m].append(t)


def turn(t):               # 0 straight on, 2 doubling back
    a, s, b = (xy(cell[m]) for m in t)
    v1 = (s[0] - a[0], s[1] - a[1]); v2 = (b[0] - s[0], b[1] - s[1])
    n1, n2 = math.hypot(*v1) or 1, math.hypot(*v2) or 1
    return 1 - (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)


def dirc(a, b):            # 0 same way as reality; heavy once it runs backwards
    ca, cb = xy(cell[a]), xy(cell[b]); ta, tb = xy(T[a]), xy(T[b])
    v1 = (cb[0] - ca[0], cb[1] - ca[1]); v2 = (tb[0] - ta[0], tb[1] - ta[1])
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / ((math.hypot(*v1) or 1) * (math.hypot(*v2) or 1))
    return (1 - cos) / 2 * (1 + 3 * (cos < 0))


def pos(s):
    dq, dr = cell[s][0] - T[s][0], cell[s][1] - T[s][1]
    return math.hypot(dq + dr / 2, dr * S3 / 2)


def local(ss):             # the cost of everything touching the stations in ss
    es = {(min(a, b), max(a, b)) for s in ss for b in adj[s] for a in (s,)}
    ts = {t for s in ss for t in tri_of[s]}
    return (W_EDGE * sum(max(0, hd(cell[a], cell[b]) - 1) ** 1.3 for a, b in es)
            + W_POS * sum(pos(s) for s in ss)
            + W_TURN * sum(turn(t) for t in ts)
            + W_DIR * sum(dirc(a, b) for a, b in es))


def total():
    return (W_EDGE * sum(max(0, hd(cell[a], cell[b]) - 1) ** 1.3 for a, b, _ in E)
            + W_POS * sum(pos(s) for s in ids) + W_TURN * sum(turn(t) for t in triples)
            + W_DIR * sum(dirc(a, b) for a, b, _ in E))


# 3. Simulated annealing.
t0, t1 = 2.5, 0.01
for i in range(A.steps):
    temp = t0 * (t1 / t0) ** (i / A.steps)
    s = random.choice(ids)
    base = cell[random.choice(adj[s])] if adj[s] and random.random() < 0.5 else cell[s]
    d = random.choice(DIRS); k = 2 if random.random() < 0.25 else 1
    c = (base[0] + d[0] * k, base[1] + d[1] * k)
    if c == cell[s]:
        continue
    o = occ.get(c); old = cell[s]
    ss = [s] + ([o] if o else [])
    before = local(ss)
    cell[s] = c; occ[c] = s
    if o: cell[o] = old; occ[old] = o
    else: del occ[old]
    dlt = local(ss) - before
    if dlt > 0 and random.random() > math.exp(-dlt / temp):
        cell[s] = old; occ[old] = s
        if o: cell[o] = c; occ[c] = o
        else: del occ[c]
    if i % 300_000 == 0:
        print(f'{i:>9,} steps  cost {total():.1f}', flush=True)

bad = sum(1 for a, b, _ in E if hd(cell[a], cell[b]) > 1)
turns = sum(1 for t in triples if turn(t) > 0.6)
back = sum(1 for a, b, _ in E if dirc(a, b) > 0.5)
print(f'seed {A.seed}: {bad} links not neighbours, {turns} sharp turns of {len(triples)}, {back} backwards, cost {total():.0f}')
json.dump({s: list(cell[s]) for s in ids}, open(A.out, 'w'))
print('->', A.out)
