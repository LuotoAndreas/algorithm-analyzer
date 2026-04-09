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
    events: list[EdgeEvent]
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

def calculate_event_time_for_edge(
    graph: nx.MultiDiGraph,
    route: list[int],
    edge_index: int,
    rng: random.Random,
) -> float | None:
    """
    Laskee tapahtumalle ajan sekunteina ennen valittua tieosuutta.

    Aika muodostetaan kumulatiivisena travel_time-summana reitin alusta.
    Tapahtuma sijoitetaan hieman ennen kyseistä kaarta, jotta muutos ehtii
    tapahtua ajon aikana ennen kuin ajoneuvo saapuu esteelle.
    """
    if edge_index < 1:
        return None

    cumulative_time = 0.0

    for i in range(edge_index):
        u = route[i]
        v = route[i + 1]

        edge_data = graph.get_edge_data(u, v)
        if edge_data is None:
            return None

        travel_times = [
            data.get("travel_time")
            for _, data in edge_data.items()
            if data.get("travel_time") is not None
        ]

        if not travel_times:
            return None

        cumulative_time += min(travel_times)

    # Laukaistaan tapahtuma hieman ennen kyseistä tieosuutta.
    # Käytetään pientä satunnaista kerrointa, jotta tapahtuma ei ole aina täsmälleen
    # samalla hetkellä.
    return cumulative_time * rng.uniform(0.6, 0.95)

def choose_event_step(edge_index: int, rng: random.Random) -> int | None:
    """
    Valitsee simulaatioaskeleen, jolla tapahtuma laukaistaan ennen muuttuvaa tieosuutta.
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


def select_multiple_events(
    candidate_edges: list[tuple[tuple[int, int], int, int, float]],
    event_count: int,
    change_type: str,
    cost_multiplier: float,
    min_index_gap: int = 2,
) -> list[EdgeEvent]:
    """
    Valitsee useita tapahtumia samalta alkuperäiseltä reitiltä.

    candidate_edges sisältää nelikoita:
    - edge
    - edge_index
    - event_step
    - event_time

    Valinta tehdään reitin järjestyksessä siten, että tapahtumat eivät ole liian lähellä toisiaan.
    """
    if not candidate_edges or event_count <= 0:
        return []

    sorted_candidates = sorted(candidate_edges, key=lambda item: item[1])

    selected: list[tuple[tuple[int, int], int, int, float]] = []
    last_selected_index: int | None = None

    for edge, edge_index, event_step, event_time in sorted_candidates:
        if last_selected_index is None or (edge_index - last_selected_index) >= min_index_gap:
            selected.append((edge, edge_index, event_step, event_time))
            last_selected_index = edge_index

        if len(selected) >= event_count:
            break

    events: list[EdgeEvent] = []
    for edge, _edge_index, event_step, event_time in selected:
        events.append(
            EdgeEvent(
                event_step=event_step,
                event_time=event_time,
                edge=edge,
                change_type=change_type,
                cost_multiplier=cost_multiplier if change_type == "increase_cost" else None,
            )
        )

    return events

def generate_scenario(
    graph: nx.MultiDiGraph,
    planners: list[BasePlanner],
    rng: random.Random,
    change_type: str = "remove",
    cost_multiplier: float = 3.0,
    max_pair_attempts: int = 100,
    event_count: int = 1,
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
            event_time = calculate_event_time_for_edge(graph, reference_route, edge_index, rng)

            if event_step is not None and event_time is not None:
                candidate_edges.append((edge, edge_index, event_step, event_time))

        if not candidate_edges:
            continue

        events = select_multiple_events(
            candidate_edges=candidate_edges,
            event_count=event_count,
            change_type=change_type,
            cost_multiplier=cost_multiplier,
            min_index_gap=2,
        )

        if len(events) < event_count:
            continue

        return Scenario(
            start_node=start_node,
            goal_node=goal_node,
            events=events,
            original_routes=original_routes,
        )

    return None