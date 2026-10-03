"""Ensure local monitoring and admin credentials exist in server/.env."""
from pathlib import Path
import secrets
import subprocess
import string

server_root = Path(__file__).resolve().parent.parent
env_path = server_root / '.env'


def _random_password(length=24):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# A single shared admin password for both Django and Grafana.
shared_admin_password = _random_password()

required = {
    'OBSERVABILITY_TOKEN': secrets.token_hex(32),
    'SECRET_KEY': secrets.token_urlsafe(48),
    # Django superuser — provisioned by docker-entrypoint.sh → ensure_default_admin.
    'DEFAULT_ADMIN_EMAIL': 'admin@proace.local',
    'DEFAULT_ADMIN_PASSWORD': shared_admin_password,
    'DEFAULT_ADMIN_FIRST_NAME': 'Admin',
    'DEFAULT_ADMIN_LAST_NAME': 'User',
    'DEFAULT_ADMIN_GENDER': 'male',
    'DEFAULT_ADMIN_PHONE': '+2348000000001',
}

existing = {}
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        existing[key.strip()] = value.strip()
else:
    env_path.write_text('')
    env_path.chmod(0o600)

missing = [f'{key}={value}' for key, value in required.items() if not existing.get(key)]
if missing:
    prefix = '\n' if env_path.read_text() and not env_path.read_text().endswith('\n') else ''
    with env_path.open('a') as target:
        target.write(prefix + '\n'.join(missing) + '\n')
    print(f'Generated {len(missing)} missing credential(s) in .env')

network = existing.get('COMMERCE_NETWORK', 'commerce-network')
inspection = subprocess.run(
    ['docker', 'network', 'inspect', network],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=False,
)
if inspection.returncode:
    subprocess.run(['docker', 'network', 'create', network], check=True)

print(f'Local credentials and Docker network {network!r} are ready.')
print()
print('Logins:')
admin_email = existing.get('DEFAULT_ADMIN_EMAIL') or required.get('DEFAULT_ADMIN_EMAIL', '')
admin_pw = existing.get('DEFAULT_ADMIN_PASSWORD') or required.get('DEFAULT_ADMIN_PASSWORD', '')
if admin_email:
    print(f'  Django admin:  http://127.0.0.1:8000/admin/  →  {admin_email} / {admin_pw}')
    print(f'  Grafana:       http://127.0.0.1:3002          →  {admin_email} / {admin_pw}')
    print('  ✓ Django and Grafana share the same admin credentials.')
