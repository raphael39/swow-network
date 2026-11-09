"""Tests for stage 1 (semfields.network.graph / describe) on small hand-made graphs."""
import networkx as nx
import polars as pl
import pytest

from semfields.network import describe, graph


@pytest.fixture
def strength() -> pl.DataFrame:
    # cues a-d; "x" is only a response; "b -> b" is a self-association
    return pl.DataFrame({
        "cue": ["a", "a", "b", "b", "c", "c", "d", "e"],
        "response": ["b", "x", "a", "b", "a", "d", "c", "x"],
        "count": [3, 1, 2, 5, 1, 4, 2, 2],
        "strength": [0.75, 0.25, 0.4, 0.6, 0.2, 0.8, 1.0, 1.0],
    })


def test_cue_graph_drops_self_loops_and_response_only_words(strength):
    edges = set(graph.build_graph(strength).edges())
    assert edges == {("a", "b"), ("b", "a"), ("c", "a"), ("c", "d"), ("d", "c")}


def test_full_graph_keeps_response_only_words(strength):
    g = graph.build_graph(strength, cues_only=False)
    assert g.has_edge("a", "x") and g.out_degree("x") == 0


def test_cue_without_cue_responses_stays_as_isolated_node(strength):
    g = graph.build_graph(strength)
    assert "e" in g and g.degree("e") == 0


def test_undirected_weight_adds_both_directions(strength):
    g = graph.build_graph(strength, directed=False)
    assert g["a"]["b"]["weight"] == pytest.approx(0.75 + 0.4)
    assert g["c"]["d"]["weight"] == pytest.approx(0.8 + 1.0)


def test_min_count_thins_weak_associations(strength):
    g = graph.build_graph(strength, min_count=2)
    assert not g.has_edge("c", "a") and g.has_edge("b", "a")


def test_sampled_path_length_is_exact_when_all_sources_are_used():
    # path a-b-c-d: distances 1,2,3,1,2,1 in both directions -> 20 / 12
    mean, longest = describe.sampled_path_length(nx.path_graph(4), sample=10)
    assert mean == pytest.approx(20 / 12)
    assert longest == 3


def test_small_world_separates_lattice_from_random_graph():
    lattice = nx.connected_watts_strogatz_graph(1000, 10, 0.05, seed=1)
    random_graph = nx.gnm_random_graph(1000, lattice.number_of_edges(), seed=1)
    kwargs = dict(n_null=2, clustering_sample=300, path_sample=50, seed=0)
    assert describe.small_world(lattice, **kwargs)["sigma"] > 3
    assert describe.small_world(describe.largest_component(random_graph), **kwargs)["sigma"] < 1.5
