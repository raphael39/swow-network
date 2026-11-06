# Semantic fields in reading

Do readers slow down when a text moves from one semantic field (a community in the
SWOW word-association network) to another, beyond frequency, length and surprisal?

## Layout

```
swow-network/
├── config/
│   └── geco.yaml              pymovements dataset definition for GECO (not in pm's library)
├── data/                      (large files, keep out of git)
│   ├── geco/
│   │   ├── downloads/         raw GECO .xlsx (reading data, materials, subject info)
│   │   └── precomputed_reading_measures/   placed here by pymovements
│   ├── swow/   
│   │   ├── SWOW-NL/           Small World of Words, Dutch
│   │   └── SWOW-EN18/         Small World of Words, English
│   ├── frequency/             SUBTLEX-UK / SUBTLEX-NL
│   ├── interim/               cleaned caches (parquet), regenerable
│   └── processed/             analysis-ready tables
├── src/semfields/             importable project code
│   ├── paths.py               all paths in one place
│   ├── eyetracking/geco.py    stage 0: GECO loading
│   ├── network/               stage 1: build + describe SWOW graphs, null models
│   ├── communities/           stage 2: Louvain, stability, WordNet check
│   ├── text/                  stage 3: tokenise/lemmatise GECO, map to communities, switch variable
│   └── analysis/              stage 4: mixed models, random-partition baseline
├── scripts/                   numbered, runnable pipeline steps (01_load_geco.py, ...)
├── notebooks/                 exploration and figures; import from src/semfields
├── results/{figures,tables}/
└── tests/
```

Each stage writes its output to `data/interim` or `data/processed`, and the next stage
reads it from there.

## Setup

Install the environment with [uv](https://docs.astral.sh/uv/) from the repository root:

```bash
uv sync
```

## Getting the data

`data/` is not in git, so everyone downloads the files once. About 1.7 GB is needed in total.
Keep the folder and file names below, because the code looks for them.

| dataset | how to get it | where it goes |
|---|---|---|
| GECO | automatic: `scripts/01_load_geco.py` downloads it from the [GECO page](https://expsy.ugent.be/downloads/geco/) and checks the checksums | `data/geco/downloads/` |
| SWOW-EN (SWOW-EN18) | manual: the [SWOW research page](https://smallworldofwords.org/en/project/research) | `data/swow/SWOW-EN18/` |
| SWOW-NL | manual: same page | `data/swow/SWOW-NL/` |
| SUBTLEX-UK | manual: [Nottingham search page](https://shiny.psychology.nottingham.ac.uk/lpzwjv/SUBTLEX-UK/) (links to the compressed files) | `data/frequency/` |
| SUBTLEX-NL | manual: [OSF](https://osf.io/3d8cx/wiki) (the version with Zipf values and POS) | `data/frequency/` |

**SWOW-EN.** Unpack the archive so that this file exists:
`data/swow/SWOW-EN18/strength.SWOW-EN.R123.20180827.csv`. The code uses the `strength.*` files.

**SWOW-NL.** The release is raw responses. These files are needed:
`data/swow/SWOW-NL/associationData.csv` and `users.csv`. The strength tables are computed from them
on first use.

**SUBTLEX.** No loader exists yet, so the exact file names are still open.

Check the licence terms before sharing data. SWOW is released under CC BY-NC-ND 3.0, and its
authors ask you to report the dataset name, version and release date you used.

To cite:

- GECO: Cop, Dirix, Drieghe & Duyck (2017), *Behavior Research Methods* 49, 602–615.
- SWOW-EN: De Deyne et al. (2019), *Behavior Research Methods* 51, 987–1006.
- SWOW-NL: De Deyne, Navarro & Storms (2013), *Behavior Research Methods* 45, 480–498.
- SUBTLEX-UK: van Heuven, Mandera, Keuleers & Brysbaert (2014), *QJEP* 67, 1176–1190.
- SUBTLEX-NL: Keuleers, Brysbaert & New (2010), *Behavior Research Methods* 42, 643–650.

## Running

From the repository root:

```bash
.venv/Scripts/python.exe scripts/01_load_geco.py
```

This downloads GECO (~560 MB; files that are already there are checksum-verified and
reused), parses it with pymovements and writes
`data/interim/geco/reading_measures_materials.parquet`.

Then cross-reference GECO's words with the SWOW cues (needs spaCy models, installed via `uv sync`):

```bash
.venv/Scripts/python.exe scripts/02_geco_swow_coverage.py
```

This writes `data/processed/geco_words_swow_{en,nl}.parquet` (one row per word token:
cleaned form, spaCy lemma/POS, `is_content_word`, matched `swow_cue`, `match_type`) and
coverage tables to `results/tables/`. Content words = spaCy NOUN/VERB/ADJ/ADV; proper
nouns are flagged separately. SWOW-NL comes as raw responses (`data/swow/SWOW-NL/associationData.csv`);
its R1/R123 strength tables are computed on first use and cached in `data/interim/swow/`.

In a notebook in `notebooks/`:

```python
import sys; sys.path.insert(0, "../src")
from semfields.eyetracking import geco
rm = geco.load_reading_measures()      # cached parquet after the first run
```

## GECO reading-measure table

One row per participant × word, with all original GECO columns plus:

| column | meaning |
|---|---|
| `participant_id`, `reader_group` | `mono` (English monolinguals), `bi_L1` (bilinguals reading Dutch), `bi_L2` (bilinguals reading English) |
| `language`, `language_rank` | English/Dutch, L1/L2 |
| `word_id`, `word` | GECO word id `part-trial-word`, word as displayed (with punctuation) |
| `ffd`, `gd`, `gopast` | first fixation, gaze duration, go-past time; null if the word was skipped in first pass |
| `trt` | total reading time (null if never fixated) |
| `skip`, `n_fix`, `n_runs`, `regression_out`, `reread` | skipping and regression indicators |
| `SENTENCE_ID`, `CHRON_ID`, `PART_OF_SPEECH`, `is_content_word`, `word_length` | from the GECO materials files |

Cite: Cop, Dirix, Drieghe & Duyck (2017), *Behavior Research Methods* 49, 602–615.
