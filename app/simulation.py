from __future__ import annotations

from dataclasses import dataclass
import networkx as nx

from app.environment import RoadEnvironment
from app.events import EdgeEvent
from app.planners import BasePlanner, PlanResult
from app.vehicle import VehicleState


@dataclass
class SimulationResult:
    """
    Yhden simulaatioajon tulos yhdelle algoritmille.
    """
    algorithm_name: str

    start_node: int
    goal_node: int

    original_route: list[int]
    final_traversed_route: list[int]
    final_remaining_route: list[int]

    original_planning_time: float
    replanning_time_total: float
    total_planning_time: float

    original_route_length: float
    original_route_travel_time: float
    original_route_travel_time_with_events: float | None
    total_distance_travelled: float
    total_travel_time: float

    replanning_count: int
    event_triggered: bool
    event_successfully_applied: bool

    changed_edge: tuple[int, int] | None
    change_type: str | None
    cost_multiplier: float | None

    route_changed_after_event: bool
    arrived: bool
    failed: bool
    failure_reason: str | None
    failure_category: str | None
    failure_node: int | None

    event_log: list[dict]


class DynamicRouteSimulation:
    """
    Suorittaa yhden dynaamisen reitityssimulaation yhdelle plannerille.
    """

    def __init__(
        self,
        environment: RoadEnvironment,
        planner: BasePlanner,
        start_node: int,
        goal_node: int,
        events: list[EdgeEvent] | None = None,
    ):
        self.environment = environment
        self.planner = planner
        self.start_node = start_node
        self.goal_node = goal_node
        self.events = events or []

    def _get_best_edge_data(self, from_node: int, to_node: int) -> dict:
        """
        Valitsee kaaren samalla logiikalla kuin reitinhaku:
        pienin travel_time voittaa. Sekä length että travel_time
        luetaan samasta fyysisestä kaaresta.
        """
        edge_data = self.environment.graph.get_edge_data(from_node, to_node)

        if edge_data is None:
            raise ValueError(f"Kaarta {from_node} -> {to_node} ei löytynyt ympäristöstä.")

        best_data = None
        best_time = float("inf")

        for _, data in edge_data.items():
            travel_time = data.get("travel_time")
            if travel_time is None:
                continue

            if travel_time < best_time:
                best_time = travel_time
                best_data = data

        if best_data is None:
            raise ValueError(f"Kaaren {from_node} -> {to_node} travel_time-arvo puuttuu.")

        return best_data

    def _get_edge_length(self, from_node: int, to_node: int) -> float:
        """
        Palauttaa valitun kaaren length-kustannuksen.
        """
        best_data = self._get_best_edge_data(from_node, to_node)
        length = best_data.get("length")

        if length is None:
            raise ValueError(f"Kaaren {from_node} -> {to_node} length-arvo puuttuu.")

        return float(length)

    def _get_edge_travel_time(self, from_node: int, to_node: int) -> float:
        """
        Palauttaa valitun kaaren travel_time-kustannuksen sekunteina.
        """
        best_data = self._get_best_edge_data(from_node, to_node)
        travel_time = best_data.get("travel_time")

        if travel_time is None:
            raise ValueError(f"Kaaren {from_node} -> {to_node} travel_time-arvo puuttuu.")

        return float(travel_time)

    def _future_route_contains_event_edge(self, vehicle: VehicleState, event: EdgeEvent) -> bool:
        """
        Tarkistaa, sisältääkö ajoneuvon jäljellä oleva reitti eventin kohdekaaren.
        """
        route = vehicle.remaining_route()
        from_node, to_node = event.edge

        for i in range(len(route) - 1):
            if route[i] == from_node and route[i + 1] == to_node:
                return True

        return False

    def _calculate_route_length(self, route: list[int]) -> float:
        """
        Laskee annetun reitin kokonaispituuden metreinä.
        """
        total_length = 0.0

        for i in range(len(route) - 1):
            total_length += self._get_edge_length(route[i], route[i + 1])

        return total_length

    def _calculate_route_travel_time_on_graph(self, route: list[int], graph) -> float | None:
        """
        Laskee annetun reitin kokonaisajan annetussa graafissa.

        Palauttaa None, jos jokin reitin kaari puuttuu graafista
        tai joltakin kaarelta puuttuu travel_time.
        """
        total_time = 0.0

        for i in range(len(route) - 1):
            u = route[i]
            v = route[i + 1]

            edge_data = graph.get_edge_data(u, v)
            if edge_data is None:
                return None

            best_data = None
            best_time = float("inf")

            for _, data in edge_data.items():
                travel_time = data.get("travel_time")
                if travel_time is None:
                    continue

                if travel_time < best_time:
                    best_time = travel_time
                    best_data = data

            if best_data is None:
                return None

            total_time += float(best_data["travel_time"])

        return total_time

    def _simulate_original_route_with_events(self, original_route: list[int]) -> float | None:
        """
        Simuloi alkuperäisen reitin läpikulun ilman uudelleenreititystä,
        mutta huomioiden tapahtumat ajon aikana.

        Palauttaa:
        - kokonaisajan sekunteina
        - None jos reitti katkeaa (remove)
        """
        total_time = 0.0
        step_index = 0

        temp_graph = self.environment.graph.copy()

        applied_event_indices: set[int] = set()

        for i in range(len(original_route) - 1):
            current_time = total_time
            u = original_route[i]
            v = original_route[i + 1]

            for event_index, event in enumerate(self.events):
                if event_index in applied_event_indices:
                    continue

                should_apply = False

                if event.event_time is not None:
                    should_apply = current_time >= event.event_time
                elif event.event_step is not None:
                    should_apply = step_index >= event.event_step

                if not should_apply:
                    continue

                if event.change_type == "remove":
                    if temp_graph.has_edge(*event.edge):
                        edge_keys = list(temp_graph[event.edge[0]][event.edge[1]].keys())
                        for key in edge_keys:
                            temp_graph.remove_edge(event.edge[0], event.edge[1], key)

                elif event.change_type == "increase_cost":
                    if temp_graph.has_edge(*event.edge):
                        for _, data in temp_graph[event.edge[0]][event.edge[1]].items():
                            if "travel_time" in data and event.cost_multiplier is not None:
                                data["travel_time"] *= event.cost_multiplier

                applied_event_indices.add(event_index)

            if not temp_graph.has_edge(u, v):
                return None

            edge_data = temp_graph.get_edge_data(u, v)
            if edge_data is None:
                return None

            best_data = None
            best_time = float("inf")

            for _, data in edge_data.items():
                travel_time = data.get("travel_time")
                if travel_time is None:
                    continue

                if travel_time < best_time:
                    best_time = travel_time
                    best_data = data

            if best_data is None:
                return None

            total_time += float(best_data["travel_time"])
            step_index += 1

        return total_time

    def run(self) -> SimulationResult:
        """
        Suorittaa koko simulaation yhdelle algoritmille.
        """
        event_triggered = False
        event_successfully_applied = False
        replanning_time_total = 0.0
        failed = False
        failure_reason = None
        failure_category = None
        route_changed_after_event = False
        original_route_travel_time_with_events = None
        event_log: list[dict] = []

        first_event = self.events[0] if self.events else None
        last_triggered_event: EdgeEvent | None = None

        try:
            initial_plan: PlanResult = self.planner.plan(
                self.environment.graph,
                self.start_node,
                self.goal_node,
            )
        except nx.NetworkXNoPath:
            return SimulationResult(
                algorithm_name=self.planner.name,
                start_node=self.start_node,
                goal_node=self.goal_node,
                original_route=[],
                final_traversed_route=[],
                final_remaining_route=[],
                original_planning_time=0.0,
                replanning_time_total=0.0,
                total_planning_time=0.0,
                original_route_length=0.0,
                original_route_travel_time=0.0,
                original_route_travel_time_with_events=None,
                total_distance_travelled=0.0,
                total_travel_time=0.0,
                replanning_count=0,
                event_triggered=False,
                event_successfully_applied=False,
                changed_edge=first_event.edge if first_event else None,
                change_type=first_event.change_type if first_event else None,
                cost_multiplier=first_event.cost_multiplier if first_event else None,
                route_changed_after_event=False,
                arrived=False,
                failed=True,
                failure_reason="Alkuperäistä reittiä ei löytynyt.",
                failure_category="no_initial_path",
                failure_node=None,
                event_log=[],
            )

        vehicle = VehicleState(
            start_node=self.start_node,
            goal_node=self.goal_node,
            current_node=self.start_node,
        )
        vehicle.initialize_route(initial_plan.route)

        original_route = initial_plan.route.copy()
        original_route_length = self._calculate_route_length(original_route)
        original_route_travel_time = initial_plan.travel_time
        original_route_travel_time_with_events = self._simulate_original_route_with_events(original_route)
        original_planning_time = initial_plan.planning_time

        step_index = 0

        while not vehicle.has_arrived:
            current_time = vehicle.total_travel_time

            for event in self.events:
                if event.should_trigger(current_step=step_index, current_time=current_time):
                    event_triggered = True
                    last_triggered_event = event

                    affects_future_route = self._future_route_contains_event_edge(vehicle, event)
                    applied = self.environment.apply_event(event)

                    event_record = {
                        "edge": event.edge,
                        "trigger_step": step_index,
                        "trigger_time": round(current_time, 6),
                        "current_node": vehicle.current_node,
                        "applied_to_graph": applied,
                        "affected_future_route": affects_future_route,
                        "replan_attempted": False,
                        "replan_success": None,
                    }

                    if applied:
                        event_successfully_applied = True

                        if hasattr(self.planner, "apply_event_to_internal_state"):
                            self.planner.apply_event_to_internal_state(
                                self.environment.graph,
                                event.change_type,
                                event.edge,
                                event.cost_multiplier,
                            )

                        if affects_future_route:
                            event_record["replan_attempted"] = True

                            try:
                                old_remaining_route = vehicle.remaining_route()

                                replan_result = self.planner.replan(
                                    self.environment.graph,
                                    vehicle.current_node,
                                    self.goal_node,
                                )

                                if replan_result.route != old_remaining_route:
                                    route_changed_after_event = True

                                vehicle.replace_planned_route_from_current(replan_result.route)
                                replanning_time_total += replan_result.planning_time
                                event_record["replan_success"] = True

                            except nx.NetworkXNoPath:
                                failed = True
                                failure_reason = (
                                    "Muutoksen jälkeen uutta reittiä ei löytynyt nykyisestä sijainnista kohteeseen."
                                )
                                failure_category = "no_alternative_path"
                                event_record["replan_success"] = False
                                event_log.append(event_record)
                                break

                    event_log.append(event_record)

            if failed:
                break

            next_node = vehicle.next_node()
            if next_node is None:
                failed = True
                failure_reason = "Ajoneuvolla ei ollut seuraavaa solmua ennen kohteen saavuttamista."
                failure_category = "no_next_node"
                break

            if not self.environment.graph.has_edge(vehicle.current_node, next_node):
                failed = True
                failure_reason = (
                    f"Ajoneuvon seuraava kaari {vehicle.current_node} -> {next_node} ei ole enää käytettävissä."
                )
                failure_category = "edge_unavailable"
                break

            edge_length = self._get_edge_length(vehicle.current_node, next_node)
            edge_travel_time = self._get_edge_travel_time(vehicle.current_node, next_node)
            vehicle.advance_to_next_node(
                edge_length=edge_length,
                edge_travel_time=edge_travel_time,
            )

            if hasattr(self.planner, "notify_agent_moved"):
                self.planner.notify_agent_moved(vehicle.current_node)

            step_index += 1

        result_event = last_triggered_event if last_triggered_event is not None else first_event
        failure_node = vehicle.current_node if failed else None

        return SimulationResult(
            algorithm_name=self.planner.name,
            start_node=self.start_node,
            goal_node=self.goal_node,
            original_route=original_route,
            final_traversed_route=vehicle.traversed_route.copy(),
            final_remaining_route=vehicle.remaining_route(),
            original_planning_time=original_planning_time,
            replanning_time_total=replanning_time_total,
            total_planning_time=original_planning_time + replanning_time_total,
            original_route_length=original_route_length,
            original_route_travel_time=original_route_travel_time,
            original_route_travel_time_with_events=original_route_travel_time_with_events,
            total_distance_travelled=vehicle.total_distance_travelled,
            total_travel_time=vehicle.total_travel_time,
            replanning_count=vehicle.replanning_count,
            event_triggered=event_triggered,
            event_successfully_applied=event_successfully_applied,
            changed_edge=result_event.edge if result_event else None,
            change_type=result_event.change_type if result_event else None,
            cost_multiplier=result_event.cost_multiplier if result_event else None,
            route_changed_after_event=route_changed_after_event,
            arrived=vehicle.has_arrived,
            failed=failed,
            failure_reason=failure_reason,
            failure_category=failure_category,
            failure_node=failure_node,
            event_log=event_log,
        )