import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login

pytestmark = pytest.mark.asyncio


async def test_create_category(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post("/categories", json={"name": "Groceries"}, headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Groceries"
    assert data["parent_category_id"] is None


async def test_create_subcategory(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    parent_response = await client.post("/categories", json={"name": "Food"}, headers=auth_headers)
    parent_id = parent_response.json()["id"]

    response = await client.post(
        "/categories",
        json={"name": "Restaurants", "parent_category_id": parent_id},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["parent_category_id"] == parent_id


async def test_create_category_with_invalid_parent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/categories",
        json={"name": "Restaurants", "parent_category_id": 9999},
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_category_cannot_be_own_parent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post("/categories", json={"name": "Food"}, headers=auth_headers)
    category_id = create_response.json()["id"]

    response = await client.patch(
        f"/categories/{category_id}",
        json={"parent_category_id": category_id},
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_list_categories(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post("/categories", json={"name": "Groceries"}, headers=auth_headers)
    await client.post("/categories", json={"name": "Rent"}, headers=auth_headers)

    response = await client.get("/categories", headers=auth_headers)

    names = {category["name"] for category in response.json()}
    assert names == {"Groceries", "Rent"}


async def test_update_category(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/categories", json={"name": "Groceries"}, headers=auth_headers
    )
    category_id = create_response.json()["id"]

    response = await client.patch(
        f"/categories/{category_id}", json={"name": "Food & Groceries"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Food & Groceries"


async def test_delete_category(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/categories", json={"name": "Groceries"}, headers=auth_headers
    )
    category_id = create_response.json()["id"]

    delete_response = await client.delete(f"/categories/{category_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/categories/{category_id}", headers=auth_headers)
    assert get_response.status_code == 404


async def test_category_not_editable_by_other_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        "/categories", json={"name": "Groceries"}, headers=auth_headers
    )
    category_id = create_response.json()["id"]

    other_headers = await register_and_login(client, "other@example.com")
    response = await client.patch(
        f"/categories/{category_id}", json={"name": "Hacked"}, headers=other_headers
    )

    assert response.status_code == 404


async def test_category_not_deletable_by_other_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        "/categories", json={"name": "Groceries"}, headers=auth_headers
    )
    category_id = create_response.json()["id"]

    other_headers = await register_and_login(client, "other4@example.com")
    response = await client.delete(f"/categories/{category_id}", headers=other_headers)

    assert response.status_code == 404


async def test_get_nonexistent_category(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/categories/9999", headers=auth_headers)
    assert response.status_code == 404


async def test_update_category_with_valid_parent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    parent_response = await client.post("/categories", json={"name": "Food"}, headers=auth_headers)
    parent_id = parent_response.json()["id"]

    create_response = await client.post(
        "/categories", json={"name": "Snacks"}, headers=auth_headers
    )
    category_id = create_response.json()["id"]

    response = await client.patch(
        f"/categories/{category_id}",
        json={"parent_category_id": parent_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["parent_category_id"] == parent_id


async def test_update_category_with_invalid_parent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        "/categories", json={"name": "Snacks"}, headers=auth_headers
    )
    category_id = create_response.json()["id"]

    response = await client.patch(
        f"/categories/{category_id}",
        json={"parent_category_id": 9999},
        headers=auth_headers,
    )

    assert response.status_code == 400
