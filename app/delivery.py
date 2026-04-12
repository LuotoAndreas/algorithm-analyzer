from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryTask:
    """
    Kuvaa yhtä yksittäistä last mile -toimitustehtävää.

    depot_node:
        Solmu, josta toimitus alkaa.
    customer_node:
        Solmu, johon toimitus päättyy.
    departure_time:
        Lähtöaika sekunteina simulaation alusta.
    service_time_seconds:
        Asiakaskohteessa käytettävä palveluaika.
    planned_arrival_time:
        Alkuperäiseen suunnitelmaan perustuva arvio saapumisesta asiakkaalle.
    deadline_time:
        Toimituksen palvelutasoraja. Jos toteutunut toimitus ylittää tämän,
        palvelutaso katsotaan rikkoutuneeksi.
    """

    depot_node: int
    customer_node: int
    departure_time: float = 0.0
    service_time_seconds: float = 120.0
    planned_arrival_time: float | None = None
    deadline_time: float | None = None

    @property
    def planned_completion_time(self) -> float | None:
        if self.planned_arrival_time is None:
            return None
        return self.planned_arrival_time + self.service_time_seconds
