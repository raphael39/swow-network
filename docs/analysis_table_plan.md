# Plan: analysis table (participant x content-word token)

Goal: one table per language with every content-word token of the GECO novel that occurs in
SWOW (as cue **or** response), each participant's first fixation duration on it, and token-level
surprisal and frequency. No aggregation over word types: every row is one occurrence in its
sentence, so word order (needed for the stay/switch variable) is preserved.

Output: `data/processed/analysis_en.parquet`, built by `scripts/04_build_analysis_table.py`
(English only for now).

## Columns

| group | columns |
|---|---|
| reader | `participant_id`, `reader_group` (mono / bi_L1 / bi_L2), `language` |
| position | `word_id`, `sentence_id`, `position_in_sentence`, `text_index` (running position in the novel), `part`, `trial` |
| word | `word` (as displayed), `form`, `lemma`, `pos`, `word_length`, `swow_node`, `swow_role` (cue / response_only) |
| eye tracking | `ffd`, plus `gd`, `trt`, `skip` for robustness checks; `ffd_outlier` flag (< 80 ms or > 1000 ms) |
| predictors | `surprisal_context` (main), `surprisal_sentence` (robustness), `zipf_frequency`, `freq_missing` flag |

## suggestions

- **Surprisal**: two columns. `surprisal_context` = model sees all preceding text of the same
  part (up to the 1024-token window); `surprisal_sentence` = model sees only the current sentence.
  The main analysis uses `surprisal_context`.
- **Skipped words / short fixations**: keep all rows; `ffd` is null when the word was skipped in
  first pass; extreme fixations are flagged, not dropped. Exclusions happen at modelling time.
- **Frequency norms**: SUBTLEX-UK (British novel) and SUBTLEX-NL, as Zipf values.
- **SWOW**: words that are only SWOW responses are included (`swow_role = response_only`).
  They only get a semantic field if stage 2 builds communities over all nodes, not only cues.

## Decisions: surprisal and frequency (agreed 2026-11-16)

Scope: English only for now. Dutch is not considered.

Surprisal

- **Model:** GPT-2 small (`gpt2`, 124M parameters). Values are in bits (-log2 p).
- **Input text:** the words exactly as displayed in GECO (punctuation and capitals included),
  joined by single spaces, in reading order.
- **Two context settings:** `surprisal_context` (main) conditions on all preceding text of the same
  part of the novel, limited by GPT-2's 1024-token window; the window slides so that every token has
  at least 512 tokens of context. `surprisal_sentence` (robustness) conditions only on the preceding
  words of the same sentence.
- **Word-level value:** plain sum of the surprisals of the word's model tokens. No whitespace
  correction (Pimentel & Meister 2024; Oh & Schuler 2024) is applied.
- **Punctuation is stripped:** model tokens without a letter or digit are not counted, so
  "subsided." gets the surprisal of "subsided". The punctuation is still part of the context the
  model sees. Tokens that are only punctuation ("...") have no surprisal.
- `n_subtokens` gives the number of model tokens counted for the word.

Frequency

- **Norms:** SUBTLEX-UK (`data/frequency/SUBTLEX-UK.txt`), because the novel is British English.
- **Scale:** Zipf = log10((count + 1) / 201.496) + 3, the formula of van Heuven et al. (2014);
  201.496 is the corpus size in millions of tokens plus types. It reproduces the file's own
  `LogFreq(Zipf)` column to the second decimal.
- **Lookup key:** the lowercased word form as displayed, with edge punctuation and the possessive
  "'s" removed. Not the lemma: "ran" gets the frequency of "ran".
- **Missing words:** forms not listed in SUBTLEX-UK get a count of 0 (Zipf 0.70, the lowest
  possible value) and `freq_missing = True`.
- **Hyphenated compounds** are looked up as written ("mother-in-law" is listed). If the compound
  is not listed ("despatch-case") it counts as missing; there is no back-off to its parts.

Sentences

- GECO's per-word `SENTENCE_ID` (ALL sheet, and the `SENTENCE_ID` column of the reading-measures
  table) is unreliable: about 4% of the words are missing from that sheet, and around them the ids
  are shifted by one word. Sentences are therefore taken from the SENTENCE sheet's texts.
- Interest areas that hold two words across a sentence boundary ('pouf!" ...he') go to the earlier
  sentence. `sentence_imputed` marks the tokens without an exact match.

## Steps

1. **Sentence segmentation.** Done in `semfields.text.tokens`. Sentences come from the SENTENCE
   sheet of GECO's materials file, aligned word by word with the token stream. The per-word
   `SENTENCE_ID` column is not used (see decisions below).
   Note: 111 English sentences continue onto the next screen, so sentences, not trials, are the unit.
2. **Surprisal.** Done in `semfields.text.surprisal`: GPT-2 small over the text with GECO's word
   boundaries, for every token including function words; the table is filtered afterwards.
3. **Frequency.** Done in `semfields.text.frequency`: SUBTLEX-UK lookup, Zipf scale.
   Steps 1-3 are run by `scripts/03_token_predictors.py`, which writes
   `data/interim/geco/tokens_en.parquet` (one row per word token).
4. **Assembly.** Done in `semfields.analysis.table`, run by `scripts/04_build_analysis_table.py`:
   the token table joined with the participants' reading measures on `word_id`, filtered to
   content words with a SWOW node (cue or response).
5. **Validation.** Coverage counts per step; check that surprisal, frequency and length relate to
   ffd in the expected directions.

Dutch: SWOW-NL is available (raw responses; strengths computed in `semfields.network.swow`).
Dutch lemmas: candidates from nl_core_news_sm + nl_core_news_lg + weak-past-tense rules
("mompelde" -> "mompelen"), accepted only if they are SWOW cues. Pronominal adverbs ("er",
"ervan", "waarop"), clitics ("'t") and English contractions ("isn't") are not content words.
Open question for the group: keep adverbs as content words? Modal particles such as Dutch
"nog", "nou", "immers" and English "still", "even" are tagged ADV and are not very topical.

## Network analysis tooling

Use `networkx` for stages 1 and 2, following the course workbook and the self-study notebook.
Timings on SWOW-EN (R123): 133,763 nodes and 1.39M edges in total; 12,217 nodes and 1.07M edges
between cues only.

- Fine as they are: degree and strength distributions, connected components, assortativity (5 s),
  Louvain on the cue graph (36 s).
- Use a node sample: clustering, shortest paths. A single-source BFS on the cue graph takes ~50 ms,
  so exact all-pairs paths are possible on the cue graph but not routinely on the full graph.
- Avoid: `nx.sigma`, `nx.omega`, `nx.average_node_connectivity`, exact betweenness. They are built
  for small graphs. Compute small-worldness by hand from C and L against degree-preserving rewirings.
- Community detection: **Louvain** (`louvain_communities`) is the method for stage 2. It runs on the
  undirected and the directed cue graph in under a minute. Default resolution gives 15 communities
  (Q = 0.39), resolution 3 gives 81 (Q = 0.36), so resolution has to be tuned.
- Rejected: `greedy_modularity_communities` did not finish on the cue graph within 25 minutes.
  Label propagation (`asyn_lpa_communities`, `fast_label_propagation_communities`) puts all 12,217
  cues into one community on the full graph; it only splits the graph after thinning to
  associations given by at least 6 people (1,039 communities, Q = 0.45).

## Results of `03_token_predictors.py` 

- 56,413 tokens in 5,298 sentences; 73 tokens without an exact sentence match.
- Every token has a surprisal value. Mean `surprisal_context`: 7.6 bits for content words,
  4.3 bits for the others. Correlation with Zipf frequency: -0.58 (context), -0.72 (sentence).
- Per-token means of the monolingual readers: surprisal and gaze duration r = 0.31, Zipf and gaze
  duration r = -0.34, Zipf and skipping r = 0.61. First fixation duration relates more weakly
  (0.14 and -0.12), as usual.
- 1,778 tokens (3.2%) are missing from SUBTLEX-UK: 736 proper nouns ("Inglethorp"), 434
  contractions ("don't", "I'm"; SUBTLEX-UK does not list them) and 213 hyphenated compounds.
  Of the 22,141 content-word tokens that are in SWOW (cue or response), 87 are missing.
- Known limitation: contractions get the lowest Zipf value although they are frequent. They are not
  content words, so this only matters if the previous word's frequency is used as a predictor.
- The highest surprisals are interest areas that hold several words ("parlourmaid...Dorcas,") and
  rare names ("Heavywether"). Their value is the sum over all words in the interest area.

## Results of `04_build_analysis_table.py` 

- 513,381 rows: 22,141 content-word tokens (3,839 distinct SWOW nodes) x the readers who read them.
  Monolinguals: 14 readers, 303,936 rows. Bilinguals reading English (L2): 19 readers, 209,445 rows
  (each read about half of the novel in English).
- `ffd` is null when the word was skipped in first pass: 38% of monolingual rows, 31% of L2 rows.
  `ffd_outlier` flags 2-3% of the remaining first fixations (< 80 ms or > 1000 ms).
- `swow_node` is the matched cue, or for `swow_role = response_only` the matching response.
- Rows are sorted by reader and `text_index`. For the stay/switch variable, take the previous content
  word from the text order (token table), not from the previous fixated row.

## Decisions: regression model (agreed 2026-11-16)

- **Outcomes:** log first fixation duration first (rows fixated in first pass, `ffd_outlier` excluded).
  Gaze duration and skipping follow as secondary outcomes.
- **Readers:** monolinguals only.
- **Switch variable:** defined within the sentence only. `switch = 1` if the previous content word of
  the same sentence that has a community is in a different community, 0 if it is in the same one.
  The first such content word of a sentence has no value and is left out of the model.
- **Controls:** surprisal (`surprisal_context`), Zipf frequency, word length, the word's degree in
  SWOW, and the direct association strength between the previous content word and the current one.
- **Unit of analysis:** one row per token, not per participant x token. Each participant's log
  first fixation durations are centred on that participant's own mean, then averaged over the
  readers who fixated the token. This is possible because every predictor describes the token and
  none varies between readers.
- **Model:** linear regression on the token means, weighted by the number of readers who fixated
  the token, with a random intercept per word (`swow_node`). Continuous predictors standardised.
  Skipping: the share of readers who skipped the token, as a binomial model.
- **Tooling:** Python with `statsmodels`
- **Limitation:** the result generalises across words, not across readers, and cannot show whether
  the switch effect differs between readers.
- **Future work (out of scope):** a trial-level model with one row per participant x token and
  participant terms, to test variation between readers; the L2 readers; Dutch.
- **Hypothesis 2:** fit the baseline model without `switch` once, then compare the switch-minus-stay
  difference in its residuals between the real partition and random partitions with the same
  community sizes (permutation test).
- What is still undecided is listed under "Open questions" at the end of this document.

## Open questions

Communities (stage 2)

1. **Louvain resolution.** Default resolution gives 15 communities, resolution 3 gives 81. Which
   one is used for the main analysis? It should be fixed before looking at reading times (by
   stability and agreement with WordNet), or all tested resolutions are reported.
2. **Response-only words.** Words that occur in SWOW only as responses have no outgoing edges and
   are not in the cue graph. Options: run Louvain on the full graph (134k nodes), assign each such
   word to the community it receives most association strength from, or drop them (7% of
   content-word tokens).
3. **Thinning the graph.** Keeping only associations given by several people raises modularity
   (0.39 to 0.58 at a minimum of 6 people) and changes the communities. Thin or not, and at which
   threshold?
4. **Directed or undirected.** Louvain runs on both. The directed cue graph gave the same number of
   communities at default resolution (15).

Switch variable and model (stage 3 and 4)

5. **Repetitions.** If the previous content word is the same word, it is always a "stay" and also a
   repetition, which speeds up reading by itself. Exclude these pairs, or add a repetition flag?
6. **Spillover controls.** Add the previous word's frequency, length and surprisal? If so, the
   contractions need fixing first: SUBTLEX-UK does not list "don't", "I'm" etc., so they currently
   get the lowest Zipf value.
7. **Adverbs.** Keep them as content words? Words like "still" and "even" are tagged as adverbs and
   are not very topical. Adverbs also have the lowest SWOW coverage (81% of tokens).
8. **Minimum number of readers per token.** Token means rest on 1 to 14 readers. Weighting by the
   number of readers is agreed; should tokens fixated by very few readers (fewer than 5?) be
   dropped as well?
9. **Interest areas with several words.** 73 tokens hold two or more words ('pouf!" ...he') and have
   summed surprisal values up to 55 bits. Exclude them from the model?
10. **Direct association strength.** Which direction counts: previous word to current word, the
    reverse, or the larger of the two? And R1 strengths?

Data

11. **Missing monolingual rows.** About 2% of the expected monolingual rows are absent from GECO's
    reading data. Not yet checked which trials or readers they are.
12. **Proper nouns.** They are excluded as content words at the moment (SWOW covers 33% of their
    tokens). Confirm that they stay out and are skipped when looking for the previous content word.
