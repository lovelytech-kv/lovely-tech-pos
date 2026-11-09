"""Machine role identity endpoints (Chunk 12a)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.machine_identity import MachineIdentity
from app.models.security import AuditLog
from app.schemas.api import MachineIdentityOut, MachineIdentityUpdateIn

router = APIRouter(prefix='/machine', tags=['machine'])


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
    else:  # SERVER
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

    db.add(AuditLog(
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
    ))
    db.commit()

    return MachineIdentityOut(
        machine_role=machine.machine_role,
        machine_name=machine.machine_name,
        server_url=machine.server_url,
        registered_at=machine.registered_at,
        last_seen_at=machine.last_seen_at,
    )