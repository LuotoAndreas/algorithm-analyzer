from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


DEFAULT_FIELDNAMES = [
    "scenario_id",
    "algorithm_name",

    "start_node",
    "goal_node",
    "depot_node",
    "customer_node",
    "reference_algorithm_name",

    "change_type",
    "changed_edge",
    "changed_edge_count",
    "event_scope",
    "event_scope_label",
    "impact_spread",
    "impact_spread_label",
    "region_radius_m",
    "event_severity",
    "event_step",
    "event_time",
    "event_count",
    "event_steps",
    "event_times",
    "all_changed_edges",
    "all_affected_edge_counts",
    "all_event_scopes",
    "all_impact_spreads",
    "event_triggered",
    "event_successfully_applied",
    "cost_multiplier",
    "planned_delivery_time",
    "actual_delivery_time",
    "delivery_deadline_time",
    "delivery_delay_seconds",
    "delivery_delay_pct",
    "service_level_met",

    "original_route_node_count",
    "original_route_edge_count",
    "final_traversed_node_count",
    "final_traversed_edge_count",

    "original_route_length",
    "original_route_travel_time",
    "original_route_travel_time_with_events",
    "total_distance_travelled",
    "total_travel_time",
    "replanning_time_saved",
    "distance_increase",
    "distance_increase_pct",

    "original_planning_time",
    "replanning_time_total",
    "total_planning_time",

    "replanning_count",
    "events_total",
    "events_affecting_remaining_route",
    "events_triggering_replan",
    "successful_replans",
    "ineffective_replans",
    "route_changed_after_event",
    "route_change_ratio",

    "arrived",
    "failed",
    "failure_reason",
    "failure_category",
    "failure_node",

    "event_log",

    "original_route",
    "final_traversed_route",
    "final_remaining_route",
]


def ensure_parent_dir(filepath: str | Path) -> Path:
    """
    Varmistaa, että kohdetiedoston yläkansio on olemassa.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_rows_to_csv(
    rows: list[dict[str, Any]],
    filepath: str | Path,
    fieldnames: list[str] | None = None,
) -> Path:
    """
    Kirjoittaa annetut rivit CSV-tiedostoon.
    """
    path = ensure_parent_dir(filepath)
    final_fieldnames = fieldnames if fieldnames is not None else DEFAULT_FIELDNAMES

    with path.open(mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=final_fieldnames)
        writer.writeheader()

        for row in rows:
            normalized_row = {field: row.get(field) for field in final_fieldnames}
            writer.writerow(normalized_row)

    return path


def append_rows_to_csv(
    rows: list[dict[str, Any]],
    filepath: str | Path,
    fieldnames: list[str] | None = None,
) -> Path:
    """
    Lisää rivit olemassa olevaan CSV-tiedostoon. Luo tiedoston tarvittaessa.
    """
    path = ensure_parent_dir(filepath)
    final_fieldnames = fieldnames if fieldnames is not None else DEFAULT_FIELDNAMES

    file_exists = path.exists()

    with path.open(mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=final_fieldnames)

        if not file_exists:
            writer.writeheader()

        for row in rows:
            normalized_row = {field: row.get(field) for field in final_fieldnames}
            writer.writerow(normalized_row)

    return path