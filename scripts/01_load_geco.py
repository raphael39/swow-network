"""Stage 0: download GECO and build the cleaned word-level reading-measures table.

Run from anywhere:
    python scripts/01_load_geco.py
Output: data/interim/geco/reading_measures_materials.parquet
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import polars as pl  # noqa: E402

from semfields.eyetracking import geco  # noqa: E402


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
