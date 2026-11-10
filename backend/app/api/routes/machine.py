"""Machine role identity endpoints (Chunk 12a + 13)."""
from datetime import datetime, timezone
import json as _json
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.machine_identity import MachineIdentity
from app.models.shop_identity import ShopIdentity
from app.models.security import AuditLog
from app.schemas.api import MachineIdentityOut, MachineIdentityUpdateIn

router = APIRouter(prefix='/machine', tags=['machine'])


# ============ Chunk 13 — CLIENT Join (rate limit + verify + join) ============

_URL_PATTERN = r'^https?://.+:\d+$'
_verify_rate_limit: dict[str, list[float]] = {}
_RATE_WINDOW_SECONDS = 300
_RATE_MAX_ATTEMPTS = 5


def _rate_key(client_ip: str, server_url: str) -> str:
    return f"{client_ip}::{server_url}"


def _check_rate_limit(client_ip: str, server_url: str) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    now = time.time()
    key = _rate_key(client_ip, server_url)
    timestamps = [t for t in _verify_rate_limit.get(key, []) if now - t < _RATE_WINDOW_SECONDS]
    if len(timestamps) >= _RATE_MAX_ATTEMPTS:
        _verify_rate_limit[key] = timestamps
        retry_after = max(1, int(_RATE_WINDOW_SECONDS - (now - timestamps[0])) + 1)
        return (False, retry_after)
    _verify_rate_limit[key] = timestamps
    return (True, 0)


def _record_failure(client_ip: str, server_url: str) -> None:
    key = _rate_key(client_ip, server_url)
    _verify_rate_limit.setdefault(key, []).append(time.time())


def _reset_rate_limit(client_ip: str, server_url: str) -> None:
    _verify_rate_limit.pop(_rate_key(client_ip, server_url), None)


def _http_post_json(url: str, body: dict, timeout: int = 10) -> tuple[int, dict]:
    data = _json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}, method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _json.loads(resp.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        try:
            parsed = _json.loads(e.read().decode('utf-8') or '{}')
        except Exception:
            parsed = {}
        return e.code, parsed
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return 0, {'_network_error': str(e)}


def _http_get_json(url: str, timeout: int = 5) -> tuple[int, dict]:
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _json.loads(resp.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        try:
            parsed = _json.loads(e.read().decode('utf-8') or '{}')
        except Exception:
            parsed = {}
        return e.code, parsed
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return 0, {'_network_error': str(e)}


def _verify_admin_on_server(server_url: str, username: str, password: str) -> dict:
    """Verify admin credentials against remote SERVER. Returns dict with 'valid' + details."""
    base = server_url.rstrip('/')

    health_status, health_body = _http_get_json(f"{base}/api/v1/health", timeout=5)
    if health_status != 200:
        if health_status == 0:
            return {'valid': False, 'reason': 'unreachable', 'reason_message': 'Cannot reach server. Check that the server laptop is on and connected to the same network.'}
        return {'valid': False, 'reason': 'unreachable', 'reason_message': 'Server returned an unexpected response. Contact your administrator.'}

    login_status, login_body = _http_post_json(
        f"{base}/api/v1/auth/login",
        {'username': username, 'password': password},
        timeout=10,
    )
    if login_status == 200:
        shop_status, shop_body = _http_get_json(f"{base}/api/v1/shop/identity", timeout=5)
        shop_name = shop_body.get('shop_name') if shop_status == 200 else None
        return {
            'valid': True,
            'shop_name': shop_name,
            'admin_display_name': login_body.get('display_name'),
            'role': login_body.get('role'),
            'user_id': login_body.get('user_id'),
        }
    if login_status == 401:
        return {'valid': False, 'reason': 'invalid_credentials', 'reason_message': 'Invalid username or password'}
    if login_status == 0:
        return {'valid': False, 'reason': 'unreachable', 'reason_message': 'Cannot reach server. Check that the server laptop is on and connected to the same network.'}
    return {'valid': False, 'reason': 'error', 'reason_message': 'Server error during verification. Try again in a moment.'}


class MachineVerifyAdminIn(BaseModel):
    server_url: str = Field(min_length=8, max_length=255, pattern=_URL_PATTERN)
    admin_username: str = Field(min_length=3, max_length=80)
    admin_password: str = Field(min_length=8, max_length=200)


class MachineVerifyAdminOut(BaseModel):
    valid: bool
    shop_name: str | None = None
    admin_display_name: str | None = None
    reason: str | None = None
    reason_message: str | None = None


class MachineJoinIn(BaseModel):
    server_url: str = Field(min_length=8, max_length=255, pattern=_URL_PATTERN)
    admin_username: str = Field(min_length=3, max_length=80)
    admin_password: str = Field(min_length=8, max_length=200)
    machine_name: str | None = Field(default=None, max_length=100)


class MachineJoinOut(BaseModel):
    success: bool
    machine_role: str
    server_url: str
    shop_uuid: str


@router.post('/verify-admin', response_model=MachineVerifyAdminOut)
def machine_verify_admin(
    payload: MachineVerifyAdminIn,
    request: Request,
    db: Session = Depends(db_session),
):
    """Verify remote SERVER admin credentials before allowing CLIENT join."""
    client_ip = request.client.host if request.client else 'unknown'

    allowed, retry_after = _check_rate_limit(client_ip, payload.server_url)
    if not allowed:
        raise HTTPException(
            429,
            f'Too many attempts. Try again in {retry_after} seconds.',
            headers={'Retry-After': str(retry_after)},
        )

    result = _verify_admin_on_server(
        payload.server_url, payload.admin_username.strip(), payload.admin_password
    )

    if result.get('valid'):
        role = (result.get('role') or '').upper()
        if role != 'ADMIN':
            _record_failure(client_ip, payload.server_url)
            return MachineVerifyAdminOut(
                valid=False,
                reason='not_admin',
                reason_message='The provided credentials belong to a cashier, not an admin',
            )
        _reset_rate_limit(client_ip, payload.server_url)
        return MachineVerifyAdminOut(
            valid=True,
            shop_name=result.get('shop_name'),
            admin_display_name=result.get('admin_display_name'),
        )

    _record_failure(client_ip, payload.server_url)
    return MachineVerifyAdminOut(
        valid=False,
        reason=result.get('reason'),
        reason_message=result.get('reason_message'),
    )


@router.post('/join', response_model=MachineJoinOut)
def machine_join(
    payload: MachineJoinIn,
    request: Request,
    db: Session = Depends(db_session),
):
    """Join this machine as CLIENT to a remote SERVER after verifying admin creds."""
    client_ip = request.client.host if request.client else 'unknown'

    allowed, retry_after = _check_rate_limit(client_ip, payload.server_url)
    if not allowed:
        raise HTTPException(
            429,
            f'Too many attempts. Try again in {retry_after} seconds.',
            headers={'Retry-After': str(retry_after)},
        )

    result = _verify_admin_on_server(
        payload.server_url, payload.admin_username.strip(), payload.admin_password
    )

    if not result.get('valid'):
        _record_failure(client_ip, payload.server_url)
        code = 401 if result.get('reason') == 'invalid_credentials' else 503
        raise HTTPException(code, result.get('reason_message') or 'Verification failed')

    if (result.get('role') or '').upper() != 'ADMIN':
        _record_failure(client_ip, payload.server_url)
        raise HTTPException(403, 'Provided credentials are not an admin')

    _reset_rate_limit(client_ip, payload.server_url)

    base = payload.server_url.rstrip('/')
    shop_status, shop_body = _http_get_json(f"{base}/api/v1/shop/identity", timeout=5)
    if shop_status != 200:
        raise HTTPException(503, 'Could not fetch server shop identity — try again')
    server_shop_uuid = shop_body.get('shop_uuid')
    if not server_shop_uuid:
        raise HTTPException(503, 'Server shop identity returned empty shop_uuid')

    now = datetime.now(timezone.utc)
    machine = db.scalar(select(MachineIdentity).limit(1).with_for_update())
    if machine is None:
        raise HTTPException(500, 'Machine identity not initialized (migration 0041 missing)')

    before = {
        'machine_role': machine.machine_role,
        'server_url': machine.server_url,
        'machine_name': machine.machine_name,
        'server_shop_uuid': machine.server_shop_uuid,
    }

    machine.machine_role = 'CLIENT'
    machine.server_url = payload.server_url
    if payload.machine_name is not None and payload.machine_name.strip():
        machine.machine_name = payload.machine_name.strip()
    elif not machine.machine_name:
        machine.machine_name = 'Client Laptop'
    machine.last_seen_at = now
    machine.last_join_at = now
    machine.server_shop_uuid = server_shop_uuid

    shop = db.scalar(select(ShopIdentity).limit(1))
    if shop is not None:
        shop.shop_name = '(client — see server)'

    db.add(
        AuditLog(
            branch_id=None,
            actor_user_id=None,
            action_type='CLIENT_JOINED',
            entity_type='MACHINE',
            entity_id=machine.id,
            timestamp=now,
            before_json=before,
            after_json={
                'machine_role': machine.machine_role,
                'server_url': machine.server_url,
                'machine_name': machine.machine_name,
                'server_shop_uuid': server_shop_uuid,
                'verified_admin': result.get('admin_display_name'),
                'verified_admin_user_id': result.get('user_id'),
                'client_ip': client_ip,
            },
            source_transaction_id=machine.id,
        )
    )
    db.commit()

    return MachineJoinOut(
        success=True,
        machine_role='CLIENT',
        server_url=payload.server_url,
        shop_uuid=server_shop_uuid,
    )


# ============ Existing endpoints (Chunk 12a) ============

@router.get('/identity', response_model=MachineIdentityOut)
def get_machine_identity(db: Session = Depends(db_session)):
    """Public — tells the frontend which machine role is configured."""
    machine = db.scalar(select(MachineIdentity).limit(1))
    if machine is None:
        raise HTTPException(500, 'Machine identity not initialized (migration 0041 not applied)')
    return MachineIdentityOut(
        machine_role=machine.machine_role,
        machine_name=machine.machine_name,
        server_url=machine.server_url,
        registered_at=machine.registered_at,
        last_seen_at=machine.last_seen_at,
    )


@router.put('/identity', response_model=MachineIdentityOut)
def update_machine_identity(
    payload: MachineIdentityUpdateIn,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    """Admin — change machine role (SERVER / CLIENT) + optional name/server_url."""
    machine = db.scalar(select(MachineIdentity).limit(1).with_for_update())
    if machine is None:
        raise HTTPException(500, 'Machine identity not initialized')

    role = payload.machine_role.upper()
    if role not in ('SERVER', 'CLIENT'):
        raise HTTPException(400, 'machine_role must be SERVER or CLIENT')

    if role == 'CLIENT':
        if not payload.server_url or not payload.server_url.strip():
            raise HTTPException(422, 'server_url required for CLIENT mode')
        new_server_url = payload.server_url.strip()
    else:
        new_server_url = None

    before = {
        'machine_role': machine.machine_role,
        'machine_name': machine.machine_name,
        'server_url': machine.server_url,
    }

    machine.machine_role = role
    machine.server_url = new_server_url
    if payload.machine_name is not None:
        machine.machine_name = payload.machine_name.strip() or None

    db.add(
        AuditLog(
            branch_id=user.branch_id,
            actor_user_id=user.id,
            action_type='MACHINE_ROLE_UPDATED',
            entity_type='MACHINE',
            entity_id=machine.id,
            timestamp=datetime.now(timezone.utc),
            before_json=before,
            after_json={
                'machine_role': machine.machine_role,
                'machine_name': machine.machine_name,
                'server_url': machine.server_url,
            },
            source_transaction_id=machine.id,
        )
    )
    db.commit()

    return MachineIdentityOut(
        machine_role=machine.machine_role,
        machine_name=machine.machine_name,
        server_url=machine.server_url,
        registered_at=machine.registered_at,
        last_seen_at=machine.last_seen_at,
    )