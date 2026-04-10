# Copilot instructions for this repository

This repository compares dynamic route planning algorithms using OSM street graphs.
Focus on the split between core simulation logic in `app/` and the Flask UI in `webapp/`.

- The main domain is in `app/`:
  - `app/map_loader.py` loads and cleans OSMnx graphs, keeps the largest strongly connected component, and stores `travel_time` and `max_speed_mps` metadata.
  - `app/planners.py` defines planners for Dijkstra, A*, and D* Lite. D* Lite is stateful and implements custom `replan()` plus event state updates.
  - `app/simulation.py` runs one dynamic route simulation per planner and produces `SimulationResult` objects.
  - `app/scenario_generator.py` builds scenarios by selecting start/goal pairs and event edges shared by all planners.
  - `app/results.py` writes normalized CSV rows and defines the export schema used by both scripts and the web UI.

- The web UI is a thin adapter in `webapp/`:
  - `webapp/app.py` is the Flask entrypoint and ties UI forms to `webapp/simulation_runner.run_experiment()`.
  - `webapp/map_plotter.py` renders route images into `webapp/static/routes` using OSMnx/Matplotlib.
  - `webapp/plotter.py` builds summary plots used by the results page.

- Recommended workflows:
  - Install deps: `pip install -r requirements.txt`
  - Run the web app: `python -m webapp.app`
  - Run experiments directly: `python scripts/run_experiments.py`
  - The UI does not persist run state beyond in-memory `RUN_RESULTS`; route images are generated on demand.

- Important conventions:
  - Use `app/config.py` dataclasses for default experiment and path settings.
  - Core modules expect `networkx.MultiDiGraph` graph objects with `travel_time`, `length`, `speed_kph`, `x`, and `y` attributes.
  - Dynamic events are represented by `app.events.EdgeEvent`; event activation logic may use `event_time` or legacy `event_step` values.
  - `app/planners.py` returns `PlanResult`; simulation code expects `route`, `travel_time`, and timing data.

- Avoid changing the graph load logic in `app/map_loader.py` without also updating scenario generation and planner comparisons.
- There are currently no automated tests in `tests/`; additions should target `app/simulation.py`, `app/scenario_generator.py`, and planner equivalence checks in `app/validate_algorithms.py`.

If anything in this summary is unclear or missing, tell me which part of the code flow or workflow you want me to expand.