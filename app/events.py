from dataclasses import dataclass
from typing import Literal, Optional, Tuple


ChangeType = Literal["remove", "increase_cost"]


@dataclass
class EdgeEvent:
    """
    Kuvaa yksittäistä dynaamista tapahtumaa, joka kohdistuu yhteen tieosuuteen.

    Attributes:
        event_step: Simulaation askel, jossa tapahtuma aktivoidaan
        edge: Muutettava suunnattu kaari muodossa (from_node, to_node)
        change_type: Muutoksen tyyppi
        cost_multiplier: Kustannuksen kerroin, jos change_type == "increase_cost"
        triggered: Onko tapahtuma jo aktivoitu
    """
    event_step: int
    edge: Tuple[int, int]
    change_type: ChangeType
    cost_multiplier: Optional[float] = None
    triggered: bool = False

    def should_trigger(self, current_step: int) -> bool:
        """
        Tarkistaa, pitäisikö tapahtuma aktivoida tällä simulaation askeleella.
        """
        return (not self.triggered) and current_step >= self.event_step

    def mark_triggered(self) -> None:
        """
        Merkitsee tapahtuman aktivoiduksi.
        """
        self.triggered = True