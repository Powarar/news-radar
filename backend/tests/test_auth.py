import pytest

BASE = "/api/v1/auth"

USER = {
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123",
}


async def register(client, **overrides):
    return await client.post(f"{BASE}/register", json={**USER, **overrides})


# ─────────────────────────────────────────────────────────────
#  Register
# ─────────────────────────────────────────────────────────────

class TestRegister:
    async def test_success_returns_tokens(self, client):
        r = await register(client)
        assert r.status_code == 201
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_duplicate_email(self, client):
        await register(client)
        r = await register(client, username="other")
        assert r.status_code == 409
        assert "Email already registered" in r.json()["detail"]

    async def test_duplicate_username(self, client):
        await register(client)
        r = await register(client, email="other@example.com")
        assert r.status_code == 409
        assert "Username already taken" in r.json()["detail"]

    async def test_password_too_short(self, client):
        r = await register(client, password="short")
        assert r.status_code == 422

    async def test_password_too_long(self, client):
        r = await register(client, password="x" * 65)
        assert r.status_code == 422

    async def test_invalid_email(self, client):
        r = await register(client, email="not-an-email")
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────
#  Login
# ─────────────────────────────────────────────────────────────

class TestLogin:
    async def test_success_returns_tokens(self, client):
        await register(client)
        r = await client.post(f"{BASE}/login", json={
            "email": USER["email"],
            "password": USER["password"],
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_wrong_password(self, client):
        await register(client)
        r = await client.post(f"{BASE}/login", json={
            "email": USER["email"],
            "password": "wrongpassword",
        })
        assert r.status_code == 401

    async def test_nonexistent_user(self, client):
        r = await client.post(f"{BASE}/login", json={
            "email": "nobody@example.com",
            "password": "password123",
        })
        assert r.status_code == 401

    async def test_missing_fields(self, client):
        r = await client.post(f"{BASE}/login", json={"email": USER["email"]})
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────
#  Refresh
# ─────────────────────────────────────────────────────────────

class TestRefresh:
    async def test_success_returns_new_tokens(self, client):
        reg = await register(client)
        old_access = reg.json()["access_token"]
        refresh_token = reg.json()["refresh_token"]

        r = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != old_access

    async def test_garbage_token_rejected(self, client):
        r = await client.post(f"{BASE}/refresh", json={"refresh_token": "garbage.token.here"})
        assert r.status_code == 401

    async def test_access_token_rejected_as_refresh(self, client):
        reg = await register(client)
        access_token = reg.json()["access_token"]

        r = await client.post(f"{BASE}/refresh", json={"refresh_token": access_token})
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────
#  Logout
# ─────────────────────────────────────────────────────────────

class TestLogout:
    async def test_success(self, client, mock_redis):
        reg = await register(client)
        token = reg.json()["access_token"]

        r = await client.post(
            f"{BASE}/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204
        mock_redis.setex.assert_called_once()

    async def test_no_token_returns_403(self, client):
        r = await client.post(f"{BASE}/logout")
        assert r.status_code == 403

    async def test_blacklisted_token_cannot_access_protected(self, client, mock_redis):
        reg = await register(client)
        token = reg.json()["access_token"]

        await client.post(
            f"{BASE}/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        # после логаута redis.exists должен вернуть 1 (токен в блеклисте)
        mock_redis.exists.return_value = 1

        r = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401
