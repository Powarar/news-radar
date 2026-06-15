def score_importance(topic_scores: dict[str, float]) -> float:
    """0.0–1.0 based on highest topic confidence. Replace with richer formula later."""
    if not topic_scores:
        return 0.0
    return round(max(topic_scores.values()) * 0.6, 3)
