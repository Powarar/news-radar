from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_sources():
    # TODO: all sources with user settings (enabled/blacklisted)
    pass


@router.post("/")
async def add_source():
    # TODO: add new TG channel or website (admin only)
    pass


@router.patch("/{source_id}/toggle")
async def toggle_source(source_id: int):
    # TODO: enable / disable source for current user
    pass


@router.patch("/{source_id}/blacklist")
async def blacklist_source(source_id: int):
    pass
