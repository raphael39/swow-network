"""GECO word table: one row per word token of the novel, with cleaned form, lemma and POS.

GECO's interest areas are whitespace tokens with punctuation attached ("Poirot!",
"'The"). We strip the punctuation, then run spaCy on each trial (screen of text) with
GECO's own tokenisation, so every spaCy token lines up 1:1 with a GECO `word_id`.

Lemmatisation is unreliable for Dutch (each spaCy model gets different verbs wrong), so
every word also gets `lemma_candidates`: the lemmas of all models for the language plus,
for Dutch verbs, rule-based infinitives of weak past tenses. Matching against SWOW
(semfields.text.swow_match) accepts a candidate only if it is a SWOW cue.
"""
from __future__ import annotations

import re

import polars as pl
import spacy
from spacy.tokens import Doc

# The first model gives `lemma` and `spacy_pos`; all models contribute lemma candidates.
# For Dutch, sm comes first: it tags the novel's character names as PROPN far more reliably
# (98% vs 90% of name tokens), while lg adds better lemmas for many verbs ("glimlachte").
SPACY_MODELS = {
    "English": ["en_core_web_sm"],
    "Dutch": ["nl_core_news_sm", "nl_core_news_lg"],
}
# Content words are defined by spaCy's universal POS. We don't use GECO's CONTENT_WORD
# flag: it counts auxiliaries ("was", "had") and particles ("up") as content words, and
# tags names inconsistently. Proper nouns get their own flag (`is_proper_noun`).
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Words spaCy tags as ADV/ADJ/... that are function words for our purpose.
# Dutch pronominal adverbs: "er" and er/daar/hier/waar + preposition ("ervan", "waarop").
# Bare "daar", "hier", "waar" stay content words, like English "there", "here", "where".
_NL_PREP = (r"(aan|achter|af|bij|binnen|boven|door|heen|in|langs|mee|na|naar|naast|om|omheen"
            r"|onder|op|over|rond|tegen|toe|tussen|uit|van|vandaan|voor|zonder)")
NL_PRONOMINAL_ADVERB = re.compile(rf"^(er{_NL_PREP}?|(daar|hier|waar){_NL_PREP})$")
# Clitics: GECO's "'t", "'n", "'s", "'k" lose their apostrophe in clean_token
NL_CLITICS = {"t", "n", "s", "k", "m'n", "z'n", "d'r", "'t", "'n", "'s", "'k"}
# English contractions ("isn't", "i've", "we'll") are tagged as one content token by spaCy
EN_CONTRACTION = re.compile(r"(n't|n’t|'ve|’ve|'ll|’ll|'re|’re|'d|’d|'m|’m)$", re.IGNORECASE)

# punctuation stripped from both ends of a GECO token (inner hyphens/apostrophes are kept)
STRIP_CHARS = "\"'‘’“”`.,;:!?()[]{}-–—…*_"
# English possessive clitic; not stripped for Dutch, where "'s" also marks plurals ("foto's")
EN_POSSESSIVE = ("'s", "’s", "s'", "s’")


def clean_token(word: str, language: str = "English") -> str:
    form = word.strip().strip(STRIP_CHARS)
    if language == "English":
        for clitic in EN_POSSESSIVE:
            if form.endswith(clitic) and len(form) > len(clitic):
                form = form[: -len(clitic)] + ("s" if clitic.startswith("s") else "")
                break
    return form


def is_function_override(form: str, language: str) -> bool:
    """True for tokens spaCy tags as content words but that we treat as function words."""
    lower = form.lower()
    if language == "Dutch":
        return lower in NL_CLITICS or bool(NL_PRONOMINAL_ADVERB.match(lower))
    return bool(EN_CONTRACTION.search(lower))


def dutch_weak_past_infinitives(form: str) -> list[str]:
    """Possible infinitives of a Dutch weak past tense / participle-like form.

    "mompelde" -> "mompelen", "schudde" -> "schudden", "glimlachte" -> "glimlachen",
    "maakte" -> "maken", "leefde" -> "leven", "reisde" -> "reizen". Over-generates on
    purpose; only candidates that are SWOW cues are used.
    """
    lower = form.lower()
    match = re.match(r"^(.{2,}?)(de|te|den|ten)$", lower)
    if not match:
        return []
    stem = match.group(1)
    candidates = [stem + "en"]
    if stem[-1] not in "aeiou":
        candidates.append(stem + stem[-1] + "en")                  # schud -> schudden
    if len(stem) >= 3 and stem[-2] == stem[-3] and stem[-2] in "aeou":
        candidates.append(stem[:-2] + stem[-1] + "en")             # maak -> maken
    if stem[-1] in "fs":
        voiced = {"f": "v", "s": "z"}[stem[-1]]
        base = stem[:-2] + stem[-1] if len(stem) >= 3 and stem[-2] == stem[-3] else stem
        candidates.append(base[:-1] + voiced + "en")               # leef -> leven, reis -> reizen
    return candidates


def build_word_table(reading_measures: pl.DataFrame, language: str) -> pl.DataFrame:
    """Unique word tokens of the `language` version of the novel, in reading order.

    Built from the reading measures rather than the materials file, because ~3% of
    word ids are missing from GECO's materials. GECO's own POS and content-word flag
    are kept for reference (`geco_pos`, `geco_content_word`) where available.
    """
    words = (
        reading_measures.filter(pl.col("language") == language)
        .group_by("word_id")
        .agg(
            pl.col("word").first(),
            pl.col("PART_OF_SPEECH").first().alias("geco_pos"),
            pl.col("is_content_word").first().alias("geco_content_word"),
        )
        .with_columns(
            pl.col("word_id").str.split("-").list.eval(pl.element().cast(pl.Int64))
            .list.to_struct(fields=["part", "trial", "position"]).alias("_id"),
        )
        .unnest("_id")
        .sort("part", "trial", "position")
        .with_columns(
            language=pl.lit(language),
            form=pl.col("word").map_elements(lambda w: clean_token(w, language), return_dtype=pl.Utf8),
        )
    )
    return _annotate_spacy(words, language)


def _run_spacy(words: pl.DataFrame, model: str) -> tuple[list[str], list[str]]:
    nlp = spacy.load(model, disable=["ner"])
    lemmas, pos = [], []
    for (_part, _trial), trial in words.group_by(["part", "trial"], maintain_order=True):
        # spaCy can't take empty tokens (pure-punctuation interest areas such as "...")
        forms = [f if f else "_" for f in trial["form"].to_list()]
        doc = nlp(Doc(nlp.vocab, words=forms))
        for token, form in zip(doc, trial["form"].to_list()):
            lemmas.append(token.lemma_ if form else "")
            pos.append(token.pos_ if form else "PUNCT")
    return lemmas, pos


def _annotate_spacy(words: pl.DataFrame, language: str) -> pl.DataFrame:
    models = SPACY_MODELS[language]
    lemmas, pos = _run_spacy(words, models[0])
    extra_lemmas = [_run_spacy(words, model)[0] for model in models[1:]]

    candidates = []
    for i, form in enumerate(words["form"].to_list()):
        options = [lemmas[i], *(extra[i] for extra in extra_lemmas)]
        if language == "Dutch" and pos[i] in {"VERB", "AUX", "ADJ"}:
            options += dutch_weak_past_infinitives(form)
        candidates.append(list(dict.fromkeys(o for o in options if o)))  # unique, order kept

    words = words.with_columns(
        lemma=pl.Series(lemmas),
        lemma_candidates=pl.Series(candidates, dtype=pl.List(pl.Utf8)),
        spacy_pos=pl.Series(pos),
    )
    function = words["form"].map_elements(lambda f: is_function_override(f, language), return_dtype=pl.Boolean)
    return words.with_columns(
        is_content_word=pl.col("spacy_pos").is_in(CONTENT_POS) & ~function,
        is_proper_noun=pl.col("spacy_pos") == "PROPN",
    )
