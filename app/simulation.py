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
    total_distance_travelled: float

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
        event: EdgeEvent | None = None,
    ):
        self.environment = environment
        self.planner = planner
        self.start_node = start_node
        self.goal_node = goal_node
        self.event = event

    def _get_edge_length(self, from_node: int, to_node: int) -> float:
        """
        Palauttaa kaaren pienimmän length-kustannuksen.
        """
        edge_data = self.environment.graph.get_edge_data(from_node, to_node)

        if edge_data is None:
            raise ValueError(f"Kaarta {from_node} -> {to_node} ei löytynyt ympäristöstä.")

        lengths = []
        for _, data in edge_data.items():
            length = data.get("length")
            if length is not None:
                lengths.append(length)

        if not lengths:
            raise ValueError(f"Kaaren {from_node} -> {to_node} length-arvo puuttuu.")

        return min(lengths)

    def _future_route_contains_event_edge(self, vehicle: VehicleState) -> bool:
        """
        Tarkistaa, sisältääkö ajoneuvon jäljellä oleva reitti eventin kohdekaaren.
        """
        if self.event is None:
            return False

        route = vehicle.remaining_route()
        from_node, to_node = self.event.edge

        for i in range(len(route) - 1):
            if route[i] == from_node and route[i + 1] == to_node:
                return True

        return False

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
                total_distance_travelled=0.0,
                replanning_count=0,
                event_triggered=False,
                event_successfully_applied=False,
                changed_edge=self.event.edge if self.event else None,
                change_type=self.event.change_type if self.event else None,
                cost_multiplier=self.event.cost_multiplier if self.event else None,
                route_changed_after_event=False,
                arrived=False,
                failed=True,
                failure_reason="Alkuperäistä reittiä ei löytynyt.",
                failure_category="no_initial_path",
            )

        vehicle = VehicleState(
            start_node=self.start_node,
            goal_node=self.goal_node,
            current_node=self.start_node,
        )
        vehicle.initialize_route(initial_plan.route)

        original_route = initial_plan.route.copy()
        original_route_length = initial_plan.length
        original_planning_time = initial_plan.planning_time

        step_index = 0

        while not vehicle.has_arrived:
            if self.event is not None and self.event.should_trigger(step_index):
                event_triggered = True
                self.event.mark_triggered()

                # Sovelletaan eventti vain jos muuttuva kaari on vielä tulevalla reitillä
                if self._future_route_contains_event_edge(vehicle):
                    event_successfully_applied = self.environment.apply_event(self.event)

                    if event_successfully_applied:
                        if hasattr(self.planner, "apply_event_to_internal_state"):
                            self.planner.apply_event_to_internal_state(
                                self.environment.graph,
                                self.event.change_type,
                                self.event.edge,
                                self.event.cost_multiplier,
                            )

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

                        except nx.NetworkXNoPath:
                            failed = True
                            failure_reason = (
                                "Muutoksen jälkeen uutta reittiä ei löytynyt nykyisestä sijainnista kohteeseen."
                            )
                            failure_category = "no_alternative_path"
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
            vehicle.advance_to_next_node(edge_length=edge_length)

            if hasattr(self.planner, "notify_agent_moved"):
                self.planner.notify_agent_moved(vehicle.current_node)

            step_index += 1

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
            total_distance_travelled=vehicle.total_distance_travelled,
            replanning_count=vehicle.replanning_count,
            event_triggered=event_triggered,
            event_successfully_applied=event_successfully_applied,
            changed_edge=self.event.edge if self.event else None,
            change_type=self.event.change_type if self.event else None,
            cost_multiplier=self.event.cost_multiplier if self.event else None,
            route_changed_after_event=route_changed_after_event,
            arrived=vehicle.has_arrived,
            failed=failed,
            failure_reason=failure_reason,
            failure_category=failure_category,
        )