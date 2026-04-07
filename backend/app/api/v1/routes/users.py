from fastapi import APIRouter

router = APIRouter()


@router.get("/me")
async def get_me():
    # TODO: current user profile
    pass


@router.patch("/me")
async def update_me():
    # TODO: update profile (username, language, country)
    pass
