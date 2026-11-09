"""Descriptive network measures and null models (stage 1).

Exact clustering and all-pairs shortest paths are too slow for SWOW in networkx, so both
are estimated on a random node sample (`sample` nodes; fixed `seed` for reproducibility).
Clustering and path lengths are computed on the unweighted, undirected largest connected
component.

Small-worldness compares C and L with degree-preserving random graphs (configuration model,
multi-edges and self-loops removed). `nx.sigma`/`nx.omega` are not used: they rewire edge by
edge and do not finish on graphs of this size.
"""
from __future__ import annotations

import random

import networkx as nx


def largest_component(graph: nx.Graph | nx.DiGraph) -> nx.Graph:
    """Unweighted, undirected largest connected component (a copy)."""
    undirected = graph.to_undirected() if graph.is_directed() else graph
    nodes = max(nx.connected_components(undirected), key=len)
    return nx.Graph(undirected.subgraph(nodes).edges())


def _sample(nodes: list, k: int, seed: int) -> list:
    return random.Random(seed).sample(nodes, min(k, len(nodes)))


def sampled_clustering(graph: nx.Graph, *, sample: int = 500, seed: int = 0) -> float:
    """Mean local clustering coefficient over a node sample."""
    nodes = _sample(sorted(graph.nodes, key=str), sample, seed)
    return sum(nx.clustering(graph, nodes).values()) / len(nodes)


def sampled_path_length(graph: nx.Graph, *, sample: int = 100, seed: int = 0) -> tuple[float, int]:
    """(mean shortest path length, longest path seen) from BFS out of a sample of sources.

    The graph must be connected. The longest path seen is a lower bound on the diameter.
    """
    sources = _sample(sorted(graph.nodes, key=str), sample, seed)
    total, pairs, longest = 0, 0, 0
    for source in sources:
        lengths = nx.single_source_shortest_path_length(graph, source)
        total += sum(lengths.values())
        pairs += len(lengths) - 1
        longest = max(longest, max(lengths.values()))
    return total / pairs, longest


def configuration_null(graph: nx.Graph, seed: int) -> nx.Graph:
    """Degree-preserving random graph: configuration model, simplified to a simple graph."""
    degrees = [d for _, d in graph.degree()]
    multigraph = nx.configuration_model(degrees, seed=seed)
    simple = nx.Graph(multigraph)
    simple.remove_edges_from(nx.selfloop_edges(simple))
    return simple


def small_world(
        graph: nx.Graph,
        *,
        n_null: int = 3,
        clustering_sample: int = 500,
        path_sample: int = 100,
        seed: int = 0,
) -> dict[str, float]:
    """C and L of a connected graph against `n_null` configuration-model graphs.

    sigma = (C / C_null) / (L / L_null); values well above 1 indicate a small world.
    `null_edge_share` is the share of edges that survive the simplification of the null
    graphs; if it is far below 1, the null model does not preserve the degrees well.
    """
    c = sampled_clustering(graph, sample=clustering_sample, seed=seed)
    length, _ = sampled_path_length(graph, sample=path_sample, seed=seed)
    c_null, l_null, edge_share = [], [], []
    for i in range(n_null):
        null = largest_component(configuration_null(graph, seed=seed + 1 + i))
        c_null.append(sampled_clustering(null, sample=clustering_sample, seed=seed))
        l_null.append(sampled_path_length(null, sample=path_sample, seed=seed)[0])
        edge_share.append(null.number_of_edges() / graph.number_of_edges())
    c_rand, l_rand = sum(c_null) / n_null, sum(l_null) / n_null
    return {
        "clustering": c,
        "path_length": length,
        "clustering_null": c_rand,
        "path_length_null": l_rand,
        "sigma": (c / c_rand) / (length / l_rand),
        "null_edge_share": sum(edge_share) / n_null,
    }


def summary(
        graph: nx.Graph | nx.DiGraph,
        *,
        clustering_sample: int = 500,
        path_sample: int = 100,
        seed: int = 0,
) -> dict[str, float | int]:
    """Size, connectivity, assortativity, clustering and path length of a SWOW graph."""
    n, m = graph.number_of_nodes(), graph.number_of_edges()
    undirected = graph.to_undirected() if graph.is_directed() else graph
    components = list(nx.connected_components(undirected))
    out: dict[str, float | int] = {
        "nodes": n,
        "edges": m,
        "density": nx.density(graph),
        "mean_degree": m / n if graph.is_directed() else 2 * m / n,  # out-degree if directed
        "isolates": nx.number_of_isolates(graph),
        "components": len(components),
        "largest_component_share": max(map(len, components)) / n,
    }
    if graph.is_directed():
        strong = max(map(len, nx.strongly_connected_components(graph)))
        out |= {
            "reciprocity": nx.reciprocity(graph),
            "largest_strong_component_share": strong / n,
            "assortativity_out_in": nx.degree_assortativity_coefficient(graph, x="out", y="in"),
            "assortativity_in_in": nx.degree_assortativity_coefficient(graph, x="in", y="in"),
        }
    else:
        out["assortativity"] = nx.degree_assortativity_coefficient(graph)
    core = largest_component(graph)
    out["clustering"] = sampled_clustering(core, sample=clustering_sample, seed=seed)
    out["path_length"], out["longest_path_seen"] = sampled_path_length(core, sample=path_sample, seed=seed)
    return out
