"""Look GECO words up in the SWOW vocabulary.

Each word is matched against SWOW cues in this order, and the first hit wins:

    form        exact cleaned form            ("England", "ran")
    form_lower  lowercased form               ("The" -> "the")
    lemma       spaCy lemma                    ("subsided" -> "subside")
    lemma_lower lowercased lemma
    case_fold   case-insensitive match on any of the above ("christmas" -> "Christmas")
    lemma_alt   another lemma candidate (second spaCy model, Dutch weak-verb rules:
                "mompelde" -> "mompelen"), if the word table has `lemma_candidates`

Words that are not a cue but do occur as a SWOW response get `match_type = "response_only"`.
They are nodes in the network, but only with incoming edges.
"""
from __future__ import annotations

import polars as pl

MATCH_ORDER = ["form", "form_lower", "lemma", "lemma_lower"]


def match_words(words: pl.DataFrame, cues: set[str], responses: set[str]) -> pl.DataFrame:
    """Add `swow_cue` (matched cue or null) and `match_type` to a word table from geco_words."""
    folded = {}
    for cue in sorted(cues):  # sorted: deterministic choice if two cues differ only in case
        folded.setdefault(cue.lower(), cue)

    def lookup(form: str, lemma: str, alternatives: list[str]) -> tuple[str | None, str]:
        if not form:
            return None, "punctuation"
        candidates = {"form": form, "form_lower": form.lower(), "lemma": lemma, "lemma_lower": lemma.lower()}
        for kind in MATCH_ORDER:
            if candidates[kind] in cues:
                return candidates[kind], kind
        for kind in MATCH_ORDER:
            if candidates[kind].lower() in folded:
                return folded[candidates[kind].lower()], "case_fold"
        for alternative in alternatives:
            if alternative.lower() in folded:
                return folded[alternative.lower()], "lemma_alt"
        if any(c in responses for c in [*candidates.values(), *alternatives]):
            return None, "response_only"
        return None, "none"

    alternatives = (words["lemma_candidates"].to_list() if "lemma_candidates" in words.columns
                    else [[] for _ in range(words.height)])
    matched = [lookup(f, l, a) for f, l, a in zip(words["form"].to_list(), words["lemma"].to_list(), alternatives)]
    return words.with_columns(
        swow_cue=pl.Series([m[0] for m in matched], dtype=pl.Utf8),
        match_type=pl.Series([m[1] for m in matched], dtype=pl.Utf8),
    ).with_columns(in_swow=pl.col("swow_cue").is_not_null())


def coverage_summary(
        words: pl.DataFrame,
        by: list[str] | None = None,
        subset: str = "is_content_word",
) -> pl.DataFrame:
    """Token and type coverage of the words flagged by `subset` (share that are SWOW cues)."""
    content = words.filter(pl.col(subset) & (pl.col("match_type") != "punctuation"))
    by = by or []
    return (
        content.group_by(["language", *by])
        .agg(
            tokens=pl.len(),
            token_coverage=pl.col("in_swow").mean(),
            types=pl.col("form").str.to_lowercase().n_unique(),
            type_coverage=pl.col("form").str.to_lowercase().filter(pl.col("in_swow")).n_unique()
            / pl.col("form").str.to_lowercase().n_unique(),
            response_only_share=(pl.col("match_type") == "response_only").mean(),
        )
        .sort(["language", *by])
    )
