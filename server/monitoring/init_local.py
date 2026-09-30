"""Generate local monitoring credentials without printing or overwriting them."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent
(root / 'secrets').mkdir(exist_ok=True)
(root / 'logs').mkdir(exist_ok=True)
for path, value, mode in (
    (root / 'secrets/metrics-token', secrets.token_hex(32) + '\n', 0o644),
    (root / '.env', 'GRAFANA_ADMIN_PASSWORD=' + secrets.token_urlsafe(32) + '\n', 0o600),
):
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        continue
    with os.fdopen(descriptor, 'w') as target:
        target.write(value)
print('Local credentials ready. Grafana password: monitoring/.env; scrape token: monitoring/secrets/metrics-token.')
