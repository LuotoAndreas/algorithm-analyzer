from __future__ import annotations

import random
from math import isclose

import networkx as nx

from app.map_loader import load_clean_map
from app.planners import DijkstraPlanner, AStarPlanner, DStarLitePlanner
from app.environment import RoadEnvironment
from app.events import EdgeEvent
from app.simulation import DynamicRouteSimulation


def random_distinct_node_pair(graph: nx.MultiDiGraph, rng: random.Random) -> tuple[int, int]:
    nodes = list(graph.nodes)

    while True:
        start = rng.choice(nodes)
        goal = rng.choice(nodes)

        if start != goal:
            return start, goal


def validate_static_equivalence(
    graph: nx.MultiDiGraph,
    sample_count: int = 30,
    seed: int = 42,
    tolerance: float = 1e-6,
) -> None:
    rng = random.Random(seed)

    dijkstra = DijkstraPlanner()
    astar = AStarPlanner()
    dstar = DStarLitePlanner()

    checked = 0
    attempts = 0
    max_attempts = sample_count * 20

    while checked < sample_count and attempts < max_attempts:
        attempts += 1
        start, goal = random_distinct_node_pair(graph, rng)

        try:
            dijkstra_result = dijkstra.plan(graph, start, goal)
            astar_result = astar.plan(graph, start, goal)
            dstar_result = dstar.plan(graph, start, goal)
        except nx.NetworkXNoPath:
            continue

        if not isclose(dijkstra_result.travel_time, astar_result.travel_time, rel_tol=0.0, abs_tol=tolerance):
            raise AssertionError(
                f"A* poikkeaa Dijkstrasta: start={start}, goal={goal}, "
                f"dijkstra={dijkstra_result.travel_time}, astar={astar_result.travel_time}"
            )

        if not isclose(dijkstra_result.travel_time, dstar_result.travel_time, rel_tol=0.0, abs_tol=tolerance):
            raise AssertionError(
                f"D* Lite poikkeaa Dijkstrasta: start={start}, goal={goal}, "
                f"dijkstra={dijkstra_result.travel_time}, dstar={dstar_result.travel_time}"
            )

        checked += 1

    if checked < sample_count:
        raise RuntimeError(f"Staattisia testipareja saatiin vain {checked}/{sample_count}")

    print(f"Staattinen validointi onnistui: {checked} paria.")


def validate_dynamic_dstar_against_dijkstra(
    graph: nx.MultiDiGraph,
    start_node: int,
    goal_node: int,
    event: EdgeEvent,
    tolerance: float = 1e-6,
) -> None:
    simulation = DynamicRouteSimulation(
        environment=RoadEnvironment(graph),
        planner=DStarLitePlanner(),
        start_node=start_node,
        goal_node=goal_node,
        events=[event],
    )

    result = simulation.run()

    if result.failed:
        print("D* Lite epäonnistui dynaamisessa validoinnissa; tämä voi olla aidosti mahdollinen lopputulos.")
        return

    if not result.event_log:
        raise AssertionError("Eventtiloki puuttuu dynaamisesta validoinnista.")

    successful_replans = [entry for entry in result.event_log if entry["replan_attempted"] and entry["replan_success"]]
    if not successful_replans:
        print("Ei onnistunutta uudelleenreititystä verrattavaksi.")
        return

    first_replan = successful_replans[0]
    replan_node = first_replan["current_node"]

    environment = RoadEnvironment(graph)
    environment.apply_event(event)

    dijkstra = DijkstraPlanner()
    reference = dijkstra.plan(environment.graph, replan_node, goal_node)

    # D* Lite:n lopullinen remaining_route ei tässä välttämättä kerro juuri replan-hetken kustannusta täydellisesti,
    # joten verrataan vähintään sitä, että reitti jatkuu eikä tapahtuma rikkonut mallia.
    final_remaining = result.final_remaining_route
    if final_remaining:
        reference_remaining = dijkstra.plan(environment.graph, final_remaining[0], goal_node)

        if not isclose(reference_remaining.travel_time, reference.travel_time, rel_tol=0.0, abs_tol=tolerance):
            raise AssertionError(
                f"Dynaaminen referenssivertailu poikkeaa: "
                f"reference={reference.travel_time}, remaining_reference={reference_remaining.travel_time}"
            )

    print("Dynaaminen D* Lite vs Dijkstra -validointi suoritettiin.")


if __name__ == "__main__":
    place_name = "Roihuvuori, Helsinki, Suomi"
    graph = load_clean_map(place_name)

    validate_static_equivalence(graph, sample_count=20, seed=42)