/* =================================================================
   Cairo Fire Station Simulator — Frontend
   ================================================================= */

const APP = {
  map: null,
  mode: "inspect",
  coverageOverlay: null,
  stationMarkers: {},
  routeLine: null,
  routeMarker: null,
  suggestMarker: null,
  charts: {},
  traffic: 1.0,
  showCoverage: true,
  showStations: true,
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function esc(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

function escAttr(str) {
  return String(str).replace(/[&"'<>]/g, c =>
    ({ "&": "&amp;", '"': "&quot;", "'": "&#39;", "<": "&lt;", ">": "&gt;" })[c]
  );
}

async function api(url, opts) {
  const res = await fetch(url, opts);
  return res.json();
}

function showLoading(on) {
  document.getElementById("loading").classList.toggle("hidden", !on);
}

/* ------------------------------------------------------------------ */
/*  Initialisation                                                    */
/* ------------------------------------------------------------------ */

async function init() {
  initMap();
  initTabs();
  initControls();
  await loadStations();
  await computeCoverage();
  showLoading(false);
}

function initMap() {
  APP.map = L.map("map", { center: [30.05, 31.27], zoom: 12 });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18,
  }).addTo(APP.map);
  APP.map.on("click", onMapClick);
}

function initTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
    });
  });
}

function initControls() {
  // Traffic slider
  const slider = document.getElementById("traffic-slider");
  const valSpan = document.getElementById("traffic-value");
  slider.addEventListener("input", () => {
    APP.traffic = parseFloat(slider.value);
    valSpan.textContent = slider.value + "×";
  });
  slider.addEventListener("change", () => computeCoverage());

  // Mode buttons
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      APP.mode = btn.dataset.mode;
      APP.map.getContainer().style.cursor = APP.mode === "add" ? "crosshair" : "";
    });
  });

  // Display toggles
  document.getElementById("show-coverage").addEventListener("change", e => {
    APP.showCoverage = e.target.checked;
    if (APP.coverageOverlay) APP.coverageOverlay.setOpacity(e.target.checked ? 0.55 : 0);
  });
  document.getElementById("show-stations").addEventListener("change", e => {
    APP.showStations = e.target.checked;
    Object.values(APP.stationMarkers).forEach(m => m.setOpacity(e.target.checked ? 1 : 0));
  });

  // Save scenario
  document.getElementById("btn-save-scenario").addEventListener("click", saveScenario);

  // Delete station — event delegation
  document.getElementById("station-list").addEventListener("click", e => {
    const btn = e.target.closest(".btn-delete");
    if (btn) deleteStation(btn.dataset.sid);
  });

  // Load scenario — event delegation
  document.getElementById("scenario-list").addEventListener("click", e => {
    const btn = e.target.closest(".btn-load-scenario");
    if (btn) loadScenarioByName(btn.dataset.name);
  });

  // Criticality analysis
  document.getElementById("btn-criticality").addEventListener("click", runCriticality);

  // Optimal station suggestion
  document.getElementById("btn-suggest").addEventListener("click", runSuggest);
  document.getElementById("btn-accept-suggest").addEventListener("click", acceptSuggestion);
  document.getElementById("btn-dismiss-suggest").addEventListener("click", dismissSuggestion);
}

/* ------------------------------------------------------------------ */
/*  Map clicks                                                        */
/* ------------------------------------------------------------------ */

async function onMapClick(e) {
  if (APP.mode === "add") {
    await addStation(e.latlng.lat, e.latlng.lng);
  } else {
    await showRoute(e.latlng.lat, e.latlng.lng);
  }
}

/* ------------------------------------------------------------------ */
/*  Station management                                                */
/* ------------------------------------------------------------------ */

async function loadStations() {
  const data = await api("/api/stations");
  Object.values(APP.stationMarkers).forEach(m => APP.map.removeLayer(m));
  APP.stationMarkers = {};
  for (const [sid, s] of Object.entries(data)) addStationMarker(sid, s);
  renderStationList(data);
}

function addStationMarker(sid, s) {
  const icon = L.divIcon({
    className: "station-icon",
    html: '<div class="station-marker"><span>🚒</span></div>',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
  const marker = L.marker([s.lat, s.lon], {
    icon,
    draggable: true,
    title: s.name,
  }).addTo(APP.map);

  marker.bindPopup(`<b>${esc(s.name)}</b><br>ID: ${esc(sid)}`);
  marker.on("dragend", async e => {
    const p = e.target.getLatLng();
    await api(`/api/stations/${encodeURIComponent(sid)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: p.lat, lon: p.lng }),
    });
    await computeCoverage();
  });
  APP.stationMarkers[sid] = marker;
}

function renderStationList(data) {
  document.getElementById("station-count").textContent = Object.keys(data).length;
  document.getElementById("station-list").innerHTML = Object.entries(data)
    .map(([sid, s]) =>
      `<div class="station-item">
         <span class="station-name">🚒 ${esc(s.name)}</span>
         <button class="btn-delete" data-sid="${escAttr(sid)}" title="Remove">✕</button>
       </div>`
    ).join("");
}

async function addStation(lat, lon) {
  const name = `Station ${Object.keys(APP.stationMarkers).length + 1}`;
  await api("/api/stations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, name }),
  });
  await loadStations();
  await computeCoverage();
}

async function deleteStation(sid) {
  await api(`/api/stations/${encodeURIComponent(sid)}`, { method: "DELETE" });
  if (APP.stationMarkers[sid]) {
    APP.map.removeLayer(APP.stationMarkers[sid]);
    delete APP.stationMarkers[sid];
  }
  await loadStations();
  await computeCoverage();
}

/* ------------------------------------------------------------------ */
/*  Coverage                                                          */
/* ------------------------------------------------------------------ */

async function computeCoverage() {
  showLoading(true);
  try {
    const { grid, metrics } = await api("/api/coverage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ traffic_multiplier: APP.traffic, resolution: 70 }),
    });
    renderCoverage(grid);
    updateMetrics(metrics);
  } catch (err) {
    console.error("Coverage error:", err);
  }
  showLoading(false);
}

function renderCoverage(grid) {
  if (APP.coverageOverlay) APP.map.removeLayer(APP.coverageOverlay);

  const canvas = document.createElement("canvas");
  canvas.width = grid.cols;
  canvas.height = grid.rows;
  const ctx = canvas.getContext("2d");

  for (let r = 0; r < grid.rows; r++) {
    for (let c = 0; c < grid.cols; c++) {
      ctx.fillStyle = timeColor(grid.data[r * grid.cols + c]);
      ctx.fillRect(c, grid.rows - 1 - r, 1, 1);
    }
  }

  const bounds = L.latLngBounds(
    [grid.bounds.lat_min, grid.bounds.lon_min],
    [grid.bounds.lat_max, grid.bounds.lon_max],
  );
  APP.coverageOverlay = L.imageOverlay(canvas.toDataURL(), bounds, {
    opacity: APP.showCoverage ? 0.55 : 0,
    interactive: false,
  }).addTo(APP.map);
  APP.coverageOverlay.bringToBack();
}

function timeColor(t) {
  if (t <= 4)  return "#2ecc71";
  if (t <= 6)  return "#a8e063";
  if (t <= 8)  return "#f1c40f";
  if (t <= 10) return "#f39c12";
  if (t <= 12) return "#e67e22";
  if (t <= 15) return "#e74c3c";
  return "#c0392b";
}

/* ------------------------------------------------------------------ */
/*  Metrics & Charts                                                  */
/* ------------------------------------------------------------------ */

function updateMetrics(m) {
  document.getElementById("m-avg-time").textContent  = m.avg_response_time.toFixed(1);
  document.getElementById("m-median-time").textContent = m.median_response_time.toFixed(1);
  document.getElementById("m-pop-avg").textContent   = m.pop_weighted_avg.toFixed(1);
  document.getElementById("m-max-time").textContent  = m.max_response_time.toFixed(1) + " min";
  document.getElementById("m-pct8").textContent      = m.pct_under_8min.toFixed(0) + "%";
  document.getElementById("m-p90").textContent       = m.p90_response_time.toFixed(1);
  document.getElementById("m-p95").textContent       = m.p95_response_time.toFixed(1) + " min";
  document.getElementById("m-equity").textContent    = (m.equity_score * 100).toFixed(0) + "%";

  document.getElementById("b-under4").textContent = m.distribution[0].toFixed(1) + "%";
  document.getElementById("b-4to8").textContent   = m.distribution[1].toFixed(1) + "%";
  document.getElementById("b-8to12").textContent  = m.distribution[2].toFixed(1) + "%";
  document.getElementById("b-over12").textContent = m.distribution[3].toFixed(1) + "%";

  document.getElementById("network-info").textContent =
    `${m.total_nodes} nodes · ${Object.keys(APP.stationMarkers).length} stations`;

  updateDistributionChart(m.distribution);
  updateDistrictView(m.district_metrics);
}

function updateDistributionChart(dist) {
  const ctx = document.getElementById("chart-distribution");
  if (APP.charts.dist) {
    APP.charts.dist.data.datasets[0].data = dist;
    APP.charts.dist.update();
    return;
  }
  APP.charts.dist = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["< 4 min", "4–8 min", "8–12 min", "> 12 min"],
      datasets: [{
        data: dist,
        backgroundColor: ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom", labels: { color: "#8899aa", font: { size: 11 } } } },
      cutout: "60%",
    },
  });
}

function updateDistrictView(districts) {
  const valid = districts.filter(d => d.avg_time !== null);
  const labels = valid.map(d => d.name);
  const values = valid.map(d => d.avg_time);
  const colors = values.map(timeColor);

  if (APP.charts.districts) {
    APP.charts.districts.data.labels = labels;
    APP.charts.districts.data.datasets[0].data = values;
    APP.charts.districts.data.datasets[0].backgroundColor = colors;
    APP.charts.districts.update();
  } else {
    APP.charts.districts = new Chart(document.getElementById("chart-districts"), {
      type: "bar",
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, borderRadius: 3 }],
      },
      options: {
        responsive: true,
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: "Avg Response (min)", color: "#8899aa" }, ticks: { color: "#8899aa" }, grid: { color: "#2d4a5e" } },
          y: { ticks: { color: "#8899aa", font: { size: 10 } }, grid: { display: false } },
        },
      },
    });
  }

  document.getElementById("district-list").innerHTML = valid.map(d => {
    const cls = d.avg_time <= 5 ? "time-good" : d.avg_time <= 8 ? "time-ok" : d.avg_time <= 12 ? "time-bad" : "time-critical";
    const pop = d.population_density >= 1000 ? (d.population_density / 1000).toFixed(0) + "k" : d.population_density;
    const u8 = d.pct_under_8min != null ? ` · ${d.pct_under_8min.toFixed(0)}% &lt;8m` : "";
    return `<div class="district-item"><span class="district-name">${esc(d.name)} <span class="muted" style="font-size:11px">(${pop}/km²${u8})</span></span><span class="district-time ${cls}">${d.avg_time.toFixed(1)} min</span></div>`;
  }).join("");
}

/* ------------------------------------------------------------------ */
/*  Routing                                                           */
/* ------------------------------------------------------------------ */

async function showRoute(lat, lon) {
  if (APP.routeLine)   APP.map.removeLayer(APP.routeLine);
  if (APP.routeMarker) APP.map.removeLayer(APP.routeMarker);

  try {
    const data = await api("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon, traffic_multiplier: APP.traffic }),
    });
    if (data.error) return;

    APP.routeLine = L.polyline(data.route, {
      color: "#3498db", weight: 4, opacity: 0.85, dashArray: "8,8",
    }).addTo(APP.map);

    APP.routeMarker = L.circleMarker([lat, lon], {
      radius: 8, fillColor: "#3498db", fillOpacity: 0.9, color: "#fff", weight: 2,
    }).addTo(APP.map);

    const overlay = document.getElementById("map-overlay");
    document.getElementById("route-info").innerHTML =
      `<strong>${esc(data.station_name)}</strong> → Target<br>Response time: <strong>${data.time.toFixed(1)} min</strong>`;
    overlay.classList.remove("hidden");
    clearTimeout(APP._overlayTimer);
    APP._overlayTimer = setTimeout(() => overlay.classList.add("hidden"), 6000);
  } catch (err) {
    console.error("Route error:", err);
  }
}

/* ------------------------------------------------------------------ */
/*  Optimal Station Suggestion                                        */
/* ------------------------------------------------------------------ */

async function runSuggest() {
  const btn = document.getElementById("btn-suggest");
  const loading = document.getElementById("suggest-loading");
  const result = document.getElementById("suggest-result");

  btn.classList.add("hidden");
  loading.classList.remove("hidden");
  result.classList.add("hidden");
  dismissSuggestion();

  try {
    const data = await api("/api/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ traffic_multiplier: APP.traffic }),
    });
    APP._lastSuggestion = data;
    showSuggestionOnMap(data);
    renderSuggestionResult(data);
    result.classList.remove("hidden");
  } catch (err) {
    console.error("Suggestion error:", err);
  }
  loading.classList.add("hidden");
  btn.classList.remove("hidden");
}

function showSuggestionOnMap(data) {
  if (APP.suggestMarker) APP.map.removeLayer(APP.suggestMarker);

  const icon = L.divIcon({
    className: "suggest-icon",
    html: '<div class="suggest-marker"><span>⭐</span></div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
  APP.suggestMarker = L.marker([data.lat, data.lon], { icon, zIndexOffset: 1000 })
    .addTo(APP.map)
    .bindPopup(
      `<b>Suggested Station</b><br>` +
      `Avg: ${data.baseline_avg} → ${data.suggested_avg} min<br>` +
      `&lt;8 min: ${data.baseline_pct8}% → ${data.suggested_pct8}%`
    )
    .openPopup();
  APP.map.panTo([data.lat, data.lon]);
}

function renderSuggestionResult(data) {
  document.getElementById("suggest-summary").innerHTML =
    `<div class="suggest-stat"><span class="suggest-delta">${data.delta_avg.toFixed(2)} min</span> avg improvement</div>` +
    `<div class="suggest-stat"><span class="suggest-delta-good">+${data.delta_pct8.toFixed(1)}%</span> nodes under 8 min</div>` +
    `<div class="suggest-stat muted">${data.candidates_evaluated} candidates evaluated</div>`;
}

async function acceptSuggestion() {
  const data = APP._lastSuggestion;
  if (!data) return;
  dismissSuggestion();
  await addStation(data.lat, data.lon);
}

function dismissSuggestion() {
  if (APP.suggestMarker) {
    APP.map.removeLayer(APP.suggestMarker);
    APP.suggestMarker = null;
  }
  document.getElementById("suggest-result").classList.add("hidden");
}

/* ------------------------------------------------------------------ */
/*  Station Criticality Analysis                                      */
/* ------------------------------------------------------------------ */

async function runCriticality() {
  const btn = document.getElementById("btn-criticality");
  const loading = document.getElementById("criticality-loading");
  const results = document.getElementById("criticality-results");

  btn.classList.add("hidden");
  loading.classList.remove("hidden");
  results.classList.add("hidden");

  try {
    const data = await api("/api/criticality", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ traffic_multiplier: APP.traffic }),
    });
    renderCriticality(data);
    results.classList.remove("hidden");
  } catch (err) {
    console.error("Criticality error:", err);
  }
  loading.classList.add("hidden");
  btn.classList.remove("hidden");
}

function renderCriticality(data) {
  // Coverage depth bars
  const depth = data.coverage_depth;
  const depthEl = document.getElementById("depth-bars");
  const depthLabels = { "0": "No coverage", "1": "Single station", "2": "Two stations", "3": "Three+" };
  const depthColors = { "0": "#e74c3c", "1": "#f39c12", "2": "#f1c40f", "3": "#2ecc71" };
  depthEl.innerHTML = ["0", "1", "2", "3"].map(k => {
    const pct = depth[k] || 0;
    return `<div class="depth-row">
      <span class="depth-label">${depthLabels[k]}</span>
      <div class="depth-bar-bg"><div class="depth-bar-fill" style="width:${pct}%;background:${depthColors[k]}"></div></div>
      <span class="depth-val">${pct}%</span>
    </div>`;
  }).join("");

  // Station criticality chart
  const entries = Object.entries(data.stations).sort((a, b) => b[1].delta_avg - a[1].delta_avg);
  const labels = entries.map(([, s]) => s.name);
  const deltas = entries.map(([, s]) => s.delta_avg);
  const colors = deltas.map(d => d > 1.0 ? "#e74c3c" : d > 0.3 ? "#f39c12" : "#2ecc71");

  if (APP.charts.criticality) {
    APP.charts.criticality.data.labels = labels;
    APP.charts.criticality.data.datasets[0].data = deltas;
    APP.charts.criticality.data.datasets[0].backgroundColor = colors;
    APP.charts.criticality.update();
  } else {
    APP.charts.criticality = new Chart(document.getElementById("chart-criticality"), {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Avg time increase if removed (min)", data: deltas, backgroundColor: colors, borderWidth: 0, borderRadius: 3 }],
      },
      options: {
        responsive: true,
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: "\u0394 Avg Response (min)", color: "#8899aa" }, ticks: { color: "#8899aa" }, grid: { color: "#2d4a5e" } },
          y: { ticks: { color: "#8899aa", font: { size: 10 } }, grid: { display: false } },
        },
      },
    });
  }

  // Criticality list
  document.getElementById("criticality-list").innerHTML = entries.map(([sid, s]) => {
    const cls = s.delta_avg > 1.0 ? "time-critical" : s.delta_avg > 0.3 ? "time-bad" : "time-good";
    return `<div class="district-item">
      <span class="district-name">${esc(s.name)} <span class="muted" style="font-size:11px">(${s.delta_pct8 != null ? s.delta_pct8.toFixed(1) : '?'}% chg in &lt;8m)</span></span>
      <span class="district-time ${cls}">+${s.delta_avg.toFixed(2)} min</span>
    </div>`;
  }).join("");
}

/* ------------------------------------------------------------------ */
/*  Scenarios                                                         */
/* ------------------------------------------------------------------ */

async function saveScenario() {
  const input = document.getElementById("scenario-name");
  const name = input.value.trim() || "Untitled";
  await api("/api/scenarios/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  input.value = "";
  await loadScenarios();
}

async function loadScenarios() {
  const data = await api("/api/scenarios");
  const el = document.getElementById("scenario-list");
  const keys = Object.keys(data);
  if (!keys.length) { el.innerHTML = '<p class="muted">No saved scenarios yet.</p>'; return; }
  el.innerHTML = keys.map(n =>
    `<div class="scenario-item">
       <span>${esc(n)} (${data[n].station_count} stations)</span>
       <button class="btn-load-scenario" data-name="${escAttr(n)}">Load</button>
     </div>`
  ).join("");
}

async function loadScenarioByName(name) {
  showLoading(true);
  await api("/api/scenarios/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await loadStations();
  await computeCoverage();
}

/* ------------------------------------------------------------------ */
/*  Boot                                                              */
/* ------------------------------------------------------------------ */

document.addEventListener("DOMContentLoaded", () => {
  init();
  loadScenarios();
});
