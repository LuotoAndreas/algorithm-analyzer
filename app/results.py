from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


DEFAULT_FIELDNAMES = [
    "scenario_id",
    "algorithm_name",

    "start_node",
    "goal_node",

    "change_type",
    "changed_edge",
    "event_step",
    "event_triggered",
    "event_successfully_applied",
    "cost_multiplier",

    "original_route_node_count",
    "original_route_edge_count",
    "final_traversed_node_count",
    "final_traversed_edge_count",

    "original_route_length",
    "total_distance_travelled",
    "distance_increase",
    "distance_increase_pct",

    "original_planning_time",
    "replanning_time_total",
    "total_planning_time",

    "replanning_count",
    "route_changed_after_event",
    "route_change_ratio",

    "arrived",
    "failed",
    "failure_reason",

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