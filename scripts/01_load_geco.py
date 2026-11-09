"""Stage 0: download GECO and build the cleaned word-level reading-measures table.

Run from the repository root:
    uv run scripts/01_load_geco.py
Output: data/interim/geco/reading_measures_materials.parquet
"""
import polars as pl

from semfields.eyetracking import geco


def main() -> None:
    geco.download()
    df = geco.load_reading_measures(use_cache=False)

    print(f"\n{df.height:,} rows, {df['participant_id'].n_unique()} participants")
    print(
        df.group_by("reader_group", "language")
        .agg(
            participants=pl.col("participant_id").n_unique(),
            rows=pl.len(),
            words=pl.col("word_id").n_unique(),
            content_word_share=pl.col("is_content_word").mean(),
            skip_rate=pl.col("skip").mean(),
            mean_gd=pl.col("gd").mean(),
            mean_trt=pl.col("trt").mean(),
        )
        .sort("reader_group")
    )
    unmatched = df.filter(pl.col("SENTENCE_ID").is_null()).height
    print(f"rows without matching material entry: {unmatched:,}")


if __name__ == "__main__":
    main()
