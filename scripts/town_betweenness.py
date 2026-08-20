"""One vertex per town: contract the upstate NY rail graph to a town network.

Instead of scoring 1,029 junctions and then arguing about how to aggregate them
into cities (sum? max?), collapse the network first: every junction inside a
city becomes part of that city's single vertex. Each town then has exactly one
betweenness number and the ranking needs no explanation.

Betweenness is measured over town-to-town traffic only — towns are the origins
and destinations, so the score answers "what share of journeys between other
towns pass through this one". Junctions out in the countryside stay in the graph
as pass-through, since routes run through them, but they are not endpoints.

Reads the graph built by upstate_betweenness.py, so it needs no new download.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from upstate_betweenness import city_polygons

HERE = Path(__file__).parent
DATA = HERE / "data"
FIGS = HERE / "figs"


def contract_to_towns(U: nx.Graph, cities: gpd.GeoDataFrame, buffer_km: float = 10.0):
    """Merge each city's junctions into one vertex. Returns (graph, town names).

    A junction counts as a town's if it lies within `buffer_km` of the town
    boundary, assigned to the nearest town when several are in range. Strict
    city limits (buffer_km=0) misplace the through routes: the CSX main line
    past Rochester runs about 3 km outside the boundary, through the suburbs, so
    Rochester ends up adjacent to the network rather than on it and scores a
    hard zero. Buffering is what makes the vertex mean "the town's rail access".

    Rural junctions survive as ordinary vertices — a route from Buffalo to
    Albany really does pass through junctions that belong to no town, and
    deleting them would reroute or disconnect it.
    """
    nodes = gpd.GeoDataFrame(
        {"node": list(U.nodes())},
        geometry=gpd.points_from_xy(
            [U.nodes[n]["x"] for n in U.nodes()],
            [U.nodes[n]["y"] for n in U.nodes()],
        ),
        crs="EPSG:4326",
    )
    crs = nodes.estimate_utm_crs()
    joined = gpd.sjoin_nearest(
        nodes.to_crs(crs),
        cities.to_crs(crs),
        how="inner",
        max_distance=max(buffer_km * 1000, 1e-6),
        distance_col="dist_m",
    )
    label = (
        joined.sort_values("dist_m")
        .drop_duplicates("node")
        .set_index("node")["city"]
        .to_dict()
    )

    H = nx.Graph()
    for u, v, d in U.edges(data=True):
        a, b = label.get(u, u), label.get(v, v)
        if a == b:
            continue  # edge internal to one town, now a self-loop
        length = float(d["length"])
        if H.has_edge(a, b) and H[a][b]["length"] <= length:
            continue
        H.add_edge(a, b, length=length)

    towns = {t for t in cities["city"] if t in H}
    for n in H.nodes():
        H.nodes[n]["is_town"] = n in towns
        if n not in towns:
            H.nodes[n]["x"] = U.nodes[n]["x"]
            H.nodes[n]["y"] = U.nodes[n]["y"]

    # Rural junctions of degree 2 are not junctions at all; splice them out so
    # the town graph is as small as it can be without changing any route.
    changed = True
    while changed:
        changed = False
        for n in [n for n, d in H.degree() if d == 2 and n not in towns]:
            a, b = list(H.neighbors(n))
            if a == b or H.has_edge(a, b):
                continue
            H.add_edge(a, b, length=H[n][a]["length"] + H[n][b]["length"])
            H.remove_node(n)
            changed = True
    H.remove_nodes_from([n for n, d in H.degree() if d == 0 and n not in towns])
    return H, towns


def town_betweenness(H: nx.Graph, towns: set) -> dict:
    """Share of town-to-town shortest paths running through each town."""
    raw = nx.betweenness_centrality_subset(
        H, sources=list(towns), targets=list(towns), weight="length", normalized=False
    )
    # betweenness_centrality_subset counts each unordered pair twice, and a town
    # can lie on paths between the other T-1 towns: (T-1)(T-2)/2 pairs.
    t = len(towns)
    scale = 2 / ((t - 1) * (t - 2)) if t > 2 else 1.0
    return {n: raw[n] * scale / 2 for n in towns}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", default="through")
    p.add_argument("--buffer-km", type=float, default=10.0)
    args = p.parse_args()

    U = nx.read_graphml(DATA / f"rail_upstate_{args.tag}.graphml")
    for _, _, d in U.edges(data=True):
        d["length"] = float(d["length"])
    print(f"junction graph: {U.number_of_nodes()} nodes, {U.number_of_edges()} edges")

    cities = city_polygons()
    H, towns = contract_to_towns(U, cities, args.buffer_km)
    print(
        f"town graph: {H.number_of_nodes()} vertices "
        f"({len(towns)} towns + {H.number_of_nodes() - len(towns)} rural junctions), "
        f"{H.number_of_edges()} edges"
    )

    bc = town_betweenness(H, towns)
    df = (
        pd.DataFrame(
            {
                "town": list(bc),
                "betweenness": [bc[t] for t in bc],
                "rail_neighbours": [H.degree(t) for t in bc],
            }
        )
        .sort_values("betweenness", ascending=False)
        .reset_index(drop=True)
    )
    df.insert(0, "rank", df["betweenness"].rank(ascending=False, method="min").astype(int))
    df.to_csv(DATA / f"town_betweenness_{args.tag}_{args.buffer_km:g}km.csv", index=False)

    print(f"\ntown-to-town betweenness ({len(towns)} towns on the network)")
    print(df.head(15).to_string(index=False))
    roc = df[df["town"] == "Rochester"].iloc[0]
    print(f"\nRochester: rank {roc['rank']} of {len(df)}, betweenness {roc.betweenness:.4f}")

    plot(df, f"{args.tag}_{args.buffer_km:g}km")


def plot(df: pd.DataFrame, tag: str) -> None:
    top = df.head(20)[::-1]
    fig, ax = plt.subplots(figsize=(9, 8))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    colors = ["#f5b301" if t == "Rochester" else "#5a6b8c" for t in top["town"]]
    ax.barh(top["town"], top["betweenness"], color=colors)
    ax.set_title(
        "Upstate NY: one vertex per town\ntown-to-town rail betweenness",
        color="white", fontsize=14, pad=14,
    )
    ax.set_xlabel("share of town-to-town shortest paths", color="white")
    ax.tick_params(colors="white", labelsize=10)
    for s in ax.spines.values():
        s.set_color("#39414d")
    out = FIGS / f"town_betweenness_{tag}.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
