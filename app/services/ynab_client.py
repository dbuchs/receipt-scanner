from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import get_settings

YNAB_BASE = "https://api.ynab.com/v1"
YNAB_AUTH_BASE = "https://app.ynab.com/oauth"


class YnabClient:
    """Thin async httpx wrapper around the YNAB v1 API."""

    def __init__(self, access_token: str):
        self._token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    # ── Budgets ────────────────────────────────────────────────────────────────

    async def get_budgets(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{YNAB_BASE}/budgets", headers=self._headers())
            r.raise_for_status()
            return r.json()["data"]["budgets"]

    # ── Transactions ───────────────────────────────────────────────────────────

    async def get_transactions(
        self,
        budget_id: str,
        since_date: str | None = None,
        account_id: str | None = None,
    ) -> list[dict]:
        url = (
            f"{YNAB_BASE}/budgets/{budget_id}/accounts/{account_id}/transactions"
            if account_id
            else f"{YNAB_BASE}/budgets/{budget_id}/transactions"
        )
        params: dict = {}
        if since_date:
            params["since_date"] = since_date
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()["data"]["transactions"]

    # ── Categories ─────────────────────────────────────────────────────────────

    async def get_categories(self, budget_id: str) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{YNAB_BASE}/budgets/{budget_id}/categories", headers=self._headers()
            )
            r.raise_for_status()
            groups = r.json()["data"]["category_groups"]
            cats: list[dict] = []
            for g in groups:
                cats.extend(g.get("categories", []))
            return cats

    # ── Accounts ───────────────────────────────────────────────────────────────

    async def get_accounts(self, budget_id: str) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{YNAB_BASE}/budgets/{budget_id}/accounts", headers=self._headers()
            )
            r.raise_for_status()
            return r.json()["data"]["accounts"]

    # ── Update transaction ─────────────────────────────────────────────────────

    async def update_transaction(
        self, budget_id: str, transaction_id: str, data: dict
    ) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{YNAB_BASE}/budgets/{budget_id}/transactions/{transaction_id}",
                headers=self._headers(),
                json={"transaction": data},
            )
            r.raise_for_status()
            return r.json()["data"]["transaction"]

    # ── OAuth helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def get_authorize_url(state: str) -> str:
        s = get_settings()
        return (
            f"{YNAB_AUTH_BASE}/authorize"
            f"?client_id={s.YNAB_CLIENT_ID}"
            f"&redirect_uri={s.YNAB_REDIRECT_URI}"
            f"&response_type=code"
            f"&state={state}"
        )

    @staticmethod
    async def exchange_code(code: str) -> dict:
        s = get_settings()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{YNAB_AUTH_BASE}/token",
                data={
                    "client_id": s.YNAB_CLIENT_ID,
                    "client_secret": s.YNAB_CLIENT_SECRET,
                    "redirect_uri": s.YNAB_REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code": code,
                },
            )
            r.raise_for_status()
            return r.json()

    @staticmethod
    async def refresh_token(refresh_token: str) -> dict:
        s = get_settings()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{YNAB_AUTH_BASE}/token",
                data={
                    "client_id": s.YNAB_CLIENT_ID,
                    "client_secret": s.YNAB_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            r.raise_for_status()
            return r.json()
