"""World map geometry for the regulation tracker, with no third-party packages.

templates/world.json is generated once from the world-atlas TopoJSON (Natural Earth, public domain):

    curl -o countries-110m.json https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json
    python -m aipulse.geo countries-110m.json

It holds one pre-projected SVG path per country (Equal Earth projection), keyed by ISO 3166-1
numeric id, so the page draws the map without a charting library.

templates/us.json (the tracker's map of US states) comes from us-atlas, already projected (Albers USA,
with Alaska and Hawaii inset):

    curl -o states-albers-10m.json https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json
    python -m aipulse.geo states-albers-10m.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "templates" / "world.json"
US_OUT = OUT.with_name("us.json")
SCALE = 150  # SVG units per projected unit
X_MAX = 2.7064  # |x| of the Equal Earth projection at the antimeridian
Y_MAX = 1.3173  # |y| at the poles
SKIP = {"Antarctica", "Fr. S. Antarctic Lands"}

_A1, _A2, _A3, _A4 = 1.340264, -0.081106, 0.000893, 0.003796
_M = math.sqrt(3) / 2


def project(lon: float, lat: float) -> tuple[float, float]:
    """Equal Earth projection, shifted so the top-left of the world is (0, 0)."""
    lam, phi = math.radians(lon), math.radians(lat)
    t = math.asin(_M * math.sin(phi))
    t2, t6 = t * t, t ** 6
    x = lam * math.cos(t) / (_M * (_A1 + 3 * _A2 * t2 + t6 * (7 * _A3 + 9 * _A4 * t2)))
    y = t * (_A1 + _A2 * t2 + t6 * (_A3 + _A4 * t2))
    return round((x + X_MAX) * SCALE, 1), round((Y_MAX - y) * SCALE, 1)


def _decode_arcs(topo: dict) -> list[list[tuple[float, float]]]:
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def _ring(arcs, indexes: list[int]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in indexes:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(seg[1:] if pts else seg)  # consecutive arcs share an endpoint
    return pts


def _unwrap(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Keep longitudes continuous across the antimeridian (Russia, Fiji).

    Otherwise the ring jumps from +180 to -180 and streaks across the whole map; unwrapped,
    the few points past 180° fall just outside the map and are clipped.
    """
    out, shift = [], 0.0
    for i, (lon, lat) in enumerate(ring):
        if i:
            step = lon - ring[i - 1][0]
            shift += -360 if step > 180 else 360 if step < -180 else 0
        out.append((lon + shift, lat))
    return out


def _path(rings: list[list[tuple[float, float]]]) -> str:
    out = []
    for ring in rings:
        xy = [project(lon, lat) for lon, lat in _unwrap(ring)]
        dedup = [p for i, p in enumerate(xy) if i == 0 or p != xy[i - 1]]
        if len(dedup) >= 3:
            out.append("M" + "L".join(f"{x:g},{y:g}" for x, y in dedup) + "Z")
    return "".join(out)


def build(topo: dict) -> dict:
    arcs = _decode_arcs(topo)
    countries, max_y = [], 0.0
    for g in topo["objects"]["countries"]["geometries"]:
        name = g["properties"]["name"]
        if name in SKIP or g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        rings = [_ring(arcs, r) for poly in polys for r in poly]
        d = _path(rings)
        max_y = max(max_y, *(project(lon, lat)[1] for ring in rings for lon, lat in ring))
        countries.append({"id": g.get("id") or name, "name": name, "d": d})
    width = round(2 * X_MAX * SCALE, 1)
    top = project(0, 84)[1]  # northernmost land in the atlas is ~83.6°N
    return {"viewBox": f"0 {top:g} {width:g} {round(max_y - top + 4, 1):g}", "countries": countries}


def build_us(topo: dict) -> dict:
    """US states from the pre-projected us-atlas file, keyed by postal code ("CA")."""
    from .jurisdictions import US_STATES
    code_of = {name: code for code, name in US_STATES.items()}
    arcs = _decode_arcs(topo)
    states, xs, ys = [], [], []
    for g in topo["objects"]["states"]["geometries"]:
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        rings = [_ring(arcs, r) for poly in polys for r in poly]
        parts = []
        for ring in rings:
            pts = [(round(x, 1), round(y, 1)) for x, y in ring]
            xs += [x for x, _ in pts]; ys += [y for _, y in pts]
            parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        states.append({"id": code_of[g["properties"]["name"]], "name": g["properties"]["name"], "d": "".join(parts)})
    pad = 4
    box = (min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
    return {"viewBox": " ".join(f"{v:g}" for v in (round(b, 1) for b in box)), "states": states}


if __name__ == "__main__":
    topo = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if "states" in topo["objects"]:
        data = build_us(topo)
        US_OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {US_OUT} ({len(data['states'])} states, {US_OUT.stat().st_size // 1024} KB)")
    else:
        data = build(topo)
        OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {OUT} ({len(data['countries'])} countries, {OUT.stat().st_size // 1024} KB)")
