# Engineering documentation

Start with [getting started](getting-started.md) to run the application, then use
the guide for the part of the system you are working on.

## Application guides

| Guide | What it explains |
| --- | --- |
| [Architecture](architecture.md) | Repository modules, request flow, authentication, and API routes |
| [Backend](backend.md) | Domain ownership, commerce rules, persistence, and background work |
| [Frontend](frontend.md) | Routes, components, state, forms, and the same-origin proxy |
| [Access control](access-control.md) | Customer, merchant team, staff, and administrator permissions |
| [UI and events](ui-and-events.md) | Application navigation and interaction flows |
| [Social account linking](social-account-linking.md) | Google/Apple sign-in and account linking |
| [Picture search](visual-search.md) | Local model service, recognition flow, and relevance limits |
| [Shipping integrations](shipping-integrations.md) | Carrier configuration, sandboxes, rates, and fulfillment |

## Operations guides

| Guide | What it explains |
| --- | --- |
| [Getting started](getting-started.md) | Dependencies, environment files, demo data, and local startup |
| [Infrastructure](infrastructure.md) | Compose stacks, networks, persistence, and gateway configuration |
| [Deployment](deployment.md) | HostGator setup, secrets, rollout, backups, and checks |
| [Observability](observability.md) | Metrics, logs, traces, and monitoring access |
| [Performance](performance.md) | Caching, worker/thread budgets, and test methodology |

## Working conventions

The root [README](../README.md) is the entry point. This directory contains
maintained explanations of the current codebase, not a chronological change log.
Keep source behavior and the relevant guide synchronized when making changes.

Django owns business rules and permissions. Browser API calls go through
Next.js `/api/*`; tokens remain in HTTP-only cookies. Production secrets must
not be committed. Generated QA output belongs under ignored `qa-reports/`.

From the repository root, run the standard offline checks:

```sh
npm run typecheck
npm run test:unit
.venv/bin/pytest server/
```

Use `npm run test:integration` and `npm run test:e2e` with running seeded services.
Use the performance guide when preparing a load test; record the dataset,
hardware, endpoint mix, achieved rate, latency, and errors.

