from __future__ import annotations

import os
import ast
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import osmnx as ox


OUTPUT_DIR = "webapp/static/routes"


def ensure_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _parse_route(value) -> list[int]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return ast.literal_eval(value)
    return []


def _parse_edges(value) -> list[tuple[int, int]]:
    if value is None:
        return []

    if isinstance(value, list):
        parsed_edges = []
        for item in value:
            if isinstance(item, tuple) and len(item) == 2:
                parsed_edges.append(item)
            elif isinstance(item, list) and len(item) == 2:
                parsed_edges.append((item[0], item[1]))
            elif isinstance(item, str):
                parsed = ast.literal_eval(item)
                if isinstance(parsed, tuple) and len(parsed) == 2:
                    parsed_edges.append(parsed)
        return parsed_edges

    if isinstance(value, str):
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            parsed_edges = []
            for item in parsed:
                if isinstance(item, tuple) and len(item) == 2:
                    parsed_edges.append(item)
                elif isinstance(item, list) and len(item) == 2:
                    parsed_edges.append((item[0], item[1]))
            return parsed_edges

    return []

def _set_route_view(ax, graph, routes: list[list[int]], padding_ratio: float = 0.15) -> None:
    node_ids = []
    for route in routes:
        node_ids.extend(route)

    node_ids = [node_id for node_id in node_ids if node_id in graph.nodes]

    if not node_ids:
        return

    xs = [graph.nodes[node_id]["x"] for node_id in node_ids]
    ys = [graph.nodes[node_id]["y"] for node_id in node_ids]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    x_range = max_x - min_x
    y_range = max_y - min_y

    if x_range == 0:
        x_range = 0.002
    if y_range == 0:
        y_range = 0.002

    pad_x = x_range * padding_ratio
    pad_y = y_range * padding_ratio

    ax.set_xlim(min_x - pad_x, max_x + pad_x)
    ax.set_ylim(min_y - pad_y, max_y + pad_y)


def _find_edge_start_index(route: list[int], edge: tuple[int, int]) -> int | None:
    u, v = edge
    for i in range(len(route) - 1):
        if route[i] == u and route[i + 1] == v:
            return i
    return None


def _common_prefix_length(route1: list[int], route2: list[int]) -> int:
    length = 0
    for a, b in zip(route1, route2):
        if a == b:
            length += 1
        else:
            break
    return length


def _longest_common_suffix_start(
    original_route: list[int],
    final_route: list[int],
    min_match_length: int = 2,
) -> tuple[int | None, int | None]:
    """
    Etsii kohdan, josta alkuperäisen ja uuden reitin loppuosat ovat samat.
    Palauttaa indeksit:
    - original_idx: missä yhteinen loppu alkaa original_routessa
    - final_idx: missä yhteinen loppu alkaa final_routessa

    min_match_length kertoo montako peräkkäistä solmua pitää täsmätä,
    jotta sitä pidetään oikeana takaisinliittymisenä.
    """
    best_original_idx = None
    best_final_idx = None

    for i in range(len(original_route)):
        for j in range(len(final_route)):
            match_len = 0

            while (
                i + match_len < len(original_route)
                and j + match_len < len(final_route)
                and original_route[i + match_len] == final_route[j + match_len]
            ):
                match_len += 1

            if match_len >= min_match_length:
                if best_final_idx is None or j < best_final_idx:
                    best_original_idx = i
                    best_final_idx = j

    return best_original_idx, best_final_idx


def _extract_changed_segment(
    original_route: list[int],
    final_route: list[int],
    changed_edge: tuple[int, int] | None,
) -> list[int]:
    """
    Palauttaa final_routesta vain muuttuneen osuuden.

    Punainen osuus:
    - alkaa ensisijaisesti solmusta, joka on juuri ennen muuttunutta kaarta alkuperäisellä reitillä
    - jos kyseinen solmu ei kuulu uuteen reittiin, käytetään fallbackina ensimmäistä eroamiskohtaa
    - päättyy siihen, missä uusi reitti oikeasti liittyy takaisin alkuperäiseen
    """
    if not original_route or not final_route:
        return []

    start_idx_in_final = None

    if changed_edge is not None:
        edge_start_idx = _find_edge_start_index(original_route, changed_edge)
        if edge_start_idx is not None:
            reroute_start_node = original_route[edge_start_idx]
            if reroute_start_node in final_route:
                start_idx_in_final = final_route.index(reroute_start_node)

    if start_idx_in_final is None:
        prefix_len = _common_prefix_length(original_route, final_route)
        if prefix_len == 0:
            start_idx_in_final = 0
        else:
            start_idx_in_final = prefix_len - 1

    original_tail = original_route[start_idx_in_final + 1:] if start_idx_in_final + 1 < len(original_route) else []
    final_tail = final_route[start_idx_in_final + 1:] if start_idx_in_final + 1 < len(final_route) else []

    if not final_tail:
        return []

    tail_original_idx, tail_final_idx = _longest_common_suffix_start(
        original_tail,
        final_tail,
        min_match_length=2,
    )

    if tail_original_idx is None or tail_final_idx is None:
        changed_segment = final_route[start_idx_in_final:]
    else:
        rejoin_idx_in_final = start_idx_in_final + 1 + tail_final_idx
        changed_segment = final_route[start_idx_in_final:rejoin_idx_in_final + 1]

    if len(changed_segment) < 2:
        return []

    return changed_segment


def plot_scenario_route(
    graph,
    original_route,
    final_route,
    changed_edges,
    filename: str,
    title: str | None = None,
    zoom_to_route: bool = False,
) -> str: 
    ensure_dir()

    original_route = _parse_route(original_route)
    final_route = _parse_route(final_route)
    changed_edges = _parse_edges(changed_edges)

    fig, ax = ox.plot_graph(
        graph,
        node_size=0,
        edge_linewidth=0.6,
        edge_color="lightgray",
        bgcolor="white",
        show=False,
        close=False,
    )

    if original_route:
        ox.plot_graph_route(
            graph,
            original_route,
            route_linewidth=3,
            route_color="royalblue",
            node_size=0,
            bgcolor="white",
            ax=ax,
            show=False,
            close=False,
        )

    primary_changed_edge = changed_edges[0] if changed_edges else None
    
    changed_segment = _extract_changed_segment(
        original_route,
        final_route,
        primary_changed_edge,
    )

    if changed_segment:
        ox.plot_graph_route(
            graph,
            changed_segment,
            route_linewidth=4,
            route_color="crimson",
            node_size=0,
            bgcolor="white",
            ax=ax,
            show=False,
            close=False,
        )

    closed_edge_label_added = False

    for from_node, to_node in changed_edges:
        if from_node in graph.nodes and to_node in graph.nodes:
            x1 = graph.nodes[from_node]["x"]
            y1 = graph.nodes[from_node]["y"]
            x2 = graph.nodes[to_node]["x"]
            y2 = graph.nodes[to_node]["y"]

            ax.plot(
                [x1, x2],
                [y1, y2],
                linewidth=4,
                linestyle="-",
                color="black",
                zorder=5,
                label="Suljettu tieosuus" if not closed_edge_label_added else None,
            )
            closed_edge_label_added = True

    if original_route:
        start_node = original_route[0]
        goal_node = original_route[-1]

        sx = graph.nodes[start_node]["x"]
        sy = graph.nodes[start_node]["y"]
        gx = graph.nodes[goal_node]["x"]
        gy = graph.nodes[goal_node]["y"]

        ax.scatter(sx, sy, s=70, marker="o", color="green", zorder=6, label="Lähtö")
        ax.scatter(gx, gy, s=90, marker="X", color="red", zorder=6, label="Kohde")

    routes_for_zoom = [original_route]
    if changed_segment:
        routes_for_zoom.append(changed_segment)

    if zoom_to_route:
        _set_route_view(ax, graph, routes_for_zoom, padding_ratio=0.20)

    if title:
        ax.set_title(title)
    
    ax.plot([], [], color="royalblue", linewidth=3, label="Alkuperäinen reitti")
    ax.plot([], [], color="crimson", linewidth=4, label="Muuttunut reittiosuus")

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best")

    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return path