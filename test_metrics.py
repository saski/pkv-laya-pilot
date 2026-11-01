"""Behavior checks for fair retrieval measurement."""
import pytest

from pilot import metrics, rank_by_relevance


def test_missed_gold_source_counts_even_when_not_retrieved() -> None:
    actual = metrics(["b", "a", "noise"], {"a": 2, "c": 2}, 3)
    assert actual["recall"] == 0.5
    assert actual["reciprocal_rank"] == 0.5
    assert actual["ndcg"] == pytest.approx(0.3868528072)


def test_small_context_cannot_claim_relevance_beyond_its_cutoff() -> None:
    actual = metrics(["noise", "other", "a"], {"a": 2}, 2)
    assert actual["hit"] == 0
    assert actual["recall"] == 0
    assert actual["ndcg"] == 0


def test_ranking_uses_yes_probability_not_confidence_of_no() -> None:
    assert rank_by_relevance([0.05, 0.7, 0.7]) == [1, 2, 0]


def test_invalid_model_scores_fail_instead_of_becoming_ranks() -> None:
    with pytest.raises(ValueError):
        rank_by_relevance([0.9, float("nan")])
