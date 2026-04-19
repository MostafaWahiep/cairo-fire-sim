"""Cairo road network graph — built from real OpenStreetMap data via OSMnx."""

import os
import math
from pathlib import Path

import numpy as np
import osmnx as ox
import networkx as nx
from scipy.spatial import KDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra as sp_dijkstra

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# Greater Cairo bounding box — osmnx v2 format: (west, south, east, north)
_DEFAULT_BBOX = (31.18, 29.98, 31.36, 30.13)

# Cache file so we only hit the Overpass API once
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
_CACHE_FILE = _CACHE_DIR / "cairo_roads.graphml"

# Speed assumptions (km/h) by OSM highway tag
_SPEED_MAP = {
    "motorway": 80, "motorway_link": 60,
    "trunk": 60, "trunk_link": 45,
    "primary": 50, "primary_link": 40,
    "secondary": 40, "secondary_link": 35,
    "tertiary": 35, "tertiary_link": 30,
    "residential": 25, "living_street": 20,
    "unclassified": 25, "service": 15,
}
_DEFAULT_SPEED = 25  # km/h fallback


# ---------------------------------------------------------------------------
# Graph loading / caching
# ---------------------------------------------------------------------------

def _load_or_download(bbox, cache_path):
    """Return a simplified NetworkX MultiDiGraph, cached to disk."""
    if cache_path.exists():
        print(f"  Loading cached road graph from {cache_path}")
        return ox.load_graphml(cache_path)

    print("  Downloading road network from OpenStreetMap …")
    G = ox.graph_from_bbox(
        bbox=bbox,
        network_type="drive",
    )
    # osmnx v2 already simplifies inside graph_from_bbox

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, cache_path)
    print(f"  Cached to {cache_path}")
    return G


def _edge_travel_time(data):
    """Compute travel time in minutes for one edge from its OSM attributes."""
    length_m = data.get("length", 0)  # osmnx always fills this

    highway = data.get("highway", "")
    if isinstance(highway, list):
        highway = highway[0]

    speed = _SPEED_MAP.get(highway, _DEFAULT_SPEED)
    return (length_m / 1000.0) / speed * 60.0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CairoRoadNetwork:
    """Real-road network for Greater Cairo, powered by OSMnx.

    Public API is identical to the old grid-based version so that
    CoverageAnalyzer, app.py routes, and the frontend work unchanged.
    """

    # Lat/lon bounds (extracted from the bbox for coverage grid / frontend)
    LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = _DEFAULT_BBOX

    def __init__(self, cache_path=None):
        cache_path = Path(cache_path) if cache_path else _CACHE_FILE

        self.nodes = {}                # nid -> (lat, lon)
        self._edge_count = 0

        self._build(cache_path)

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build(self, cache_path):
        G = _load_or_download(_DEFAULT_BBOX, cache_path)

        # Extract nodes
        for osm_id, data in G.nodes(data=True):
            self.nodes[osm_id] = (data["y"], data["x"])  # (lat, lon)

        # Index mappings:  node-id <-> dense integer index
        self._node_ids = list(self.nodes.keys())
        self._nid_to_idx = {nid: i for i, nid in enumerate(self._node_ids)}
        n = len(self._node_ids)

        # Build sparse CSR adjacency matrix (bidirectional, weights = travel time)
        rows, cols, weights = [], [], []
        seen = set()
        for u, v, data in G.edges(data=True):
            time_min = _edge_travel_time(data)
            ui, vi = self._nid_to_idx[u], self._nid_to_idx[v]
            for a, b in [(ui, vi), (vi, ui)]:
                if (a, b) not in seen:
                    rows.append(a)
                    cols.append(b)
                    weights.append(time_min)
                    seen.add((a, b))

        self._graph = csr_matrix(
            (weights, (rows, cols)), shape=(n, n), dtype=np.float64,
        )
        self._edge_count = len(rows)

        # KDTree for fast nearest-node queries
        coords = [(self.nodes[nid][0], self.nodes[nid][1]) for nid in self._node_ids]
        self._kdtree = KDTree(coords)

    # ------------------------------------------------------------------
    # Node lookup
    # ------------------------------------------------------------------

    def find_nearest_node(self, lat, lon):
        """O(log n) nearest-node lookup via KDTree."""
        _, idx = self._kdtree.query([lat, lon])
        return self._node_ids[idx]

    # ------------------------------------------------------------------
    # Routing  (scipy C-level Dijkstra — ~30× faster than pure-Python)
    # ------------------------------------------------------------------

    def _scaled_graph(self, traffic_mult):
        if traffic_mult == 1.0:
            return self._graph
        return self._graph * traffic_mult

    def dijkstra(self, source, traffic_mult=1.0, max_time=30.0):
        """Single-source shortest path.  Returns {node_id: time}."""
        idx = self._nid_to_idx[source]
        dist_row = sp_dijkstra(
            self._scaled_graph(traffic_mult), indices=[idx], limit=max_time,
        )[0]
        return {
            self._node_ids[i]: float(dist_row[i])
            for i in range(len(self._node_ids))
            if dist_row[i] <= max_time
        }

    def dijkstra_matrix(self, source_indices, traffic_mult=1.0, max_time=30.0):
        """Batch Dijkstra returning raw numpy array (len(sources), N).

        This avoids Python-dict overhead and is ideal for vectorised
        scoring in coverage analysis.
        """
        return sp_dijkstra(
            self._scaled_graph(traffic_mult),
            indices=source_indices,
            limit=max_time,
        )

    def compute_response_times(self, station_nodes, traffic_mult=1.0):
        """Multi-source Dijkstra from all stations.

        Returns (dist_dict, assigned_dict) with the same API as before.
        """
        sid_list = []
        idx_list = []
        for sid, snode in station_nodes.items():
            if snode is None:
                continue
            sid_list.append(sid)
            idx_list.append(self._nid_to_idx[snode])

        if not idx_list:
            return {}, {}

        graph = self._scaled_graph(traffic_mult)
        dist_matrix = sp_dijkstra(graph, indices=idx_list, limit=30.0)
        # dist_matrix shape: (num_stations, num_nodes)

        min_dist = np.min(dist_matrix, axis=0)
        min_idx = np.argmin(dist_matrix, axis=0)

        dist = {}
        assigned = {}
        for i in range(len(self._node_ids)):
            d = min_dist[i]
            if not np.isinf(d):
                nid = self._node_ids[i]
                dist[nid] = float(d)
                assigned[nid] = sid_list[int(min_idx[i])]

        return dist, assigned

    def find_route(self, source, target, traffic_mult=1.0):
        """Return (list_of_latlng, total_time) or (None, None)."""
        src_idx = self._nid_to_idx[source]
        tgt_idx = self._nid_to_idx[target]

        dist_row, pred_row = sp_dijkstra(
            self._scaled_graph(traffic_mult),
            indices=[src_idx],
            return_predecessors=True,
        )
        dist_row = dist_row[0]
        pred_row = pred_row[0]

        if np.isinf(dist_row[tgt_idx]):
            return None, None

        # Reconstruct path from predecessors
        path = []
        idx = tgt_idx
        while idx != src_idx and idx >= 0:
            path.append(self.nodes[self._node_ids[idx]])
            idx = pred_row[idx]
        path.append(self.nodes[self._node_ids[src_idx]])
        path.reverse()

        return path, float(dist_row[tgt_idx])

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def num_nodes(self):
        return len(self.nodes)

    @property
    def num_edges(self):
        return self._edge_count
