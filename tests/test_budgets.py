import datetime as dt

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_account(client: AsyncClient, headers: dict[str, str]) -> int:
    response = await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=headers
    )
    return response.json()["id"]


async def _create_category(client: AsyncClient, headers: dict[str, str], name: str) -> int:
    response = await client.post("/categories", json={"name": name}, headers=headers)
    return response.json()["id"]


async def test_create_budget(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    category_id = await _create_category(client, auth_headers, "Groceries")
    start_of_month = dt.date.today().replace(day=1)

    response = await client.post(
        "/budgets",
        json={
            "category_id": category_id,
            "amount_limit": 300,
            "period": "monthly",
            "start_date": start_of_month.isoformat(),
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["amount_limit"] == 300
    assert data["spent"] == 0
    assert data["remaining"] == 300


async def test_budget_tracks_spending(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    account_id = await _create_account(client, auth_headers)
    category_id = await _create_category(client, auth_headers, "Groceries")
    start_of_month = dt.date.today().replace(day=1)

    create_response = await client.post(
        "/budgets",
        json={
            "category_id": category_id,
            "amount_limit": 200,
            "period": "monthly",
            "start_date": start_of_month.isoformat(),
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["id"]

    today = dt.date.today()
    for amount in (50, 30):
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": category_id,
                "amount": amount,
                "type": "expense",
                "date": today.isoformat(),
            },
            headers=auth_headers,
        )

    # An expense in a different category should not count toward this budget
    other_category_id = await _create_category(client, auth_headers, "Rent")
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": other_category_id,
            "amount": 1000,
            "type": "expense",
            "date": today.isoformat(),
        },
        headers=auth_headers,
    )

    response = await client.get(f"/budgets/{budget_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["spent"] == 80
    assert data["remaining"] == 120


async def test_budget_with_invalid_category(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/budgets",
        json={
            "category_id": 9999,
            "amount_limit": 100,
            "period": "monthly",
            "start_date": dt.date.today().isoformat(),
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_update_and_delete_budget(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    category_id = await _create_category(client, auth_headers, "Groceries")
    create_response = await client.post(
        "/budgets",
        json={
            "category_id": category_id,
            "amount_limit": 200,
            "period": "monthly",
            "start_date": dt.date.today().replace(day=1).isoformat(),
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["id"]

    patch_response = await client.patch(
        f"/budgets/{budget_id}", json={"amount_limit": 400}, headers=auth_headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["amount_limit"] == 400

    delete_response = await client.delete(f"/budgets/{budget_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/budgets/{budget_id}", headers=auth_headers)
    assert get_response.status_code == 404
