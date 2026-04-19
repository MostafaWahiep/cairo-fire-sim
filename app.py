#!/usr/bin/env python3
"""Cairo Fire Station Placement Simulator — desktop demo server."""

import copy
import os
import webbrowser
import threading
from datetime import datetime

from flask import Flask, render_template, jsonify, request

from engine.network import CairoRoadNetwork
from engine.coverage import CoverageAnalyzer
from engine.districts import DEFAULT_STATIONS

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
network = None
analyzer = None
stations = {}
next_id = 100
settings = {"traffic_multiplier": 1.0}
scenarios = {}
_coverage_cache = {}  # keyed by (frozenset of station nodes, traffic)


def init_engine():
    global network, analyzer, stations, next_id
    print("Building Cairo road network …")
    network = CairoRoadNetwork()
    analyzer = CoverageAnalyzer(network)

    for sid, sdata in DEFAULT_STATIONS.items():
        node = network.find_nearest_node(sdata["lat"], sdata["lon"])
        stations[sid] = {
            "name": sdata["name"],
            "lat": sdata["lat"],
            "lon": sdata["lon"],
            "node": node,
        }
    next_id = max(int(s[1:]) for s in stations) + 1
    print(
        f"  {network.num_nodes} intersections, "
        f"{network.num_edges} road segments, "
        f"{len(stations)} stations"
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Station CRUD
# ---------------------------------------------------------------------------
@app.route("/api/stations", methods=["GET"])
def get_stations():
    return jsonify(
        {sid: {"name": s["name"], "lat": s["lat"], "lon": s["lon"]} for sid, s in stations.items()}
    )


@app.route("/api/stations", methods=["POST"])
def add_station():
    global next_id
    data = request.get_json(force=True)
    lat = float(data["lat"])
    lon = float(data["lon"])
    name = str(data.get("name", f"New Station {next_id}"))[:80]

    sid = f"s{next_id}"
    next_id += 1
    node = network.find_nearest_node(lat, lon)
    stations[sid] = {"name": name, "lat": lat, "lon": lon, "node": node}
    return jsonify({"id": sid, "name": name, "lat": lat, "lon": lon})


@app.route("/api/stations/<sid>", methods=["PUT"])
def update_station(sid):
    if sid not in stations:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True)
    if "lat" in data and "lon" in data:
        stations[sid]["lat"] = float(data["lat"])
        stations[sid]["lon"] = float(data["lon"])
        stations[sid]["node"] = network.find_nearest_node(float(data["lat"]), float(data["lon"]))
    if "name" in data:
        stations[sid]["name"] = str(data["name"])[:80]
    return jsonify({"ok": True})


@app.route("/api/stations/<sid>", methods=["DELETE"])
def delete_station(sid):
    if sid in stations:
        del stations[sid]
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


# ---------------------------------------------------------------------------
# Coverage & routing
# ---------------------------------------------------------------------------
def _cache_key(snodes, traffic):
    return (frozenset(snodes.items()), round(traffic, 2))


@app.route("/api/coverage", methods=["POST"])
def compute_coverage():
    data = request.get_json(force=True) or {}
    traffic = float(data.get("traffic_multiplier", settings["traffic_multiplier"]))
    resolution = max(20, min(int(data.get("resolution", 70)), 120))

    snodes = {sid: s["node"] for sid, s in stations.items()}
    grid, metrics = analyzer.compute_full(snodes, traffic, resolution)

    # cache response times for fast route lookups
    key = _cache_key(snodes, traffic)
    rt, assigned = network.compute_response_times(snodes, traffic)
    _coverage_cache["latest"] = (rt, assigned, snodes, traffic)

    return jsonify({"grid": grid, "metrics": metrics})


@app.route("/api/route", methods=["POST"])
def find_route():
    data = request.get_json(force=True)
    lat = float(data["lat"])
    lon = float(data["lon"])
    traffic = float(data.get("traffic_multiplier", settings["traffic_multiplier"]))

    target = network.find_nearest_node(lat, lon)
    if target is None:
        return jsonify({"error": "no node"}), 400

    # Reuse cached coverage when available (avoids re-running 12 Dijkstras)
    cached = _coverage_cache.get("latest")
    snodes = {sid: s["node"] for sid, s in stations.items()}
    if cached and cached[2] == snodes and abs(cached[3] - traffic) < 0.01:
        _, assigned = cached[0], cached[1]
    else:
        _, assigned = network.compute_response_times(snodes, traffic)

    serving = assigned.get(target)
    if serving is None:
        return jsonify({"error": "unreachable"}), 400

    route, time = network.find_route(stations[serving]["node"], target, traffic)
    if route is None:
        return jsonify({"error": "no route"}), 400

    return jsonify({
        "route": [[p[0], p[1]] for p in route],
        "time": round(time, 2),
        "station_id": serving,
        "station_name": stations[serving]["name"],
    })


# ---------------------------------------------------------------------------
# Station criticality analysis (heavier computation)
# ---------------------------------------------------------------------------
@app.route("/api/criticality", methods=["POST"])
def compute_criticality():
    data = request.get_json(force=True) or {}
    traffic = float(data.get("traffic_multiplier", settings["traffic_multiplier"]))
    snodes = {sid: s["node"] for sid, s in stations.items()}
    result = analyzer.compute_criticality(snodes, traffic)
    # Attach station names for the frontend
    for sid, info in result["stations"].items():
        info["name"] = stations.get(sid, {}).get("name", sid)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Optimal station suggestion
# ---------------------------------------------------------------------------
@app.route("/api/suggest", methods=["POST"])
def suggest_station():
    data = request.get_json(force=True) or {}
    traffic = float(data.get("traffic_multiplier", settings["traffic_multiplier"]))
    snodes = {sid: s["node"] for sid, s in stations.items()}
    result = analyzer.suggest_station(snodes, traffic)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
@app.route("/api/scenarios", methods=["GET"])
def list_scenarios():
    return jsonify({
        n: {"station_count": len(s["stations"]), "saved_at": s["saved_at"]}
        for n, s in scenarios.items()
    })


@app.route("/api/scenarios/save", methods=["POST"])
def save_scenario():
    data = request.get_json(force=True)
    name = str(data.get("name", "Untitled"))[:60]
    scenarios[name] = {
        "stations": copy.deepcopy(
            {sid: {"name": s["name"], "lat": s["lat"], "lon": s["lon"]} for sid, s in stations.items()}
        ),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    return jsonify({"ok": True})


@app.route("/api/scenarios/load", methods=["POST"])
def load_scenario():
    global stations, next_id
    data = request.get_json(force=True)
    name = str(data.get("name", ""))
    if name not in scenarios:
        return jsonify({"error": "not found"}), 404

    stored = scenarios[name]["stations"]
    stations = {}
    for sid, sd in stored.items():
        node = network.find_nearest_node(sd["lat"], sd["lon"])
        stations[sid] = {**sd, "node": node}
    next_id = max((int(s[1:]) for s in stations), default=0) + 1

    return jsonify({
        "ok": True,
        "stations": {sid: {"name": s["name"], "lat": s["lat"], "lon": s["lon"]} for sid, s in stations.items()},
    })


@app.route("/api/info")
def api_info():
    return jsonify({
        "nodes": network.num_nodes,
        "edges": network.num_edges,
        "bounds": {
            "lat_min": network.LAT_MIN,
            "lat_max": network.LAT_MAX,
            "lon_min": network.LON_MIN,
            "lon_max": network.LON_MAX,
        },
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
# Always init the engine (gunicorn imports the module but doesn't run __main__)
init_engine()

if __name__ == "__main__":
    if not os.environ.get("RENDER"):
        def _open():
            import time
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:5000")

        threading.Thread(target=_open, daemon=True).start()
        print("\n  Cairo Fire Station Simulator")
        print("  http://127.0.0.1:5000\n")

    app.run(debug=False, port=5000)
