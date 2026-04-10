from __future__ import annotations

import math
import os
from typing import Iterable

import folium


OUTPUT_DIR = "webapp/static/interactive_maps"


def ensure_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _graph_center(graph) -> tuple[float, float]:
    ys = [data["y"] for _, data in graph.nodes(data=True)]
    xs = [data["x"] for _, data in graph.nodes(data=True)]
    return (sum(ys) / len(ys), sum(xs) / len(xs))


def _edge_midpoint_and_direction(graph, u: int, v: int) -> tuple[float, float, float, float]:
    x1 = graph.nodes[u]["x"]
    y1 = graph.nodes[u]["y"]
    x2 = graph.nodes[v]["x"]
    y2 = graph.nodes[v]["y"]

    mid_lat = (y1 + y2) / 2
    mid_lon = (x1 + x2) / 2

    dlat = y2 - y1
    dlon = x2 - x1
    length = math.hypot(dlat, dlon)

    if length == 0:
        return mid_lat, mid_lon, mid_lat, mid_lon

    # Pieni nuoli kaaren keskelle
    arrow_half = min(length * 0.18, 0.00018)
    start_lat = mid_lat - (dlat / length) * arrow_half
    start_lon = mid_lon - (dlon / length) * arrow_half
    end_lat = mid_lat + (dlat / length) * arrow_half
    end_lon = mid_lon + (dlon / length) * arrow_half

    return start_lat, start_lon, end_lat, end_lon


def generate_full_direction_map(
    graph,
    filename: str = "full_direction_map.html",
    max_arrows: int | None = 8000,
) -> str:
    """
    Luo interaktiivisen HTML-kartan, jossa näkyy koko tieverkko
    ja harmaat ajosuuntanuolet.
    """
    ensure_dir()

    center_lat, center_lon = _graph_center(graph)

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        control_scale=True,
        tiles="CartoDB positron",
    )

    # Piirretään ensin tieverkko kevyesti
    drawn_edges = 0
    for u, v, key, data in graph.edges(keys=True, data=True):
        latlon = [
            (graph.nodes[u]["y"], graph.nodes[u]["x"]),
            (graph.nodes[v]["y"], graph.nodes[v]["x"]),
        ]
        folium.PolyLine(
            latlon,
            color="lightgray",
            weight=2,
            opacity=0.8,
        ).add_to(fmap)
        drawn_edges += 1

    # Sitten nuolisuunnat
    drawn_arrows = 0
    seen_pairs: set[tuple[int, int]] = set()

    for u, v, key, data in graph.edges(keys=True, data=True):
        if max_arrows is not None and drawn_arrows >= max_arrows:
            break

        if (u, v) in seen_pairs:
            continue
        seen_pairs.add((u, v))

        start_lat, start_lon, end_lat, end_lon = _edge_midpoint_and_direction(graph, u, v)

        folium.PolyLine(
            [(start_lat, start_lon), (end_lat, end_lon)],
            color="dimgray",
            weight=2,
            opacity=0.9,
        ).add_to(fmap)

        # pieni kolmio nuolen kärjeksi
        folium.RegularPolygonMarker(
            location=(end_lat, end_lon),
            number_of_sides=3,
            radius=4,
            rotation=_bearing_degrees(start_lat, start_lon, end_lat, end_lon),
            color="dimgray",
            fill=True,
            fill_color="dimgray",
            fill_opacity=0.9,
            weight=1,
        ).add_to(fmap)

        drawn_arrows += 1

    folium.LayerControl().add_to(fmap)

    path = os.path.join(OUTPUT_DIR, filename)
    fmap.save(path)
    return path


def _bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Laskee markerin kiertosuunnan asteina.
    """
    angle = math.degrees(math.atan2(lon2 - lon1, lat2 - lat1))
    return angle