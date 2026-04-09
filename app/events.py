from dataclasses import dataclass
from typing import Literal, Optional, Tuple


ChangeType = Literal["remove", "increase_cost"]


@dataclass
class EdgeEvent:
    """
    Kuvaa yksittäistä dynaamista tapahtumaa, joka kohdistuu yhteen tieosuuteen.

    Attributes:
        event_step: Vanha askelpohjainen laukaisu. Säilytetään siirtymävaiheessa.
        event_time: Uusi aikapohjainen laukaisu sekunteina simulaation alusta.
        edge: Muutettava suunnattu kaari muodossa (from_node, to_node)
        change_type: Muutoksen tyyppi
        cost_multiplier: Kustannuksen kerroin, jos change_type == "increase_cost"
        triggered: Onko tapahtuma jo aktivoitu
    """
    event_step: Optional[int]
    event_time: Optional[float]
    edge: Tuple[int, int]
    change_type: ChangeType
    cost_multiplier: Optional[float] = None
    triggered: bool = False

    def should_trigger(self, current_step: int | None = None, current_time: float | None = None) -> bool:
        """
        Tarkistaa, pitäisikö tapahtuma aktivoida tällä simulaation hetkellä.

        Käyttää ensisijaisesti event_time-arvoa, jos se on asetettu.
        Muuten käyttää event_step-arvoa siirtymävaiheen yhteensopivuuden vuoksi.
        """
        if self.triggered:
            return False

        if self.event_time is not None and current_time is not None:
            return current_time >= self.event_time

        if self.event_step is not None and current_step is not None:
            return current_step >= self.event_step

        return False

    def mark_triggered(self) -> None:
        """
        Merkitsee tapahtuman aktivoiduksi.
        """
        self.triggered = True