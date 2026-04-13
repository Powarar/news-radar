"""
Multilingual summarization via HuggingFace (csebuetnlp/mT5_multilingual_XLSum).
Supports 45+ languages including Russian and English.
"""


async def summarize(text: str, language: str, api_token: str) -> str:
    # TODO: call HF Inference API
    # POST https://api-inference.huggingface.co/models/csebuetnlp/mT5_multilingual_XLSum
    # body: {"inputs": text}
    raise NotImplementedError
