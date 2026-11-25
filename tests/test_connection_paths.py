import pytest

from socialchain.social import NetworkMap, Profile


@pytest.fixture
def network():
    graph = NetworkMap()
    for did in "ABCDEF":
        graph.add_profile(Profile(did, did))
    for start, end in ["AC", "CD", "AB", "BD", "DE"]:
        graph.add_connection(start, end)
    return graph


def test_excluding_an_intermediary_compares_routes_without_changing_network(network):
    original = network.visualize()
    result = network.connection_path("A", "E", "B")
    assert result["baseline"] == {"path": ["A", "B", "D", "E"], "hops": 3, "reachable_profiles": 4}
    assert result["scenario"] == {"path": ["A", "C", "D", "E"], "hops": 3, "reachable_profiles": 3}
    assert network.visualize() == original


def test_bridge_exclusion_and_disconnected_target(network):
    assert network.connection_path("A", "E", "D")["scenario"] == {
        "path": [], "hops": None, "reachable_profiles": 2,
    }
    assert network.connection_path("F", "B")["baseline"] == {
        "path": [], "hops": None, "reachable_profiles": 0,
    }


def test_zero_hops_and_reverse_traversal(network):
    assert network.connection_path("F", "F")["baseline"] == {
        "path": ["F"], "hops": 0, "reachable_profiles": 0,
    }
    assert network.connection_path("E", "A")["baseline"]["path"] == ["E", "D", "B", "A"]


def test_detour_cost_and_refresh(network):
    network.add_connection("A", "F")
    network.add_connection("F", "E")
    result = network.connection_path("A", "E", "F")
    assert result["baseline"]["hops"] == 2
    assert result["scenario"]["hops"] == 3
    network.remove_profile("F")
    refreshed = network.connection_path("A", "E")
    assert refreshed["baseline"]["hops"] == 3
    assert refreshed["scenario"] is None


def test_path_api_uses_existing_profile_connections(client, app_state, network):
    app_state.network_map = network
    response = client.get("/api/social/paths?source=A&target=E&avoid=D")
    assert response.status_code == 200
    assert response.json == network.connection_path("A", "E", "D")


@pytest.mark.parametrize(("query", "status"), [
    ("source=A", 400), ("source=A&target=missing", 404),
    ("source=A&target=B&avoid=missing", 404), ("source=A&target=B&avoid=A", 400),
    ("source=A&target=B&avoid=B", 400),
])
def test_invalid_path_requests(client, app_state, network, query, status):
    app_state.network_map = network
    response = client.get("/api/social/paths?" + query)
    assert response.status_code == status
    assert response.json["error"]
