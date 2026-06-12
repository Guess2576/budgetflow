# BudgetFlow

A personal finance / budget tracking API built with FastAPI and SQLAlchemy (async). BudgetFlow lets users manage accounts, record transactions, organize spending into categories, and set budgets with reporting on spend vs. limits.

## Status

**Done:**
- Phase 1 — project scaffold, data models, database migrations, JWT authentication (register / login / refresh)
- Phase 2 — Accounts & Categories CRUD, with ownership checks and category hierarchy support
- Phase 3 — Transactions CRUD with filtering/sorting/pagination, and CSV bank-statement import (auto-categorization)
- Phase 4 — Budgets (with rolling period tracking vs. spend) and reporting endpoints (summary, by-category breakdown, monthly trends)
- Phase 5 — Dockerized app + Postgres via docker-compose, GitHub Actions CI/CD (lint, format check, tests, GHCR image publish, Render deployment)

**Planned:**
- Background jobs for recurring transactions and budget alerts

## Tech Stack

- **FastAPI** (async) for the API layer
- **SQLAlchemy 2.0** (async) + **SQLite** for local dev, **PostgreSQL** in production
- **Alembic** for schema migrations
- **JWT** (via `python-jose`) + `bcrypt` for authentication
- **pytest** + **httpx** for async integration testing

## Getting Started

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env

# Apply database migrations
alembic upgrade head

# Run the dev server
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs` once the server is running.

## Running Tests

```bash
pytest
```

## Running with Docker

```bash
docker compose up --build
```

This starts the API (with migrations applied automatically) alongside a PostgreSQL database. The API is available at `http://localhost:8000`.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`:
- `ruff check` and `ruff format --check`
- the full pytest suite with coverage reporting
- on push to `main`: builds the Docker image and publishes it to GitHub Container Registry (`ghcr.io/<owner>/<repo>`)

## Deployment

`render.yaml` defines a [Render](https://render.com) Blueprint: a Dockerized web service plus a managed Postgres database. Connect the repo on Render and it provisions both, wiring `DATABASE_URL` (auto-converted to the `asyncpg` driver scheme) and a generated `SECRET_KEY`. Migrations run automatically via the service's pre-deploy command.

## Data Model

- **User** — account holder, owns accounts/categories/budgets
- **Account** — a financial account (checking, savings, credit, etc.)
- **Category** — spending category, supports parent/child hierarchy
- **Transaction** — a single income or expense entry tied to an account
- **Budget** — a spending limit per category over a period (weekly/monthly/yearly)

## Project Structure

```
app/
├── api/
│   ├── deps.py          # shared dependencies (DB session, current user)
│   ├── ownership.py      # shared ownership-check helpers
│   └── routes/          # API route modules
├── core/
│   └── security.py       # password hashing & JWT helpers
├── models/                # SQLAlchemy ORM models
├── schemas/               # Pydantic request/response schemas
├── config.py              # app settings
├── database.py            # engine/session setup
└── main.py                # FastAPI app entrypoint
alembic/                    # database migrations
tests/                       # pytest suite
```

## API Overview

- `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`
- `GET|POST /accounts`, `GET|PATCH|DELETE /accounts/{id}`
- `GET|POST /categories`, `GET|PATCH|DELETE /categories/{id}` (supports parent/child hierarchy)
- `GET|POST /transactions`, `GET|PATCH|DELETE /transactions/{id}` (filter by account/category/type/date range, sort, paginate)
- `POST /transactions/import` — upload a CSV (`date, description, amount, category`) to bulk-import transactions
- `GET|POST /budgets`, `GET|PATCH|DELETE /budgets/{id}` — tracks spend vs. limit for the current period
- `GET /reports/summary` — income/expenses/net for a date range (defaults to current month)
- `GET /reports/by-category` — spending breakdown by category for a date range
- `GET /reports/trends` — month-over-month income/expenses/net for the last N months
