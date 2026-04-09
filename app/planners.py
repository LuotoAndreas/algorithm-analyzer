from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from app.dstar_lite_core import DStarLiteCore
import time
import networkx as nx


@dataclass
class PlanResult:
    """
    Yhden reitinsuunnittelukerran tulos.
    """
    route: list[int]
    length: float
    planning_time: float
    expanded_nodes: int | None = None
    touched_edges: int | None = None


def haversine_distance(graph: nx.MultiDiGraph, node_a: int, node_b: int) -> float:
    """
    Laskee kahden solmun välisen linnuntie-etäisyyden metreinä.
    """
    lon1 = graph.nodes[node_a]["x"]
    lat1 = graph.nodes[node_a]["y"]
    lon2 = graph.nodes[node_b]["x"]
    lat2 = graph.nodes[node_b]["y"]

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    earth_radius_m = 6371000
    return earth_radius_m * c


class BasePlanner(ABC):
    """
    Yhteinen rajapinta kaikille reitinsuunnittelijoille.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def plan(self, graph: nx.MultiDiGraph, start_node: int, goal_node: int) -> PlanResult:
        """
        Laskee reitin start_node -> goal_node.
        """
        raise NotImplementedError

    def replan(self, graph: nx.MultiDiGraph, start_node: int, goal_node: int) -> PlanResult:
        """
        Oletuksena uudelleensuunnittelu tehdään samalla tavalla kuin alkuperäinen suunnittelu.
        D* Lite voi myöhemmin ylikirjoittaa tämän.
        """
        return self.plan(graph, start_node, goal_node)
    
    def notify_agent_moved(self, new_start_node: int) -> None:
        """
        Hook plannerille tilanteisiin, joissa agentti liikkuu yhden askeleen eteenpäin.

        Oletuksena ei tehdä mitään. Stateful-plannerit, kuten D* Lite,
        voivat käyttää tätä sisäisen tilansa päivittämiseen.
        """
        return


class DijkstraPlanner(BasePlanner):
    def __init__(self):
        super().__init__(name="Dijkstra")

    def plan(self, graph: nx.MultiDiGraph, start_node: int, goal_node: int) -> PlanResult:
        start_time = time.perf_counter()

        route = nx.shortest_path(
            graph,
            source=start_node,
            target=goal_node,
            weight="length",
            method="dijkstra",
        )
        length = nx.path_weight(graph, route, weight="length")

        planning_time = time.perf_counter() - start_time

        return PlanResult(
            route=route,
            length=length,
            planning_time=planning_time,
        )


class AStarPlanner(BasePlanner):
    def __init__(self):
        super().__init__(name="A*")

    def plan(self, graph: nx.MultiDiGraph, start_node: int, goal_node: int) -> PlanResult:
        start_time = time.perf_counter()

        route = nx.astar_path(
            graph,
            start_node,
            goal_node,
            heuristic=lambda a, b: haversine_distance(graph, a, b),
            weight="length",
        )
        length = nx.path_weight(graph, route, weight="length")

        planning_time = time.perf_counter() - start_time

        return PlanResult(
            route=route,
            length=length,
            planning_time=planning_time,
        )

class DStarLitePlanner(BasePlanner):
    def __init__(self):
        super().__init__(name="D* Lite")
        self.core: DStarLiteCore | None = None
        self.last_graph_id: int | None = None
        self.last_goal_node: int | None = None

    def plan(self, graph: nx.MultiDiGraph, start_node: int, goal_node: int) -> PlanResult:
        start_time = time.perf_counter()

        self.core = DStarLiteCore(graph, start_node, goal_node)
        self.core.initialize()
        self.core.compute_shortest_path()

        route = self.core.get_path()
        length = self.core.get_path_length(route)

        planning_time = time.perf_counter() - start_time

        self.last_graph_id = id(graph)
        self.last_goal_node = goal_node

        return PlanResult(
            route=route,
            length=length,
            planning_time=planning_time,
        )

    def replan(self, graph: nx.MultiDiGraph, start_node: int, goal_node: int) -> PlanResult:
        if (
            self.core is None
            or self.last_graph_id != id(graph)
            or self.last_goal_node != goal_node
        ):
            return self.plan(graph, start_node, goal_node)

        start_time = time.perf_counter()

        self.core.set_start(start_node)
        self.core.compute_shortest_path()

        route = self.core.get_path()
        length = self.core.get_path_length(route)

        planning_time = time.perf_counter() - start_time

        return PlanResult(
            route=route,
            length=length,
            planning_time=planning_time,
        )

    def notify_agent_moved(self, new_start_node: int) -> None:
        """
        Ilmoittaa D* Litelle, että agentti on siirtynyt uuteen nykyiseen solmuun.
        """
        if self.core is None:
            return

        self.core.set_start(new_start_node)

    def apply_event_to_internal_state(
        self,
        graph: nx.MultiDiGraph,
        change_type: str,
        edge: tuple[int, int],
        cost_multiplier: float | None = None,
    ) -> bool:
        """
        Päivittää D* Liten sisäisen tilan vastaamaan ympäristön muutosta.
        Tätä kutsutaan simulaatiosta heti sen jälkeen, kun environment on muuttunut.
        """
        if self.core is None:
            return False

        if self.last_graph_id != id(graph):
            return False

        u, v = edge

        if change_type == "remove":
            return self.core.remove_edge(u, v)

        if change_type == "increase_cost":
            if cost_multiplier is None:
                raise ValueError("increase_cost vaatii cost_multiplier-arvon.")
            return self.core.increase_edge_cost(u, v, cost_multiplier)

        raise ValueError(f"Tuntematon change_type: {change_type}")

def get_default_planners() -> list[BasePlanner]:
    """
    Palauttaa tällä hetkellä käytössä olevat plannerit.
    """
    return [
        DijkstraPlanner(),
        AStarPlanner(),
        DStarLitePlanner(),
    ]