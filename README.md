# Dynaamisen last mile -reitityksen analyysi

Projekti vertailee Dijkstra-, A*- ja D* Lite -algoritmeja dynaamisessa tieverkossa last mile -toimitusten näkökulmasta.

Nykyinen painopiste on erityisesti **increase_cost**-skenaarioissa, joissa tieverkkoon syntyy ruuhkan, hidastumisen tai paikallisen kuormituksen kaltaisia muutoksia. **remove**-skenaario säilyy mukana vertailua varten, mutta sitä kannattaa käyttää täydentävänä häiriötyyppinä eikä pääfokuksena.

## Käynnistys

```bash
pip install -r requirements.txt
python -m webapp.app
```

## Suositus gradukäyttöön

- Häiriötyyppi: `increase_cost`
- Kustannuskerroin: `3.0`
- Häiriöiden määrä: `5`
- Häiriöalueen muodostustapa: `traffic_hotspot`
- Palveluaika asiakkaalla: `120 s`
- Palvelutason aikakerroin: `1.15`

Tämä asetusjoukko tuottaa simulaatioita, jotka kuvaavat paremmin ruuhkaa, viivettä ja toimituspalvelutason heikkenemistä kuin pelkät tiekatkokset.
