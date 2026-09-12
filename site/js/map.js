/**
 * site/js/map.js
 *
 * Loads the pre-built substations GeoJSON (see pipeline/02_build_geojson.py)
 * and renders it as a clustered Leaflet map. Also fills in the hero
 * stat boxes from the same data, since it's already being fetched.
 *
 * Path note: this assumes the site is served with the repo root as the
 * web root (site/ and data/ as siblings) - e.g. `python3 -m http.server`
 * run from the repo root, or a static host configured that way. See
 * README.md for the deployment approach.
 */

(function () {
  "use strict";

  const GEOJSON_URL = "../data/processed/substations.geojson";
  const IRELAND_CENTER = [53.4, -8.0];
  const IRELAND_ZOOM = 7;

  const COLORS = {
    available: "#3F7A5C",
    constrained: "#B23A2E",
  };

  const LAYER_FIELDS = {
    demand: {
      constrainedFlag: "demand_is_constrained",
      valueField: "demand_available_mva",
      unit: "MVA",
      label: "demand headroom",
    },
    generation: {
      constrainedFlag: "generation_is_constrained",
      valueField: "gen_available_firm_mw",
      unit: "MW",
      label: "generation headroom",
    },
  };

  let activeLayer = "demand";
  let onlyUnconstrained = false;
  let geoData = null;
  let map = null;
  let clusterGroup = null;

  // -----------------------------------------------------------------
  // Map setup
  // -----------------------------------------------------------------
  function initMap() {
    map = L.map("leaflet-map", {
      scrollWheelZoom: true,
    }).setView(IRELAND_CENTER, IRELAND_ZOOM);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 40,
      spiderfyOnMaxZoom: true,
    });
    map.addLayer(clusterGroup);
  }

  // -----------------------------------------------------------------
  // Marker styling
  // -----------------------------------------------------------------
  function radiusForValue(value) {
    if (value === null || value === undefined || isNaN(value)) return 3;
    // sqrt scale so radius grows sub-linearly with headroom magnitude -
    // keeps small LV substations visible while big stations don't swamp the map
    const r = 3 + Math.sqrt(value) * 3;
    return Math.max(3, Math.min(r, 16));
  }

  function pointToLayer(feature, latlng) {
    const fields = LAYER_FIELDS[activeLayer];
    const props = feature.properties;
    const isConstrained = !!props[fields.constrainedFlag];
    const value = props[fields.valueField];

    return L.circleMarker(latlng, {
      radius: radiusForValue(value),
      color: isConstrained ? COLORS.constrained : COLORS.available,
      fillColor: isConstrained ? COLORS.constrained : COLORS.available,
      fillOpacity: 0.55,
      weight: 1,
    });
  }

  function popupHtml(props) {
    const fields = LAYER_FIELDS[activeLayer];
    const value = props[fields.valueField];
    const valueText =
      value === null || value === undefined
        ? "n/a"
        : `${value.toFixed(2)} ${fields.unit}`;
    const statusText = props[fields.constrainedFlag]
      ? "Constrained"
      : "Headroom available";

    return `
      <strong>${escapeHtml(props.station_name)}</strong><br>
      ${props.voltage_class || ""}<br>
      ${fields.label}: ${valueText}<br>
      Status: ${statusText}<br>
      Parent: ${escapeHtml(props.parent_station || "n/a")}
    `;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // -----------------------------------------------------------------
  // Layer / filter rendering
  // -----------------------------------------------------------------
  function featureFilter(feature) {
    if (!onlyUnconstrained) return true;
    const fields = LAYER_FIELDS[activeLayer];
    return !feature.properties[fields.constrainedFlag];
  }

  function renderMarkers() {
    if (!geoData) return;

    clusterGroup.clearLayers();

    const layer = L.geoJSON(geoData, {
      filter: featureFilter,
      pointToLayer: pointToLayer,
      onEachFeature: (feature, layer) => {
        layer.bindPopup(popupHtml(feature.properties));
        layer.on("mouseover", () => {
          document.getElementById("map-hover-detail").textContent =
            feature.properties.station_name;
        });
      },
    });

    clusterGroup.addLayer(layer);
  }

  function updateLegendScale() {
    const fields = LAYER_FIELDS[activeLayer];
    const el = document.getElementById("map-legend-scale");
    el.innerHTML = `
      <div><span class="sld__swatch sld__swatch--available" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${COLORS.available};margin-right:0.4rem;"></span>Headroom available</div>
      <div style="margin-top:0.3rem;"><span class="sld__swatch sld__swatch--constrained" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${COLORS.constrained};margin-right:0.4rem;"></span>Constrained</div>
      <div style="margin-top:0.5rem;font-size:0.75rem;">Marker size ~ ${fields.label} (${fields.unit})</div>
    `;
  }

  // -----------------------------------------------------------------
  // Controls wiring
  // -----------------------------------------------------------------
  function wireControls() {
    document.querySelectorAll(".layer-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".layer-toggle").forEach((b) =>
          b.setAttribute("aria-pressed", "false")
        );
        btn.setAttribute("aria-pressed", "true");
        activeLayer = btn.dataset.layer;
        updateLegendScale();
        renderMarkers();
      });
    });

    document
      .getElementById("filter-unconstrained")
      .addEventListener("change", (e) => {
        onlyUnconstrained = e.target.checked;
        renderMarkers();
      });
  }

  // -----------------------------------------------------------------
  // Hero stats (derived from the same fetched data, no extra request)
  // -----------------------------------------------------------------
  function updateHeroStats(data) {
    const total = data.features.length;
    const constrainedCount = data.features.filter(
      (f) => f.properties.is_constrained
    ).length;
    const constrainedPct = total ? (constrainedCount / total) * 100 : 0;

    const availableGenMw = data.features
      .filter((f) => !f.properties.generation_is_constrained)
      .reduce((sum, f) => sum + (f.properties.gen_available_firm_mw || 0), 0);

    document.getElementById("stat-total").textContent =
      total.toLocaleString();
    document.getElementById("stat-constrained-pct").textContent =
      constrainedPct.toFixed(0) + "%";
    document.getElementById("stat-available-mw").textContent =
      Math.round(availableGenMw).toLocaleString() + " MW";
  }

  // -----------------------------------------------------------------
  // Boot
  // -----------------------------------------------------------------
  function init() {
    initMap();
    wireControls();
    updateLegendScale();

    fetch(GEOJSON_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load ${GEOJSON_URL}: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        geoData = data;
        updateHeroStats(data);
        renderMarkers();
      })
      .catch((err) => {
        console.error(err);
        document.getElementById("map-hover-detail").textContent =
          "Could not load substation data.";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
