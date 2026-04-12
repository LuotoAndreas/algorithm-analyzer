from dataclasses import dataclass, field
from typing import Literal, Optional, Tuple


ChangeType = Literal["remove", "increase_cost"]


@dataclass
class EdgeEvent:
    """
    Kuvaa dynaamista tapahtumaa, joka voi kohdistua yhteen tieosuuteen
    tai useampaan samaa toimituskäytävää häiritsevään tieosuuteen.

    Attributes:
        event_step: Vanha askelpohjainen laukaisu. Säilytetään siirtymävaiheessa.
        event_time: Uusi aikapohjainen laukaisu sekunteina simulaation alusta.
        edge: Tapahtuman ankkurikaari muodossa (from_node, to_node).
        affected_edges: Kaikki kaaret, joihin muutos kohdistuu. Jos tyhjä,
            käytetään edge-arvoa.
        change_type: Muutoksen tyyppi.
        cost_multiplier: Kustannuksen kerroin, jos change_type == "increase_cost".
        region_center: Mahdollisen alueellisen muodostuksen keskipiste.
        region_radius_m: Mahdollinen sisäinen apumittari häiriöalueelle.
            Tätä ei tarvitse käyttää tulosten päämittarina.
        severity_label: Tapahtuman vakavuusluokka raportointia varten.
        triggered: Onko tapahtuma jo aktivoitu.
    """
    event_step: Optional[int]
    event_time: Optional[float]
    edge: Tuple[int, int]
    change_type: ChangeType
    cost_multiplier: Optional[float] = None
    affected_edges: list[Tuple[int, int]] = field(default_factory=list)
    region_center: Optional[Tuple[float, float]] = None
    region_radius_m: Optional[float] = None
    severity_label: Optional[str] = None
    triggered: bool = False

    @property
    def target_edges(self) -> list[Tuple[int, int]]:
        if self.affected_edges:
            return self.affected_edges
        return [self.edge]

    @property
    def affected_edge_count(self) -> int:
        return len(self.target_edges)

    @property
    def event_scope(self) -> str:
        return "single_edge" if self.affected_edge_count <= 1 else "route_corridor"

    @property
    def event_scope_label(self) -> str:
        labels = {
            "single_edge": "yksittäinen tieosuus",
            "route_corridor": "toimituskäytävän häiriö",
        }
        return labels[self.event_scope]

    @property
    def impact_spread(self) -> str:
        count = self.affected_edge_count
        if count <= 1:
            return "single_edge"
        if count <= 3:
            return "narrow"
        if count <= 6:
            return "medium"
        return "wide"

    @property
    def impact_spread_label(self) -> str:
        labels = {
            "single_edge": "yksi tieosuus",
            "narrow": "kapea häiriökäytävä",
            "medium": "keskilaaja häiriökäytävä",
            "wide": "laaja häiriökäytävä",
        }
        return labels[self.impact_spread]

    def should_trigger(self, current_step: int | None = None, current_time: float | None = None) -> bool:
        if self.triggered:
            return False

        if self.event_time is not None and current_time is not None:
            return current_time >= self.event_time

        if self.event_step is not None and current_step is not None:
            return current_step >= self.event_step

        return False

    def mark_triggered(self) -> None:
        self.triggered = True
