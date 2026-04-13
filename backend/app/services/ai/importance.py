"""
Importance scoring: combines engagement signals + topic classification confidence
to rank how globally significant a news item is (0.0 – 1.0).
"""


def score_importance(
    topic_scores: dict[str, float],
    source_reach: int = 1000,   # subscriber count or Alexa rank proxy
    reactions_count: int = 0,
) -> float:
    # TODO: weighted formula
    # e.g. max_topic_score * 0.6 + log(source_reach) / log(10_000_000) * 0.3 + reaction_boost * 0.1
    raise NotImplementedError
