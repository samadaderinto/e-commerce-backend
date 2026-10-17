from __future__ import annotations

import logging
from unittest.mock import patch

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from observability.logging import JsonFormatter, request_context
from observability.middleware import ObservabilityMiddleware
from observability.stages import request_stages, stage


@override_settings(OTEL_TRACING_ENABLED=False)
class RequestStageTests(SimpleTestCase):
    def test_stages_are_request_local_and_correlated(self) -> None:
        def respond(request: HttpRequest) -> HttpResponse:
            with stage("search"):
                self.assertIsNotNone(request_stages.get())
            return HttpResponse("ok")

        middleware = ObservabilityMiddleware(respond)
        with patch("observability.middleware.logger.info") as info:
            response = middleware(RequestFactory().get("/api/v1/products/"))
        extra = info.call_args.kwargs["extra"]
        self.assertGreaterEqual(extra["stage_durations_ms"]["search"], 0)
        self.assertRegex(response["X-Request-ID"], r"^[a-f0-9]{32}$")
        self.assertRegex(response["Server-Timing"], r"^app;dur=\d+\.\d{2}, db;dur=\d+\.\d{2}$")
        self.assertIsNone(request_stages.get())
        self.assertEqual(request_context.get(), {})
        self.assertIn("stage_durations_ms", JsonFormatter().format(
            logging.makeLogRecord({"stage_durations_ms": {"search": 1.2}})
        ))

    def test_exception_resets_request_context(self) -> None:
        def fail(request: HttpRequest) -> HttpResponse:
            with stage("hydrate"):
                raise RuntimeError("diagnostic fixture")

        with self.assertRaises(RuntimeError):
            ObservabilityMiddleware(fail)(RequestFactory().get("/api/v1/products/"))
        self.assertIsNone(request_stages.get())
        self.assertEqual(request_context.get(), {})

    def test_stage_names_are_bounded_and_no_request_is_a_noop(self) -> None:
        with stage("search"):
            self.assertIsNone(request_stages.get())
        with self.assertRaises(ValueError):
            with stage("user-controlled-query"):
                self.fail("unreachable")
