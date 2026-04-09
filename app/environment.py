import networkx as nx


class RoadEnvironment:
    """
    Ylläpitää simulaation tieverkkoa ja siihen tehtäviä muutoksia.
    """

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph.copy()

    def copy(self) -> "RoadEnvironment":
        """
        Palauttaa ympäristöstä kopion.
        """
        return RoadEnvironment(self.graph.copy())

    def has_edge(self, from_node: int, to_node: int) -> bool:
        """
        Tarkistaa, onko suunnattu kaari olemassa.
        """
        return self.graph.has_edge(from_node, to_node)

    def remove_edge(self, from_node: int, to_node: int) -> bool:
        """
        Poistaa kaikki kaaret solmujen from_node -> to_node väliltä.

        Returns:
            True, jos vähintään yksi kaari poistettiin, muuten False.
        """
        removed = False

        if self.graph.has_edge(from_node, to_node):
            edge_keys = list(self.graph[from_node][to_node].keys())
            for key in edge_keys:
                self.graph.remove_edge(from_node, to_node, key)
                removed = True

        return removed

    def increase_edge_cost(self, from_node: int, to_node: int, multiplier: float) -> bool:
        """
        Kasvattaa kaikkien kaarien length-arvoa solmujen from_node -> to_node välillä.

        Returns:
            True, jos vähintään yhden kaaren kustannusta muutettiin, muuten False.
        """
        updated = False

        if self.graph.has_edge(from_node, to_node):
            for _, edge_data in self.graph[from_node][to_node].items():
                if "length" in edge_data:
                    edge_data["length"] *= multiplier
                    updated = True

        return updated

    def apply_event(self, event) -> bool:
        """
        Soveltaa tapahtuman ympäristöön.

        Supported change types:
            - remove
            - increase_cost

        Returns:
            True, jos muutos onnistui, muuten False.
        """
        from_node, to_node = event.edge

        if event.change_type == "remove":
            changed = self.remove_edge(from_node, to_node)

        elif event.change_type == "increase_cost":
            if event.cost_multiplier is None:
                raise ValueError("increase_cost-tapahtuma vaatii cost_multiplier-arvon.")
            changed = self.increase_edge_cost(from_node, to_node, event.cost_multiplier)

        else:
            raise ValueError(f"Tuntematon change_type: {event.change_type}")

        if changed:
            event.mark_triggered()

        return changed