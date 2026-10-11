"""Bounded concurrent USPS network calls, with no ORM work in the event loop."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


async def usps_prices(
    base: str,
    client_id: str,
    client_secret: str,
    payload: dict[str, Any],
    mail_classes: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not client_id or not client_secret:
        raise ValueError("Carrier credentials missing")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(8.0),
        limits=httpx.Limits(max_connections=3, max_keepalive_connections=3),
    ) as client:
        token_response = await client.post(
            base + "/oauth2/v3/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]

        async def price(mail_class: str) -> dict[str, Any]:
            response = await client.post(
                base + "/prices/v3/base-rates/search",
                headers={"Authorization": f"Bearer {token}"},
                json={**payload, "mailClass": mail_class},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        tasks = [asyncio.create_task(price(value)) for value in mail_classes]
        try:
            return list(await asyncio.gather(*tasks))
        except BaseException:
            # Finish cancellation before closing the shared connection pool.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
