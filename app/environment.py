import networkx as nx


class RoadEnvironment:
    """
    Ylläpitää simulaation tieverkkoa ja siihen tehtäviä muutoksia.
    """

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph.copy()

    def copy(self) -> "RoadEnvironment":
        return RoadEnvironment(self.graph.copy())

    def has_edge(self, from_node: int, to_node: int) -> bool:
        return self.graph.has_edge(from_node, to_node)

    def remove_edge(self, from_node: int, to_node: int) -> bool:
        removed = False
        if self.graph.has_edge(from_node, to_node):
            edge_keys = list(self.graph[from_node][to_node].keys())
            for key in edge_keys:
                self.graph.remove_edge(from_node, to_node, key)
                removed = True
        return removed

    def increase_edge_cost(self, from_node: int, to_node: int, multiplier: float) -> bool:
        updated = False
        if self.graph.has_edge(from_node, to_node):
            for _, edge_data in self.graph[from_node][to_node].items():
                if "travel_time" in edge_data:
                    edge_data["travel_time"] *= multiplier
                    updated = True
        return updated

    def apply_event(self, event) -> bool:
        """
        Soveltaa tapahtuman ympäristöön.

        Returns:
            True, jos vähintään yksi tapahtuman kohdekaari muuttui.
        """
        changed = False
        target_edges = event.target_edges

        if event.change_type == "remove":
            for from_node, to_node in target_edges:
                changed = self.remove_edge(from_node, to_node) or changed

        elif event.change_type == "increase_cost":
            if event.cost_multiplier is None:
                raise ValueError("increase_cost-tapahtuma vaatii cost_multiplier-arvon.")
            for from_node, to_node in target_edges:
                changed = self.increase_edge_cost(from_node, to_node, event.cost_multiplier) or changed

        else:
            raise ValueError(f"Tuntematon change_type: {event.change_type}")

        if changed:
            event.mark_triggered()

        return changed
