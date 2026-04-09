import osmnx as ox
import networkx as nx


def load_map(place_name: str, network_type: str = "drive", simplify: bool = True, retain_all: bool = False):
    """
    Lataa tieverkon OpenStreetMapista ja palauttaa sen graafina.

    Args:
        place_name: Alueen nimi, esimerkiksi "Helsinki, Suomi"
        network_type: Verkkotyyppi, esimerkiksi "drive"
        simplify: Yhdistetäänkö yksinkertaiset solmuketjut automaattisesti
        retain_all: Säilytetäänkö kaikki komponentit vai vain relevantit osat

    Returns:
        NetworkX MultiDiGraph
    """
    graph = ox.graph_from_place(
        place_name,
        network_type=network_type,
        simplify=simplify,
        retain_all=retain_all,
    )

    return graph


def get_largest_strongly_connected_component(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Palauttaa graafin suurimman vahvasti yhtenäisen komponentin.
    Tämä vähentää tilanteita, joissa reittiä ei löydy suunnattavuuden vuoksi.

    Args:
        graph: OSMnx:n palauttama suunnattu graafi

    Returns:
        Suurimman vahvasti yhtenäisen komponentin aligraafi kopiona
    """
    largest_component_nodes = max(nx.strongly_connected_components(graph), key=len)
    subgraph = graph.subgraph(largest_component_nodes).copy()
    return subgraph


def load_clean_map(place_name: str, network_type: str = "drive", simplify: bool = True) -> nx.MultiDiGraph:
    """
    Lataa kartan ja rajaa sen suurimpaan vahvasti yhtenäiseen komponenttiin.

    Args:
        place_name: Alueen nimi
        network_type: Verkkotyyppi
        simplify: Yksinkertaistetaanko verkko

    Returns:
        Siistitty tieverkko
    """
    graph = load_map(
        place_name=place_name,
        network_type=network_type,
        simplify=simplify,
        retain_all=True,
    )

    clean_graph = get_largest_strongly_connected_component(graph)
    return clean_graph