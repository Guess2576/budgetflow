import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login

pytestmark = pytest.mark.asyncio


async def test_create_account(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/accounts",
        json={"name": "Chase Checking", "type": "checking", "balance": 1000, "currency": "USD"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Chase Checking"
    assert data["type"] == "checking"
    assert data["balance"] == 1000


async def test_create_account_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/accounts", json={"name": "Chase Checking", "type": "checking"})

    assert response.status_code == 401


async def test_list_accounts(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=auth_headers
    )
    await client.post(
        "/accounts", json={"name": "Savings", "type": "savings"}, headers=auth_headers
    )

    response = await client.get("/accounts", headers=auth_headers)

    assert response.status_code == 200
    names = {account["name"] for account in response.json()}
    assert names == {"Checking", "Savings"}


async def test_get_account(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.get(f"/accounts/{account_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == account_id


async def test_update_account(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/accounts",
        json={"name": "Checking", "type": "checking", "balance": 100},
        headers=auth_headers,
    )
    account_id = create_response.json()["id"]

    response = await client.patch(
        f"/accounts/{account_id}", json={"balance": 250.50}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["balance"] == 250.50
    assert response.json()["name"] == "Checking"


async def test_delete_account(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    delete_response = await client.delete(f"/accounts/{account_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/accounts/{account_id}", headers=auth_headers)
    assert get_response.status_code == 404


async def test_account_not_visible_to_other_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    other_headers = await register_and_login(client, "other@example.com")
    response = await client.get(f"/accounts/{account_id}", headers=other_headers)

    assert response.status_code == 404


async def test_account_not_updatable_or_deletable_by_other_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    other_headers = await register_and_login(client, "other5@example.com")

    patch_response = await client.patch(
        f"/accounts/{account_id}", json={"balance": 999}, headers=other_headers
    )
    assert patch_response.status_code == 404

    delete_response = await client.delete(f"/accounts/{account_id}", headers=other_headers)
    assert delete_response.status_code == 404


async def test_get_nonexistent_account(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/accounts/9999", headers=auth_headers)
    assert response.status_code == 404
