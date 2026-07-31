from app.services.ai.importance import score_importance


def test_importance_uses_topic_percentile_instead_of_raw_score():
    history = [
        {"military": 0.80, "technology": 0.10},
        {"military": 0.85, "technology": 0.20},
        {"military": 0.90, "technology": 0.30},
        {"military": 0.95, "technology": 0.40},
    ]

    # 0.86 looks high in absolute terms, but it is ordinary for "military".
    assert score_importance({"military": 0.86}, history) == 0.4

    # 0.35 is lower in absolute terms, but unusually high for "technology".
    assert score_importance({"technology": 0.35}, history) == 0.6


def test_importance_takes_strongest_topic_percentile():
    history = [
        {"military": 0.80, "technology": 0.10},
        {"military": 0.85, "technology": 0.20},
        {"military": 0.90, "technology": 0.30},
        {"military": 0.95, "technology": 0.40},
    ]

    assert score_importance(
        {"military": 0.86, "technology": 0.35},
        history,
    ) == 0.6


def test_importance_has_deterministic_cold_start_fallback():
    assert score_importance({"business": 0.75}, []) == 0.45
    assert score_importance({}, [{"business": 0.75}]) == 0.0
