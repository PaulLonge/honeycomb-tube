"""Fetch the London Underground and Elizabeth line network from the TfL Unified API.

For each line, /Line/<id>/Route/Sequence/outbound gives every branch as an ordered list of stops. A station is
its TfL hub (topMostParentId) where it has one, so interchanges like King's Cross St. Pancras are a single node;
a link is two consecutive stops on a branch, labelled with every line that runs along it.

Writes data/network.json: {"nodes": {id: {name, lat, lon}}, "edges": [[a, b, [lines]], ...]}

    python fetch_network.py

Powered by TfL Open Data.
"""
import collections, json, os, re, urllib.request

LINES = ['bakerloo', 'central', 'circle', 'district', 'hammersmith-city', 'jubilee', 'metropolitan',
         'northern', 'piccadilly', 'victoria', 'waterloo-city', 'elizabeth']
UA = {'User-Agent': 'honeycomb-tube (github.com/PaulLonge/honeycomb-tube)'}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'network.json')


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()


def clean(name):
    """'Baker Street Underground Station' -> 'Baker Street'."""
    name = re.sub(r' (Underground|Rail|DLR)? ?Station$', '', name)
    name = re.sub(r' \(.*?\)$', '', name)
    return name.replace(' Underground', '').strip()


def network():
    nodes, edges = {}, collections.defaultdict(set)
    for line in LINES:
        d = json.loads(get(f'https://api.tfl.gov.uk/Line/{line}/Route/Sequence/outbound'))
        seqs = {s['branchId']: s for s in d['stopPointSequences']}
        key = lambda p: p.get('topMostParentId') or p['stationId']
        for s in seqs.values():
            ids = []
            for p in s['stopPoint']:
                nodes.setdefault(key(p), {'name': clean(p['name']), 'lat': p['lat'], 'lon': p['lon']})
                ids.append(key(p))
            for a, b in zip(ids, ids[1:]):
                if a != b:
                    edges[frozenset((a, b))].add(line)
            for nb in s.get('nextBranchIds', []):          # join a branch to the one it continues into
                if nb in seqs:
                    k0 = key(seqs[nb]['stopPoint'][0])
                    if ids[-1] != k0:
                        edges[frozenset((ids[-1], k0))].add(line)
    return {'nodes': nodes, 'edges': [[*sorted(e), sorted(ls)] for e, ls in edges.items()]}


if __name__ == '__main__':
    net = network()
    json.dump(net, open(OUT, 'w', encoding='utf-8'), indent=0)
    print(len(net['nodes']), 'stations,', len(net['edges']), 'links ->', OUT)
