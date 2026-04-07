from fastapi import APIRouter

router = APIRouter()


@router.post("/register")
async def register():
    # TODO: register with email/password
    pass


@router.post("/login")
async def login():
    # TODO: JWT login
    pass


@router.post("/refresh")
async def refresh():
    # TODO: refresh JWT
    pass


@router.get("/google")
async def google_oauth():
    # TODO: Google OAuth redirect
    pass


@router.get("/google/callback")
async def google_callback():
    # TODO: Google OAuth callback
    pass


@router.post("/logout")
async def logout():
    pass
