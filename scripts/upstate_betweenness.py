"""Where does Rochester rank in the upstate New York rail network?

Builds one rail graph for all of upstate NY, scores every junction by
length-weighted betweenness, then aggregates junctions into the 53 upstate
cities and ranks the cities.

Upstate = New York State minus the downstate counties (the five NYC boroughs,
Nassau, Suffolk, Westchester, Rockland). Definitions of "upstate" vary; this one
is stated so the boundary effect is visible rather than hidden.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd

import railnet

HERE = Path(__file__).parent
DATA = HERE / "data"
FIGS = HERE / "figs"
CACHE = str(DATA / "osm_cache")

DOWNSTATE = [
    "Bronx County, New York, USA",
    "Kings County, New York, USA",
    "New York County, New York, USA",
    "Queens County, New York, USA",
    "Richmond County, New York, USA",
    "Nassau County, New York, USA",
    "Suffolk County, New York, USA",
    "Westchester County, New York, USA",
    "Rockland County, New York, USA",
]

# All 53 New York State cities outside the downstate counties above.
UPSTATE_CITIES = [
    "Albany", "Amsterdam", "Auburn", "Batavia", "Beacon", "Binghamton",
    "Buffalo", "Canandaigua", "Cohoes", "Corning", "Cortland", "Dunkirk",
    "Elmira", "Fulton", "Geneva", "Glens Falls", "Gloversville", "Hornell",
    "Hudson", "Ithaca", "Jamestown", "Johnstown", "Kingston", "Lackawanna",
    "Little Falls", "Lockport", "Mechanicville", "Middletown", "Newburgh",
    "Niagara Falls", "North Tonawanda", "Norwich", "Ogdensburg", "Olean",
    "Oneida", "Oneonta", "Oswego", "Plattsburgh", "Port Jervis",
    "Poughkeepsie", "Rensselaer", "Rochester", "Rome", "Salamanca",
    "Saratoga Springs", "Schenectady", "Sherrill", "Syracuse", "Tonawanda",
    "Troy", "Utica", "Watertown", "Watervliet",
]


# The exact state outline runs to ~5000 vertices, and Overpass has to test every
# one of them against every way. Inlined into a `poly:` query that is heavy
# enough that the endpoint drops the connection. 0.02 deg (~2 km) cuts it to ~65
# vertices while keeping 99.96% of the area — the study boundary only needs to be
# approximately right, since cities are assigned by their own polygons.
BOUNDARY_SIMPLIFY_DEG = 0.02


def upstate_polygon():
    ox.settings.use_cache = True
    ox.settings.cache_folder = CACHE
    state = ox.geocode_to_gdf("New York State, USA").loc[0, "geometry"]
    down = ox.geocode_to_gdf(DOWNSTATE).union_all()
    return state.difference(down).simplify(BOUNDARY_SIMPLIFY_DEG).buffer(0)


# Smallest upstate city (Sherrill) is ~7 km2, which is 6.6e-4 in squared degrees
# at this latitude. Anything an order of magnitude below that is not a city.
MIN_CITY_AREA_DEG2 = 5e-5


def city_polygons() -> gpd.GeoDataFrame:
    """Boundaries for the upstate cities, as a GeoDataFrame of name + geometry.

    Uses *structured* geocoding. Free-text "City of Buffalo, New York, USA"
    silently matches a cinema on Buffalo Road in Rochester — a real polygon, so
    an area>0 check waves it through, and Buffalo then scores zero junctions.
    Structured queries constrain the match to a place named Buffalo in New York.

    Geocoded one at a time so that one bad answer cannot take the other 52 down
    with it, and each result is checked for name and plausible size.
    """
    rows, rejected = [], []
    for city in UPSTATE_CITIES:
        # Structured first, free text as backup: structured resolves Buffalo
        # correctly but answers "Amsterdam" with the state of New York. Both
        # candidates go through the same two checks, which is what keeps the
        # free-text fallback from reintroducing the cinema.
        candidates = [
            {"city": city, "state": "New York", "country": "USA"},
            f"City of {city}, New York, USA",
        ]
        why = []
        for query in candidates:
            try:
                gdf = ox.geocode_to_gdf(query)
                geom, name = gdf.loc[0, "geometry"], gdf.loc[0, "display_name"]
            except (TypeError, ValueError, KeyError, IndexError) as exc:
                why.append(type(exc).__name__)
                continue
            if city.lower() not in name.lower():
                why.append(f"matched '{name[:32]}'")
            elif geom is None or geom.is_empty or geom.area < MIN_CITY_AREA_DEG2:
                why.append(f"area {geom.area:.1e}")
            else:
                rows.append({"city": city, "geometry": geom})
                break
        else:
            rejected.append(f"{city} ({'; '.join(why)})")

    if rejected:
        print(f"  rejected boundaries: {' | '.join(rejected)}")
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


FILTERS = {"through": railnet.THROUGH_FILTER, "all": railnet.RAIL_FILTER}


def build_graph(polygon, filter_name: str) -> nx.Graph:
    # `through` (no `service` tag) keeps the download small and drops yard track,
    # but relies on tagging that is uneven; `all` is ~2x the data and connects
    # more of the network. A 600 km tile is larger than upstate, so either goes
    # out as a single Overpass query instead of the default grid of ~50, each of
    # which is a chance to be dropped by a flaky backend.
    G = railnet.download_polygon(
        polygon, CACHE, custom_filter=FILTERS[filter_name], tile_km=600
    )
    print(f"raw OSM graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    U = railnet.prune_degree_two(railnet.to_simple_undirected(G))
    comps = sorted(nx.connected_components(U), key=len, reverse=True)
    km = sum(d["length"] for _, _, d in U.edges(data=True)) / 1000
    print(
        f"junction graph: {U.number_of_nodes()} nodes, {U.number_of_edges()} edges, "
        f"{len(comps)} components (largest = {len(comps[0])} nodes), {km:.0f} km track"
    )
    return U


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--filter", default="through", choices=sorted(FILTERS))
    p.add_argument("--tag", default=None, help="output suffix (default: --filter)")
    args = p.parse_args()
    tag = args.tag or args.filter

    U = build_graph(upstate_polygon(), args.filter)

    print("computing betweenness ...")
    node_bc, edge_bc = railnet.betweenness(U)
    nx.set_node_attributes(U, node_bc, "betweenness")
    nx.set_edge_attributes(U, edge_bc, "betweenness")
    nx.write_graphml(U, DATA / f"rail_upstate_{tag}.graphml")

    nodes = gpd.GeoDataFrame(
        {
            "osmid": list(U.nodes()),
            "degree": [U.degree(n) for n in U.nodes()],
            "betweenness": [node_bc[n] for n in U.nodes()],
        },
        geometry=gpd.points_from_xy(
            [U.nodes[n]["x"] for n in U.nodes()],
            [U.nodes[n]["y"] for n in U.nodes()],
        ),
        crs="EPSG:4326",
    )
    nodes["lon"] = nodes.geometry.x
    nodes["lat"] = nodes.geometry.y
    nodes.drop(columns="geometry").sort_values(
        "betweenness", ascending=False
    ).to_csv(DATA / f"node_betweenness_upstate_{tag}.csv", index=False)

    cities = city_polygons()
    print(f"resolved {len(cities)} of {len(UPSTATE_CITIES)} city boundaries")

    joined = gpd.sjoin(nodes, cities, how="inner", predicate="within")
    inside = joined["osmid"].nunique()
    print(
        f"{inside} of {len(nodes)} junctions ({inside / len(nodes):.0%}) "
        "fall inside a city boundary"
    )

    # Two aggregations, because they answer different questions: `total` is how
    # much of the network's traffic the city carries overall, `peak` is how
    # critical its single most important junction is.
    agg = (
        joined.groupby("city")["betweenness"]
        .agg(total="sum", peak="max", junctions="size")
        .reindex(cities["city"])
        .fillna({"total": 0.0, "peak": 0.0, "junctions": 0})
    )
    agg["junctions"] = agg["junctions"].astype(int)
    agg["rank_total"] = agg["total"].rank(ascending=False, method="min").astype(int)
    agg["rank_peak"] = agg["peak"].rank(ascending=False, method="min").astype(int)
    agg = agg.sort_values("total", ascending=False)
    agg.to_csv(DATA / f"city_betweenness_upstate_{tag}.csv")

    print("\nupstate NY cities by total rail betweenness")
    print(agg.head(15).to_string())

    roc = agg.loc["Rochester"]
    print(
        f"\nRochester: rank {roc.rank_total} of {len(agg)} by total "
        f"(sum={roc.total:.4f}), rank {roc.rank_peak} by peak junction "
        f"(max={roc.peak:.4f}), {roc.junctions} junctions"
    )

    plot(U, node_bc, cities, agg, tag)


def plot(U, node_bc, cities, agg, tag) -> None:
    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(19, 9), gridspec_kw={"width_ratios": [1.35, 1]}
    )
    for a in (ax, ax2):
        a.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#0d1117")

    cities.boundary.plot(ax=ax, color="#39414d", linewidth=0.6, zorder=0)

    nmax = max(node_bc.values()) or 1.0
    segs_x, segs_y = [], []
    for u, v in U.edges():
        segs_x += [U.nodes[u]["x"], U.nodes[v]["x"], None]
        segs_y += [U.nodes[u]["y"], U.nodes[v]["y"], None]
    ax.plot(segs_x, segs_y, color="#4a5568", linewidth=0.45, zorder=1)

    order = sorted(U.nodes(), key=lambda n: node_bc[n])
    ax.scatter(
        [U.nodes[n]["x"] for n in order],
        [U.nodes[n]["y"] for n in order],
        s=[2 + 130 * (node_bc[n] / nmax) for n in order],
        c=[node_bc[n] for n in order],
        cmap="plasma", linewidths=0, zorder=2,
    )

    roc = cities.loc[cities["city"] == "Rochester"].geometry.iloc[0].centroid
    ax.annotate(
        "Rochester", (roc.x, roc.y), color="white", fontsize=11, weight="bold",
        xytext=(roc.x - 1.3, roc.y + 0.55),
        arrowprops=dict(color="white", arrowstyle="->", linewidth=1.2), zorder=3,
    )
    ax.set_title(
        "Upstate NY rail network — junction betweenness",
        color="white", fontsize=14, pad=12,
    )
    ax.set_aspect("equal")
    ax.axis("off")

    top = agg.head(15)[::-1]
    colors = ["#f5b301" if c == "Rochester" else "#5a6b8c" for c in top.index]
    ax2.barh(top.index, top["total"], color=colors)
    ax2.set_title(
        "Total betweenness by city (top 15)", color="white", fontsize=14, pad=12
    )
    ax2.tick_params(colors="white", labelsize=10)
    for s in ax2.spines.values():
        s.set_color("#39414d")
    ax2.set_xlabel("sum of junction betweenness", color="white")

    out = FIGS / f"rail_betweenness_upstate_{tag}.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
