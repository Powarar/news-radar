from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_preferences():
    # TODO: user topic preferences + language/country settings
    pass


@router.put("/")
async def update_preferences():
    # TODO: update topic weights, language, country
    pass
