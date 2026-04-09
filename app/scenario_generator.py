from __future__ import annotations

from dataclasses import dataclass
import random
import networkx as nx

from app.events import EdgeEvent
from app.planners import BasePlanner

@dataclass
class Scenario:
    """
    Yksi simulaatioskenaario, jota voidaan käyttää kaikille algoritmeille.
    """
    start_node: int
    goal_node: int
    event: EdgeEvent
    original_routes: dict[str, list[int]]


def route_to_edges(route: list[int]) -> list[tuple[int, int]]:
    """
    Muuntaa reitin suunnatuiksi kaariksi.
    """
    return [(route[i], route[i + 1]) for i in range(len(route) - 1)]


def find_common_edges(routes: dict[str, list[int]]) -> list[tuple[int, int]]:
    """
    Etsii kaaret, jotka esiintyvät kaikkien algoritmien alkuperäisissä reiteissä.

    Palauttaa kaaret ensimmäisen reitin järjestyksessä.
    """
    route_lists = list(routes.values())
    if not route_lists:
        return []

    first_edges = route_to_edges(route_lists[0])
    common_edge_set = set(first_edges)

    for route in route_lists[1:]:
        common_edge_set &= set(route_to_edges(route))

    return [edge for edge in first_edges if edge in common_edge_set]


def find_edge_index(route: list[int], edge: tuple[int, int]) -> int | None:
    """
    Palauttaa kaaren alkusolmun indeksin reitillä.
    """
    from_node, to_node = edge

    for i in range(len(route) - 1):
        if route[i] == from_node and route[i + 1] == to_node:
            return i

    return None


def choose_event_step(edge_index: int, rng: random.Random) -> int | None:
    """
    Valitsee simulaatioaskeleen, jolla tapahtuma laukaistaan ennen muuttuvaa tieosuutta.

    Jos muuttuva tieosuus on route[i] -> route[i+1], event_step pitää olla korkeintaan i-1,
    jotta kaari ei ole vielä ajettu.

    Esimerkiksi:
        route = [A, B, C, D]
        edge_index = 2 tarkoittaa kaarta C -> D
        silloin eventti voidaan laukaista stepissä 0 tai 1 tai 2 ennen kuin C->D ajetaan

    Tässä vältetään kaikkein ensimmäinen hetki, jos mahdollista.
    """
    if edge_index < 1:
        return None

    min_step = 1 if edge_index >= 2 else 0
    max_step = edge_index

    if min_step > max_step:
        return None

    return rng.randint(min_step, max_step)


def generate_random_node_pair(graph: nx.MultiDiGraph, rng: random.Random) -> tuple[int, int]:
    """
    Valitsee satunnaisen lähtö- ja kohdesolmun.
    """
    nodes = list(graph.nodes)

    while True:
        start_node = rng.choice(nodes)
        goal_node = rng.choice(nodes)

        if start_node != goal_node:
            return start_node, goal_node


def generate_scenario(
    graph: nx.MultiDiGraph,
    planners: list[BasePlanner],
    rng: random.Random,
    change_type: str = "remove",
    cost_multiplier: float = 3.0,
    max_pair_attempts: int = 100,
) -> Scenario | None:
    """
    Generoi yhden reilun skenaarion kaikille algoritmeille.

    Ehdot:
    - kaikille algoritmeille löytyy alkuperäinen reitti
    - reiteillä on vähintään yksi yhteinen kaari
    - eventille voidaan valita askel ennen muuttuvaa tieosuutta
    """
    for _ in range(max_pair_attempts):
        start_node, goal_node = generate_random_node_pair(graph, rng)

        original_routes: dict[str, list[int]] = {}
        failed = False

        for planner in planners:
            try:
                result = planner.plan(graph, start_node, goal_node)
                if len(result.route) < 3:
                    failed = True
                    break

                original_routes[planner.name] = result.route
            except nx.NetworkXNoPath:
                failed = True
                break

        if failed:
            continue

        common_edges = find_common_edges(original_routes)
        if not common_edges:
            continue

        # Käytetään ensimmäisen plannerin reittiä indeksien tarkistukseen.
        reference_route = next(iter(original_routes.values()))

        candidate_edges = []
        for edge in common_edges:
            edge_index = find_edge_index(reference_route, edge)
            if edge_index is None:
                continue

            event_step = choose_event_step(edge_index, rng)
            if event_step is not None:
                candidate_edges.append((edge, edge_index, event_step))

        if not candidate_edges:
            continue

        selected_edge, selected_edge_index, event_step = rng.choice(candidate_edges)

        event = EdgeEvent(
            event_step=event_step,
            edge=selected_edge,
            change_type=change_type,
            cost_multiplier=cost_multiplier if change_type == "increase_cost" else None,
        )

        return Scenario(
            start_node=start_node,
            goal_node=goal_node,
            event=event,
            original_routes=original_routes,
        )

    return None