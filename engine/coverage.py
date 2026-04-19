"""Coverage analysis and metrics computation."""

import math
import numpy as np
from engine.districts import CAIRO_DISTRICTS

_BASELINE_DENSITY = 15000  # suburban fallback (people / km²)


class CoverageAnalyzer:
    def __init__(self, network):
        self.network = network
        self._node_pop = self._precompute_node_weights()

    # ------------------------------------------------------------------
    # Pre-computation
    # ------------------------------------------------------------------

    def _precompute_node_weights(self):
        """Map every node → population density based on district membership."""
        node_pop = {}
        districts = list(CAIRO_DISTRICTS.values())
        # Pre-convert radii to degrees once
        dinfo = [
            (d["center"][0], d["center"][1], d["radius_km"] / 111.32, d["population_density"])
            for d in districts
        ]
        for nid, (nlat, nlon) in self.network.nodes.items():
            best = _BASELINE_DENSITY
            for clat, clon, rad, density in dinfo:
                if math.hypot(nlat - clat, nlon - clon) <= rad:
                    best = max(best, density)
            node_pop[nid] = best
        return node_pop

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def compute_full(self, station_nodes, traffic_mult=1.0, resolution=70):
        """Return (grid_dict, metrics_dict) for the current station layout."""
        response_times, assigned = self.network.compute_response_times(
            station_nodes, traffic_mult
        )
        grid = self._build_grid(response_times, resolution)
        metrics = self._compute_metrics(response_times, assigned, station_nodes)
        return grid, metrics

    # ------------------------------------------------------------------
    # Coverage grid (for visualisation)
    # ------------------------------------------------------------------

    def _build_grid(self, response_times, resolution):
        net = self.network
        lat_step = (net.LAT_MAX - net.LAT_MIN) / resolution
        lon_step = (net.LON_MAX - net.LON_MIN) / resolution

        data = []
        for r in range(resolution):
            for c in range(resolution):
                lat = net.LAT_MIN + (r + 0.5) * lat_step
                lon = net.LON_MIN + (c + 0.5) * lon_step
                node = net.find_nearest_node(lat, lon)
                t = response_times.get(node, 30.0) if node is not None else 30.0
                data.append(round(min(t, 30.0), 2))

        return {
            "data": data,
            "rows": resolution,
            "cols": resolution,
            "bounds": {
                "lat_min": net.LAT_MIN,
                "lat_max": net.LAT_MAX,
                "lon_min": net.LON_MIN,
                "lon_max": net.LON_MAX,
            },
        }

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------

    def _compute_metrics(self, response_times, assigned, station_nodes):
        items = [(nid, t) for nid, t in response_times.items() if t < float("inf")]
        if not items:
            return self._empty()

        times = [t for _, t in items]
        n = len(times)

        # --- basic ---
        avg = sum(times) / n
        mx = max(times)
        u4 = sum(1 for t in times if t <= 4) / n * 100
        u8 = sum(1 for t in times if t <= 8) / n * 100
        u12 = sum(1 for t in times if t <= 12) / n * 100

        distribution = [
            round(u4, 1),
            round(u8 - u4, 1),
            round(u12 - u8, 1),
            round(100 - u12, 1),
        ]

        # --- percentiles ---
        stimes = sorted(times)
        median = stimes[n // 2]
        p90 = stimes[int(n * 0.90)]
        p95 = stimes[int(n * 0.95)]

        # --- population-weighted average ---
        total_w = 0.0
        weighted_sum = 0.0
        for nid, t in items:
            w = self._node_pop.get(nid, _BASELINE_DENSITY)
            total_w += w
            weighted_sum += t * w
        pop_avg = weighted_sum / total_w if total_w > 0 else avg

        # --- station load ---
        station_load = {}
        for sid in station_nodes:
            station_load[sid] = sum(1 for s in assigned.values() if s == sid)

        # --- district metrics ---
        district_metrics = self._district_metrics(response_times)

        # --- equity score ---
        dt = [d["avg_time"] for d in district_metrics if d["avg_time"] is not None]
        if len(dt) > 1:
            mean_dt = sum(dt) / len(dt)
            var = sum((t - mean_dt) ** 2 for t in dt) / len(dt)
            equity = max(0.0, 1.0 - math.sqrt(var) / mean_dt) if mean_dt > 0 else 0.0
        else:
            equity = 1.0

        return {
            "avg_response_time": round(avg, 2),
            "max_response_time": round(mx, 2),
            "median_response_time": round(median, 2),
            "p90_response_time": round(p90, 2),
            "p95_response_time": round(p95, 2),
            "pop_weighted_avg": round(pop_avg, 2),
            "pct_under_4min": round(u4, 1),
            "pct_under_8min": round(u8, 1),
            "pct_under_12min": round(u12, 1),
            "distribution": distribution,
            "station_load": station_load,
            "district_metrics": district_metrics,
            "equity_score": round(equity, 2),
            "total_nodes": n,
        }

    def _district_metrics(self, response_times):
        net = self.network
        results = []
        for did, district in CAIRO_DISTRICTS.items():
            clat, clon = district["center"]
            radius_deg = district["radius_km"] / 111.32
            times_in = []
            pop_w_times = []
            density = district["population_density"]
            for nid, (nlat, nlon) in net.nodes.items():
                if math.hypot(nlat - clat, nlon - clon) <= radius_deg:
                    t = response_times.get(nid)
                    if t is not None and t < float("inf"):
                        times_in.append(t)
                        pop_w_times.append(t * density)
            avg = round(sum(times_in) / len(times_in), 2) if times_in else None
            pop_avg = round(sum(pop_w_times) / (len(pop_w_times) * density), 2) if pop_w_times else None
            pct8 = round(sum(1 for t in times_in if t <= 8) / len(times_in) * 100, 1) if times_in else None
            results.append({
                "id": did,
                "name": district["name"],
                "avg_time": avg,
                "pop_weighted_avg": pop_avg,
                "pct_under_8min": pct8,
                "population_density": district["population_density"],
                "nodes_covered": len(times_in),
            })
        results.sort(key=lambda x: x["avg_time"] if x["avg_time"] is not None else 999)
        return results

    # ------------------------------------------------------------------
    # Station criticality (remove-one analysis)
    # ------------------------------------------------------------------

    def compute_criticality(self, station_nodes, traffic_mult=1.0):
        """For each station, measure degradation if it were removed.

        Also computes per-node coverage depth (how many stations can
        reach each node in ≤ 8 min) via individual single-source Dijkstras.
        """
        net = self.network

        # Baseline: all stations active
        base_dist, _ = net.compute_response_times(station_nodes, traffic_mult)
        base_times = [t for t in base_dist.values() if t < float("inf")]
        base_avg = sum(base_times) / len(base_times) if base_times else 0.0
        base_u8 = (
            sum(1 for t in base_times if t <= 8) / len(base_times) * 100
            if base_times else 0.0
        )

        # --- Coverage depth (individual Dijkstras, cutoff at 8 min) ---
        station_reach = {}  # sid -> set of reachable node ids
        for sid, snode in station_nodes.items():
            if snode is None:
                continue
            dists = net.dijkstra(snode, traffic_mult, max_time=8.0)
            station_reach[sid] = set(dists.keys())

        all_reached = set(base_dist.keys())
        depth_counts = {0: 0, 1: 0, 2: 0, 3: 0}  # 3 means "3+"
        for nid in all_reached:
            cnt = sum(1 for sid in station_reach if nid in station_reach[sid])
            depth_counts[min(cnt, 3)] += 1
        total = sum(depth_counts.values()) or 1
        depth_pct = {str(k): round(v / total * 100, 1) for k, v in depth_counts.items()}

        # --- Remove-one analysis ---
        station_results = {}
        for sid in station_nodes:
            reduced = {k: v for k, v in station_nodes.items() if k != sid}
            if not reduced:
                station_results[sid] = {
                    "delta_avg": 30.0,
                    "pct_under_8_without": 0.0,
                    "nodes_degraded": len(base_times),
                }
                continue
            alt_dist, _ = net.compute_response_times(reduced, traffic_mult)
            alt_times = [t for t in alt_dist.values() if t < float("inf")]
            alt_avg = sum(alt_times) / len(alt_times) if alt_times else 30.0
            alt_u8 = (
                sum(1 for t in alt_times if t <= 8) / len(alt_times) * 100
                if alt_times else 0.0
            )
            degraded = sum(
                1 for nid in base_dist
                if alt_dist.get(nid, 30.0) > base_dist[nid] + 0.5
            )
            station_results[sid] = {
                "delta_avg": round(alt_avg - base_avg, 2),
                "delta_pct8": round(alt_u8 - base_u8, 1),
                "pct_under_8_without": round(alt_u8, 1),
                "nodes_degraded": degraded,
            }

        return {
            "baseline_avg": round(base_avg, 2),
            "baseline_pct8": round(base_u8, 1),
            "stations": station_results,
            "coverage_depth": depth_pct,
        }

    @staticmethod
    def _empty():
        return {
            "avg_response_time": 0,
            "max_response_time": 0,
            "median_response_time": 0,
            "p90_response_time": 0,
            "p95_response_time": 0,
            "pop_weighted_avg": 0,
            "pct_under_4min": 0,
            "pct_under_8min": 0,
            "pct_under_12min": 0,
            "distribution": [0, 0, 0, 0],
            "station_load": {},
            "district_metrics": [],
            "equity_score": 0,
            "total_nodes": 0,
        }

    # ------------------------------------------------------------------
    # Optimal station suggestion (batched scipy + numpy scoring)
    # ------------------------------------------------------------------

    def suggest_station(self, station_nodes, traffic_mult=1.0, top_k=500):
        """Find the single best new station location.

        Uses batched scipy Dijkstra + numpy vectorised scoring:
          1. Baseline via multi-source Dijkstra (C-level).
          2. Top-k worst-served nodes as candidates.
          3. Batch Dijkstra from all candidates via dijkstra_matrix().
          4. Vectorised scoring: only count gains at nodes currently > 8 min.
        """
        net = self.network
        existing_set = set(station_nodes.values())
        n_total = len(net._node_ids)

        # --- baseline as numpy array ---
        base_dist, _ = net.compute_response_times(station_nodes, traffic_mult)
        baseline = np.full(n_total, 30.0)
        for nid, t in base_dist.items():
            baseline[net._nid_to_idx[nid]] = t

        reachable = baseline < 30.0
        n_reach = int(reachable.sum())
        if n_reach == 0:
            return self._empty_suggestion()

        base_avg = float(baseline[reachable].mean())
        base_u8 = float((baseline[reachable] <= 8).sum()) / n_reach * 100

        # --- pick candidates: worst-served nodes not already stations ---
        existing_idx = {net._nid_to_idx[nid] for nid in existing_set if nid in net._nid_to_idx}
        sorted_indices = np.argsort(-baseline)
        candidates = []
        for idx in sorted_indices:
            if int(idx) in existing_idx:
                continue
            candidates.append(int(idx))
            if len(candidates) >= top_k:
                break

        if not candidates:
            return self._empty_suggestion()

        # --- batched Dijkstra + vectorised scoring ---
        THRESHOLD = 8.0
        underserved = baseline > THRESHOLD      # (N,) boolean mask
        BATCH = 50
        best_idx = candidates[0]
        best_score = 0.0

        for start in range(0, len(candidates), BATCH):
            batch = candidates[start:start + BATCH]
            dist_matrix = net.dijkstra_matrix(batch, traffic_mult, max_time=30.0)
            # dist_matrix shape: (len(batch), N)

            # improvement = max(baseline - candidate, 0)  only where under-served
            improvement = np.maximum(baseline[np.newaxis, :] - dist_matrix, 0.0)
            improvement[:, ~underserved] = 0.0
            scores = improvement.sum(axis=1)            # (len(batch),)

            batch_best = int(np.argmax(scores))
            if scores[batch_best] > best_score:
                best_score = float(scores[batch_best])
                best_idx = batch[batch_best]

        best_node = net._node_ids[best_idx]

        # --- final verification with full multi-source ---
        trial = {**station_nodes, "__suggest__": best_node}
        trial_dist, _ = net.compute_response_times(trial, traffic_mult)
        trial_arr = np.full(n_total, 30.0)
        for nid, t in trial_dist.items():
            trial_arr[net._nid_to_idx[nid]] = t

        trial_reach = trial_arr < 30.0
        n_trial = int(trial_reach.sum())
        trial_avg = float(trial_arr[trial_reach].mean()) if n_trial else 30.0
        trial_u8 = float((trial_arr[trial_reach] <= 8).sum()) / n_trial * 100 if n_trial else 0.0

        lat, lon = net.nodes[best_node]
        return {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "candidates_evaluated": len(candidates),
            "baseline_avg": round(base_avg, 2),
            "suggested_avg": round(trial_avg, 2),
            "delta_avg": round(trial_avg - base_avg, 2),
            "baseline_pct8": round(base_u8, 1),
            "suggested_pct8": round(trial_u8, 1),
            "delta_pct8": round(trial_u8 - base_u8, 1),
        }

    @staticmethod
    def _empty_suggestion():
        return {
            "lat": 0, "lon": 0, "candidates_evaluated": 0,
            "baseline_avg": 0, "suggested_avg": 0, "delta_avg": 0,
            "baseline_pct8": 0, "suggested_pct8": 0, "delta_pct8": 0,
        }
