from __future__ import annotations

import random
from pathlib import Path

from app.map_loader import load_clean_map
from app.environment import RoadEnvironment
from app.events import EdgeEvent
from app.planners import get_default_planners
from app.scenario_generator import generate_scenario
from app.simulation import DynamicRouteSimulation
from app.metrics import build_result_row, summarize_rows
from app.results import write_rows_to_csv


def _is_meaningful_last_mile_scenario(rows: list[dict], change_type: str) -> bool:
    if not rows:
        return False

    if change_type == "remove":
        return True

    reference_row = next((row for row in rows if row.get("algorithm_name") == "Dijkstra"), rows[0])
    if not reference_row.get("event_triggered"):
        return False

    planned = reference_row.get("planned_delivery_time")
    actual = reference_row.get("actual_delivery_time")
    original_travel = reference_row.get("original_route_travel_time")
    total_travel = reference_row.get("total_travel_time")
    delay = reference_row.get("delivery_delay_seconds")
    route_changed = bool(reference_row.get("route_changed_after_event"))
    replan_count = int(reference_row.get("replanning_count") or 0)

    delivery_growth = None
    if planned is not None and actual is not None:
        delivery_growth = actual - planned

    travel_growth = None
    if original_travel is not None and total_travel is not None:
        travel_growth = total_travel - original_travel

    meaningful_delay = delay is not None and delay >= 1.0
    meaningful_delivery_growth = delivery_growth is not None and delivery_growth >= 30.0
    meaningful_travel_growth = travel_growth is not None and travel_growth >= 30.0

    return any([
        meaningful_delay,
        meaningful_delivery_growth,
        meaningful_travel_growth,
        route_changed,
        replan_count > 0,
        reference_row.get("service_level_met") is False,
    ])


def build_output_filename(change_type: str, cost_multiplier: float | None) -> str:
    if change_type == "remove":
        return "web_results_remove.csv"

    if change_type == "increase_cost":
        multiplier_str = str(cost_multiplier if cost_multiplier is not None else 3.0).replace(".", "_")
        return f"web_results_increase_cost_{multiplier_str}.csv"

    return f"web_results_{change_type}.csv"


def run_experiment(
    place_name: str,
    seed: int,
    target_count: int,
    max_attempts: int,
    change_type: str,
    cost_multiplier: float,
    outputs_dir: Path,
    event_count: int = 1,
    service_time_seconds: float = 120.0,
    delivery_deadline_factor: float = 1.15,
    disruption_mode: str = "route_corridor",
) -> dict:
    rng = random.Random(seed)

    graph = load_clean_map(
        place_name=place_name,
        network_type="drive",
        simplify=True,
    )

    rows: list[dict] = []
    accepted_scenarios = 0
    rejected_as_trivial = 0
    scenario_id = 1

    for _attempt in range(1, max_attempts + 1):
        scenario = generate_scenario(
            graph=graph,
            planners=get_default_planners(),
            rng=rng,
            change_type=change_type,
            cost_multiplier=cost_multiplier,
            event_count=event_count,
            service_time_seconds=service_time_seconds,
            delivery_deadline_factor=delivery_deadline_factor,
            disruption_mode=disruption_mode,
        )

        if scenario is None:
            continue

        scenario_rows = []

        for planner in get_default_planners():
            environment = RoadEnvironment(graph)
            
            event_copies = [
                EdgeEvent(
                    event_step=event.event_step,
                    event_time=event.event_time,
                    edge=event.edge,
                    change_type=event.change_type,
                    cost_multiplier=event.cost_multiplier,
                    affected_edges=list(event.affected_edges),
                    region_center=event.region_center,
                    region_radius_m=event.region_radius_m,
                    severity_label=event.severity_label,
                )
                for event in scenario.events
            ]

            simulation = DynamicRouteSimulation(
                environment=environment,
                planner=planner,
                start_node=scenario.start_node,
                goal_node=scenario.goal_node,
                events=event_copies,
                delivery_task=scenario.delivery_task,
            )

            simulation_result = simulation.run()

            row = build_result_row(
                scenario=scenario,
                simulation_result=simulation_result,
                scenario_id=scenario_id,
            )
            scenario_rows.append(row)

        if not _is_meaningful_last_mile_scenario(scenario_rows, change_type):
            rejected_as_trivial += 1
            continue

        rows.extend(scenario_rows)
        accepted_scenarios += 1
        scenario_id += 1

        if accepted_scenarios >= target_count:
            break

    output_filename = build_output_filename(change_type, cost_multiplier)
    output_path = outputs_dir / output_filename

    if rows:
        write_rows_to_csv(rows, output_path)

    summary = summarize_rows(rows) if rows else {}

    return {
        "place_name": place_name,
        "seed": seed,
        "target_count": target_count,
        "max_attempts": max_attempts,
        "change_type": change_type,
        "cost_multiplier": cost_multiplier,
        "event_count": event_count,
        "accepted_scenarios": accepted_scenarios,
        "rejected_as_trivial": rejected_as_trivial,
        "service_time_seconds": service_time_seconds,
        "delivery_deadline_factor": delivery_deadline_factor,
        "disruption_mode": disruption_mode,
        "rows": rows,
        "summary": summary,
        "output_path": str(output_path),
        "graph": graph,
    }