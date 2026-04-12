from pathlib import Path
from collections import defaultdict
from uuid import uuid4

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for

from webapp.interactive_map import generate_full_direction_map
from webapp.map_plotter import plot_scenario_route
from webapp.plotter import plot_distance_increase, plot_total_time
from webapp.simulation_runner import run_experiment

app = Flask(__name__)

# Väliaikainen muistivarasto ajotuloksille
RUN_RESULTS: dict[str, dict] = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    place_name = request.form["place_name"]
    seed = int(request.form["seed"])
    target_count = int(request.form["target_count"])
    max_attempts = int(request.form["max_attempts"])

    change_type = request.form["change_type"]

    if change_type == "increase_cost":
        cost_multiplier = float(request.form["cost_multiplier"])
    else:
        cost_multiplier = 1.0

    event_count = int(request.form["event_count"])
    service_time_seconds = float(request.form.get("service_time_seconds", 120.0))
    delivery_deadline_factor = float(request.form.get("delivery_deadline_factor", 1.15))
    disruption_mode = request.form.get("disruption_mode", "route_corridor")

    outputs_dir = Path("data") / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    result = run_experiment(
        place_name=place_name,
        seed=seed,
        target_count=target_count,
        max_attempts=max_attempts,
        change_type=change_type,
        cost_multiplier=cost_multiplier,
        outputs_dir=outputs_dir,
        event_count=event_count,
        service_time_seconds=service_time_seconds,
        delivery_deadline_factor=delivery_deadline_factor,
        disruption_mode=disruption_mode,
    )

    if result["rows"]:
        df = pd.read_csv(result["output_path"])
        df_success = df[df["failed"] == False]
        if not df_success.empty:
            plot_distance_increase(df_success, "distance.png")
            plot_total_time(df_success, "time.png")

    grouped_rows = defaultdict(list)
    for row in result["rows"]:
        grouped_rows[row["scenario_id"]].append(row)
        row["route_image_full"] = None
        row["route_image_zoom"] = None
        row["algorithm_slug"] = row["algorithm_name"].replace("*", "star").replace(" ", "_")

    scenario_groups = {}
    for scenario_id, rows in grouped_rows.items():
        failed_count = sum(1 for row in rows if row["failed"])
        total_count = len(rows)

        if failed_count == 0:
            scenario_status = "all-success"
        elif failed_count == total_count:
            scenario_status = "all-failed"
        else:
            scenario_status = "partial-failed"

        scenario_groups[scenario_id] = {
            "rows": rows,
            "status": scenario_status,
        }

    result["grouped_rows"] = scenario_groups
    result["open_scenario"] = None

    run_id = uuid4().hex
    result["run_id"] = run_id
    RUN_RESULTS[run_id] = result

    return render_template("results.html", result=result)


@app.route("/generate-scenario-routes/<run_id>/<int:scenario_id>")
def generate_scenario_routes(run_id: str, scenario_id: int):
    result = RUN_RESULTS.get(run_id)
    if result is None:
        return redirect(url_for("index"))

    open_scenario = request.args.get("open_scenario", type=int)

    graph = result["graph"]

    scenario_rows = [row for row in result["rows"] if row["scenario_id"] == scenario_id]
    if not scenario_rows:
        return redirect(url_for("index"))

    for row in scenario_rows:
        algorithm_slug = row["algorithm_name"].replace("*", "star").replace(" ", "_")

        full_filename = f"{run_id}_scenario_{scenario_id}_{algorithm_slug}_full.png"
        zoom_filename = f"{run_id}_scenario_{scenario_id}_{algorithm_slug}_zoom.png"

        failure_node = row.get("failure_node")
        is_failed = bool(row.get("failed"))

        # Full-kuva: normaali näkymä, ei ajosuuntanuolia
        plot_scenario_route(
            graph=graph,
            original_route=row["original_route"],
            final_route=row["final_traversed_route"],
            changed_edges=row["all_changed_edges"],
            change_type=row["change_type"],
            filename=full_filename,
            title=f"Skenaario {scenario_id} – {row['algorithm_name']}",
            zoom_to_route=False,
            failure_node=failure_node,
            show_local_directions=False,
        )

        direction_nodes = []
        if row.get("original_route"):
            direction_nodes.append(row["original_route"][0])   # lähtösolmu
        if failure_node is not None:
            direction_nodes.append(failure_node)               # epäonnistumiskohta

        plot_scenario_route(
            graph=graph,
            original_route=row["original_route"],
            final_route=row["final_traversed_route"],
            changed_edges=row["all_changed_edges"],
            change_type=row["change_type"],
            filename=zoom_filename,
            title=f"Skenaario {scenario_id} – {row['algorithm_name']} (zoom)",
            zoom_to_route=not is_failed,
            failure_node=failure_node,
            show_local_directions=is_failed,
            direction_nodes=direction_nodes,
            show_start_outgoing_directions=is_failed,
        )

        row["route_image_full"] = f"routes/{full_filename}"
        row["route_image_zoom"] = f"routes/{zoom_filename}"

    result["open_scenario"] = open_scenario

    return render_template("results.html", result=result)

@app.route("/generate-full-direction-map/<run_id>")
def generate_full_direction_map_view(run_id: str):
    result = RUN_RESULTS.get(run_id)
    if result is None:
        return redirect(url_for("index"))

    html_path = generate_full_direction_map(
        graph=result["graph"],
        filename=f"full_direction_map_{run_id}.html",
    )

    return redirect(url_for("static", filename=f"interactive_maps/full_direction_map_{run_id}.html"))

if __name__ == "__main__":
    app.run(debug=True)