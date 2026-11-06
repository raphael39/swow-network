"""Cross-reference GECO words with the SWOW cue vocabulary (week-1 coverage check).

Run from anywhere (after 01_load_geco.py):
    python scripts/02_geco_swow_coverage.py
Outputs:
    data/processed/geco_words_swow_{en,nl}.parquet   one row per word token, with match
    results/tables/geco_swow_coverage.csv            coverage overall and per POS
    results/tables/geco_swow_unmatched_{en,nl}.csv   unmatched content words by frequency
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import polars as pl  # noqa: E402

from semfields.eyetracking import geco  # noqa: E402
from semfields.network import swow  # noqa: E402
from semfields.paths import PROCESSED_DIR, TABLES_DIR  # noqa: E402
from semfields.text import geco_words, swow_match  # noqa: E402

LANG_CODES = {"English": "en", "Dutch": "nl"}


def main() -> None:
    rm = geco.load_reading_measures()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    summaries = []
    for language, code in LANG_CODES.items():
        try:
            strength = swow.load_strength(language)
        except FileNotFoundError as e:
            print(f"\n[{language}] skipped: {e}")
            continue
        cues, responses = swow.vocabulary(strength)
        words = swow_match.match_words(geco_words.build_word_table(rm, language), cues, responses)
        words.write_parquet(PROCESSED_DIR / f"geco_words_swow_{code}.parquet")

        content = words.filter(pl.col("is_content_word") & (pl.col("match_type") != "punctuation"))
        print(f"\n[{language}] {words.height:,} word tokens, {content.height:,} content-word tokens, "
              f"{len(cues):,} SWOW cues")
        print(content["match_type"].value_counts(sort=True))

        overall = swow_match.coverage_summary(words).with_columns(spacy_pos=pl.lit("CONTENT"))
        per_pos = swow_match.coverage_summary(words, by=["spacy_pos"])
        propn = swow_match.coverage_summary(words, by=["spacy_pos"], subset="is_proper_noun")
        summary = pl.concat([overall, per_pos, propn], how="diagonal")
        with pl.Config(tbl_rows=-1):
            print(summary)
        summaries.append(summary)

        unmatched = (
            content.filter(~pl.col("in_swow"))
            .group_by(pl.col("form").str.to_lowercase().alias("form"))
            .agg(tokens=pl.len(), lemma=pl.col("lemma").mode().first(),
                 spacy_pos=pl.col("spacy_pos").mode().first(), match_type=pl.col("match_type").first())
            .sort("tokens", descending=True)
        )
        unmatched.write_csv(TABLES_DIR / f"geco_swow_unmatched_{code}.csv")
        print("most frequent unmatched content words:")
        with pl.Config(tbl_rows=-1):
            print(unmatched.head(25))

    if summaries:
        pl.concat(summaries).write_csv(TABLES_DIR / "geco_swow_coverage.csv")


if __name__ == "__main__":
    main()
