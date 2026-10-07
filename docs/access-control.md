# Back-office roles and staff activation

The API is authoritative. The client hides consumer routes and navigation for administrative accounts and sends them to `/admin`. All protected JSON endpoints use `Authorization: Bearer <access JWT>`. Browser clients use the Next.js proxy, which keeps JWTs in HTTP-only cookies. Public authentication and catalog endpoints do not require a token.

## Roles

| Role | Database flags | Scope |
| --- | --- | --- |
| Technical admin | `is_superuser=true`, `is_staff=true` | Root business operations and technical monitoring |
| Business admin | `is_business_admin=true`, `is_staff=true`, `is_superuser=false` | Business operations, staff management, seller verification, official stores |
| Staff | `is_staff=true`, both admin flags false | Operational dashboards, customer order review, global backoffice data manipulation, and all Proace official stores in seller interface |
| Customer / seller | All admin flags false | Consumer features; sellers also manage their own stores |

`GET /api/v1/me/` and successful login responses include `role`, `is_staff`, `is_superuser`, `is_business_admin`, and `must_change_password`. Role flags are read-only in self-service serializers. Administrative peers cannot modify, block, or demote either kind of administrator. The staff list excludes both kinds of admin. Business admin creation is an operator-only management command; ordinary API payloads cannot grant that role or root permissions.

## Global operational dashboard

All active back-office accounts—staff, business administrators, and technical administrators—can view the global commerce dashboard and its order-status chart, revenue and order totals, user/store/catalog health, top stores, and recent orders. They can also perform support operations when a merchant cannot access their account:

- deactivate or reactivate coupons;
- permanently delete coupons only when they have never been redeemed (used coupons remain as audit history and can only be deactivated);
- approve or decline a pending refund once, recording the processor and processing time;
- override a non-refunded order's operational status with a mandatory support reason. The change is appended to tracking history and the customer is notified.

Changing an order to `refunded` is excluded from the general status control. Staff must use the refund workflow so wallet credits and merchant ledger reversals remain consistent. Used coupon history and completed refund decisions are immutable through these controls.

Grafana remains technical-admin-only in the application. Business administrators and staff can use commerce charts but do not receive Grafana links or credentials.

## Endpoint permission matrix

Paths below have prefix `/api/v1/`. Staff members have global backoffice access by default to view and manage data across all stores via the centralized Backoffice platform (`/admin`, `admin/staff/...`), deprecating manual store-to-staff assignment. In the Seller Interface (`/merchant`, `StoreViewSet`), Staff and Administrators are strictly limited to app-owned Proace official stores (`is_official=True`) and are strictly forbidden from accessing third-party/independent seller dashboards.

| Endpoint / operation | Customer / seller | Staff | Business admin | Technical admin |
| --- | --- | --- | --- | --- |
| `auth/login`, `register`, `verify`, `forgot`, `reset`, `refresh`, `logout` | Public action-specific authentication | Same | Same | Same (reset syncs MinIO/Grafana) |
| `me` GET/PATCH | Own account; no role changes | Same | Same | Same |
| `password/change` POST | Own account | Own account | Own account | Own account (syncs MinIO/Grafana) |
| `products`, public store catalog GET | Public | Public preview API | Public preview API | Public preview API |
| `cart`, `wishlist`, `addresses`, `wallet`, `orders` collection | Own only | Denied | Denied | Denied |
| `products/{id}/reviews` GET/POST/DELETE | Authenticated (posting: verified buyer; DELETE: own review) | Moderation DELETE allowed | Moderation DELETE allowed | Moderation DELETE allowed |
| `checkout/validate-coupon` POST | Cart discount validation | Denied | Denied | Denied |
| `checkout`, shipping rates, wallet session/confirm | Own only (split-tender allowed) | Denied | Denied | Denied |
| `orders/{id}/cancel` POST | Own pending/confirmed orders | Denied | Denied | Denied |
| `orders/{id}/refund` | Own order | Denied | Denied | Denied |
| `orders/{id}`, `orders/{id}/tracking` GET | Own order | Customer order review | Any order | Any order |
| `stores` GET and store detail/profile/insights/orders | Owned | Proace official stores (`is_official=True`) | Proace official stores (`is_official=True`) | Proace official stores (`is_official=True`) |
| `stores` POST or `stores/create` | Seller onboarding, pending approval | Denied | Official, active store | Official, active store |
| `stores/{id}/delete` DELETE | Denied | Denied | Allowed | Allowed |
| `stores/{id}/staff` PUT | Denied | Deprecated | Deprecated | Deprecated |
| Store products CRUD, images, specifications, visibility schedules | Owned store | Proace official stores | Proace official stores | Proace official stores |
| Store order tracking POST | Owned store order | Proace official store orders | Proace official store orders | Proace official store orders |
| `admin/stores` GET (Store directory & product catalog) | Denied | Allowed (read-only audit & catalog preview) | Allowed | Allowed |
| `admin/stores`, approve/block seller verification | Denied | Denied | Allowed | Allowed |
| `admin/coupons` GET/POST | Denied | Denied | Allowed | Allowed |
| `admin/staff` list/create/detail/block/unblock | Denied | Denied | Staff targets only | Staff targets only |
| `admin/staff/dashboard`, users, stores, orders, coupons, refund/payout queues GET | Denied | Allowed | Allowed | Allowed |
| `admin/staff/orders/{id}/status/` POST | Denied | Allowed (override shipping status) | Allowed (override shipping status) | Allowed (override shipping status) |
| `admin/staff/users` GET (directory filters) | Denied | Allowed | Allowed | Allowed |
| `admin/staff/users/{id}` PATCH (activate/deactivate) | Denied | Denied | Non-admin targets only | Non-admin targets only |
| `admin/staff/stores/{id}/block` or unblock | Denied | Denied | Allowed | Allowed |
| `admin/staff/payouts` GET / `/process` POST | Denied | Allowed | Allowed | Allowed |
| Refund `/process` POST | Denied | Allowed (refund processing) | Allowed | Allowed |
| Store withdrawal requests POST | Owned store only | Denied | Owned official store only | Owned official store only |
| Notifications | Own recipient inbox | Own inbox (unfiltered global operator notifications) | Own inbox (unfiltered global operator notifications) | Own inbox (unfiltered global operator notifications) |
| Grafana, Silk technical profiling | Denied | Denied | Denied | Separate technical credentials / root session |

Legacy cart and payment viewsets also use the consumer policy. Monitoring scrape endpoints use a separate server-only `OBSERVABILITY_TOKEN`, not commerce JWTs. Keep that service token within technical operations.

## Staff onboarding & authentication flow

`POST /api/v1/admin/staff/` accepts:

```json
{"email":"staff@example.com","first_name":"Taylor","last_name":"Smith","phone1":"+15551234567","gender":"female"}
```

The response is `201` with the staff profile, `is_active=false`, and `staff_email_verified=false`. Password input is rejected. The admin form renders a fixed `••••••••` value without a password form field.

The onboarding workflow operates as follows:

1. **Email verification link**: The newly created staff member receives a signed, 24-hour email verification link.
2. **Account activation & temporary password**: Upon successful email verification via `POST /api/v1/auth/verify/` with the verification token, the system generates a secure temporary password, sets it on the user account, activates the account (`is_active=true`, `staff_email_verified=true`, incrementing `credential_version`), and emails the temporary credentials to the staff member. Reusing the verification link fails.
3. **Forgot password guidance**: The credential email containing the temporary password explicitly advises the staff member:
   > *Please note: You are advised to use the "Forgot Password" flow later to set a permanent, secure password.*
4. **Direct login**: Staff members can immediately log in with the temporary password and begin work without being forced into an initial password change.

## Separation of backoffice vs. internal store access

### 1. Global staff access (store assignment deprecated)
The legacy staff-to-store assignment logic (`Store.assigned_staff` and `PUT /api/v1/stores/{id}/staff/`) is deprecated. All authenticated staff members automatically have global backoffice access to view and manage data across all stores without needing explicit assignment.

### 2. Strict separation of backoffice vs. third-party store interfaces
Administrators and Staff members are strictly forbidden from accessing a third-party seller's internal store dashboard or seller interface (`/merchant` and `StoreViewSet`).
Backoffice interaction with store data is strictly conducted through the centralized Backoffice platform (`/admin` and `StaffViewSet`), providing high-level operational capabilities:
- Updating order shipping statuses (e.g. transitioning from "Shipped" to "Delivered") with required support reasons and customer audit logs;
- Processing, approving, and rejecting refunds with automated wallet credit and merchant ledger reversal;
- Executing overarching database queries, coupon management, user reviews, and customer service actions.

### 3. Proace official stores exception
For "Proace Official Stores" (`is_official=True`, created directly by Administrators), all Staff members and Admins are automatically granted access to the actual Seller Interface (`/merchant` and `StoreViewSet`) upon login. This gives staff the ability to act as the sellers specifically for app-owned official stores, while remaining locked out of third-party stores.

### 4. Backoffice operator notification feed
Notification popups in the backoffice interface deliver an unfiltered feed of all events directed to the operator's inbox without store-based UI dropdown filters. Note that notification feeds remain recipient-specific rather than a global immutable platform audit ledger (BA-16).

### 5. Storefront preview mode for backoffice operators
Backoffice operators (Staff and Admins) audit the public storefront and store catalogs in read-only mode by passing `?preview=1` on `/shop` and `/products/{id}` routes. Consumer shopping operations (cart addition, checkout, wallet creation) remain strictly forbidden at the API level for backoffice accounts. Links generated in backoffice store previews retain `?preview=1` to maintain audit context (BA-17).

## Operator setup

Run migrations before starting the new API:

```sh
.venv/bin/python server/manage.py migrate --settings=codematics.storefront_settings
.venv/bin/python server/manage.py ensure_default_admin --settings=codematics.storefront_settings
```

Configure all six existing `DEFAULT_ADMIN_*` variables described in `.env.example`; this seeds an immutable technical admin and does not overwrite existing users. For a business admin, set a private `BUSINESS_ADMIN_PASSWORD` environment variable, then run:

```sh
.venv/bin/python server/manage.py create_business_admin --settings=codematics.storefront_settings --email business-admin@example.com
```

Existing `is_superuser` accounts are technical admins; existing plain `is_staff` accounts remain staff. Existing staff created by trusted development seeds are already active and do not go through invitation onboarding. Production staff should use invitations.

Grafana remains bound to loopback on port 3002; anonymous authentication and signup are disabled. Sign in using technical credentials configured by `DEFAULT_ADMIN_EMAIL`/`DEFAULT_ADMIN_PASSWORD`. Commerce business admins and staff are not provisioned Grafana accounts. For remote production access, use a private tunnel or a TLS gateway with technical-team-only authentication. Do not enable anonymous access or share Grafana credentials with business users. Silk remains disabled by default and requires an active Django superuser when enabled.
