from dataclasses import dataclass
from enum import Enum
import heapq
from collections import deque


CITIES = {
    "beppu": 0,
    "fukuoka": 1,
    "gero": 2,
    "gifu": 3,
    "gujo": 4,
    "hakodate": 5,
    "himeji": 6,
    "hiroshima": 7,
    "kagoshima": 8,
    "kanazawa": 9,
    "kobe": 10,
    "kumamoto": 11,
    "kusatsu": 12,
    "kyoto": 13,
    "matsuyama": 14,
    "nagoya": 15,
    "naha": 16,
    "niigata": 17,
    "okayama": 18,
    "osaka": 19,
    "sapporo": 20,
    "sendai": 21,
    "takayama": 22,
    "tokyo": 23,
}


class Transportation(Enum):
    PUBLIC = 1  # Bus or Train
    SHINKANSEN = 2
    FLIGHT = 10


@dataclass
class MapEdge:
    from_index: int
    to_index: int
    transportation_type: Transportation


class GraphMap:
    nodes: list[str]
    edges: list[MapEdge]

    def __init__(self):
        self.nodes = [""] * len(CITIES)
        for city_name, index in CITIES.items():
            self.nodes[index] = city_name

        edges = [
            # Public
            ("beppu", "fukuoka", Transportation.PUBLIC),
            ("beppu", "kumamoto", Transportation.PUBLIC),
            ("fukuoka", "kumamoto", Transportation.PUBLIC),
            ("gero", "gifu", Transportation.PUBLIC),
            ("gifu", "gujo", Transportation.PUBLIC),
            ("gifu", "kyoto", Transportation.PUBLIC),
            ("gifu", "nagoya", Transportation.PUBLIC),
            ("gifu", "takayama", Transportation.PUBLIC),
            ("hakodate", "niigata", Transportation.PUBLIC),
            ("hakodate", "sapporo", Transportation.PUBLIC),
            ("hiroshima", "matsuyama", Transportation.PUBLIC),
            ("kanazawa", "niigata", Transportation.PUBLIC),
            ("kumamoto", "kagoshima", Transportation.PUBLIC),
            ("kusatsu", "tokyo", Transportation.PUBLIC),
            ("nagoya", "takayama", Transportation.PUBLIC),
            # Shinkansen
            ("fukuoka", "hiroshima", Transportation.SHINKANSEN),
            ("hakodate", "sendai", Transportation.SHINKANSEN),
            ("himeji", "kobe", Transportation.SHINKANSEN),
            ("himeji", "okayama", Transportation.SHINKANSEN),
            ("hiroshima", "okayama", Transportation.SHINKANSEN),
            ("kanazawa", "tokyo", Transportation.SHINKANSEN),
            ("kobe", "osaka", Transportation.SHINKANSEN),
            ("kyoto", "osaka", Transportation.SHINKANSEN),
            ("kyoto", "nagoya", Transportation.SHINKANSEN),
            ("nagoya", "tokyo", Transportation.SHINKANSEN),
            ("sendai", "tokyo", Transportation.SHINKANSEN),
            ("sendai", "sapporo", Transportation.SHINKANSEN),
            # Flights
            ("fukuoka", "osaka", Transportation.FLIGHT),
            ("fukuoka", "nagoya", Transportation.FLIGHT),
            ("fukuoka", "naha", Transportation.FLIGHT),
            ("fukuoka", "sapporo", Transportation.FLIGHT),
            ("fukuoka", "sendai", Transportation.FLIGHT),
            ("fukuoka", "tokyo", Transportation.FLIGHT),
            ("nagoya", "sapporo", Transportation.FLIGHT),
            ("nagoya", "tokyo", Transportation.FLIGHT),
            ("nagoya", "naha", Transportation.FLIGHT),
            ("naha", "sapporo", Transportation.FLIGHT),
            ("naha", "tokyo", Transportation.FLIGHT),
            ("osaka", "sapporo", Transportation.FLIGHT),
            ("osaka", "tokyo", Transportation.FLIGHT),
            ("sapporo", "tokyo", Transportation.FLIGHT),
        ]

        self.edges = []
        for frm, to, transport in edges:
            self.edges.append(MapEdge(CITIES[frm], CITIES[to], transport))
            self.edges.append(MapEdge(CITIES[to], CITIES[frm], transport))

    def find_cheapest_path(self, start_city: str, end_city: str) -> list[str]:
        """
        Find the cheapest path between two cities using Dijkstra's algorithm.
        The cost is determined by the Transportation enum value (1 for PUBLIC, 2 for SHINKANSEN, 10 for FLIGHT).
        """
        start_city = start_city.lower()
        end_city = end_city.lower()

        # Check if cities exist
        if start_city not in CITIES or end_city not in CITIES:
            return []

        start_index = CITIES[start_city]
        end_index = CITIES[end_city]

        # Initialize distances and previous nodes
        distances = {i: float("inf") for i in range(len(self.nodes))}
        previous = {i: -1 for i in range(len(self.nodes))}
        distances[start_index] = 0

        # Priority queue for Dijkstra's algorithm
        pq = [(0.0, start_index)]
        visited = set()

        while pq:
            _, current_node = heapq.heappop(pq)

            if current_node in visited:
                continue

            visited.add(current_node)

            # If we reached the destination
            if current_node == end_index:
                break

            # Check neighbors
            for edge in self.edges:
                if edge.from_index == current_node:
                    neighbor = edge.to_index
                    weight = edge.transportation_type.value  # Cost of the edge

                    if neighbor not in visited:
                        new_distance = distances[current_node] + weight

                        if new_distance < distances[neighbor]:
                            distances[neighbor] = new_distance
                            previous[neighbor] = current_node
                            heapq.heappush(pq, (new_distance, neighbor))

        # Reconstruct path
        path = []
        current = end_index

        if distances[end_index] == float("inf"):
            return []  # No path found

        while current != -1:
            path.append(self.nodes[current])
            current = previous[current]

        path.reverse()
        return path

    def find_most_convenient_path(self, start_city: str, end_city: str) -> list[str]:
        """
        Find the most convenient path (least number of edges) between two cities using BFS.
        """
        start_city = start_city.lower()
        end_city = end_city.lower()

        # Check if cities exist
        if start_city not in CITIES or end_city not in CITIES:
            return []

        start_index = CITIES[start_city]
        end_index = CITIES[end_city]

        # BFS
        queue = deque([(start_index, [start_index])])
        visited = {start_index}

        while queue:
            current_node, path = queue.popleft()

            if current_node == end_index:
                # Convert indices back to city names
                return [self.nodes[i] for i in path]

            # Check neighbors
            for edge in self.edges:
                if edge.from_index == current_node and edge.to_index not in visited:
                    visited.add(edge.to_index)
                    queue.append((edge.to_index, path + [edge.to_index]))

        return []  # No path found
