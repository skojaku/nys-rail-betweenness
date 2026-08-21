"""Render the towns as an inline SVG map of upstate New York.

No tiles, no projection library, no network request at view time, because the
page that embeds this has none either.

Deliberately just two layers: the land, and the towns on it. The rail network
was drawn here once and it read as a scribble — a thousand faint segments with
no geography behind them. The map's job is to show that the six most central
towns lie on one west-to-east line; the track is not needed to say that.

The outline is the state boundary, which along the north and west *is* the Lake
Ontario and Lake Erie shore. That is what makes the shape read as New York.
"""

import argparse
import math
import random
from pathlib import Path

import json

import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, MultiLineString, MultiPolygon
from shapely.ops import linemerge, unary_union

from upstate_betweenness import CACHE, DOWNSTATE, city_polygons

HERE = Path(__file__).parent
DATA = HERE / "data"

W = 900.0
PAD = 30.0

# Coarser than a printed map on purpose. The hand-drawn pass bows each straight
# run, and a 0.004-degree outline has runs a few pixels long — bowing those gives
# fuzz, not a pen line. At 0.015 the coast is a few dozen deliberate strokes and
# the state is still unmistakably itself.
SIMPLIFY = 0.015

# West to east. The order is the map's argument: these six lie on one line.
CORRIDOR = ["Buffalo", "Rochester", "Syracuse", "Rome", "Utica", "Little Falls"]

# Where each label sits relative to its dot: (dx, dy, text-anchor). Rome, Utica
# and Little Falls are inside 60 km of each other and collide if all go on top.
LABEL = {
    "Buffalo": (-12, 5, "end"),
    "Rochester": (0, -15, "middle"),
    "Syracuse": (-4, 22, "middle"),
    "Rome": (0, -15, "middle"),
    "Utica": (6, 23, "start"),
    "Little Falls": (14, -9, "start"),
}


def land_polygon():
    ox.settings.use_cache = True
    ox.settings.cache_folder = CACHE
    state = ox.geocode_to_gdf("New York State, USA").loc[0, "geometry"]
    down = ox.geocode_to_gdf(DOWNSTATE).union_all()
    # Finer than the download polygon: this one is looked at, not queried with.
    return state.difference(down).simplify(SIMPLIFY)


def rings(geom):
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in polys:
        if p.area > 1e-4:  # drop slivers left by the county subtraction
            yield list(p.exterior.coords)


def rough(pts, seed, amp=2.2, jitter=1.4):
    """A ring redrawn as if by hand: every straight run becomes a slightly bowed
    curve and every corner shifts a little.

    Two things make this read as a pen rather than as noise. The bow is scaled
    by segment length, so a short segment barely moves and a long coastline
    sweeps; and the caller draws the ring twice with different seeds, which is
    what a hand does when it goes back over a line it has already drawn.
    """
    rnd = random.Random(seed)
    out = []
    n = len(pts)
    for i in range(n):
        px_, py_ = pts[i]
        qx, qy = pts[(i + 1) % n]
        px_ += rnd.uniform(-jitter, jitter)
        py_ += rnd.uniform(-jitter, jitter)
        dx, dy = qx - px_, qy - py_
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        k = rnd.uniform(-amp, amp) * min(1.0, L / 55.0)
        cx, cy = (px_ + qx) / 2 + nx * k, (py_ + qy) / 2 + ny * k
        if i == 0:
            out.append(f"M{px_:.1f} {py_:.1f}")
        out.append(f"Q{cx:.1f} {cy:.1f} {qx:.1f} {qy:.1f}")
    return "".join(out) + "Z"


def load_layer(name, land, simplify_deg, min_km):
    """Overpass `out geom` for one layer, merged into long lines and thinned.

    Merging first matters: the canal arrives as 208 separate ways and the main
    line as 8,588, and simplifying those one at a time keeps every join. Merged,
    a whole subdivision is one line and the tolerance can bite.
    """
    raw = json.loads((DATA / f"layer_{name}.json").read_text())
    lines = [
        LineString([(p["lon"], p["lat"]) for p in w["geometry"]])
        for w in raw["elements"] if len(w.get("geometry", [])) > 1
    ]
    merged = linemerge(unary_union(lines))
    parts = merged.geoms if isinstance(merged, MultiLineString) else [merged]
    keep = []
    for g in parts:
        g = g.simplify(simplify_deg)
        # Degrees to km at this latitude, near enough for a drop test.
        if g.length * 85.0 < min_km:
            continue
        g = g.intersection(land.buffer(0.03))
        for h in (g.geoms if hasattr(g, "geoms") else [g]):
            if isinstance(h, LineString) and len(h.coords) > 1:
                keep.append(list(h.coords))
    return keep


def rough_line(pts, seed, amp=1.4, jitter=0.7):
    """rough(), but for an open line: no closing segment, gentler hand."""
    rnd = random.Random(seed)
    out = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        px_, py_ = pts[i]
        qx, qy = pts[i + 1]
        qx += rnd.uniform(-jitter, jitter)
        qy += rnd.uniform(-jitter, jitter)
        dx, dy = qx - px_, qy - py_
        L = math.hypot(dx, dy) or 1.0
        k = rnd.uniform(-amp, amp) * min(1.0, L / 45.0)
        cx = (px_ + qx) / 2 - dy / L * k
        cy = (py_ + qy) / 2 + dx / L * k
        out.append(f"Q{cx:.1f} {cy:.1f} {qx:.1f} {qy:.1f}")
    return "".join(out)


# The Erie Canal, drawn rather than surveyed. OSM's `waterway=canal` for the
# Erie arrives as 208 ways with gaps where the route runs in the Mohawk or a
# lake, and drawn faithfully it reads as dashes rather than as a canal. What the
# map has to say is "one line, through these towns", so the line is one line: a
# spine of waypoints down the historic route, smoothed and drawn with the same
# pen as the coast. It is approximate on purpose and the caption says so.
CANAL_SPINE = [
    (-78.878, 42.886),  # Buffalo, the western terminus
    (-78.880, 43.020),  # Tonawanda
    (-78.690, 43.171),  # Lockport
    (-77.939, 43.213),  # Brockport
    (-77.611, 43.155),  # Rochester, over the Genesee
    (-77.442, 43.099),  # Fairport
    (-77.232, 43.062),  # Palmyra
    (-76.990, 43.064),  # Lyons
    (-76.869, 43.084),  # Clyde
    (-76.560, 43.049),  # Weedsport
    (-76.148, 43.048),  # Syracuse
    (-75.868, 43.045),  # Chittenango
    (-75.752, 43.081),  # Canastota
    (-75.456, 43.213),  # Rome, the Oneida Carry
    (-75.232, 43.101),  # Utica
    (-75.036, 43.015),  # Ilion
    (-74.859, 43.043),  # Little Falls, the gorge
    (-74.674, 43.001),  # St Johnsville
    (-74.570, 42.906),  # Canajoharie
    (-74.377, 42.956),  # Fonda
    (-74.188, 42.938),  # Amsterdam
    (-73.939, 42.814),  # Schenectady
    (-73.700, 42.774),  # Cohoes
    (-73.756, 42.652),  # Albany, where it meets the Hudson
]


def smooth(pts, seed, jitter=2.4):
    """One continuous line through the waypoints, with a hand on it.

    Catmull-Rom through jittered points, converted to cubics: the wobble lands
    on the route rather than on every segment, which is what a line drawn in one
    go looks like. Bowing each segment instead — the treatment the coast gets —
    made the canal look serrated at this scale.
    """
    rnd = random.Random(seed)
    p = [(x + rnd.uniform(-jitter, jitter), y + rnd.uniform(-jitter, jitter))
         for x, y in pts]
    p = [p[0]] + p + [p[-1]]
    d = [f"M{p[1][0]:.1f} {p[1][1]:.1f}"]
    for i in range(1, len(p) - 2):
        a, b, c, e = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (b[0] + (c[0] - a[0]) / 6, b[1] + (c[1] - a[1]) / 6)
        c2 = (c[0] - (e[0] - b[0]) / 6, c[1] - (e[1] - b[1]) / 6)
        d.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {c[0]:.1f} {c[1]:.1f}")
    return "".join(d)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", default="through")
    p.add_argument("--buffer-km", type=float, default=10.0)
    p.add_argument("--out", default=str(DATA / "map.svg"))
    args = p.parse_args()

    towns = pd.read_csv(DATA / f"town_betweenness_{args.tag}_{args.buffer_km:g}km.csv")
    cities = city_polygons().set_index("city")
    cent = {c: (g.centroid.x, g.centroid.y) for c, g in cities["geometry"].items()}

    land = land_polygon()
    lat0 = (land.bounds[1] + land.bounds[3]) / 2
    k = math.cos(math.radians(lat0))
    bx0, by0, bx1, by1 = land.bounds
    x0, x1, y0, y1 = bx0 * k, bx1 * k, by0, by1
    s = (W - 2 * PAD) / (x1 - x0)
    H = s * (y1 - y0) + 2 * PAD

    def px(lon, lat):
        return PAD + (lon * k - x0) * s, PAD + (y1 - lat) * s  # north is up

    shapes = []
    for ri, ring in enumerate(rings(land)):
        pts = [px(x, y) for x, y in ring[:-1]]
        first = rough(pts, seed=101 + ri)
        second = rough(pts, seed=202 + ri, amp=2.8, jitter=2.0)
        shapes.append(f'<path class="m-land" d="{first}"/>')
        shapes.append(f'<path class="m-ink" d="{first}"/>')
        shapes.append(f'<path class="m-ink m-ink2" d="{second}"/>')

    # Main line first, canal on top: where they run together — and along the
    # Mohawk they run within sight of each other — the canal is the argument.
    rails = load_layer("mainrail", land, 0.010, 12)
    for coords in rails:
        pts = [px(x, y) for x, y in coords]
        shapes.append(f'<path class="m-rail" d="{rough_line(pts, seed=len(shapes), amp=1.1)}"/>')

    spine = [px(x, y) for x, y in CANAL_SPINE]
    shapes.append(f'<path class="m-canal" d="{smooth(spine, seed=7)}"/>')
    shapes.append(f'<path class="m-canal m-canal2" d="{smooth(spine, seed=23, jitter=3.4)}"/>')
    print(f"  main line: {len(rails)} strokes, canal: one line of "
          f"{len(CANAL_SPINE)} waypoints")

    bmax = towns["betweenness"].max()
    dots, labels = [], []
    for _, r in towns.iterrows():
        t = r["town"]
        if t not in cent:
            continue
        cx, cy = px(*cent[t])
        top, host = t in CORRIDOR, t == "Rochester"
        rad = 2.4 + 7.4 * (r["betweenness"] / bmax) ** 0.75
        cls = "m-host" if host else ("m-top" if top else "m-town")
        dots.append(
            f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.1f}">'
            f'<title>{t} — betweenness {r["betweenness"]:.3f}</title></circle>'
        )
        if top:
            dx, dy, anc = LABEL[t]
            labels.append(
                f'<text class="{"m-lab m-lab-host" if host else "m-lab"}" '
                f'x="{cx + dx:.1f}" y="{cy + dy:.1f}" text-anchor="{anc}">{t}</text>'
            )

    svg = f"""<svg viewBox="0 0 {W:.0f} {H:.0f}" class="map" role="img" aria-label="Map of upstate New York. The six most central towns — Buffalo, Rochester, Syracuse, Rome, Utica and Little Falls — lie along one west-to-east line across the middle of the state, the line of the Erie Canal.">
{chr(10).join(shapes)}
{chr(10).join(dots)}
{chr(10).join(labels)}
</svg>"""

    Path(args.out).write_text(svg)
    print(f"wrote {args.out}  ({len(svg) / 1024:.0f} kB, {len(dots)} towns, "
          f"{W:.0f}x{H:.0f})")


if __name__ == "__main__":
    main()
