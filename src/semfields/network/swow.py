"""Loading Small World of Words (SWOW) association strengths.

The `strength.*` tables have one row per cue -> response pair:
cue, response, count (R1 or R123), N (number of valid responses to the cue), strength = count / N.

SWOW-EN ships these tables preprocessed. SWOW-NL comes as raw responses
(`associationData.csv`: one row per participant x cue with asso1-3), so its strength
tables are computed here and cached in `data/interim/swow/`.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from semfields.paths import INTERIM_DIR, SWOW_EN_DIR, SWOW_NL_DIR

SWOW_DIRS = {"English": SWOW_EN_DIR, "Dutch": SWOW_NL_DIR}
DERIVED_DIR = INTERIM_DIR / "swow"

# SWOW-NL codes "no (further) response" / "unknown cue" as "x"
NL_MISSING = {"x", ""}
RESPONSE_SLOTS = {"R1": ["asso1"], "R123": ["asso1", "asso2", "asso3"]}


def strength_file(language: str, responses: str = "R123") -> Path:
    """Path of the strength file for `language` ("English"/"Dutch") and `responses` ("R1"/"R123")."""
    if language == "Dutch":
        path = DERIVED_DIR / f"strength.SWOW-NL.{responses}.csv"
        if not path.exists():
            build_strength_from_raw(SWOW_NL_DIR / "associationData.csv", responses, path)
        return path

    directory = SWOW_DIRS[language]
    matches = sorted(directory.glob(f"strength.SWOW-*.{responses}.*.csv"))
    if not matches:
        raise FileNotFoundError(f"No SWOW {responses} strength file for {language} in {directory}.")
    return matches[-1]


def build_strength_from_raw(raw: Path, responses: str, out: Path) -> pl.DataFrame:
    """Compute a SWOW-EN-style strength table from raw SWOW-NL responses.

    Responses are whitespace-normalised but otherwise kept as given (no spelling
    correction, case kept as for SWOW-EN cues). N counts the valid responses per cue,
    as in SWOW-EN's R123.Strength.
    """
    if not raw.exists():
        raise FileNotFoundError(f"Raw SWOW-NL file not found: {raw}")
    data = pl.read_csv(raw, separator=";", infer_schema_length=0)
    long = (
        data.unpivot(index="cue", on=RESPONSE_SLOTS[responses], value_name="response")
        .with_columns(
            pl.col("cue").str.strip_chars().str.replace_all(r"\s+", " "),
            pl.col("response").str.strip_chars().str.replace_all(r"\s+", " "),
        )
        .filter(pl.col("response").is_not_null() & ~pl.col("response").is_in(list(NL_MISSING)))
    )
    strength = (
        long.group_by("cue", "response").agg(pl.len().alias(responses))
        .with_columns(N=pl.col(responses).sum().over("cue"))
        .with_columns((pl.col(responses) / pl.col("N")).alias(f"{responses}.Strength"))
        .sort(["cue", responses], descending=[False, True])
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    strength.write_csv(out, separator="\t")
    return strength


def load_strength(language: str = "English", responses: str = "R123") -> pl.DataFrame:
    """Cue -> response association strengths, columns: cue, response, count, n, strength."""
    df = pl.read_csv(
        strength_file(language, responses),
        separator="\t",
        quote_char=None,
        schema_overrides={"cue": pl.Utf8, "response": pl.Utf8},
    )
    return df.rename({responses: "count", "N": "n", f"{responses}.Strength": "strength"})


def vocabulary(strength: pl.DataFrame) -> tuple[set[str], set[str]]:
    """(cues, responses) of a strength table. Only cues have outgoing edges in the network."""
    return set(strength["cue"].to_list()), set(strength["response"].drop_nulls().to_list())
