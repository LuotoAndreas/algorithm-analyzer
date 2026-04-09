from __future__ import annotations

import random

from app.config import get_config
from app.map_loader import load_clean_map
from app.environment import RoadEnvironment
from app.events import EdgeEvent
from app.planners import get_default_planners
from app.scenario_generator import generate_scenario
from app.simulation import DynamicRouteSimulation
from app.metrics import build_result_row, summarize_rows
from app.results import write_rows_to_csv


def run_single_event_scenario(
    graph,
    planners,
    rng: random.Random,
    target_count: int,
    max_attempts: int,
    change_type: str,
    cost_multiplier: float | None,
    output_path,
) -> None:
    rows: list[dict] = []
    accepted_scenarios = 0
    scenario_id = 1

    print()
    print("=" * 70)
    print(f"Ajetaan skenaario: change_type={change_type}, cost_multiplier={cost_multiplier}")
    print("=" * 70)

    for attempt in range(1, max_attempts + 1):
        print(f"Yritys {attempt}/{max_attempts}...")

        scenario = generate_scenario(
            graph=graph,
            planners=planners,
            rng=rng,
            change_type=change_type,
            cost_multiplier=cost_multiplier if cost_multiplier is not None else 3.0,
        )

        if scenario is None:
            print("  Skenaariota ei voitu muodostaa.")
            continue

        print(
            f"  Skenaario hyväksytty: start={scenario.start_node}, "
            f"goal={scenario.goal_node}, "
            f"event_edge={scenario.event.edge}, "
            f"event_step={scenario.event.event_step}, "
            f"change_type={scenario.event.change_type}"
        )

        scenario_rows = []

        for planner in planners:
            environment = RoadEnvironment(graph)

            event_copy = EdgeEvent(
                event_step=scenario.event.event_step,
                edge=scenario.event.edge,
                change_type=scenario.event.change_type,
                cost_multiplier=scenario.event.cost_multiplier,
            )

            simulation = DynamicRouteSimulation(
                environment=environment,
                planner=planner,
                start_node=scenario.start_node,
                goal_node=scenario.goal_node,
                event=event_copy,
            )

            simulation_result = simulation.run()

            row = build_result_row(
                scenario=scenario,
                simulation_result=simulation_result,
                scenario_id=scenario_id,
            )
            scenario_rows.append(row)

            status = (
                "onnistui"
                if not simulation_result.failed
                else f"epäonnistui ({simulation_result.failure_reason})"
            )

            print(
                f"    {planner.name}: {status}, "
                f"alkuperäinen pituus={simulation_result.original_route_length:.2f}, "
                f"toteutunut matka={simulation_result.total_distance_travelled:.2f}, "
                f"replanningit={simulation_result.replanning_count}"
            )

        rows.extend(scenario_rows)
        accepted_scenarios += 1
        scenario_id += 1

        print(
            f"  Hyväksyttyjä skenaarioita yhteensä: "
            f"{accepted_scenarios}/{target_count}"
        )

        if accepted_scenarios >= target_count:
            break

    if not rows:
        print("Yhtään tulosriviä ei muodostunut. CSV:tä ei tallennettu.")
        return

    write_rows_to_csv(rows, output_path)

    print()
    print(f"Tulokset tallennettu tiedostoon: {output_path}")

    summary = summarize_rows(rows)

    print()
    print("=== Yhteenveto algoritmeittain ===")
    for algorithm_name, values in summary.items():
        print(f"\n{algorithm_name}")
        print(f"  Skenaarioita: {values['scenario_count']}")
        print(f"  Onnistuneita: {values['successful_count']}")
        print(f"  Epäonnistuneita: {values['failed_count']}")

        def fmt(value):
            return "N/A" if value is None else f"{value:.6f}"

        print(f"  Keskimääräinen alkuperäinen reitin pituus: {fmt(values['avg_original_route_length'])}")
        print(f"  Keskimääräinen toteutunut matka: {fmt(values['avg_total_distance_travelled'])}")
        print(f"  Keskimääräinen matkan piteneminen: {fmt(values['avg_distance_increase'])}")
        print(f"  Keskimääräinen matkan piteneminen (%): {fmt(values['avg_distance_increase_pct'])}")
        print(f"  Keskimääräinen alkuperäinen laskenta-aika: {fmt(values['avg_original_planning_time'])}")
        print(f"  Keskimääräinen replanning-aika yhteensä: {fmt(values['avg_replanning_time_total'])}")
        print(f"  Keskimääräinen kokonaislaskenta-aika: {fmt(values['avg_total_planning_time'])}")
        print(f"  Keskimääräinen replanningien määrä: {fmt(values['avg_replanning_count'])}")
        print(f"  Keskimääräinen reitin muutosaste: {fmt(values['avg_route_change_ratio'])}")


def build_output_filename(change_type: str, cost_multiplier: float | None) -> str:
    if change_type == "remove":
        return "results_remove.csv"

    if change_type == "increase_cost":
        multiplier_str = str(cost_multiplier if cost_multiplier is not None else 3.0).replace(".", "_")
        return f"results_increase_cost_{multiplier_str}.csv"

    return f"results_{change_type}.csv"


def main() -> None:
    config = get_config()
    rng = random.Random(config.experiment.seed)

    print("Ladataan tieverkko...")
    graph = load_clean_map(
        place_name=config.map.place_name,
        network_type=config.map.network_type,
        simplify=config.map.simplify,
    )

    print("Tieverkko ladattu.")
    print(f"Solmuja: {len(graph.nodes)}")
    print(f"Kaaria: {len(graph.edges)}")

    planners = get_default_planners()
    print("Käytettävät plannerit:")
    for planner in planners:
        print(f" - {planner.name}")

    for scenario_cfg in config.event.scenarios:
        output_filename = build_output_filename(
            change_type=scenario_cfg.change_type,
            cost_multiplier=scenario_cfg.cost_multiplier,
        )
        output_path = config.paths.outputs_dir / output_filename

        run_single_event_scenario(
            graph=graph,
            planners=planners,
            rng=rng,
            target_count=config.experiment.target_count,
            max_attempts=config.experiment.max_attempts,
            change_type=scenario_cfg.change_type,
            cost_multiplier=scenario_cfg.cost_multiplier,
            output_path=output_path,
        )


if __name__ == "__main__":
    main()