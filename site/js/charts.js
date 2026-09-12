/**
 * site/js/charts.js
 *
 * Loads data/processed/model_results.json (see pipeline/04_export_predictions.py)
 * and fills in the "What predicts constraint" section: a model comparison
 * table and a feature-importance bar chart. Built with plain DOM/CSS -
 * no charting library, since it's a handful of static values.
 *
 * Path note: same assumption as map.js - repo root as web root.
 */

(function () {
  "use strict";

  const RESULTS_URL = "../data/processed/model_results.json";

  function formatPct(value) {
    return (value * 100).toFixed(1) + "%";
  }

  function renderMetrics(data) {
    const container = document.querySelector("#model-metrics .model-card__body");

    const intro = document.createElement("p");
    intro.textContent =
      `Trained on ${data.n_train.toLocaleString()} substations, tested on ` +
      `${data.n_test.toLocaleString()} held-out examples. ${formatPct(data.base_rate_constrained)} ` +
      `of substations are constrained at some point in the network, so the ` +
      `baseline "always predict constrained" guess would already score ` +
      `${formatPct(data.base_rate_constrained)} accuracy - precision, recall and ROC AUC ` +
      `below are the metrics that actually matter here.`;

    const table = document.createElement("table");
    table.className = "metrics-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Model</th>
          <th>Precision</th>
          <th>Recall</th>
          <th>F1</th>
          <th>ROC AUC</th>
        </tr>
      </thead>
      <tbody>
        ${data.models
          .map(
            (m) => `
          <tr>
            <td>${escapeHtml(m.name)}</td>
            <td>${formatPct(m.precision)}</td>
            <td>${formatPct(m.recall)}</td>
            <td>${formatPct(m.f1)}</td>
            <td>${formatPct(m.roc_auc)}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    `;

    container.innerHTML = "";
    container.appendChild(intro);
    container.appendChild(table);
  }

  function renderFeatureImportance(data) {
    const container = document.querySelector("#feature-importance-chart .model-card__body");
    const features = data.feature_importance;
    const maxImportance = Math.max(...features.map((f) => f.importance));

    const intro = document.createElement("p");
    intro.textContent = `Top factors the model relies on to predict constraint:`;

    const chart = document.createElement("div");
    chart.className = "importance-chart";
    chart.innerHTML = features
      .map((f) => {
        const pct = (f.importance / maxImportance) * 100;
        return `
          <div class="importance-bar-row">
            <span class="importance-bar-label">${escapeHtml(f.label)}</span>
            <div class="importance-bar-track">
              <div class="importance-bar-fill" style="width:${pct}%"></div>
            </div>
            <span class="importance-bar-value">${f.importance.toFixed(3)}</span>
          </div>
        `;
      })
      .join("");

    container.innerHTML = "";
    container.appendChild(intro);
    container.appendChild(chart);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function showError() {
    document.querySelectorAll(".model-card__body").forEach((el) => {
      el.innerHTML = '<p class="model-card__pending">Could not load model results.</p>';
    });
  }

  function init() {
    fetch(RESULTS_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load ${RESULTS_URL}: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        renderMetrics(data);
        renderFeatureImportance(data);
      })
      .catch((err) => {
        console.error(err);
        showError();
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
