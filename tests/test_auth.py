import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_user(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "alice@example.com", "password": "supersecret123"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data


async def test_register_duplicate_email_fails(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 400


async def test_login_success(client: AsyncClient) -> None:
    payload = {"email": "carol@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)

    response = await client.post("/auth/login", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password_fails(client: AsyncClient) -> None:
    payload = {"email": "dave@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)

    response = await client.post(
        "/auth/login", json={"email": "dave@example.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401


async def test_refresh_token(client: AsyncClient) -> None:
    payload = {"email": "erin@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login_response = await client.post("/auth/login", json=payload)
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_with_access_token_fails(client: AsyncClient) -> None:
    payload = {"email": "frank@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login_response = await client.post("/auth/login", json=payload)
    access_token = login_response.json()["access_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401
