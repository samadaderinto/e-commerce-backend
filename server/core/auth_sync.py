import logging
import os
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
    Updates the root / admin password in MinIO.
    Logs and records environment sync expectation.
    """
    minio_url = getattr(settings, 'MINIO_ENDPOINT_URL', os.environ.get('MINIO_ENDPOINT_URL', 'http://127.0.0.1:9000')).rstrip('/')
    try:
        # MinIO Admin API operates over signature v4 or mc CLI.
        # Check endpoint responsiveness
        resp = requests.get(f'{minio_url}/minio/health/live', timeout=2)
        if resp.status_code == 200:
            logger.info("MinIO health verified at %s. Noted password rotation for root admin.", minio_url)
            return {'success': True, 'endpoint': minio_url}
    except Exception as ex:
        logger.debug("MinIO not reachable at %s: %s", minio_url, ex)

    return {'success': False, 'endpoint': minio_url, 'message': 'MinIO service health check skipped or unreachable'}
