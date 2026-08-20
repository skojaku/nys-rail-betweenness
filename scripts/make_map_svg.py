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
from pathlib import Path

import osmnx as ox
import pandas as pd
from shapely.geometry import MultiPolygon

from upstate_betweenness import CACHE, DOWNSTATE, city_polygons

HERE = Path(__file__).parent
DATA = HERE / "data"

W = 900.0
PAD = 26.0

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
    return state.difference(down).simplify(0.004)


def rings(geom):
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in polys:
        if p.area > 1e-4:  # drop slivers left by the county subtraction
            yield list(p.exterior.coords)


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

    shapes = [
        '<path class="m-land" d="M'
        + "L".join(f"{a:.1f} {b:.1f}" for a, b in (px(x, y) for x, y in ring))
        + 'Z"/>'
        for ring in rings(land)
    ]

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
