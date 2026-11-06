"""Loading pipeline for GECO (Ghent Eye-Tracking Corpus) via pymovements.

Typical use::

    from semfields.eyetracking import geco
    geco.download()                    # once; ~560 MB, skips verified files
    rm = geco.load_reading_measures()  # all readers, cleaned + joined with materials

The first call to `load_reading_measures` parses ~550 MB of Excel and takes a few
minutes; the result is cached as parquet in `data/interim/geco/`.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import polars as pl
import pymovements as pm

from semfields.paths import GECO_DEFINITION, GECO_DIR, INTERIM_DIR

CACHE_DIR = INTERIM_DIR / "geco"

# GECO marks missing values with "."
NULL_TOKEN = "."

STRING_COLUMNS = ["PP_NR", "GROUP", "LANGUAGE_RANK", "LANGUAGE", "WORD_ID", "WORD"]
INT_COLUMNS = ["PART", "TRIAL", "WORD_ID_WITHIN_TRIAL"]

MATERIAL_FILES = {"English": "EnglishMaterial.xlsx", "Dutch": "DutchMaterials.xlsx"}
SUBJECT_FILE = "SubjectInformation.xlsx"


def get_dataset(path: str | Path = GECO_DIR) -> pm.Dataset:
    """Return the pymovements Dataset for GECO, using our own definition in config/geco.yaml."""
    return pm.Dataset(GECO_DEFINITION, path=path)


def download(path: str | Path = GECO_DIR) -> pm.Dataset:
    """Download (or verify already downloaded) GECO files and move them into place."""
    dataset = get_dataset(path)
    dataset.download()
    return dataset


def _load_pymovements(path: str | Path = GECO_DIR) -> list[pl.DataFrame]:
    """Scan and load the precomputed reading measures through pymovements."""
    dataset = get_dataset(path)
    with warnings.catch_warnings():
        # our 'supplementary' resources are intentionally unknown to pymovements' scanner
        warnings.filterwarnings("ignore", message="content type supplementary")
        dataset.load()
    return [rm.frame for rm in dataset.precomputed_reading_measures]


def _cast_reading_measures(df: pl.DataFrame) -> pl.DataFrame:
    """GECO is read as all-string; turn '.' into null and cast measures to numbers."""
    numeric = [c for c in df.columns if c not in STRING_COLUMNS]
    return df.with_columns(
        pl.col(numeric).replace(NULL_TOKEN, None).cast(pl.Float64, strict=False),
    ).with_columns(
        pl.col(INT_COLUMNS).cast(pl.Int64),
    )


def _add_analysis_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Add short, consistently named columns used throughout the analysis.

    First-pass measures (ffd, gd) are only defined when the word was fixated during first
    pass; GECO still reports them when the first fixation came after a regression
    (WORD_SKIP == 1), so we set them to null in that case. `trt` is null for words that
    were never fixated. The raw columns are kept.
    """
    first_pass = pl.col("WORD_SKIP") == 0
    return df.with_columns(
        participant_id=pl.col("PP_NR"),
        reader_group=pl.when(pl.col("GROUP") == "monolingual")
        .then(pl.lit("mono"))
        .otherwise(pl.lit("bi_") + pl.col("LANGUAGE_RANK")),
        language=pl.col("LANGUAGE"),
        language_rank=pl.col("LANGUAGE_RANK"),
        word_id=pl.col("WORD_ID"),
        word=pl.col("WORD"),
        skip=pl.col("WORD_SKIP").cast(pl.Int8),
        n_fix=pl.col("WORD_FIXATION_COUNT").fill_null(0).cast(pl.Int32),
        n_runs=pl.col("WORD_RUN_COUNT").fill_null(0).cast(pl.Int32),
        ffd=pl.when(first_pass).then(pl.col("WORD_FIRST_FIXATION_DURATION")),
        gd=pl.when(first_pass).then(pl.col("WORD_GAZE_DURATION")),
        gopast=pl.when(first_pass).then(pl.col("WORD_GO_PAST_TIME")),
        # non-fixated words are coded "." in most files but 0 in some (esp. the L1 file)
        trt=pl.when(pl.col("WORD_FIXATION_COUNT") > 0).then(pl.col("WORD_TOTAL_READING_TIME")),
    ).with_columns(
        # leaving the word to the left before moving past it -> go-past exceeds gaze duration
        regression_out=(pl.col("gopast") > pl.col("gd")).cast(pl.Int8),
        reread=(pl.col("n_runs") > 1).cast(pl.Int8),
    )


def load_materials(language: str, path: str | Path = GECO_DIR) -> pl.DataFrame:
    """Word-level stimulus table (sentence, POS, content-word flag, length, AOI box).

    `language` is "English" or "Dutch". The Dutch file calls the word id `IA_ID`; it is
    renamed to `WORD_ID` so both languages share one schema.
    """
    file = Path(path) / "downloads" / MATERIAL_FILES[language]
    df = pl.read_excel(file, sheet_name="ALL", infer_schema_length=0)
    df = df.rename({"IA_ID": "WORD_ID"}, strict=False)
    int_cols = [c for c in df.columns if c not in ("WORD_ID", "SENTENCE_ID", "WORD", "PART_OF_SPEECH")]
    return df.with_columns(
        pl.col(int_cols).replace(NULL_TOKEN, None).cast(pl.Int64, strict=False),
        LANGUAGE=pl.lit(language),
    )


def load_subjects(path: str | Path = GECO_DIR) -> pl.DataFrame:
    """Participant information (age, AoA, LexTALE, proficiency, ...)."""
    file = Path(path) / "downloads" / SUBJECT_FILE
    return pl.read_excel(file, sheet_name="DATA")


def load_reading_measures(
        path: str | Path = GECO_DIR,
        *,
        use_cache: bool = True,
        with_materials: bool = True,
) -> pl.DataFrame:
    """All GECO word-level reading measures (monolingual, bilingual L1, bilingual L2).

    One row per participant x word. If `with_materials`, the stimulus information
    (SENTENCE_ID, CHRON_ID, PART_OF_SPEECH, CONTENT_WORD, WORD_LENGTH, ...) is joined in.
    """
    cache = CACHE_DIR / ("reading_measures_materials.parquet" if with_materials else "reading_measures.parquet")
    if use_cache and cache.exists():
        return pl.read_parquet(cache)

    frames = [_cast_reading_measures(df) for df in _load_pymovements(path)]
    df = _add_analysis_columns(pl.concat(frames, how="diagonal_relaxed"))

    if with_materials:
        materials = pl.concat([load_materials(lang, path) for lang in MATERIAL_FILES])
        materials = materials.drop("WORD").rename({"WORD_LENGTH": "word_length"})
        df = df.join(materials, on=["LANGUAGE", "WORD_ID"], how="left", validate="m:1")
        df = df.with_columns(is_content_word=pl.col("CONTENT_WORD") == 1)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.write_parquet(cache)
    return df
