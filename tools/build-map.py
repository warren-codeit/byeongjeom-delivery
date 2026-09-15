#!/usr/bin/env python3
"""OpenStreetMap에서 병점역 일대를 받아 assets/data/map.json으로 굽는다.

사용: python3 tools/build-map.py
의존: 표준 라이브러리만. 네트워크(Overpass·OSRM 공개 서버) 필요.
좌표계: 중심(37.2115, 127.039)을 원점으로 한 미터 단위 평면. x 동쪽, y 남쪽(화면 좌표).
"""
import json, math, os, urllib.parse

UA = 'byeongjeom-delivery-game/0.1 (github.com/warren-codeit)'
BBOX = (37.201, 127.027, 37.221, 127.051)
LAT0, LON0 = 37.2115, 127.039
KX = math.cos(math.radians(LAT0)) * 111320
KY = 110540
STATION = (37.206834, 127.0331291)      # 병점역 (railway=station)
HOME = (37.2158467, 127.0455244)        # 주공 10·11단지 정류장
LANDMARKS = [('병점역', 0), ('병점사거리', 178), ('병점초등학교', 305), ('병점지하차도교차로', 493), ('화남아파트', 924),
             ('진안동 정류장', 1104), ('공영주차장사거리', 1158), ('중심상가사거리', 1375), ('롯데시네마', 1432), ('중심상가', 1587), ('주공 10·11단지', 1751)]
OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'data', 'map.json')


def P(lat, lon):
    return [round((lon - LON0) * KX, 1), round(-(lat - LAT0) * KY, 1)]


def get(url, data=None):
    # macOS 기본 python의 TLS가 overpass-api.de와 악수에 실패해 curl로 받는다
    import subprocess
    cmd = ['curl', '-sS', '--max-time', '180', '-A', UA, url] + (['--data', data] if data else [])
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return json.loads(out)


def simplify(pts, tol):
    if len(pts) < 3:
        return pts

    def dp(a, b):
        if b - a < 2:
            return [a, b]
        ax, ay = pts[a]; bx, by = pts[b]; mx, mi = 0, a
        for i in range(a + 1, b):
            px, py = pts[i]; dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy or 1
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > mx:
                mx, mi = d, i
        return dp(a, mi)[:-1] + dp(mi, b) if mx > tol else [a, b]
    return [pts[i] for i in dp(0, len(pts) - 1)]


CLASS = {'trunk': 'A', 'trunk_link': 'A', 'primary': 'A', 'primary_link': 'A', 'secondary': 'B', 'secondary_link': 'B',
         'tertiary': 'B', 'tertiary_link': 'B', 'residential': 'C', 'unclassified': 'C', 'living_street': 'C',
         'service': 'D', 'track': 'D', 'footway': 'F', 'cycleway': 'F', 'steps': 'F', 'pedestrian': 'F'}

b = '(%s,%s,%s,%s)' % BBOX
q = ('[out:json][timeout:60];(way["highway"]%s;way["railway"~"rail|subway"]%s;way["building"]%s;way["waterway"]%s;'
     'way["landuse"~"grass|park"]%s;way["leisure"~"park|playground|pitch"]%s;node["highway"="crossing"]%s;'
     'node["highway"="traffic_signals"]%s;node["name"]["amenity"]%s;node["name"]["shop"]%s;way["name"]["amenity"]%s;way["name"]["shop"]%s;'
     'node["public_transport"~"platform|stop_position"]%s;node["railway"~"station|subway_entrance"]%s;);out body;>;out skel qt;') % ((b,) * 14)
d = get('https://overpass-api.de/api/interpreter', 'data=' + urllib.parse.quote(q))
nodes = {e['id']: (e['lat'], e['lon']) for e in d['elements'] if e['type'] == 'node'}
roads, rails, blds, green, water = [], [], [], [], []
for e in d['elements']:
    if e['type'] != 'way':
        continue
    t = e.get('tags', {}); pts = [P(*nodes[n]) for n in e['nodes'] if n in nodes]
    if len(pts) < 2:
        continue
    if 'highway' in t:
        c = CLASS.get(t['highway'])
        if c:
            roads.append({'c': c, 'n': t.get('name', ''), 'p': simplify(pts, 1.5)})
    elif 'railway' in t:
        rails.append(simplify(pts, 1.5))
    elif 'building' in t:
        s = simplify(pts, 1.0)
        if len(s) >= 4:
            blds.append({'p': s[:-1] if s[0] == s[-1] else s, 'n': t.get('name', ''), 'a': t.get('building') in ('apartments', 'residential')})
    elif t.get('leisure') or t.get('landuse'):
        green.append(simplify(pts, 2))
    elif t.get('waterway'):
        water.append(simplify(pts, 2))
pois = []
for e in d['elements']:
    tg = e.get('tags', {})
    if not tg.get('name'):
        continue
    kind = tg.get('amenity') or tg.get('shop') or tg.get('railway') or tg.get('public_transport')
    if not kind:
        continue
    if e['type'] == 'node':
        pt = P(e['lat'], e['lon'])
    else:
        pts = [nodes[n] for n in e.get('nodes', []) if n in nodes]
        if not pts:
            continue
        pt = P(sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts))
    pois.append({'n': tg['name'], 'k': kind, 'p': pt})
cross = [P(e['lat'], e['lon']) for e in d['elements'] if e['type'] == 'node' and e.get('tags', {}).get('highway') == 'crossing']
sig = [P(e['lat'], e['lon']) for e in d['elements'] if e['type'] == 'node' and e.get('tags', {}).get('highway') == 'traffic_signals']

r = get('https://router.project-osrm.org/route/v1/driving/%s,%s;%s,%s?overview=full&geometries=geojson' % (STATION[1], STATION[0], HOME[1], HOME[0]))['routes'][0]
out = {'meta': {'center': [LAT0, LON0], 'kx': KX, 'ky': KY, 'attribution': '© OpenStreetMap contributors (ODbL). Route: OSRM.', 'route_m': r['distance']},
       'start': P(*STATION), 'goal': P(*HOME), 'route': [P(lat, lon) for lon, lat in r['geometry']['coordinates']],
       'roads': roads, 'rails': rails, 'buildings': blds, 'green': green, 'water': water, 'crossings': cross, 'signals': sig, 'pois': pois,
       'landmarks': [{'n': n, 's': s} for n, s in LANDMARKS]}
s = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open(OUT, 'w', encoding='utf-8').write(s)
print('wrote', OUT, len(s.encode()), 'bytes; roads', len(roads), 'buildings', len(blds), 'pois', len(pois), 'route', round(r['distance']), 'm')
