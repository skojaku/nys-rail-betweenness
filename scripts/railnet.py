"""Shared helpers for building and scoring OSM rail networks."""

import time
from collections import deque

import networkx as nx
import osmnx as ox
import requests

# overpass-api.de round-robins between two named backends, and one can refuse
# connections while the other serves fine — a download left to the round-robin
# fails roughly half the time with ECONNREFUSED, which reads like a rate limit
# but is not. Pin to one backend by name.
#
# This must be a CONSTANT, not something probed per call: OSMnx keys its
# response cache on the request URL, so an endpoint that varies between runs
# turns every cache hit into a fresh download — which is how we got IP-banned
# re-fetching data we already had on disk.
OVERPASS_ENDPOINT = "https://lambert.openstreetmap.de/api"


def overpass_available(url: str = OVERPASS_ENDPOINT, timeout: int = 15) -> bool:
    """True if the pinned Overpass backend is currently answering."""
    try:
        r = requests.get(
            f"{url}/status",
            headers={"User-Agent": ox.settings.http_user_agent},
            timeout=timeout,
        )
    except requests.RequestException:
        return False
    return r.status_code == 200

# OSM railway values that carry trains. Excludes disused/abandoned/razed
# (e.g. the old Rochester subway) and yard-only tags like `service`.
RAIL_FILTER = '["railway"~"^(rail|light_rail|subway|tram|narrow_gauge)$"]'

# Through-running track only: `usage=main|branch` drops industrial spurs and
# yard leads. At state scale that is most of the data volume and almost none of
# the betweenness — spurs are dead ends, so they score ~0 either way.
#
# Do not use this one for centrality. `usage` is tagged unevenly in the US, and
# every untagged segment becomes a gap that cuts the network in two: upstate NY
# comes back as 37 components whose largest holds barely half the junctions.
MAINLINE_FILTER = '["railway"="rail"]["usage"~"^(main|branch)$"]'

# Preferred filter at regional scale. Absence of a `service` tag is what
# distinguishes running line from yard track, sidings, spurs and crossovers, and
# it does not depend on `usage` being filled in — so the network stays connected.
# Barely larger than MAINLINE_FILTER (12.5k vs 11.3k ways statewide).
THROUGH_FILTER = '["railway"="rail"]["service"!~"."]'


def download_polygon(
    polygon,
    cache_folder: str,
    custom_filter: str = RAIL_FILTER,
    tile_km: float = 50,
    retries: int = 5,
) -> nx.MultiDiGraph:
    """Fetch the rail network inside `polygon` (WGS84).

    OSMnx splits the polygon into tiles of `tile_km` square and issues one
    Overpass query each. The public endpoint allows two concurrent slots and
    starts refusing connections when a large area is fired at it as dozens of
    small tiles, so state-scale callers should pass a bigger `tile_km` and lean
    on the retry loop rather than the default 50 km grid.
    """
    ox.settings.use_cache = True
    ox.settings.cache_folder = cache_folder
    ox.settings.overpass_rate_limit = True
    ox.settings.requests_timeout = 600
    ox.settings.max_query_area_size = (tile_km * 1000) ** 2

    ox.settings.overpass_url = OVERPASS_ENDPOINT

    for attempt in range(retries):
        try:
            return ox.graph.graph_from_polygon(
                polygon,
                custom_filter=custom_filter,
                retain_all=True,  # rail networks are genuinely disconnected
                truncate_by_edge=True,
                simplify=True,
            )
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            if attempt == retries - 1:
                raise
            wait = 10 * 2**attempt
            print(f"  overpass attempt {attempt + 1} failed ({exc}); retry in {wait}s")
            time.sleep(wait)


def to_simple_undirected(G: nx.MultiDiGraph) -> nx.Graph:
    """Collapse the OSMnx multigraph to a simple undirected graph.

    Track direction is a signalling detail, not a topological one: a train can
    traverse a line either way, so betweenness belongs on the undirected graph.
    Parallel edges collapse to the shortest.
    """
    U = nx.Graph()
    U.add_nodes_from(G.nodes(data=True))
    for u, v, d in G.edges(data=True):
        if u == v:
            continue
        length = float(d.get("length", 0.0))
        if U.has_edge(u, v) and U[u][v]["length"] <= length:
            continue
        U.add_edge(u, v, length=length)
    return U


def prune_degree_two(G: nx.Graph) -> nx.Graph:
    """Splice out degree-2 nodes, summing lengths.

    OSMnx keeps a node wherever two OSM ways meet even when nothing branches
    there. Those nodes are not junctions and would otherwise dominate the
    ranking with the betweenness of the line segment they sit on.

    Worklist-driven: splicing a node can make a neighbour degree-2, so only the
    touched neighbours get re-queued rather than rescanning the whole graph.
    """
    H = G.copy()
    queue = deque(n for n, d in H.degree() if d == 2)
    while queue:
        n = queue.popleft()
        if n not in H or H.degree(n) != 2:
            continue
        a, b = list(H.neighbors(n))
        if a == b or H.has_edge(a, b):
            continue
        H.add_edge(a, b, length=H[n][a]["length"] + H[n][b]["length"])
        H.remove_node(n)
        for m in (a, b):
            if H.degree(m) == 2:
                queue.append(m)
    H.remove_nodes_from([n for n, d in H.degree() if d == 0])
    return H


def betweenness(G: nx.Graph, weight: str = "length"):
    """Length-weighted, normalized node and edge betweenness.

    Uses igraph's C implementation when available — NetworkX's pure-Python
    Brandes is too slow once the graph passes a few thousand junctions.
    Falls back to NetworkX so the script still runs without igraph.
    """
    try:
        import igraph
    except ImportError:
        return (
            nx.betweenness_centrality(G, weight=weight, normalized=True),
            nx.edge_betweenness_centrality(G, weight=weight, normalized=True),
        )

    nodes = list(G.nodes())
    index = {n: i for i, n in enumerate(nodes)}
    edges = [(index[u], index[v]) for u, v in G.edges()]
    weights = [G[u][v][weight] for u, v in G.edges()]
    g = igraph.Graph(n=len(nodes), edges=edges, directed=False)

    n = len(nodes)
    # igraph returns raw pair counts; networkx normalizes by the pair total.
    node_scale = 2.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
    edge_scale = 2.0 / (n * (n - 1)) if n > 1 else 1.0

    node_bc = {
        nodes[i]: bc * node_scale
        for i, bc in enumerate(g.betweenness(weights=weights))
    }
    edge_bc = {
        (nodes[e[0]], nodes[e[1]]): bc * edge_scale
        for e, bc in zip(edges, g.edge_betweenness(weights=weights))
    }
    return node_bc, edge_bc
