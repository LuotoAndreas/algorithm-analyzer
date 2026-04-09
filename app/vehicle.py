from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VehicleState:
    """
    Kuvaa ajoneuvon tilaa simulaation aikana.
    """
    start_node: int
    goal_node: int
    current_node: int

    planned_route: list[int] = field(default_factory=list)
    traversed_route: list[int] = field(default_factory=list)

    total_distance_travelled: float = 0.0
    total_travel_time: float = 0.0
    replanning_count: int = 0
    has_arrived: bool = False

    def initialize_route(self, route: list[int]) -> None:
        """
        Asettaa ajoneuvolle alkuperäisen suunnitellun reitin.
        """
        self.planned_route = route.copy()
        self.traversed_route = [self.current_node]
        self.has_arrived = self.current_node == self.goal_node

    def replace_planned_route_from_current(self, new_route: list[int]) -> None:
        """
        Korvaa nykyisestä solmusta eteenpäin suunnitellun reitin uudella reitillä.
        """
        self.planned_route = new_route.copy()
        self.replanning_count += 1
        self.has_arrived = self.current_node == self.goal_node

    def next_node(self) -> int | None:
        """
        Palauttaa seuraavan solmun nykyisessä suunnitellussa reitissä.
        Jos seuraavaa solmua ei ole, palauttaa None.
        """
        if len(self.planned_route) < 2:
            return None

        if self.planned_route[0] != self.current_node:
            return None

        return self.planned_route[1]

    def advance_to_next_node(self, edge_length: float, edge_travel_time: float) -> None:
        """
        Siirtää ajoneuvon seuraavaan solmuun suunnitellulla reitillä.
        """
        next_node = self.next_node()
        if next_node is None:
            raise ValueError("Ajoneuvoa ei voida siirtää eteenpäin: seuraavaa solmua ei ole.")

        self.current_node = next_node
        self.total_distance_travelled += edge_length
        self.total_travel_time += edge_travel_time
        self.traversed_route.append(next_node)

        # Poistetaan reitin ensimmäinen solmu, koska siihen on jo saavuttu
        self.planned_route = self.planned_route[1:]

        if self.current_node == self.goal_node:
            self.has_arrived = True

    def remaining_route(self) -> list[int]:
        """
        Palauttaa nykyisen jäljellä olevan reitin.
        """
        return self.planned_route.copy()