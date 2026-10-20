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

### Stream capacity

Long-lived SSE connections occupy finite worker/thread slots. Size the dedicated
stream process independently and measure stream admission, reconnect errors,
interactive request latency, and database connections together. Successful-only
latency can hide timeouts; report all attempts and errors. Separate process
isolation does not make WSGI streaming unlimited.

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

Measure equally warmed pools using the same job mix. Record aggregate worker
memory, queue delay, throughput, failures, and provider response time. Indexing
throughput alone is not evidence of email/push delivery capacity.

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

Measure frontend code size separately from network latency and Core Web Vitals.
Record cold/warm navigation waterfalls on representative devices; a smaller
bundle does not by itself establish API throughput.

Run the split-route browser regression against a production server:

```sh
E2E_BASE_URL=http://127.0.0.1:3001 npx playwright test --config client/playwright.config.ts client/tests/frontend-loading.spec.ts
```

Generated before/after profiles belong in the ignored
`qa-reports/performance-testing/load/` directory. Continue with real-device request
waterfalls and navigation timings before changing cache staleness or adding caches.

## Preparing a volume dataset

Use the canonical development seeder without clearing the database:

```sh
docker compose -f server/compose.yaml exec -T api python manage.py populate_fake_data --scale huge --products 6000 --orders 4000 --users 1000 --stores 50 --reviews 3000 --seed 20261020
```

This appends 6,000 products and 4,000 orders, plus supporting records. Known demo
accounts/scenarios may be reused or refreshed. Preserve the existing technical
admin password. The command refuses production mode and rebuilds search after
commit. Check actual counts and indexing completion before benchmarking; never
generate data during a timed load run.

Record the final table counts, eligible public product count, database size,
index size, and endpoint query distribution. A large total count is not the
same as a large working set: repeated first-page cache hits can hide database cost.

## Planning a 5,000 requests/second test

5,000 requests/second is a throughput target, not 5,000 simultaneous users or
5,000 open connections. Define an acceptable p95/p99, error budget, duration,
and endpoint mix before selecting a configuration.

The existing runner is closed-loop and controls concurrent workers:

```sh
npm run test:load -- --url http://127.0.0.1:3000 --concurrency 100 --duration 60
```

Its concurrency setting does not request a fixed arrival rate and cannot certify
a 5,000 RPS target merely by using a large worker count. For rate-target testing,
use an open-loop arrival-rate generator with enough independent load-generation
capacity. Record offered, achieved, and dropped requests separately.

Start with smoke/warmup traffic, then increase offered rates in measured steps
until latency/error limits fail. Measure the real browser-facing proxy path as
well as the direct API path; separate anonymous cached catalog, search,
authenticated reads, writes, and SSE scenarios. Do not include real payment,
carrier-purchase, or email operations in synthetic load.

Run the generator on another machine when measuring server capacity. Track CPU,
memory/swap, network, API queueing, PostgreSQL connections/locks/slow queries,
Redis, Elasticsearch, and worker backlogs. Include unsuccessful requests in
latency/error reporting. Do not weaken normal authentication, ownership, stock,
or financial controls to improve a benchmark.

A 10,000-record addition prepares volume only. Capacity is established by a
sustained representative run on the intended hardware, not by record count,
thread count, or a short cache-hit spike.
