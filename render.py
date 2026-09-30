"""Draw the honeycomb map as an SVG: one hexagon per station, the lines drawn through the cell centres.

    python render.py                              # cells shaded by how many lines serve each station
    python render.py values.json --title "..."    # cells shaded by your own numbers: {station id: number}

Station ids are TfL hub ids, as in data/network.json. Writes docs/honeycomb.svg (or --out).
"""
import argparse, collections, html, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('values', nargs='?', help='JSON of {station id: number} to shade the cells by')
ap.add_argument('--title', default='The Tube as a honeycomb')
ap.add_argument('--out', default=os.path.join(HERE, 'docs', 'honeycomb.svg'))
A = ap.parse_args()

net = json.load(open(os.path.join(HERE, 'data', 'network.json'), encoding='utf-8'))
cells = json.load(open(os.path.join(HERE, 'data', 'cells.json'), encoding='utf-8'))
N = net['nodes']
# Line colours: TfL's published palette, used to say which line is which (not as branding).
LINE = {'bakerloo': '#B36305', 'central': '#E32017', 'circle': '#FFD300', 'district': '#00782A',
        'hammersmith-city': '#F3A9BB', 'jubilee': '#A0A5A9', 'metropolitan': '#9B0056', 'northern': '#231F20',
        'piccadilly': '#003688', 'victoria': '#0098D4', 'waterloo-city': '#95CDBA', 'elizabeth': '#6950A1'}
ORDER = list(LINE)
# Purple ramp; the lightest stop is kept clearly darker than the background so every cell reads as a cell.
RAMP = [(232, 206, 222), (205, 150, 190), (160, 90, 150), (110, 45, 110), (60, 14, 70)]
R, S3 = 14.0, math.sqrt(3)


def mix(t):
    t = max(0, min(1, t)) * (len(RAMP) - 1); i = min(len(RAMP) - 2, int(t)); f = t - i
    return 'rgb(%d,%d,%d)' % tuple(round(RAMP[i][k] + (RAMP[i + 1][k] - RAMP[i][k]) * f) for k in range(3))


per = collections.defaultdict(set)
for a, b, ls in net['edges']:
    per[a].update(ls); per[b].update(ls)
if A.values:
    vals = {k: float(v) for k, v in json.load(open(A.values, encoding='utf-8')).items() if v is not None}
    legend = 'your values'
else:
    vals = {s: len(per[s]) for s in cells}
    legend = 'lines serving the station'
lo, hi = min(vals.values()), max(vals.values())

pts = {s: (R * S3 * (c[0] + c[1] / 2), R * 1.5 * c[1]) for s, c in cells.items()}
xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
ox, oy = -min(xs) + 40, -min(ys) + 150
W, H = max(xs) - min(xs) + 80, max(ys) - min(ys) + 210
out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" font-family="system-ui,sans-serif">',
       '<rect width="100%" height="100%" fill="#FAF0DB"/>',
       f'<text x="40" y="52" font-size="30" font-weight="700" fill="#2B1A0C">{html.escape(A.title)}</text>']
for s, (x, y) in pts.items():
    v = vals.get(s)
    fill = mix((v - lo) / ((hi - lo) or 1)) if v is not None else '#E4DDD0'
    pp = ' '.join(f'{x + ox + R * math.cos(math.radians(60 * i - 30)):.1f},{y + oy + R * math.sin(math.radians(60 * i - 30)):.1f}'
                  for i in range(6))
    out.append(f'<polygon points="{pp}" fill="{fill}" stroke="#FAF0DB" stroke-width="2"><title>{html.escape(N[s]["name"])}'
               f'{"" if v is None else f": {v:g}"}</title></polygon>')
for a, b, ls in net['edges']:
    (x1, y1), (x2, y2) = pts[a], pts[b]
    dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1; nx, ny = -dy / L, dx / L
    for i, l in enumerate(sorted(ls, key=ORDER.index)):
        off = (i - (len(ls) - 1) / 2) * 3.4
        out.append(f'<line x1="{x1 + ox + nx * off:.1f}" y1="{y1 + oy + ny * off:.1f}" x2="{x2 + ox + nx * off:.1f}" '
                   f'y2="{y2 + oy + ny * off:.1f}" stroke="{LINE[l]}" stroke-width="3" stroke-linecap="round"/>')
for s, (x, y) in pts.items():
    big = len(per[s]) > 1
    out.append(f'<circle cx="{x + ox:.1f}" cy="{y + oy:.1f}" r="{3.6 if big else 2.2}" fill="#fff" stroke="#231F20" '
               f'stroke-width="{1.4 if big else 1}"/>')
key = ''.join(f'<rect x="{40 + i * 22}" y="{H - 44}" width="22" height="12" fill="{mix(i / 9)}"/>' for i in range(10))
out.append(key + f'<text x="40" y="{H - 52}" font-size="13" fill="#6A4A22">{html.escape(legend)}: {lo:g} to {hi:g}</text>')
NAMES = {'bakerloo': 'Bakerloo', 'central': 'Central', 'circle': 'Circle', 'district': 'District',
         'hammersmith-city': 'Hammersmith & City', 'jubilee': 'Jubilee', 'metropolitan': 'Metropolitan', 'northern': 'Northern',
         'piccadilly': 'Piccadilly', 'victoria': 'Victoria', 'waterloo-city': 'Waterloo & City', 'elizabeth': 'Elizabeth'}
for i, l in enumerate(ORDER):
    x, y = 40 + (i % 4) * 160, 74 + (i // 4) * 18
    out.append(f'<rect x="{x}" y="{y - 5}" width="18" height="5" rx="2" fill="{LINE[l]}"/>'
               f'<text x="{x + 24}" y="{y}" font-size="12" fill="#2B1A0C">{html.escape(NAMES[l])}</text>')
out.append(f'<text x="{W - 40}" y="{H - 34}" font-size="12" fill="#6A4A22" text-anchor="end">Powered by TfL Open Data · '
           f'github.com/PaulLonge/honeycomb-tube</text></svg>')
os.makedirs(os.path.dirname(A.out), exist_ok=True)
open(A.out, 'w', encoding='utf-8').write('\n'.join(out))
print(len(pts), 'stations ->', A.out)
