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


async def _create_transaction(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: int,
    amount: float,
    type_: str,
    tx_date: dt.date,
    category_id: int | None = None,
) -> None:
    payload = {
        "account_id": account_id,
        "amount": amount,
        "type": type_,
        "date": tx_date.isoformat(),
    }
    if category_id is not None:
        payload["category_id"] = category_id

    await client.post("/transactions", json=payload, headers=headers)


async def test_summary_report(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    account_id = await _create_account(client, auth_headers)
    today = dt.date.today()

    await _create_transaction(client, auth_headers, account_id, 2000, "income", today)
    await _create_transaction(client, auth_headers, account_id, 500, "expense", today)
    await _create_transaction(client, auth_headers, account_id, 200, "expense", today)

    response = await client.get("/reports/summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["income"] == 2000
    assert data["expenses"] == 700
    assert data["net"] == 1300


async def test_by_category_report(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    account_id = await _create_account(client, auth_headers)
    groceries_id = await _create_category(client, auth_headers, "Groceries")
    rent_id = await _create_category(client, auth_headers, "Rent")
    today = dt.date.today()

    await _create_transaction(client, auth_headers, account_id, 100, "expense", today, groceries_id)
    await _create_transaction(client, auth_headers, account_id, 50, "expense", today, groceries_id)
    await _create_transaction(client, auth_headers, account_id, 1200, "expense", today, rent_id)

    response = await client.get("/reports/by-category", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["category_name"] == "Rent"
    assert items[0]["total"] == 1200
    assert items[1]["category_name"] == "Groceries"
    assert items[1]["total"] == 150
    assert items[1]["transaction_count"] == 2


async def test_trends_report(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    account_id = await _create_account(client, auth_headers)
    today = dt.date.today()

    await _create_transaction(client, auth_headers, account_id, 1000, "income", today)
    await _create_transaction(client, auth_headers, account_id, 400, "expense", today)

    response = await client.get("/reports/trends", params={"months": 3}, headers=auth_headers)

    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 3

    current_month = today.strftime("%Y-%m")
    current_point = next(p for p in points if p["month"] == current_month)
    assert current_point["income"] == 1000
    assert current_point["expenses"] == 400
    assert current_point["net"] == 600


async def test_summary_report_custom_date_range(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    last_month = dt.date.today().replace(day=1) - dt.timedelta(days=1)

    await _create_transaction(client, auth_headers, account_id, 300, "income", last_month)

    response = await client.get(
        "/reports/summary",
        params={"start_date": last_month.isoformat(), "end_date": last_month.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["income"] == 300
    assert data["start_date"] == last_month.isoformat()
