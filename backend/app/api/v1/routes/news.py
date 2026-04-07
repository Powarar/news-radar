from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_feed():
    # TODO: personalized feed with filters (topic, language, country, source)
    # sorted by importance_score + user preference weight
    pass


@router.get("/top")
async def get_top():
    # TODO: most important news (importance_score desc, last 24h)
    pass


@router.get("/{news_id}")
async def get_news(news_id: int):
    pass


@router.post("/{news_id}/react")
async def react(news_id: int):
    # TODO: like / dislike / blacklist
    pass
