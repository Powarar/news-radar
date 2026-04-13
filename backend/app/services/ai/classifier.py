"""
Topic classification via HuggingFace zero-shot (facebook/bart-large-mnli).
Returns topic → confidence score dict.
"""

TOPICS = [
    "politics",
    "military",
    "technology",
    "health",
    "science",
    "business",
    "sports",
    "culture",
    "environment",
]


async def classify(text: str, api_token: str) -> dict[str, float]:
    # TODO: call HF Inference API
    # POST https://api-inference.huggingface.co/models/facebook/bart-large-mnli
    # body: {"inputs": text, "parameters": {"candidate_labels": TOPICS}}
    # returns: {"labels": [...], "scores": [...]}
    raise NotImplementedError
