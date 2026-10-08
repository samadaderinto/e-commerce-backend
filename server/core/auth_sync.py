import logging
import os
import shutil
import subprocess
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def is_technical_super_admin(user) -> bool:
    """
    Returns True ONLY if the given user is the technical super admin.
    Business admins (is_business_admin=True) and regular staff return False.
    """
    if not user:
        return False

    # Never treat business admins as technical admin
    if getattr(user, 'is_business_admin', False):
        return False

    # Check is_superuser or email matching technical admin email
    tech_admin_email = os.environ.get('TECHNICAL_ADMIN_EMAIL', getattr(settings, 'DEFAULT_ADMIN_EMAIL', '')).strip().lower()
    user_email = (getattr(user, 'email', '') or '').strip().lower()

    if getattr(user, 'is_superuser', False):
        return True

    if tech_admin_email and user_email == tech_admin_email:
        return True

    return False


def sync_technical_admin_credentials(user, new_password: str) -> dict:
    """
    Synchronizes technical super admin password with external services (Grafana, MinIO).
    Executes safely with error capturing so local password updates are never blocked
    if external services are temporarily unreachable.
    """
    if not is_technical_super_admin(user):
        return {'synced': False, 'reason': 'not_technical_admin'}

    results = {
        'synced': True,
        'grafana': sync_grafana_admin_password(new_password),
        'minio': sync_minio_admin_password(new_password),
    }
    return results


def sync_grafana_admin_password(new_password: str) -> dict:
    """
    Updates the admin password in Grafana via Grafana's HTTP Admin API.
    Endpoint: PUT /api/admin/users/:userId/password
    """
    grafana_url = os.environ.get('GRAFANA_API_URL', 'http://127.0.0.1:3002').rstrip('/')
    # Internal Docker container fallback if run inside docker network
    if '127.0.0.1' in grafana_url or 'localhost' in grafana_url:
        container_host = os.environ.get('GRAFANA_INTERNAL_URL', 'http://grafana:3000').rstrip('/')
    else:
        container_host = grafana_url

    # Check for configured service token or fallback basic auth
    admin_user = os.environ.get('TECHNICAL_ADMIN_EMAIL', os.environ.get('DEFAULT_ADMIN_EMAIL', 'admin@proace.local'))
    auth_token = os.environ.get('GRAFANA_SERVICE_TOKEN', '')
    
    headers = {'Content-Type': 'application/json'}
    auth = None
    if auth_token:
        headers['Authorization'] = f'Bearer {auth_token}'
    else:
        # Fallback to current configured root admin credentials
        current_admin_pwd = os.environ.get('TECHNICAL_ADMIN_PASSWORD', os.environ.get('GRAFANA_ADMIN_PASSWORD', ''))
        if current_admin_pwd:
            auth = (admin_user, current_admin_pwd)

    for base_url in [container_host, grafana_url]:
        try:
            # First user (ID 1) is always the primary administrator in Grafana
            url = f'{base_url}/api/admin/users/1/password'
            resp = requests.put(url, json={'password': new_password}, headers=headers, auth=auth, timeout=3)
            if resp.status_code in (200, 204):
                logger.info("Successfully synced technical admin password to Grafana at %s", base_url)
                return {'success': True, 'url': base_url}
            else:
                logger.warning("Grafana responded with status %s at %s: %s", resp.status_code, base_url, resp.text)
        except Exception as ex:
            logger.debug("Could not reach Grafana at %s: %s", base_url, ex)

    return {'success': False, 'message': 'Grafana service not directly reachable via Admin API'}


def sync_minio_admin_password(new_password: str) -> dict:
    """
    Updates the technical admin password in MinIO via the MinIO Client (mc) CLI.
    Rotates the password for the technical admin user and guarantees the 'consoleAdmin' policy
    so the administrator can log directly into the MinIO Console (:9001).
    """
    minio_url = getattr(settings, 'MINIO_ENDPOINT_URL', os.environ.get('MINIO_ENDPOINT_URL', 'http://127.0.0.1:9000')).rstrip('/')
    if '127.0.0.1' in minio_url or 'localhost' in minio_url:
        container_endpoint = os.environ.get('MINIO_INTERNAL_URL', 'http://minio:9000').rstrip('/')
    else:
        container_endpoint = minio_url

    root_user = os.environ.get('MINIO_ROOT_USER', os.environ.get('TECHNICAL_ADMIN_EMAIL', os.environ.get('DEFAULT_ADMIN_EMAIL', 'commerce-admin')))
    root_pwd = os.environ.get('MINIO_ROOT_PASSWORD', os.environ.get('TECHNICAL_ADMIN_PASSWORD', os.environ.get('DEFAULT_ADMIN_PASSWORD', '')))
    target_user = os.environ.get('TECHNICAL_ADMIN_EMAIL', os.environ.get('DEFAULT_ADMIN_EMAIL', 'admin@proace.local'))

    mc_bin = shutil.which('mc')
    if not mc_bin:
        for candidate in ['/usr/local/bin/mc', '/opt/homebrew/bin/mc', os.path.expanduser('~/.local/bin/mc')]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                mc_bin = candidate
                break

    if not mc_bin:
        # Fallback health check if mc CLI is not locally installed
        try:
            resp = requests.get(f'{minio_url}/minio/health/live', timeout=2)
            if resp.status_code == 200:
                logger.info("MinIO is online, but mc CLI is required for password rotation. Install mc or use .env.")
                return {'success': False, 'endpoint': minio_url, 'message': 'MinIO online, mc CLI required to rotate IAM user password.'}
        except Exception:
            pass
        return {'success': False, 'endpoint': minio_url, 'message': 'MinIO Client (mc) not found in PATH or standard locations.'}

    endpoints_to_try = [container_endpoint, minio_url] if container_endpoint != minio_url else [minio_url]
    last_err = None

    for endpoint in endpoints_to_try:
        try:
            alias_name = 'local-admin-sync'
            # 1. Configure MinIO alias using root credentials
            alias_cmd = [mc_bin, 'alias', 'set', alias_name, endpoint, root_user, root_pwd]
            alias_proc = subprocess.run(alias_cmd, capture_output=True, text=True, timeout=5)
            if alias_proc.returncode != 0:
                last_err = alias_proc.stderr.strip()
                continue

            # 2. Add or update technical admin user with new password
            user_cmd = [mc_bin, 'admin', 'user', 'add', alias_name, target_user, new_password]
            user_proc = subprocess.run(user_cmd, capture_output=True, text=True, timeout=5)
            if user_proc.returncode != 0:
                last_err = user_proc.stderr.strip()
                continue

            # 3. Attach consoleAdmin policy
            policy_cmd = [mc_bin, 'admin', 'policy', 'attach', alias_name, 'consoleAdmin', '--user', target_user]
            subprocess.run(policy_cmd, capture_output=True, text=True, timeout=5)

            logger.info("Successfully synced technical admin password to MinIO at %s for %s", endpoint, target_user)
            return {'success': True, 'endpoint': endpoint, 'user': target_user}
        except subprocess.TimeoutExpired:
            last_err = f"mc command timed out connecting to {endpoint}"
        except Exception as ex:
            last_err = str(ex)

    return {'success': False, 'message': last_err or 'Failed to update MinIO user credentials via mc'}
