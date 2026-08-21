from sqlalchemy import select

from app.models.user import User

USER = {
    "email": "source-admin@example.com",
    "username": "source-admin",
    "password": "password123",
}

SOURCE = {
    "name": "Example News",
    "url": "https://example.com/feed.xml",
    "type": "rss",
    "language": "en",
    "country": "US",
    "topics": ["technology"],
}


async def _register(client) -> str:
    response = await client.post("/api/v1/auth/register", json=USER)
    assert response.status_code == 201
    return response.json()["access_token"]


class TestSourceAdminAccess:
    async def test_regular_user_cannot_add_global_source(self, client):
        token = await _register(client)

        response = await client.post(
            "/api/v1/sources/",
            json=SOURCE,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    async def test_admin_can_add_global_source(self, client, db_session):
        token = await _register(client)
        user = await db_session.scalar(select(User).where(User.email == USER["email"]))
        user.is_admin = True
        await db_session.commit()

        response = await client.post(
            "/api/v1/sources/",
            json=SOURCE,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        assert response.json()["url"] == SOURCE["url"]
