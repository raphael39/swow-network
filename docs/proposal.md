# Project proposal

## Research question

We test whether readers are sensitive to associaction fields, found as communities in a word-association
network, while reading natural text.

**Research question:** Do readers slow down when a text moves from one semantic field to another,
beyond what word frequency, length and language-model surprisal explain?

## Hypotheses

1. Words that start a new community (the previous content word belongs to a different one) have
   longer reading times than words that stay in the same community.
2. This effect is larger for the communities we find than for random groupings of the same words
   with matching group sizes.
3. (Exploratory) The effect appears in both English and Dutch, and differs between reading in the
   first and the second language.

**Why it is new:** most reading research measures context fit with surprisal, which captures what
fits the next position in a sentence. Semantic fields capture topical neighbourhood regardless of
syntax, and network science gives us a principled way to find them.

## Data

Both core datasets are public and exist in English and Dutch, which would alllow us a two-language
comparison without extra data collection, if we want to.

| Dataset | What it is | Languages | Role in the project |
|---|---|---|---|
| Small World of Words (SWOW) | Free-association norms: people see a cue word and name the first three words that come to mind; roughly 12,000 cues per language | English | Directed, weighted association network (cue to response, weight = response frequency) |
| GECO (Ghent Eye-Tracking Corpus) | Eye movements of people reading a full novel; Dutch–English bilinguals read it in both languages, plus an English monolingual group | English | Word-level reading measures: first fixation, gaze duration, total reading time, regressions |
| Pretrained language models (e.g. GPT-2) | Used only to compute word surprisal | English | Control variable |
| Word frequency norms (e.g. SUBTLEX) | Corpus word frequencies | English | Control variable |



## Method

The project runs in four stages; each stage's output is the next stage's input.

1. **Build the networks.** Turn SWOW into a directed, weighted graph per language. Describe it with
   standard measures (degree and strength distributions, clustering, path lengths, assortativity)
   and compare it with null models.
2. **Find association fields.** Run Louvain community detection at several resolutions. Check that the
   partitions are stable and that they look like semantic fields, for example against WordNet
   categories and by inspecting samples.
3. **Map fields onto the text.** Tokenise and lemmatise GECO, keep content words, look each one up
   in SWOW, and label it with its community. For every word, record whether it stays in the previous
   content word's community or switches.
4. **Test reader sensitivity.** Fit mixed-effects regressions of reading measures on the switch
   variable, controlling for frequency, length, surprisal and the word's degree, with random effects
   for participants and words. Compare the real partition against random partitions with the same
   group sizes (hypothesis 2).



## Roles
