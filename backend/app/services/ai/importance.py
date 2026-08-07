import json
import logging

logger = logging.getLogger(__name__)


def score_importance(topic_scores: dict[str, float] | str | None, historical_topics: list[dict | str] | None = None) -> float:
    """0.0–1.0 based on percentile rank among recent news.

    For each topic in this article we ask: what % of recent articles
    scored LOWER than this one on that same topic?  The highest % across
    all topics becomes the importance score.

    This way a topic that is usually scored 0.85 (e.g. military)
    doesn't automatically dominate — only unusually high confidence
    for ITS topic is treated as important.
    """
    if isinstance(topic_scores, str):
        try:
            topic_scores = json.loads(topic_scores)
        except Exception:
            topic_scores = None

    if not topic_scores or not isinstance(topic_scores, dict):
        return 0.0

    if not historical_topics:
        # no history yet — fall back to simple max
        return round(max(topic_scores.values()) * 0.6, 3)

    # Build per-topic lists of historical scores
    hist: dict[str, list[float]] = {}
    for row in historical_topics:
        if not row:
            continue
        if isinstance(row, str):
            try:
                row = json.loads(row)
            except Exception:
                continue
        if not isinstance(row, dict):
            continue
        for topic, score in row.items():
            if isinstance(score, (int, float)):
                hist.setdefault(topic, []).append(float(score))

    if not hist:
        return round(max(topic_scores.values()) * 0.6, 3)

    best_pct = 0.0
    for topic, score in topic_scores.items():
        scores = hist.get(topic)
        if not scores:
            # New topic never seen before — it's "unusual" by definition
            best_pct = max(best_pct, 0.8)
            continue
        below = sum(1 for s in scores if s < score)
        pct = below / len(scores)
        best_pct = max(best_pct, pct)

    return round(best_pct * 0.8, 3)
