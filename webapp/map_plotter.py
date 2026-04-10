from __future__ import annotations

import os
import ast
import math
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


def _route_to_edges(route: list[int]) -> list[tuple[int, int]]:
    """
    Muuntaa reitin kaariksi muodossa (u, v).
    """
    return [(route[i], route[i + 1]) for i in range(len(route) - 1)]


def _extract_detour_segments(
    original_route: list[int],
    final_route: list[int],
) -> list[list[int]]:
    """
    Palauttaa toteutuneesta reitistä ne yhtenäiset osat, joita ei ollut alkuperäisessä reitissä.
    """
    if not original_route or not final_route:
        return []

    original_edges = set(_route_to_edges(original_route))
    final_edges = _route_to_edges(final_route)

    detour_segments: list[list[int]] = []
    current_segment: list[int] = []

    for u, v in final_edges:
        if (u, v) not in original_edges:
            if not current_segment:
                current_segment = [u, v]
            else:
                if current_segment[-1] == u:
                    current_segment.append(v)
                else:
                    if len(current_segment) >= 2:
                        detour_segments.append(current_segment)
                    current_segment = [u, v]
        else:
            if len(current_segment) >= 2:
                detour_segments.append(current_segment)
            current_segment = []

    if len(current_segment) >= 2:
        detour_segments.append(current_segment)

    return detour_segments


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


def _set_view_to_nodes(
    ax,
    graph,
    node_ids: list[int],
    padding_ratio: float = 0.25,
    min_span: float = 0.0008,
) -> None:
    """
    Rajaa näkymän niin, että kaikki annetut solmut mahtuvat kuvaan.
    """
    valid_nodes = [node_id for node_id in node_ids if node_id in graph.nodes]
    if not valid_nodes:
        return

    xs = [graph.nodes[node_id]["x"] for node_id in valid_nodes]
    ys = [graph.nodes[node_id]["y"] for node_id in valid_nodes]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    x_range = max(max_x - min_x, min_span)
    y_range = max(max_y - min_y, min_span)

    pad_x = x_range * padding_ratio
    pad_y = y_range * padding_ratio

    ax.set_xlim(min_x - pad_x, max_x + pad_x)
    ax.set_ylim(min_y - pad_y, max_y + pad_y)

def _set_view_to_route_and_nodes(
    ax,
    graph,
    route: list[int],
    extra_nodes: list[int] | None = None,
    padding_ratio: float = 0.20,
    min_span: float = 0.0015,
) -> None:
    """
    Rajaa näkymän niin, että koko reitti ja halutut lisäsolmut mahtuvat kuvaan.
    """
    node_ids = [node_id for node_id in route if node_id in graph.nodes]

    if extra_nodes:
        node_ids.extend([node_id for node_id in extra_nodes if node_id in graph.nodes])

    if not node_ids:
        return

    xs = [graph.nodes[node_id]["x"] for node_id in node_ids]
    ys = [graph.nodes[node_id]["y"] for node_id in node_ids]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    x_range = max(max_x - min_x, min_span)
    y_range = max(max_y - min_y, min_span)

    pad_x = x_range * padding_ratio
    pad_y = y_range * padding_ratio

    ax.set_xlim(min_x - pad_x, max_x + pad_x)
    ax.set_ylim(min_y - pad_y, max_y + pad_y)

def _draw_local_direction_arrows(
    ax,
    graph,
    center_node: int,
    radius: float = 0.00045,
    max_arrows: int = 12,
) -> None:
    """
    Piirtää pienet ajosuuntanuolet epäonnistumiskohdan lähiteille.
    """
    if center_node not in graph.nodes:
        return

    cx = graph.nodes[center_node]["x"]
    cy = graph.nodes[center_node]["y"]

    arrows_drawn = 0
    seen_pairs: set[tuple[int, int]] = set()

    for u, v, key, data in graph.edges(keys=True, data=True):
        if arrows_drawn >= max_arrows:
            break

        if u not in graph.nodes or v not in graph.nodes:
            continue

        x1 = graph.nodes[u]["x"]
        y1 = graph.nodes[u]["y"]
        x2 = graph.nodes[v]["x"]
        y2 = graph.nodes[v]["y"]

        midpoint_x = (x1 + x2) / 2
        midpoint_y = (y1 + y2) / 2

        if abs(midpoint_x - cx) > radius or abs(midpoint_y - cy) > radius:
            continue

        if (u, v) in seen_pairs:
            continue
        seen_pairs.add((u, v))

        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)

        if length == 0:
            continue

        unit_dx = dx / length
        unit_dy = dy / length

        arrow_len = min(length * 0.22, radius * 0.22)

        start_x = midpoint_x - unit_dx * arrow_len * 0.5
        start_y = midpoint_y - unit_dy * arrow_len * 0.5
        end_x = midpoint_x + unit_dx * arrow_len * 0.5
        end_y = midpoint_y + unit_dy * arrow_len * 0.5

        ax.annotate(
            "",
            xy=(end_x, end_y),
            xytext=(start_x, start_y),
            arrowprops=dict(
                arrowstyle="->",
                color="dimgray",
                lw=1.2,
                shrinkA=0,
                shrinkB=0,
                alpha=0.9,
            ),
            zorder=4,
        )

        arrows_drawn += 1

def _draw_direction_arrows_for_nodes(
    ax,
    graph,
    center_nodes: list[int],
    radius: float = 0.00045,
    max_arrows_per_center: int = 10,
    color: str = "dimgray",
    linewidth: float = 1.2,
) -> None:
    """
    Piirtää ajosuuntanuolia usean keskussolmun ympärille.
    """
    valid_centers = [node for node in center_nodes if node in graph.nodes]
    if not valid_centers:
        return

    seen_pairs: set[tuple[int, int]] = set()

    for center_node in valid_centers:
        cx = graph.nodes[center_node]["x"]
        cy = graph.nodes[center_node]["y"]
        arrows_drawn = 0

        for u, v, key, data in graph.edges(keys=True, data=True):
            if arrows_drawn >= max_arrows_per_center:
                break

            if u not in graph.nodes or v not in graph.nodes:
                continue

            x1 = graph.nodes[u]["x"]
            y1 = graph.nodes[u]["y"]
            x2 = graph.nodes[v]["x"]
            y2 = graph.nodes[v]["y"]

            midpoint_x = (x1 + x2) / 2
            midpoint_y = (y1 + y2) / 2

            if abs(midpoint_x - cx) > radius or abs(midpoint_y - cy) > radius:
                continue

            if (u, v) in seen_pairs:
                continue
            seen_pairs.add((u, v))

            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)

            if length == 0:
                continue

            unit_dx = dx / length
            unit_dy = dy / length

            arrow_len = min(length * 0.22, radius * 0.22)

            start_x = midpoint_x - unit_dx * arrow_len * 0.5
            start_y = midpoint_y - unit_dy * arrow_len * 0.5
            end_x = midpoint_x + unit_dx * arrow_len * 0.5
            end_y = midpoint_y + unit_dy * arrow_len * 0.5

            ax.annotate(
                "",
                xy=(end_x, end_y),
                xytext=(start_x, start_y),
                arrowprops=dict(
                    arrowstyle="->",
                    color=color,
                    lw=linewidth,
                    shrinkA=0,
                    shrinkB=0,
                    alpha=0.95,
                ),
                zorder=4,
            )

            arrows_drawn += 1

def _draw_outgoing_arrows_from_node(
    ax,
    graph,
    node_id: int,
    radius: float = 0.0012,
) -> None:
    """
    Piirtää nuolen kaikille annetusta solmusta lähteville kaarille.
    Tämä sopii erityisesti lähtösolmun ympäristön tarkasteluun.
    """
    if node_id not in graph.nodes:
        return

    seen_successors: set[int] = set()

    x1 = graph.nodes[node_id]["x"]
    y1 = graph.nodes[node_id]["y"]

    for succ in graph.successors(node_id):
        if succ in seen_successors:
            continue
        seen_successors.add(succ)

        if succ not in graph.nodes:
            continue

        x2 = graph.nodes[succ]["x"]
        y2 = graph.nodes[succ]["y"]

        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)

        if length == 0:
            continue

        unit_dx = dx / length
        unit_dy = dy / length

        arrow_len = min(length * 0.35, radius * 0.8)

        start_x = x1 + unit_dx * arrow_len * 0.15
        start_y = y1 + unit_dy * arrow_len * 0.15
        end_x = x1 + unit_dx * arrow_len
        end_y = y1 + unit_dy * arrow_len

        ax.annotate(
            "",
            xy=(end_x, end_y),
            xytext=(start_x, start_y),
            arrowprops=dict(
                arrowstyle="->",
                color="black",
                lw=1.4,
                shrinkA=0,
                shrinkB=0,
                alpha=0.95,
            ),
            zorder=8,
        )

def plot_scenario_route(
    graph,
    original_route,
    final_route,
    changed_edges,
    change_type: str | None,
    filename: str,
    title: str | None = None,
    zoom_to_route: bool = False,
    failure_node: int | None = None,
    show_local_directions: bool = False,
    direction_nodes: list[int] | None = None,
    show_start_outgoing_directions: bool = False,
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

    detour_segments = _extract_detour_segments(
        original_route,
        final_route,
    )

    for detour_segment in detour_segments:
        ox.plot_graph_route(
            graph,
            detour_segment,
            route_linewidth=4,
            route_color="crimson",
            node_size=0,
            bgcolor="white",
            ax=ax,
            show=False,
            close=False,
        )

    change_label_added = False

    if change_type == "remove":
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
                    label="Suljettu tieosuus" if not change_label_added else None,
                )
                change_label_added = True

    elif change_type == "increase_cost":
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
                    color="darkorange",
                    zorder=5,
                    label="Hidastunut tieosuus" if not change_label_added else None,
                )
                change_label_added = True

    if original_route:
        start_node = original_route[0]
        goal_node = original_route[-1]

        sx = graph.nodes[start_node]["x"]
        sy = graph.nodes[start_node]["y"]
        gx = graph.nodes[goal_node]["x"]
        gy = graph.nodes[goal_node]["y"]

        ax.scatter(sx, sy, s=70, marker="o", color="green", zorder=6, label="Lähtö")
        ax.scatter(gx, gy, s=90, marker="X", color="red", zorder=6, label="Kohde")

    if failure_node is not None and failure_node in graph.nodes:
        fx = graph.nodes[failure_node]["x"]
        fy = graph.nodes[failure_node]["y"]
        ax.scatter(
            fx,
            fy,
            s=90,
            marker="s",
            color="orange",
            edgecolors="black",
            zorder=7,
            label="Epäonnistumiskohta",
        )

    if show_local_directions and failure_node is not None:
        extra_nodes = []

        if original_route:
            extra_nodes.append(original_route[0])   # lähtö
            extra_nodes.append(original_route[-1])  # kohde

        if direction_nodes:
            extra_nodes.extend(direction_nodes)

        extra_nodes.append(failure_node)

        _set_view_to_route_and_nodes(
            ax,
            graph,
            route=original_route,
            extra_nodes=extra_nodes,
            padding_ratio=0.14,
            min_span=0.0030,
        )

        if direction_nodes:
            _draw_direction_arrows_for_nodes(
                ax,
                graph,
                center_nodes=direction_nodes,
                radius=0.00045,
                max_arrows_per_center=10,
                color="dimgray",
                linewidth=1.2,
            )
        else:
            _draw_local_direction_arrows(ax, graph, failure_node)

    elif zoom_to_route:
        routes_for_zoom = [original_route]
        routes_for_zoom.extend(detour_segments)
        _set_route_view(ax, graph, routes_for_zoom, padding_ratio=0.20)

    if title:
        ax.set_title(title)

    ax.plot([], [], color="royalblue", linewidth=3, label="Alkuperäinen reitti")
    ax.plot([], [], color="crimson", linewidth=4, label="Kiertoreitti")

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best")

    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return path