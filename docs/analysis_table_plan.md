# Plan: analysis table (participant x content-word token)

Goal: one table per language with every content-word token of the GECO novel that occurs in
SWOW (as cue **or** response), each participant's first fixation duration on it, and token-level
surprisal and frequency. No aggregation over word types: every row is one occurrence in its
sentence, so word order (needed for the stay/switch variable) is preserved.

Output: `data/processed/analysis_{en,nl}.parquet`, built by `scripts/04_build_analysis_table.py`.

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

## Steps

1. **Sentence segmentation.** Use GECO's `SENTENCE_ID`. The ~2k tokens missing from the
   materials file are mostly sentence-final words ("Essex.", "Evie?\""); each takes the
   sentence of the word before it. Validate against `NUMBER_WORDS_SENTENCE` in the SENTENCE sheet.
   Note: 111 English sentences continue onto the next screen, so sentences, not trials, are the unit.
2. **Surprisal.** GPT-2 small (EN) and GroNLP `gpt2-small-dutch` (NL), run over the text with
   GECO's word boundaries. Multi-subword words: sum of subword surprisals. Each word is
   scored together with its following space (Pimentel et al. 2024; Oh & Schuler 2024).
   Computed for every token, including function words; the table is filtered afterwards.
   Needs `torch` + `transformers`.
3. **Frequency.** SUBTLEX lookup on the lowercased form; Zipf = log10(per-million) + 3, using
   Laplace smoothing so missing words get the Zipf value of a count of 1 (flagged in `freq_missing`).
4. **Assembly.** Token table (1-3 + SWOW match from `02_geco_swow_coverage.py`) joined with
   the participant reading measures on `word_id`; filter to content words with a SWOW node.
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
