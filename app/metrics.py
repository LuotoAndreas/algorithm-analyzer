from __future__ import annotations

from typing import Any

from app.scenario_generator import Scenario
from app.simulation import SimulationResult


def route_to_edges(route: list[int]) -> list[tuple[int, int]]:
    """
    Muuntaa reitin suunnatuiksi kaariksi.
    """
    return [(route[i], route[i + 1]) for i in range(len(route) - 1)]


def count_shared_edges(route_a: list[int], route_b: list[int]) -> int:
    """
    Laskee kuinka monta yhteistä suunnattua kaarta kahdella reitillä on.
    """
    edges_a = set(route_to_edges(route_a))
    edges_b = set(route_to_edges(route_b))
    return len(edges_a & edges_b)


def compute_route_change_ratio(original_route: list[int], traversed_route: list[int]) -> float | None:
    """
    Arvioi reitin muuttumisen määrää vertaamalla alkuperäisen reitin kaaria
    toteutuneen reitin kaariin.

    Palauttaa arvon väliltä 0.0 ... 1.0:
    - 0.0 = ei muutosta
    - 1.0 = ei yhteisiä kaaria

    Jos vertailu ei ole mielekäs, palauttaa None.
    """
    original_edges = route_to_edges(original_route)
    traversed_edges = route_to_edges(traversed_route)

    if not original_edges:
        return None

    shared_count = count_shared_edges(original_route, traversed_route)
    return 1.0 - (shared_count / len(original_edges))


def build_result_row(
    scenario: Scenario,
    simulation_result: SimulationResult,
    scenario_id: int,
) -> dict[str, Any]:
    """
    Muuntaa yhden simulaation tuloksen yhdeksi tallennettavaksi riviksi.
    """
    first_event = scenario.events[0] if scenario.events else None

    original_route_node_count = len(simulation_result.original_route)
    original_route_edge_count = max(0, original_route_node_count - 1)

    final_traversed_node_count = len(simulation_result.final_traversed_route)
    final_traversed_edge_count = max(0, final_traversed_node_count - 1)

    if simulation_result.failed:
        distance_increase = None
        distance_increase_pct = None
    else:
        distance_increase = (
            simulation_result.total_distance_travelled
            - simulation_result.original_route_length
        )

        if simulation_result.original_route_length > 0:
            distance_increase_pct = (
                distance_increase / simulation_result.original_route_length
            ) * 100.0
        else:
            distance_increase_pct = None

    route_change_ratio = compute_route_change_ratio(
        simulation_result.original_route,
        simulation_result.final_traversed_route,
    )

    if (
        simulation_result.original_route_travel_time_with_events is not None
        and simulation_result.total_travel_time is not None
        and not simulation_result.failed
    ):
        replanning_time_saved = (
            simulation_result.original_route_travel_time_with_events
            - simulation_result.total_travel_time
        )
    else:
        replanning_time_saved = None

    row = {
        "scenario_id": scenario_id,
        "algorithm_name": simulation_result.algorithm_name,

        "start_node": simulation_result.start_node,
        "goal_node": simulation_result.goal_node,

        "change_type": simulation_result.change_type,
        "changed_edge": simulation_result.changed_edge,
        "event_step": first_event.event_step if first_event else None,
        "event_time": first_event.event_time if first_event else None,
        "event_count": len(scenario.events),
        "event_steps": [event.event_step for event in scenario.events],
        "event_times": [event.event_time for event in scenario.events],
        "all_changed_edges": [event.edge for event in scenario.events],
        "event_triggered": simulation_result.event_triggered,
        "event_successfully_applied": simulation_result.event_successfully_applied,
        "cost_multiplier": simulation_result.cost_multiplier,

        "original_route_node_count": original_route_node_count,
        "original_route_edge_count": original_route_edge_count,
        "final_traversed_node_count": final_traversed_node_count,
        "final_traversed_edge_count": final_traversed_edge_count,

        "original_route_length": simulation_result.original_route_length,
        "original_route_travel_time": simulation_result.original_route_travel_time,
        "original_route_travel_time_with_events": simulation_result.original_route_travel_time_with_events,
        "total_distance_travelled": simulation_result.total_distance_travelled,
        "total_travel_time": simulation_result.total_travel_time,
        "replanning_time_saved": replanning_time_saved,
        "distance_increase": distance_increase,
        "distance_increase_pct": distance_increase_pct,

        "original_planning_time": simulation_result.original_planning_time,
        "replanning_time_total": simulation_result.replanning_time_total,
        "total_planning_time": simulation_result.total_planning_time,

        "replanning_count": simulation_result.replanning_count,
        "route_changed_after_event": simulation_result.route_changed_after_event,
        "route_change_ratio": route_change_ratio,

        "arrived": simulation_result.arrived,
        "failed": simulation_result.failed,
        "failure_reason": simulation_result.failure_reason,
        "failure_category": simulation_result.failure_category,

        "original_route": simulation_result.original_route,
        "final_traversed_route": simulation_result.final_traversed_route,
        "final_remaining_route": simulation_result.final_remaining_route,
    }

    return row


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Muodostaa karkean yhteenvedon algoritmittain.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        grouped.setdefault(row["algorithm_name"], []).append(row)

    summary: dict[str, dict[str, Any]] = {}

    for algorithm_name, algorithm_rows in grouped.items():
        count = len(algorithm_rows)
        successful_rows = [r for r in algorithm_rows if not r["failed"]]

        def avg(field: str) -> float | None:
            values = [r[field] for r in successful_rows if r[field] is not None]
            if not values:
                return None
            return sum(values) / len(values)

        failure_category_counts: dict[str, int] = {}
        for row in algorithm_rows:
            category = row.get("failure_category")
            if category:
                failure_category_counts[category] = failure_category_counts.get(category, 0) + 1

        summary[algorithm_name] = {
            "scenario_count": count,
            "successful_count": len(successful_rows),
            "failed_count": count - len(successful_rows),
            "failure_category_counts": failure_category_counts,
            "avg_original_route_length": avg("original_route_length"),
            "avg_original_route_travel_time": avg("original_route_travel_time"),
            "avg_original_route_travel_time_with_events": avg("original_route_travel_time_with_events"),
            "avg_total_distance_travelled": avg("total_distance_travelled"),
            "avg_total_travel_time": avg("total_travel_time"),
            "avg_replanning_time_saved": avg("replanning_time_saved"),
            "avg_distance_increase": avg("distance_increase"),
            "avg_distance_increase_pct": avg("distance_increase_pct"),
            "avg_original_planning_time": avg("original_planning_time"),
            "avg_replanning_time_total": avg("replanning_time_total"),
            "avg_total_planning_time": avg("total_planning_time"),
            "avg_replanning_count": avg("replanning_count"),
            "avg_route_change_ratio": avg("route_change_ratio"),
        }

    return summary