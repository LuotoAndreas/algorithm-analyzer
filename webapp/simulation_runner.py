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
) -> dict:
    rng = random.Random(seed)

    graph = load_clean_map(
        place_name=place_name,
        network_type="drive",
        simplify=True,
    )

    rows: list[dict] = []
    accepted_scenarios = 0
    scenario_id = 1

    for _attempt in range(1, max_attempts + 1):
        scenario = generate_scenario(
            graph=graph,
            planners=get_default_planners(),
            rng=rng,
            change_type=change_type,
            cost_multiplier=cost_multiplier,
            event_count=event_count,
        )

        if scenario is None:
            continue

        scenario_rows = []

        for planner in get_default_planners():
            environment = RoadEnvironment(graph)

            event_copies = [
                EdgeEvent(
                    event_step=event.event_step,
                    edge=event.edge,
                    change_type=event.change_type,
                    cost_multiplier=event.cost_multiplier,
                )
                for event in scenario.events
            ]

            simulation = DynamicRouteSimulation(
                environment=environment,
                planner=planner,
                start_node=scenario.start_node,
                goal_node=scenario.goal_node,
                events=event_copies,
            )

            simulation_result = simulation.run()

            row = build_result_row(
                scenario=scenario,
                simulation_result=simulation_result,
                scenario_id=scenario_id,
            )
            scenario_rows.append(row)

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
        "rows": rows,
        "summary": summary,
        "output_path": str(output_path),
        "graph": graph,
    }