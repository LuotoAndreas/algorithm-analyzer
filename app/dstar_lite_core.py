from __future__ import annotations

import heapq
from math import radians, sin, cos, sqrt, atan2
import networkx as nx

INF = float("inf")


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


class DStarLiteCore:
    """
    D* Lite -algoritmin ydin.
    Säilyttää tilan muutosten välillä.
    """

    def __init__(self, graph: nx.MultiDiGraph, start: int, goal: int):
        self.graph = graph
        self.start = start
        self.goal = goal

        self.km = 0.0
        self.g: dict[int, float] = {}
        self.rhs: dict[int, float] = {}
        self.queue: list[tuple[float, float, int]] = []
        self.entry_finder: dict[int, tuple[float, float]] = {}

        self.initialized = False
        self.max_speed_mps = graph.graph.get("max_speed_mps", 200.0 / 3.6)

    def initialize(self) -> None:
        self.g = {node: INF for node in self.graph.nodes}
        self.rhs = {node: INF for node in self.graph.nodes}
        self.queue = []
        self.entry_finder = {}
        self.km = 0.0

        self.rhs[self.goal] = 0.0
        self._push(self.goal, self.calculate_key(self.goal))
        self.initialized = True

    def set_start(self, start: int) -> None:
        """
        Päivittää nykyisen lähtösolmun D* Lite -logiikan mukaisesti.

        Kun agentti siirtyy, km-arvoa kasvatetaan vanhan ja uuden start-solmun
        heuristisella etäisyydellä.
        """
        if not self.initialized:
            self.start = start
            return

        if start == self.start:
            return

        old_start = self.start
        self.km += self.heuristic(old_start, start)
        self.start = start

    def heuristic(self, node_a: int, node_b: int) -> float:
        """
        Heuristiikka sekunteina.
        """
        distance_m = haversine_distance(self.graph, node_a, node_b)
        return distance_m / self.max_speed_mps

    def edge_cost(self, u: int, v: int) -> float:
        """
        Kaaren kustannus sekunteina käyttäen travel_time-arvoa.
        """
        if not self.graph.has_edge(u, v):
            return INF

        edge_data = self.graph.get_edge_data(u, v)
        if edge_data is None:
            return INF

        travel_times = []
        for _, data in edge_data.items():
            travel_time = data.get("travel_time")
            if travel_time is not None:
                travel_times.append(travel_time)

        if not travel_times:
            return INF

        return min(travel_times)

    def successors(self, node: int) -> list[int]:
        return list(self.graph.successors(node))

    def predecessors(self, node: int) -> list[int]:
        return list(self.graph.predecessors(node))

    def calculate_key(self, node: int) -> tuple[float, float]:
        best = min(self.g[node], self.rhs[node])
        return (
            best + self.heuristic(self.start, node) + self.km,
            best,
        )

    def _push(self, node: int, key: tuple[float, float]) -> None:
        self.entry_finder[node] = key
        heapq.heappush(self.queue, (key[0], key[1], node))

    def _top_key(self) -> tuple[float, float]:
        while self.queue:
            k1, k2, node = self.queue[0]
            current_key = self.entry_finder.get(node)

            if current_key is None or current_key != (k1, k2):
                heapq.heappop(self.queue)
                continue

            return (k1, k2)

        return (INF, INF)

    def _pop(self) -> tuple[tuple[float, float], int] | None:
        while self.queue:
            k1, k2, node = heapq.heappop(self.queue)
            current_key = self.entry_finder.get(node)

            if current_key is None or current_key != (k1, k2):
                continue

            del self.entry_finder[node]
            return ((k1, k2), node)

        return None

    def update_vertex(self, node: int) -> None:
        if node != self.goal:
            succs = self.successors(node)
            if succs:
                self.rhs[node] = min(
                    self.edge_cost(node, succ) + self.g[succ]
                    for succ in succs
                )
            else:
                self.rhs[node] = INF

        if self.g[node] != self.rhs[node]:
            self._push(node, self.calculate_key(node))

    def compute_shortest_path(self) -> None:
        if not self.initialized:
            raise RuntimeError("D* Lite -ydintä ei ole alustettu. Kutsu initialize() ensin.")

        iterations = 0
        max_iterations = 200000

        while (
            self._top_key() < self.calculate_key(self.start)
            or self.rhs[self.start] != self.g[self.start]
        ):
            iterations += 1
            if iterations > max_iterations:
                raise RuntimeError(
                    f"D* Lite compute_shortest_path ylitti iteraatiorajan ({max_iterations}). "
                    f"start={self.start}, goal={self.goal}, queue_size={len(self.queue)}"
                )

            item = self._pop()
            if item is None:
                break

            k_old, u = item
            k_new = self.calculate_key(u)

            if k_old < k_new:
                self._push(u, k_new)
            elif self.g[u] > self.rhs[u]:
                self.g[u] = self.rhs[u]
                for pred in self.predecessors(u):
                    self.update_vertex(pred)
            else:
                self.g[u] = INF
                self.update_vertex(u)
                for pred in self.predecessors(u):
                    self.update_vertex(pred)

    def get_path(self) -> list[int]:
        if not self.initialized:
            raise RuntimeError("D* Lite -ydintä ei ole alustettu. Kutsu initialize() ensin.")

        if self.g[self.start] == INF and self.rhs[self.start] == INF:
            raise nx.NetworkXNoPath("D* Lite ei löytänyt reittiä.")

        path = [self.start]
        current = self.start
        visited = {current}

        while current != self.goal:
            succs = self.successors(current)
            if not succs:
                raise nx.NetworkXNoPath("D* Lite ei löytänyt reittiä.")

            best_succ = None
            best_cost = INF

            for succ in succs:
                cost = self.edge_cost(current, succ) + self.g[succ]
                if cost < best_cost:
                    best_cost = cost
                    best_succ = succ

            if best_succ is None or best_cost == INF:
                raise nx.NetworkXNoPath("D* Lite ei löytänyt reittiä.")

            current = best_succ

            if current in visited:
                raise nx.NetworkXNoPath("D* Lite -reitissä havaittiin silmukka.")

            visited.add(current)
            path.append(current)

        return path

    def get_path_length(self, path: list[int]) -> float:
        """
        Palauttaa reitin kokonaiskustannuksen sekunteina.
        """
        total = 0.0
        for i in range(len(path) - 1):
            total += self.edge_cost(path[i], path[i + 1])
        return total

    def notify_edge_removed(self, u: int, v: int) -> bool:
        """
        Ilmoittaa D* Litelle, että kaari u->v on jo poistettu ympäristön graafista.
        Päivittää vain sisäisen tilan, ei muuta graafia enää itse.
        """
        affected_nodes = {u}
        affected_nodes.update(self.predecessors(u))

        for node in affected_nodes:
            self.update_vertex(node)

        return True

    def notify_edge_cost_changed(self, u: int, v: int) -> bool:
        """
        Ilmoittaa D* Litelle, että kaaren u->v kustannus on jo muuttunut
        ympäristön graafissa. Päivittää vain sisäisen tilan.
        """
        affected_nodes = {u}
        affected_nodes.update(self.predecessors(u))

        for node in affected_nodes:
            self.update_vertex(node)

        return True