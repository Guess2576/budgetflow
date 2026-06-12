import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login

pytestmark = pytest.mark.asyncio


async def _create_account(client: AsyncClient, headers: dict[str, str]) -> int:
    response = await client.post(
        "/accounts", json={"name": "Checking", "type": "checking"}, headers=headers
    )
    return response.json()["id"]


async def _create_category(client: AsyncClient, headers: dict[str, str], name: str) -> int:
    response = await client.post("/categories", json={"name": name}, headers=headers)
    return response.json()["id"]


async def test_create_transaction(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    account_id = await _create_account(client, auth_headers)

    response = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": 42.50,
            "type": "expense",
            "description": "Coffee",
            "date": "2026-06-01",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 42.50
    assert data["type"] == "expense"


async def test_create_transaction_with_invalid_account(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/transactions",
        json={"account_id": 9999, "amount": 10, "type": "expense", "date": "2026-06-01"},
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_create_transaction_rejects_zero_amount(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)

    response = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 0, "type": "expense", "date": "2026-06-01"},
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_get_update_delete_transaction(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    create_response = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 100, "type": "income", "date": "2026-06-01"},
        headers=auth_headers,
    )
    transaction_id = create_response.json()["id"]

    get_response = await client.get(f"/transactions/{transaction_id}", headers=auth_headers)
    assert get_response.status_code == 200

    patch_response = await client.patch(
        f"/transactions/{transaction_id}", json={"amount": 150}, headers=auth_headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["amount"] == 150

    delete_response = await client.delete(f"/transactions/{transaction_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/transactions/{transaction_id}", headers=auth_headers)
    assert missing_response.status_code == 404


async def test_list_transactions_filtering_and_pagination(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    groceries_id = await _create_category(client, auth_headers, "Groceries")

    for i in range(5):
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": groceries_id,
                "amount": 10 + i,
                "type": "expense",
                "date": f"2026-06-{i + 1:02d}",
            },
            headers=auth_headers,
        )

    await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 500, "type": "income", "date": "2026-06-10"},
        headers=auth_headers,
    )

    response = await client.get(
        "/transactions",
        params={"type": "expense", "page": 1, "page_size": 2, "sort_by": "date", "order": "asc"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["date"] == "2026-06-01"


async def test_csv_import(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    account_id = await _create_account(client, auth_headers)

    csv_content = (
        "date,description,amount,category\n"
        "2026-06-01,Paycheck,2000,Income\n"
        "2026-06-02,Groceries,-54.32,Groceries\n"
        "2026-06-03,Rent,-1200,Rent\n"
        "not-a-date,Bad row,10,Misc\n"
    )

    response = await client.post(
        "/transactions/import",
        data={"account_id": str(account_id)},
        files={"file": ("transactions.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 3
    assert len(data["skipped"]) == 1

    list_response = await client.get(
        "/transactions", params={"account_id": account_id}, headers=auth_headers
    )
    items = list_response.json()["items"]
    assert len(items) == 3

    income_item = next(item for item in items if item["type"] == "income")
    assert income_item["amount"] == 2000

    expense_item = next(item for item in items if item["description"] == "Groceries")
    assert expense_item["amount"] == 54.32
    assert expense_item["category_id"] is not None


async def test_transaction_not_visible_to_other_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    create_response = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 50, "type": "expense", "date": "2026-06-01"},
        headers=auth_headers,
    )
    transaction_id = create_response.json()["id"]

    other_headers = await register_and_login(client, "other2@example.com")
    response = await client.get(f"/transactions/{transaction_id}", headers=other_headers)

    assert response.status_code == 404


async def test_transaction_update_and_delete_not_visible_to_other_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    create_response = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 50, "type": "expense", "date": "2026-06-01"},
        headers=auth_headers,
    )
    transaction_id = create_response.json()["id"]

    other_headers = await register_and_login(client, "other3@example.com")

    patch_response = await client.patch(
        f"/transactions/{transaction_id}", json={"amount": 99}, headers=other_headers
    )
    assert patch_response.status_code == 404

    delete_response = await client.delete(f"/transactions/{transaction_id}", headers=other_headers)
    assert delete_response.status_code == 404


async def test_update_transaction_with_invalid_account_or_category(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    create_response = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 50, "type": "expense", "date": "2026-06-01"},
        headers=auth_headers,
    )
    transaction_id = create_response.json()["id"]

    response = await client.patch(
        f"/transactions/{transaction_id}", json={"account_id": 9999}, headers=auth_headers
    )
    assert response.status_code == 404

    response = await client.patch(
        f"/transactions/{transaction_id}", json={"category_id": 9999}, headers=auth_headers
    )
    assert response.status_code == 404


async def test_update_transaction_changes_account_and_category(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    other_account_id = await _create_account(client, auth_headers)
    category_id = await _create_category(client, auth_headers, "Groceries")

    create_response = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": 50, "type": "expense", "date": "2026-06-01"},
        headers=auth_headers,
    )
    transaction_id = create_response.json()["id"]

    response = await client.patch(
        f"/transactions/{transaction_id}",
        json={"account_id": other_account_id, "category_id": category_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == other_account_id
    assert data["category_id"] == category_id


async def test_csv_import_with_invalid_account(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    csv_content = "date,amount\n2026-06-01,100\n"

    response = await client.post(
        "/transactions/import",
        data={"account_id": "9999"},
        files={"file": ("transactions.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_csv_import_missing_required_columns(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    csv_content = "description,category\nCoffee,Dining\n"

    response = await client.post(
        "/transactions/import",
        data={"account_id": str(account_id)},
        files={"file": ("transactions.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "missing required column" in response.json()["detail"]


async def test_csv_import_unparseable_file(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)

    response = await client.post(
        "/transactions/import",
        data={"account_id": str(account_id)},
        files={"file": ("transactions.csv", b"", "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Could not parse CSV" in response.json()["detail"]


async def test_csv_import_reuses_existing_category(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    account_id = await _create_account(client, auth_headers)
    groceries_id = await _create_category(client, auth_headers, "Groceries")

    csv_content = "date,amount,category\n2026-06-01,-10,Groceries\n2026-06-02,-20,groceries\n"

    response = await client.post(
        "/transactions/import",
        data={"account_id": str(account_id)},
        files={"file": ("transactions.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 2

    list_response = await client.get(
        "/transactions", params={"category_id": groceries_id}, headers=auth_headers
    )
    items = list_response.json()["items"]
    assert len(items) == 2
