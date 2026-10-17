# Social account linking

Customers can use email/password, Google or Apple without separate profiles. The
connected-accounts panel is available on `/account/profile` and `/settings`.
Staff, business administrators and technical administrators continue to use their
existing password authentication and cannot connect social providers.

## Database and identity resolution

Migration `core.0023_socialaccount` adds `SocialAccount` with `user`, `provider`,
provider `subject`, last verified provider `email`, `connected`, `created_at` and
`updated_at`. `(provider, subject)` uniquely owns a provider identity; a conditional
unique constraint permits one connected identity per user/provider. Tokens,
provider passwords and OAuth refresh tokens are not stored.

A disconnected identity remains as an inactive ownership record. This prevents a
later login from silently relinking the same identity by email. A customer can
explicitly reconnect it in settings, or connect another account after disconnecting
the previous one. Retired identity ownership is preserved when replacing accounts.

On login, the backend verifies the provider credential and verified email, resolves
the stable subject first, and rejects disconnected identities. Connected identities
continue to resolve to their original user even if the provider email changes; the
primary application email is preserved. For an unseen identity, a verified matching
email links an existing active customer account; otherwise a new customer is
created with an unusable password. Pending/inactive accounts and operator accounts
are never activated or bypassed by social login. Existing social accounts receive
an identity record on their next verified login; migration does not invent provider
subjects from old emails.

Identity operations lock the user row and rely on database uniqueness constraints
for cross-user conflicts. Linking does not create duplicate profiles or reassign an
identity already owned by another user. Repeated login does not create another
referral reward. Newly created social customers retain referral, Google avatar
import and phone-completion behavior.

## API routes

All browser calls use the same-origin `/api/` proxy; the Django paths below are the
server endpoints. Requests require an authenticated session except existing public
social sign-in endpoints.

| Django endpoint | Request / behavior |
| --- | --- |
| `GET /api/v1/auth/methods/` | Returns `has_password`, `can_link`, and the caller's connected provider/email rows. |
| `POST /api/v1/auth/connect/google/` | Fresh `credential`; optional `current_password` for a different provider email. |
| `POST /api/v1/auth/connect/apple/` | Fresh `credential`, optional Apple's `user` name payload, and optional `current_password`. |
| `POST /api/v1/auth/disconnect/google/` | No payload required; disconnects only the caller's identity. |
| `POST /api/v1/auth/disconnect/apple/` | Same lockout guard and ownership rules. |
| `POST /api/v1/auth/password/` | Social-only password setup: `provider`, fresh `credential`, strong `password`, and optional Apple name payload. |
| `POST /api/v1/auth/google/` or `/apple/` | Existing public sign-in routes now resolve connected identities by subject before email. |

Connecting a verified identity matching the primary email proves ownership of that
email. Connecting a different email requires the caller's current password. A
social-only customer must set a password first to connect a different email.
An already connected provider must be disconnected before connecting another
identity for that provider.

Disconnect cannot remove the last active method: either a usable password or
another connected provider must remain. Empty/unusable password values do not
count. No API accepts a target user ID from the browser. Disconnect is idempotent
and affects future provider login; it does not terminate current sessions.

Social-only password setup requires fresh authentication through an identity
belonging to the profile (or a verified matching primary email for legacy accounts).
Disconnected or another user's identities cannot authorize password setup. Password
validation is identical to regular account password rules. Setup rotates the
credential version, invalidating older sessions, and returns renewed tokens for the
current session. The Next.js proxy stores these in HTTP-only cookies and strips
them from the browser response. Existing passwords use `/password/change/` instead.

Connect/disconnect changes and password setup create recipient-scoped security
notifications with the existing transactional delivery outbox. Repeating an
unchanged connect/disconnect does not send another security notice. Provider errors
produce clean API guidance; credentials are not logged or returned.

## Frontend flow

The panel fetches the authenticated methods endpoint, displays provider emails and
password status, and provides connect/disconnect controls. Google uses its official
account-selection button; Apple uses its configured popup. Connect passes the fresh
credential to the linking endpoint without signing into another app profile.
A different-email connection includes password confirmation.

Disconnect asks for confirmation and disables the last-method control; the backend
enforces the same rule regardless of client state. Successful changes refresh
methods/profile queries. Social-only accounts can enter a new password and confirm
an existing provider to enable password login. No browser storage contains app JWTs.

Provider configuration remains required: matching Google client IDs on frontend and
backend, authorized JavaScript origins, and Apple Services ID/registered return URL.
Local mock tokens exist only for development/tests. Production provider verification
must be enabled with debug/test mode off. Test coverage verifies identity ownership,
email changes, last-method protection, revocation/reconnect, provider replacement,
password setup proof and operator boundaries. Real Apple popup and provider delivery
flows require configured provider credentials and a live browser test.

Real Google credentials require a configured client ID and successful Google verification. Real Apple credentials require a configured client ID and signature/audience verification. Failed provider verification never falls back to unsigned claims, even in debug mode; only explicit mock/dev tokens are supported for offline non-production tests.
