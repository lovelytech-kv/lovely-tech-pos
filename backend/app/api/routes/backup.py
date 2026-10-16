from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission, current_user
from app.backup.service import create_postgres_dump, decrypt_backup, restore_postgres_backup, sync_backup_to_google_drive, validate_backup_envelope_metadata, BackupError
from app.security.reauth import require_admin_reauth
from app.models.backup import BackupPoint, RestoreEvent
from app.models.master import User
from app.models.security import AuditLog
from app.schemas.api import BackupCreateIn, BackupOut
from app.core.shop_identity import ShopIdentityStatus, inspect_shop_identity
from app.core.restore_state import (
    RestoreState,

    append_restore_journal,
    acquire_restore_interlock,
    read_restore_state,
    RestoreStateError,
    RestoreInterlockBusy,
    restore_state_path,
    write_restore_state,
)
import uuid

router=APIRouter(prefix='/backup',tags=['backup'])


def _backup_envelope_metadata(db: Session, backup_point_id: UUID) -> dict[str, str]:
    metadata = {'backup_point_id': str(backup_point_id)}
    identity = inspect_shop_identity(db)
    if identity.status is ShopIdentityStatus.PRESENT and identity.shop_id is not None:
        metadata['shop_id'] = str(identity.shop_id)
    return metadata


@router.post('/create',response_model=BackupOut)
def create(payload:BackupCreateIn,user:User=Depends(require_permission('BACKUP_MANAGE')),db:Session=Depends(db_session)):
    settings=__import__('app.core.config',fromlist=['settings']).settings
    safe_name=re.sub(r"[^A-Za-z0-9._-]", "_", payload.filename)
    if not safe_name.lower().endswith('.ltbak'):
        safe_name += '.ltbak'
    root=Path(settings.backup_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    dest=(root / safe_name).resolve()
    if root not in dest.parents:
        raise HTTPException(400,'Invalid backup filename')
    point=BackupPoint(branch_id=user.branch_id,state='CREATING',storage_target=str(root),filename=safe_name,created_by=user.id)
    db.add(point); db.flush()
    try:
        blob=create_postgres_dump(pg_dump=settings.pg_dump_bin,database_url=settings.database_url,destination=dest,secret=settings.secret_key,metadata=_backup_envelope_metadata(db, point.id))
        meta,_=decrypt_backup(blob.read_bytes(),secret=settings.secret_key)
        validate_backup_envelope_metadata(meta)
        point.state='VERIFIED'; point.sha256=meta['sha256']; point.verified_at=datetime.now(timezone.utc)
        if settings.google_drive_rclone_remote:
            try:
                point.remote_path=sync_backup_to_google_drive(rclone_bin=settings.rclone_bin,remote=settings.google_drive_rclone_remote,remote_path=settings.google_drive_backup_path,local_file=dest)
                point.sync_state='SYNCED'
            except Exception as sync_exc:
                point.sync_state='PENDING_SYNC'; point.failure_reason=f'Local backup verified; Google Drive sync pending: {str(sync_exc)[:1500]}'
        else:
            point.sync_state='LOCAL_ONLY'
        db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='BACKUP_VERIFIED',entity_type='BACKUP_POINT',entity_id=point.id,timestamp=datetime.now(timezone.utc),after_json={'filename':safe_name,'sha256':point.sha256},source_transaction_id=point.id))
        db.commit()
    except Exception as exc:
        point.state='FAILED'; point.failure_reason=str(exc)[:2000]; db.commit(); raise HTTPException(500,f'PostgreSQL backup failed: {exc}')
    return BackupOut(backup_id=point.id,state=point.state,filename=point.filename,sha256=point.sha256,verified_at=point.verified_at,sync_state=point.sync_state,remote_path=point.remote_path)

@router.get('/status')
def backup_status(user:User=Depends(current_user),db:Session=Depends(db_session)):
    latest=db.scalar(select(BackupPoint).where(BackupPoint.branch_id==user.branch_id,BackupPoint.state=='VERIFIED').order_by(BackupPoint.verified_at.desc()).limit(1))
    return {
        'status': 'VERIFIED' if latest else 'NO_VERIFIED_BACKUP',
        'last_backup_time': latest.verified_at if latest else None,
        'sync_state': latest.sync_state if latest else None,
        'filename': latest.filename if latest else None,
    }

@router.get('/points',response_model=list[BackupOut])
def points(user:User=Depends(require_permission('BACKUP_MANAGE')),db:Session=Depends(db_session)):
    rows=db.scalars(select(BackupPoint).where((BackupPoint.branch_id==user.branch_id)|(BackupPoint.branch_id.is_(None))).order_by(BackupPoint.verified_at.desc().nullslast()).limit(100)).all()
    return [BackupOut(backup_id=x.id,state=x.state,filename=x.filename,sha256=x.sha256,verified_at=x.verified_at,sync_state=x.sync_state,remote_path=x.remote_path) for x in rows]

@router.post('/verify/{backup_id}')
def verify(backup_id:str,user:User=Depends(require_permission('BACKUP_MANAGE')),db:Session=Depends(db_session)):
    point=db.scalar(select(BackupPoint).where(BackupPoint.id==backup_id,BackupPoint.branch_id==user.branch_id).with_for_update())
    if not point: raise HTTPException(404,'Backup point not found')
    path=Path(point.storage_target)/point.filename
    try:
        meta,_=decrypt_backup(path.read_bytes(),secret=__import__('app.core.config',fromlist=['settings']).settings.secret_key)
        validate_backup_envelope_metadata(meta)
    except Exception as exc: point.state='FAILED'; point.failure_reason=str(exc); db.commit(); raise HTTPException(400,str(exc))
    point.state='VERIFIED'; point.sha256=meta['sha256']; point.verified_at=datetime.now(timezone.utc); point.failure_reason=None; db.commit()
    return {'backup_id':str(point.id),'state':point.state,'sha256':point.sha256}

@router.post('/restore/{backup_id}')
def restore(backup_id:str, confirm:bool=False, admin_password:str|None=None, user:User=Depends(require_permission('BACKUP_MANAGE')), db:Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='database restore')
    if not confirm: raise HTTPException(400,'Restore requires explicit confirm=true')
    point=db.scalar(select(BackupPoint).where(BackupPoint.id==backup_id,BackupPoint.branch_id==user.branch_id).with_for_update())
    if not point or point.state!='VERIFIED': raise HTTPException(400,'Only VERIFIED backup points can be restored')
    settings=__import__('app.core.config',fromlist=['settings']).settings
    event=RestoreEvent(branch_id=user.branch_id,backup_point_id=point.id,actor_user_id=user.id,status='STARTED',reason='Admin restore started')
    db.add(event); db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='RESTORE_STARTED',entity_type='BACKUP_POINT',entity_id=point.id,timestamp=datetime.now(timezone.utc),after_json={'status':'STARTED'},source_transaction_id=point.id)); db.commit()
    engine = db.get_bind()
    db.close()
    engine.dispose()
    state_path=restore_state_path(settings.backup_root)
    operation_id=None
    expected_shop_id=None
    try:
        with acquire_restore_interlock(settings.backup_root):
            try:
                current_state = read_restore_state(state_path)
            except RestoreStateError as exc:
                raise HTTPException(status_code=503, detail="Restore recovery state is unavailable; restore is disabled.") from exc
            if current_state.state is not RestoreState.READY:
                raise HTTPException(status_code=409, detail="Restore recovery is incomplete; restore is disabled.")
            try:
                backup_path=Path(point.storage_target)/point.filename
                meta,_=decrypt_backup(backup_path.read_bytes(),secret=settings.secret_key)
                expected_shop_id=validate_backup_envelope_metadata(meta)
                operation_id=uuid.uuid4()
                write_restore_state(state_path,state=RestoreState.RESTORE_IN_PROGRESS,phase='BEFORE_REPLACEMENT',operation_id=operation_id,expected_shop_id=expected_shop_id)
                append_restore_journal(settings.backup_root,{'event':'RESTORE_IN_PROGRESS','operation_id':str(operation_id),'backup_id':backup_id,'expected_shop_id':str(expected_shop_id)})
                safety=Path(settings.backup_root)/f'pre-restore-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.ltbak'
                restore_postgres_backup(pg_dump=settings.pg_dump_bin,pg_restore=settings.pg_restore_bin,psql=settings.psql_bin,database_url=settings.database_url,encrypted_backup=backup_path,safety_output=safety,secret=settings.secret_key)
                write_restore_state(state_path,state=RestoreState.READY,phase='RECONCILIATION_SUCCEEDED')
                append_restore_journal(settings.backup_root,{'event':'RECONCILIATION_SUCCEEDED','operation_id':str(operation_id),'backup_id':backup_id,'shop_id':str(expected_shop_id)})
                return {'backup_id':str(point.id),'status':'SUCCEEDED','safety_backup':str(safety)}
            except Exception as exc:
                report_error = None
                try:
                    if operation_id is not None:
                        write_restore_state(state_path,state=RestoreState.RECOVERY_REQUIRED,phase='FAILED',operation_id=operation_id,expected_shop_id=expected_shop_id,error=str(exc)[:500])
                        append_restore_journal(settings.backup_root,{'event':'RESTORE_FAILED','operation_id':str(operation_id),'backup_id':backup_id,'actor':str(user.id),'error':str(exc)[:500]})
                except Exception as report_exc:
                    report_error = report_exc
                if report_error is not None:
                    raise HTTPException(500,'Restore failed and recovery state could not be durably reported.') from report_error
                raise HTTPException(500,f'Restore failed and was not reported successful: {exc}')
    except RestoreInterlockBusy as exc:
        raise HTTPException(503,'Bootstrap or restore is already in progress.') from exc


@router.post('/sync/{backup_id}')
def sync_backup(backup_id:str,user:User=Depends(require_permission('BACKUP_MANAGE')),db:Session=Depends(db_session)):
    settings=__import__('app.core.config',fromlist=['settings']).settings
    if not settings.google_drive_rclone_remote: raise HTTPException(400,'Google Drive sync is not configured')
    point=db.scalar(select(BackupPoint).where(BackupPoint.id==backup_id,BackupPoint.branch_id==user.branch_id,BackupPoint.state=='VERIFIED').with_for_update())
    if not point: raise HTTPException(404,'Verified backup point not found')
    try:
        remote=sync_backup_to_google_drive(rclone_bin=settings.rclone_bin,remote=settings.google_drive_rclone_remote,remote_path=settings.google_drive_backup_path,local_file=Path(point.storage_target)/point.filename)
        point.remote_path=remote; point.sync_state='SYNCED'; point.failure_reason=None; db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='BACKUP_SYNCED',entity_type='BACKUP_POINT',entity_id=point.id,timestamp=datetime.now(timezone.utc),after_json={'remote_path':remote},source_transaction_id=point.id)); db.commit()
        return {'backup_id':str(point.id),'sync_state':point.sync_state,'remote_path':remote}
    except Exception as exc:
        point.sync_state='PENDING_SYNC'; point.failure_reason=str(exc)[:2000]; db.commit(); raise HTTPException(500,f'Google Drive sync failed: {exc}')
