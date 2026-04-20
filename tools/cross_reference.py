from difflib import SequenceMatcher

_NEGATION_WORDS = {"not", "no", "never", "false", "incorrect", "wrong", "unlike", "contrary", "cannot", "isn't", "doesn't", "aren't"}
_MIN_SHARED_WORDS = 4


def _token_overlap(a: str, b: str) -> set[str]:
    return set(a.lower().split()) & set(b.lower().split()) - _NEGATION_WORDS


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_contradictions(facts: list[str]) -> list[tuple[str, str]]:
    """
    Detect likely contradictions: pairs that share a topic (keyword overlap)
    but differ on polarity (one uses negation, the other doesn't).
    """
    contradictions: list[tuple[str, str]] = []
    for i, fact_a in enumerate(facts):
        words_a = set(fact_a.lower().split())
        neg_a = bool(words_a & _NEGATION_WORDS)
        for fact_b in facts[i + 1 :]:
            words_b = set(fact_b.lower().split())
            if len(_token_overlap(fact_a, fact_b)) >= _MIN_SHARED_WORDS:
                neg_b = bool(words_b & _NEGATION_WORDS)
                if neg_a != neg_b:
                    contradictions.append((fact_a, fact_b))
    return contradictions
