# ESB Grid Capacity

Where can new solar, EV chargers, or housing actually connect to Ireland's
electricity grid today — and what predicts where the network runs out of
room?

**[Live demo](https://romapanaskar.github.io/esb-grid-capacity/site/index.html)** · built on ESB Networks' public capacity heatmap (July 2026)

---

## The problem

Ireland's electricity distribution network publishes a capacity heatmap i.e
a snapshot of how much headroom exists at every transformer and substation
in the country, for both new demand (EV chargers, heat pumps, housing) and
new generation (solar, wind). It's the dataset that actually determines
whether a proposed connection can go ahead without a grid upgrade.

This project turns that raw export into three things:

1. **An interactive map** of where the grid has spare capacity right now,
   where it's constrained, and which currently-unconstrained substations
   look likely to become constrained next.
2. **A classifier** that predicts whether a substation sits behind a
   constrained connection, based only on its own specification — useful
   for spotting likely bottlenecks before requesting a formal capacity
   check.
3. **A sustainability estimate** translating blocked renewable generation
   capacity into an illustrative CO₂ impact figure.

## Features

- **Capacity map** — every substation plotted on an interactive Leaflet map
  of Ireland, colour-coded by headroom, with three toggleable layers:
  - *Demand headroom* — where new load (EV chargers, heat pumps, housing)
    can connect today
  - *Generation headroom* — where new solar/wind can connect today
  - *At risk (predicted)* — currently-unconstrained substations the model
    flags as structurally similar to already-constrained ones
  - An "only show unconstrained" filter and a click-through popup with
    each substation's real figures
- **Constraint classifier** — predicts whether a substation is constrained
  using only its own specification, not the headroom figures the label is
  derived from. Also scores every substation's *probability* of being
  constrained, which is what powers the "at risk" map layer.
- **Sustainability impact section** — sums the generation headroom
  currently blocked by parent-network constraints, and converts it into
  an illustrative annual CO₂-avoided estimate, with every assumption
  stated on the page itself.
- **Label leakage check** — before picking model features, several
  candidate columns were found to be mechanically derived from the same
  logic as the target label and excluded.

## Key findings

- **46,525** substations mapped across Ireland
- **72.2%** are constrained at some point in their connection to the wider
  network
- A gradient-boosted classifier predicts this with **0.90 F1 / 0.93 ROC AUC**
- The single strongest predictor is **how many other substations share the
  same parent station**
- **3,245 substations (25% of currently-unconstrained ones)** are flagged
  as "at risk" of becoming constrained next
- An estimated **3,683 MW of renewable generation capacity** is currently
  blocked — illustratively, roughly **994,000 tonnes of CO₂/year** of
  avoided-emissions potential if that capacity could connect

## How it's built

... (architecture, repo structure, run instructions, data source, and
known limitations — same structure as before, updated for the 6-step
pipeline and new files)
