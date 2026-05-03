"""
Importance scoring: combines engagement signals + topic classification confidence
to rank how globally significant a news item is (0.0 – 1.0).
"""

#TODO add real formula, not default value
def score_importance(                                                                                                                                               
      topic_scores: dict[str, float],                                                                                                                                 
      source_reach: int = 1000,                                                                                                                                       
      reactions_count: int = 0,
  ) -> float:                                                                                                                                                         
      if not topic_scores:
          return 0.0
      return max(topic_scores.values()) * 0.6
