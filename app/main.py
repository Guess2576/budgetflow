from fastapi import FastAPI

from app.api.routes import accounts, auth, budgets, categories, reports, transactions

app = FastAPI(title="BudgetFlow API", version="0.1.0")

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(reports.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
