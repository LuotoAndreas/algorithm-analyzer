from __future__ import annotations

from dataclasses import dataclass
import math
import random
import networkx as nx

from app.delivery import DeliveryTask
from app.events import EdgeEvent
from app.planners import BasePlanner


@dataclass
class Scenario:
    """Yksi simulaatioskenaario, jota voidaan käyttää kaikille algoritmeille."""
    start_node: int
    goal_node: int
    events: list[EdgeEvent]
    original_routes: dict[str, list[int]]
    delivery_task: DeliveryTask
    reference_algorithm_name: str
    disruption_mode: str = "route_corridor"


def route_to_edges(route: list[int]) -> list[tuple[int, int]]:
    return [(route[i], route[i + 1]) for i in range(len(route) - 1)]


def find_edge_index(route: list[int], edge: tuple[int, int]) -> int | None:
    from_node, to_node = edge
    for i in range(len(route) - 1):
        if route[i] == from_node and route[i + 1] == to_node:
            return i
    return None


def calculate_event_time_for_edge(graph: nx.MultiDiGraph, route: list[int], edge_index: int, rng: random.Random) -> float | None:
    if edge_index < 1:
        return None
    cumulative_time = 0.0
    for i in range(edge_index):
        u = route[i]
        v = route[i + 1]
        edge_data = graph.get_edge_data(u, v)
        if edge_data is None:
            return None
        travel_times = [data.get("travel_time") for _, data in edge_data.items() if data.get("travel_time") is not None]
        if not travel_times:
            return None
        cumulative_time += min(travel_times)
    return cumulative_time * rng.uniform(0.6, 0.95)


def choose_event_step(edge_index: int, rng: random.Random) -> int | None:
    if edge_index < 1:
        return None
    min_step = 1 if edge_index >= 2 else 0
    max_step = edge_index
    if min_step > max_step:
        return None
    return rng.randint(min_step, max_step)


def generate_random_node_pair(graph: nx.MultiDiGraph, rng: random.Random) -> tuple[int, int]:
    nodes = list(graph.nodes)
    while True:
        start_node = rng.choice(nodes)
        goal_node = rng.choice(nodes)
        if start_node != goal_node:
            return start_node, goal_node


def _build_target_edge_indices(min_edge_index: int, max_edge_index: int, event_count: int) -> list[int]:
    if event_count <= 0 or min_edge_index > max_edge_index:
        return []
    if event_count == 1:
        return [round((min_edge_index + max_edge_index) / 2)]
    span = max_edge_index - min_edge_index
    return [min_edge_index + round(span * ((i + 1) / (event_count + 1))) for i in range(event_count)]


def _edge_midpoint(graph: nx.MultiDiGraph, edge: tuple[int, int]) -> tuple[float, float]:
    u, v = edge
    x = (float(graph.nodes[u]["x"]) + float(graph.nodes[v]["x"])) / 2.0
    y = (float(graph.nodes[u]["y"]) + float(graph.nodes[v]["y"])) / 2.0
    return x, y


def _distance_m_between_points(graph: nx.MultiDiGraph, point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    lon1, lat1 = point_a
    lon2, lat2 = point_b
    # kevyt haversine ilman lisäriippuvuuksia
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _region_radius_for_event_count(event_count: int, rng: random.Random) -> float:
    base = 110.0 + (event_count - 1) * 10.0
    return base + rng.uniform(0.0, 70.0)


def _affected_edge_target_count(change_type: str, cost_multiplier: float, event_count: int, rng: random.Random) -> int:
    if change_type == "remove":
        return 1 if rng.random() < 0.75 else 2

    if cost_multiplier >= 3.0:
        low, high = 4, 8
    elif cost_multiplier >= 2.0:
        low, high = 3, 6
    else:
        low, high = 2, 4

    if event_count >= 5:
        high = min(high + 1, 8)

    return rng.randint(low, high)


def _high_degree_hotspot_nodes(graph: nx.MultiDiGraph, limit: int = 40) -> list[int]:
    weighted_nodes: list[tuple[int, int]] = []
    for node in graph.nodes:
        degree = graph.out_degree(node) + graph.in_degree(node)
        if degree > 2:
            weighted_nodes.append((degree, node))
    weighted_nodes.sort(reverse=True)
    return [node for _, node in weighted_nodes[:limit]]


def _edges_near_hotspot(
    graph: nx.MultiDiGraph,
    hotspot_node: int,
    reference_edges: list[tuple[int, int]],
    radius_m: float,
    max_edges: int,
) -> list[tuple[int, int]]:
    center = (float(graph.nodes[hotspot_node]["x"]), float(graph.nodes[hotspot_node]["y"]))
    nearby: list[tuple[tuple[int, int], float]] = []
    for edge in reference_edges:
        point = _edge_midpoint(graph, edge)
        distance = _distance_m_between_points(graph, center, point)
        if distance <= radius_m:
            nearby.append((edge, distance))
    nearby.sort(key=lambda item: item[1])
    return [edge for edge, _ in nearby[:max_edges]]


def _severity_label(change_type: str, cost_multiplier: float | None, affected_count: int) -> str:
    if change_type == "remove":
        return "closure"
    if cost_multiplier is None:
        return "unknown"
    if affected_count >= 6 or cost_multiplier >= 3.0:
        return "high"
    if affected_count >= 3 or cost_multiplier >= 1.75:
        return "medium"
    return "low"


def _collect_regional_edges(
    graph: nx.MultiDiGraph,
    reference_edges: list[tuple[int, int]],
    anchor_edge: tuple[int, int],
    radius_m: float,
    anchor_index: int,
    max_edges: int,
) -> list[tuple[int, int]]:
    center = _edge_midpoint(graph, anchor_edge)
    indexed_edges: list[tuple[tuple[int, int], int, float]] = []
    for idx, candidate in enumerate(reference_edges):
        point = _edge_midpoint(graph, candidate)
        distance = _distance_m_between_points(graph, center, point)
        if distance <= radius_m:
            indexed_edges.append((candidate, idx, distance))

    indexed_edges.sort(key=lambda item: (item[2], abs(item[1] - anchor_index)))
    return [edge for edge, _, _ in indexed_edges[:max_edges]] or [anchor_edge]


def _event_current_node_from_route(route: list[int], event_step: int | None) -> int | None:
    if not route or event_step is None:
        return None
    if event_step < 0:
        return route[0]
    if event_step >= len(route):
        return route[-1]
    return route[event_step]


def _remove_edges_from_graph_copy(graph: nx.MultiDiGraph, edges: list[tuple[int, int]]) -> nx.MultiDiGraph:
    copied = graph.copy()
    for u, v in edges:
        if copied.has_edge(u, v):
            for key in list(copied[u][v].keys()):
                copied.remove_edge(u, v, key)
    return copied


def _has_alternative_path_after_remove(graph: nx.MultiDiGraph, route: list[int], goal_node: int, event: EdgeEvent) -> bool:
    current_node = _event_current_node_from_route(route, event.event_step)
    if current_node is None:
        return False
    modified_graph = _remove_edges_from_graph_copy(graph, event.target_edges)
    try:
        nx.shortest_path(modified_graph, source=current_node, target=goal_node, weight="travel_time", method="dijkstra")
        return True
    except nx.NetworkXNoPath:
        return False


def _create_regional_event(
    graph: nx.MultiDiGraph,
    reference_route: list[int],
    anchor_edge: tuple[int, int],
    edge_index: int,
    change_type: str,
    cost_multiplier: float,
    rng: random.Random,
    event_count: int,
    disruption_mode: str = "route_corridor",
) -> EdgeEvent | None:
    event_step = choose_event_step(edge_index, rng)
    event_time = calculate_event_time_for_edge(graph, reference_route, edge_index, rng)
    if event_step is None or event_time is None:
        return None

    reference_edges = route_to_edges(reference_route)
    max_edges = _affected_edge_target_count(
        change_type=change_type,
        cost_multiplier=cost_multiplier,
        event_count=event_count,
        rng=rng,
    )
    radius_m = _region_radius_for_event_count(event_count, rng)

    affected_edges = _collect_regional_edges(
        graph=graph,
        reference_edges=reference_edges,
        anchor_edge=anchor_edge,
        radius_m=radius_m,
        anchor_index=edge_index,
        max_edges=max_edges,
    )

    region_center = _edge_midpoint(graph, anchor_edge)

    if disruption_mode == "traffic_hotspot":
        hotspot_candidates = _high_degree_hotspot_nodes(graph)
        if hotspot_candidates:
            hotspot_candidates.sort(
                key=lambda node: _distance_m_between_points(
                    graph,
                    region_center,
                    (float(graph.nodes[node]["x"]), float(graph.nodes[node]["y"]))
                )
            )
            hotspot_node = hotspot_candidates[0]
            hotspot_center = (float(graph.nodes[hotspot_node]["x"]), float(graph.nodes[hotspot_node]["y"]))
            hotspot_edges = _edges_near_hotspot(
                graph=graph,
                hotspot_node=hotspot_node,
                reference_edges=reference_edges,
                radius_m=max(radius_m, 140.0),
                max_edges=max_edges,
            )
            if hotspot_edges:
                affected_edges = hotspot_edges
                region_center = hotspot_center

    return EdgeEvent(
        event_step=event_step,
        event_time=event_time,
        edge=anchor_edge,
        change_type=change_type,
        cost_multiplier=cost_multiplier if change_type == "increase_cost" else None,
        affected_edges=affected_edges,
        region_center=region_center,
        region_radius_m=radius_m,
        severity_label=_severity_label(change_type, cost_multiplier, len(affected_edges)),
    )




def _sort_events_for_simulation(events: list[EdgeEvent]) -> list[EdgeEvent]:
    def sort_key(event: EdgeEvent) -> tuple[float, float]:
        if event.event_time is not None:
            return (float(event.event_time), float(event.event_step if event.event_step is not None else 0))
        if event.event_step is not None:
            return (float(event.event_step), float(event.event_step))
        return (float("inf"), float("inf"))

    return sorted(events, key=sort_key)

def generate_scenario(
    graph: nx.MultiDiGraph,
    planners: list[BasePlanner],
    rng: random.Random,
    change_type: str = "increase_cost",
    cost_multiplier: float = 3.0,
    max_pair_attempts: int = 100,
    event_count: int = 1,
    service_time_seconds: float = 120.0,
    delivery_deadline_factor: float = 1.15,
    disruption_mode: str = "route_corridor",
) -> Scenario | None:
    if not planners:
        return None

    reference_planner = next((planner for planner in planners if planner.name == "Dijkstra"), planners[0])

    for _ in range(max_pair_attempts):
        start_node, goal_node = generate_random_node_pair(graph, rng)
        original_routes: dict[str, list[int]] = {}
        failed = False
        reference_route: list[int] | None = None
        reference_travel_time: float | None = None

        for planner in planners:
            try:
                result = planner.plan(graph, start_node, goal_node)
                if len(result.route) < 3:
                    failed = True
                    break
                original_routes[planner.name] = result.route
                if planner.name == reference_planner.name:
                    reference_route = result.route
                    reference_travel_time = result.travel_time
            except nx.NetworkXNoPath:
                failed = True
                break

        if failed or reference_route is None or reference_travel_time is None:
            continue

        reference_edges = route_to_edges(reference_route)
        if len(reference_edges) < 3:
            continue

        eligible = [(idx, edge) for idx, edge in enumerate(reference_edges) if 1 <= idx < len(reference_edges) - 1]
        if len(eligible) < event_count:
            continue

        target_indices = _build_target_edge_indices(eligible[0][0], eligible[-1][0], event_count)
        selected: list[tuple[int, tuple[int, int]]] = []
        min_gap = 2
        for target in target_indices:
            candidates = []
            for idx, edge in eligible:
                if any(abs(idx - chosen_idx) < min_gap for chosen_idx, _ in selected):
                    continue
                candidates.append((abs(idx - target), rng.random(), idx, edge))
            if not candidates:
                continue
            _, _, idx, edge = sorted(candidates)[0]
            selected.append((idx, edge))
        if len(selected) < event_count:
            continue
        selected.sort(key=lambda item: item[0])

        events: list[EdgeEvent] = []
        for idx, edge in selected[:event_count]:
            event = _create_regional_event(
                graph=graph,
                reference_route=reference_route,
                anchor_edge=edge,
                edge_index=idx,
                change_type=change_type,
                cost_multiplier=cost_multiplier,
                rng=rng,
                event_count=event_count,
                disruption_mode=disruption_mode,
            )
            if event is None:
                break
            events.append(event)

        if len(events) < event_count:
            continue

        events = _sort_events_for_simulation(events)

        if change_type == "remove" and not _has_alternative_path_after_remove(graph, reference_route, goal_node, events[0]):
            continue

        delivery_task = DeliveryTask(
            depot_node=start_node,
            customer_node=goal_node,
            departure_time=0.0,
            service_time_seconds=service_time_seconds,
            planned_arrival_time=reference_travel_time,
            deadline_time=reference_travel_time * delivery_deadline_factor + service_time_seconds,
        )

        return Scenario(
            start_node=start_node,
            goal_node=goal_node,
            events=events,
            original_routes=original_routes,
            delivery_task=delivery_task,
            reference_algorithm_name=reference_planner.name,
            disruption_mode=disruption_mode,
        )

    return None
