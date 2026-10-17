# Latency and query performance

## Request tracing and safe search caching

### Catalog and transport optimizations

Uncached catalog pagination beyond page one uses a narrow ordered-ID query followed by hydration of at most 24 current product graphs. Page one uses the ordering index directly and retains the existing five-query budget. Exact count/filter/order semantics and page-number API contracts are unchanged. Migration `product.0015` adds created/ID and category/created/ID indexes. Deeper pages cost one additional bounded hydration query in exchange for avoiding sorting/offsetting wide joined payloads and review subqueries. Public snapshot HIT validation remains unchanged.

Snapshot misses are coalesced by a per-snapshot two-second cache-add lease. Followers poll for at most 200 ms and revalidate any reusable payload before returning; timeout falls back to normal generation. Leases expire rather than unconditional deletion, avoiding release of a newer owner's lease. Errors/invalid responses are not cached. Authenticated, transactional and search reads still bypass public catalog snapshots. The lease is a performance aid, never a business lock, and cache failures retain the existing explicit error policy. Serializer image resolution is memoized only inside a single response.

The reusable Elasticsearch client now includes `ELASTICSEARCH_CONNECTIONS_PER_NODE` (default 32, bounded 1–64) in its process-local configuration. This addresses connection-pool waiting without changing all-term fuzzy relevance, filters, totals or pagination. Partial/timed-out search results use the SQL fallback instead of being treated as complete. Size this pool with worker counts, Elasticsearch capacity and database connection budgets; more connections are not universally faster.

### Dedicated notification stream process

The dedicated image installs `requirements-stream.txt` through `INSTALL_STREAM_POOL=true`. PostgreSQL connections are returned after access checks to a process-local pool (`min_size=0`, `max_size=4`, acquisition timeout 3 seconds), avoiding a fresh database authentication on each heartbeat. `CONN_MAX_AGE=0` is required for Django pooling. Budget up to four physical PostgreSQL connections per stream worker, including idle pooled sockets. Non-Compose dedicated stream deployments must install this extra requirements file; ordinary API images do not require it.

Compose runs `notification-stream` with the same image and normal authentication/security stack but restricted URLconf `notification.stream_urls` (SSE and health probes only). It has no published host port, runs no startup migrations, and isolates its metrics files from API processes. Its database connections use `CONN_MAX_AGE=0` and are released after access rechecks, before Redis waits, and on stream cleanup; it must not retain one idle database socket per stream thread. Cleanup never closes an enclosing atomic transaction. Defaults: `STREAM_WORKERS=1`, `STREAM_THREADS=32`; finite WSGI capacity remains, so this is process isolation, not an unlimited async-streaming architecture. Budget database connections across API, streams, workers and scheduler before scaling.

Next.js preserves the same-origin browser URL and sends only `notifications/stream` to `NOTIFICATION_STREAM_URL`. Compose configures `CONTAINER_NOTIFICATION_STREAM_URL` as `http://notification-stream:8000/api/v1`. Local `npm run dev` can leave `NOTIFICATION_STREAM_URL` blank to use `API_URL`. Refresh calls always go to the ordinary API and share the same refresh-deduplication key across streams and non-stream requests. No automatic fallback to the ordinary API is used when an explicitly configured stream process fails, preventing stream load from silently returning to the interactive pool. Existing reconnect behavior, user-scoped Redis subscription and periodic account/credential-version checks remain intact.

Targeted refresh after changes: rebuild `api notification-worker celery-beat notification-stream`, then `client`. Existing datasets/volumes are preserved. To roll back stream routing only, set `CONTAINER_NOTIFICATION_STREAM_URL=http://api:8000/api/v1` and recreate `client`; API pool isolation is then lost, so do not lower API thread capacity on that basis.

Every instrumented API request generates its own opaque `X-Request-ID`; caller-supplied IDs do not override it. `Server-Timing` reports inclusive application and SQL wall durations, not database CPU time. The Next.js proxy forwards only validated request IDs, HIT/MISS/BYPASS catalog flags and numeric application/SQL timings. Its added `proxy` timing is inclusive elapsed handler time through response preparation, not a measure of proxy-only overhead or stream-body duration. It does not forward arbitrary backend headers, cookies, secrets, SQL or internal URLs.

Internal JSON logs include `stage_durations_ms` for bounded catalog stages: `catalog_cache`, `search`, `hydrate`, and `serialize`. Search hydration evaluates the ORM graph before timing serialization. These measurements exclude some rendering/middleware/queueing work and are not exhaustive additive accounting. Stage context is request-local, reset after failures, and produces matching spans when OpenTelemetry is enabled. No search terms, IDs, SQL text or business payloads are added to stage logs. Correlate individual proxy measurements with API logs by request ID rather than subtracting percentiles from independent batches.

`SEARCH_REQUEST_CACHE_ENABLED=true` enables explicit Elasticsearch shard request caching for anonymous nontransactional searches. Set it to `false` to compare or disable. The cache key is Elasticsearch's complete search request body, including filters, sort, offset, size and total-hit policy; cached entries invalidate at index refresh. Django always hydrates current matching products from PostgreSQL and recomputes recipient-specific serialization. No serialized Django search payload or authentication data is shared in Redis. Authenticated/transactional callers do not opt in. `_source` is omitted because only hit IDs and totals are used; relevance, fuzzy clauses and `track_total_hits=True` remain unchanged. Existing worker-indexing/refresh eventual consistency still applies to membership and totals. This is not immediate transactional search consistency.

Verify caching with repeated identical queries, `indices.stats(metric="request_cache")` deltas, equality of IDs/order/count with cache disabled, and isolated temporary-index refresh tests. Do not clear production caches or modify live products to test invalidation. See [Elasticsearch 8.15 cache documentation](https://www.elastic.co/guide/en/elasticsearch/reference/8.15/shard-request-cache.html).

## Worker/thread trials

Keep source, search cache mode, dataset, warmup, concurrency and benchmark duration fixed while comparing Gunicorn configurations. Record p95/p99, error counts, cache hits, API process memory and background/stream behavior. The default remains two processes and 32 threads until evidence covers both interactive traffic and long-lived notification streams. Anonymous-only improvements are not sufficient to adopt fewer global thread slots. Use a temporary Compose override for `WEB_CONCURRENCY`/`GUNICORN_THREADS`, disable startup migrations during trials, recreate only `api`, then restore the base Compose configuration. Never alter database/Redis/Elasticsearch volumes for a trial.

All generated raw metrics, trial overrides and reports belong under Git-ignored `qa-reports/performance-testing/`. Run load tests sequentially; run functional checks separately so they do not distort benchmark CPU/memory. These local results include Docker/host contention and are not production capacity estimates.

### Authenticated stream contention result

A local follow-up compared 2 processes × 32 threads with 2 × 8 under 8 and 20 authenticated SSE connections plus 25 catalog clients. With 20 requested streams, 2 × 32 established all 20 and completed 974 catalog requests without errors. The 2 × 8 candidate established at most 13, recorded 16 stream-read timeouts across reconnect attempts, and timed out 51 of 1,099 catalog requests (4.64%). Its aggregate p95 was misleadingly low because timeout requests fell beyond p95; p99 exceeded five seconds. Keep the global 2 × 32 default. Short anonymous-only or successful-only latency improvements must not override stream admission/reliability failures.

This exploratory test reused one demo shopper across independent authenticated connections, not 20 distinct users. It exercised real Redis-backed SSE and PostgreSQL/Redis/Elasticsearch readiness I/O, not live carrier/payment providers, long-duration token refresh, or production hardware. It did not publish business events or submit checkout/shipping quotes. Compare a dedicated stream process or async streaming stack in a separately scoped deployment trial before lowering request thread capacity. Generated evidence is in Git-ignored `qa-reports/performance-testing/load/stream-worker-trial-2026-10-16.*`.

## Local Celery worker memory

`server/compose.yaml` explicitly sets the notification worker pool from
`CELERY_WORKER_CONCURRENCY`, defaulting to `2`. This local Compose command does not
change Celery defaults for host-managed workers. Deployments that reuse this
Compose file, including the HostGator helper, inherit the default unless they set
an explicit override; choose their pool size from deployment-specific load tests.
The API, scheduler,
Elasticsearch heap and container limits are unchanged. Prefetch multiplier, late
acknowledgements, retry/recovery and delivery durability remain unchanged; actual
prefetch count scales with the smaller pool.

Apply the local default from the repository root:

```sh
docker compose -f server/compose.yaml up -d --build --no-deps notification-worker
```

Restore the previous seven-process pool without rebuilding other services:

```sh
CELERY_WORKER_CONCURRENCY=7 docker compose -f server/compose.yaml up -d --no-deps notification-worker
```

An exported environment override takes precedence over `.env`; remove that override
to use the default again. Tune production concurrency against queue depth, task
wait time and throughput rather than copying this local value blindly. Compare
equally warmed workers; old process age can inflate memory comparisons. Controlled
local indexing jobs do not establish real email/push provider latency or inbox
delivery. Generated profiles belong under `qa-reports/performance-testing/volume/`.

The 2026-10-16 local 7→2→7→2 trial used identical 35-job warm-ups and three
100-job indexing bursts per pool. In the warm-cache control/final runs, median
warmed worker memory fell from 539.1 to 202.7 MiB (62.4%). Median burst throughput
was 83.3 versus 91.9 jobs/second, and the median of burst p95 publish-to-start
delays was 922 versus 941 ms. All 1,340 benchmark index operations were confirmed
across four trials, with no benchmark failures. These short local indexing
results support the local default, not a general production speedup or memory SLA.

Order-list endpoints batch their related data per selected page. Customer history
loads its refunds and store fulfillments in two additional queries and joins the
buyer record. Merchant history preloads fulfillments once and loads current cart
items only for legacy orders without immutable item snapshots. Snapshot-backed
orders do not read current cart items for serialization.

This is request-local loading, not shared response caching. Customer ownership,
merchant store scope, safe refund messages, variant download links, filtering,
pagination counts and fresh state on the next request remain authoritative.

## Offline regression check

```sh
.venv/bin/pytest server/storefront/test_order_query_performance.py -q -s
```

The fixture compares 1-row and 20-row pages for customer history, merchant
snapshot-backed history and legacy merchant history. It checks both query-growth
and total-query budgets, plus refund freshness, ownership and avoiding unnecessary
cart reads. The profile prints `(query count, median milliseconds)` from five
in-process SQLite requests per scenario. Those timings exclude HTTP transport,
the Next.js proxy, Redis, PostgreSQL and real browser rendering; they are not a
production p50/p95 or an SLA. Query counts are the regression metric.

## Live follow-up

Once the local infrastructure is healthy, use the existing load runner to compare
equivalent warm/cold runs, then collect authenticated order/dashboard p50/p95,
database time and payload sizes under representative concurrency. Keep generated
reports under `qa-reports/performance-testing/` and untracked. Do not claim a live
improvement from offline timing alone.

## Frontend route bundles

The catch-all server page resolves routes and redirects, then selects a component
from the client-side `route-components.tsx` dynamic-import boundary. SSR remains
enabled. Shared shell, theme and providers stay eager; unrelated feature bundles
are not downloaded on every route.

Firebase application/messaging libraries load only after the same-origin config
endpoint confirms push availability. Recipient checks, registration ownership and
unsubscribe-on-unmount behavior remain intact. No private-data cache or freshness
settings were changed.

Production-build Chrome checks with mocked API data on 2026-10-15 measured decoded
JavaScript response bodies after each cold-context route settled: Home and Shop
fell from 1,146,414 to 672,802 bytes (41.3%), Cart to 763,249 (33.4%), and payouts to
782,743 (31.7%). These are uncompressed code-size measurements, not network latency,
Core Web Vitals or production p95 claims. More chunk requests are expected.

Run the split-route browser regression against a production server:

```sh
E2E_BASE_URL=http://127.0.0.1:3001 npx playwright test --config client/playwright.config.ts client/tests/frontend-loading.spec.ts
```

Generated before/after profiles belong in the ignored
`qa-reports/performance-testing/load/` directory. Continue with real-device request
waterfalls and navigation timings before changing cache staleness or adding caches.
