"""Build SWOW association graphs from a strength table (stage 1).

Nodes are words, a directed edge cue -> response means that people gave `response` to
`cue`, weighted by association strength (count / N). Two vertex sets are used:

    cues_only=True   only words that were themselves cues (~12k per language). Every node
                     then has both outgoing and incoming edges; this is the graph that
                     community detection (stage 2) runs on.
    cues_only=False  all cues and responses (~130k nodes for SWOW-EN). Response-only words
                     have no outgoing edges.

Self-associations (cue == response) are dropped. For the undirected graph, the weights of
a -> b and b -> a are added.
"""
from __future__ import annotations

import networkx as nx
import polars as pl


def edge_table(strength: pl.DataFrame, *, cues_only: bool = True, min_count: int = 1) -> pl.DataFrame:
    """Directed edges (cue, response, count, strength) of a strength table from `swow.load_strength`.

    `min_count` drops associations that fewer than `min_count` people gave (thinning).
    """
    edges = strength.filter(
        pl.col("response").is_not_null()
        & (pl.col("cue") != pl.col("response"))
        & (pl.col("count") >= min_count)
    )
    if cues_only:
        edges = edges.filter(pl.col("response").is_in(strength["cue"].unique().implode()))
    return edges.select("cue", "response", "count", "strength")


def build_graph(
        strength: pl.DataFrame,
        *,
        directed: bool = True,
        cues_only: bool = True,
        min_count: int = 1,
        weight: str = "strength",
) -> nx.Graph | nx.DiGraph:
    """SWOW association graph with edge attribute `weight` (association strength or raw count).

    With `cues_only`, every cue is a node, even if none of its responses is a cue (it is then
    isolated), so that later stages can rely on one node per cue.
    """
    edges = edge_table(strength, cues_only=cues_only, min_count=min_count)
    if directed:
        graph = nx.DiGraph()
        graph.add_weighted_edges_from(edges.select("cue", "response", weight).iter_rows())
    else:
        undirected = (
            edges.with_columns(
                a=pl.min_horizontal("cue", "response"),
                b=pl.max_horizontal("cue", "response"),
            )
            .group_by("a", "b")
            .agg(pl.col(weight).sum())
        )
        graph = nx.Graph()
        graph.add_weighted_edges_from(undirected.select("a", "b", weight).iter_rows())
    if cues_only:
        graph.add_nodes_from(strength["cue"].unique().to_list())
    graph.graph.update(directed=directed, cues_only=cues_only, min_count=min_count, weight=weight)
    return graph


def degree_table(graph: nx.Graph | nx.DiGraph) -> pl.DataFrame:
    """One row per node: degree and strength (in/out for directed graphs)."""
    nodes = list(graph.nodes)
    if graph.is_directed():
        return pl.DataFrame({
            "node": nodes,
            "in_degree": [graph.in_degree(n) for n in nodes],
            "out_degree": [graph.out_degree(n) for n in nodes],
            "in_strength": [graph.in_degree(n, weight="weight") for n in nodes],
            "out_strength": [graph.out_degree(n, weight="weight") for n in nodes],
        })
    return pl.DataFrame({
        "node": nodes,
        "degree": [graph.degree(n) for n in nodes],
        "strength": [graph.degree(n, weight="weight") for n in nodes],
    })
