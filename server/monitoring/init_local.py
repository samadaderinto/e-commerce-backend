"""Ensure local monitoring credentials exist in server/.env."""
from pathlib import Path
import secrets
import subprocess

server_root = Path(__file__).resolve().parent.parent
env_path = server_root / '.env'
required = {
    'OBSERVABILITY_TOKEN': secrets.token_hex(32),
    'GRAFANA_ADMIN_PASSWORD': secrets.token_urlsafe(32),
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
