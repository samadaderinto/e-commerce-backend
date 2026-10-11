"""Prove network overlap, deterministic results, and cancellation without a carrier account."""

import asyncio
import json
from decimal import Decimal
from unittest.mock import patch

import httpx
from asgiref.sync import async_to_sync
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from payment.async_carriers import usps_prices
from payment.carriers import calculate_carrier_rates


class AsyncCarrierTests(SimpleTestCase):
    def test_prices_overlap_and_preserve_service_order(self) -> None:
        async def scenario() -> None:
            started: list[str] = []
            all_started = asyncio.Event()

            async def handle(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                if request.url.path.endswith("/token"):
                    self.assertEqual(body["client_id"], "fixture-client")
                    return httpx.Response(200, json={"access_token": "fixture-token"})
                self.assertEqual(
                    request.headers["Authorization"], "Bearer fixture-token"
                )
                self.assertEqual(body["weight"], 2.0)
                started.append(body["mailClass"])
                if len(started) == 3:
                    all_started.set()
                # Sequential requests would time out before reaching this barrier.
                await asyncio.wait_for(all_started.wait(), timeout=1)
                return httpx.Response(
                    200,
                    json={
                        "totalBasePrice": {"ground": 5, "priority": 9, "express": 30}[
                            body["mailClass"]
                        ]
                    },
                )

            client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
            with patch(
                "payment.async_carriers.httpx.AsyncClient", return_value=client
            ) as factory:
                rows = await usps_prices(
                    "https://carrier.test",
                    "fixture-client",
                    "fixture-secret",
                    {"weight": 2.0},
                    ("ground", "priority", "express"),
                )
            self.assertEqual([row["totalBasePrice"] for row in rows], [5, 9, 30])
            self.assertEqual(factory.call_args.kwargs["limits"].max_connections, 3)
            self.assertTrue(client.is_closed)

        async_to_sync(scenario)()

    def test_one_failure_cancels_siblings_before_closing_pool(self) -> None:
        async def scenario() -> None:
            started = 0
            ready = asyncio.Event()
            cancelled: list[str] = []

            async def handle(request: httpx.Request) -> httpx.Response:
                nonlocal started
                if request.url.path.endswith("/token"):
                    return httpx.Response(200, json={"access_token": "fixture"})
                service = json.loads(request.content)["mailClass"]
                started += 1
                if started == 3:
                    ready.set()
                await ready.wait()
                if service == "ground":
                    return httpx.Response(503, json={"internal": "do not expose"})
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.append(service)
                    raise

            client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
            with patch("payment.async_carriers.httpx.AsyncClient", return_value=client):
                with self.assertRaises(httpx.HTTPStatusError):
                    await usps_prices(
                        "https://carrier.test",
                        "fixture",
                        "fixture",
                        {},
                        ("ground", "priority", "express"),
                    )
            self.assertCountEqual(cancelled, ["priority", "express"])
            self.assertTrue(client.is_closed)

        async_to_sync(scenario)()

    @patch.dict("os.environ", {"SHIPPING_RATE_MODE": "live"})
    @patch(
        "payment.carriers.live_rates",
        side_effect=httpx.ReadTimeout("internal upstream details"),
    )
    def test_timeout_returns_clean_shipping_error(self, mock_rates: object) -> None:
        with self.assertRaises(ValidationError) as error:
            calculate_carrier_rates(
                "USPS", "33602", "33601", Decimal("2"), Decimal("20"), True
            )
        self.assertEqual(
            str(error.exception.detail["carrier"]),
            "USPS rates are unavailable. Choose another carrier or retry.",
        )
        self.assertNotIn("internal", str(error.exception.detail))

    def test_missing_credentials_do_not_make_network_calls(self) -> None:
        with patch("payment.async_carriers.httpx.AsyncClient") as client:
            with self.assertRaises(ValueError):
                async_to_sync(usps_prices)(
                    "https://carrier.test", "", "", {}, ("ground",)
                )
        client.assert_not_called()
