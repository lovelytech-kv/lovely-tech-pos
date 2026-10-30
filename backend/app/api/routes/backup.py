from datetime import datetime, timezone
from pathlib import Path
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission, current_user
from app.backup.auto import create_verified_backup
from app.backup.service import create_postgres_dump, decrypt_backup, restore_postgres_backup, sync_backup_to_google_drive, BackupError
from app.security.reauth import require_admin_reauth
from app.models.backup import BackupPoint, RestoreEvent
from app.models.master import User
from app.models.security import AuditLog
from app.schemas.api import BackupCreateIn, BackupOut

router=APIRouter(prefix='/backup',tags=['backup'])

@router.post('/create',response_model=BackupOut)
def create(payload:BackupCreateIn,user:User=Depends(require_permission('BACKUP_MANAGE')),db:Session=Depends(db_session)):
    try:
        point=create_verified_backup(db,branch_id=user.branch_id,user_id=user.id,filename=payload.filename)
    except BackupError as exc:
        if str(exc)=='Invalid backup filename': raise HTTPException(400,'Invalid backup filename')
        raise HTTPException(500,f'PostgreSQL backup failed: {exc}')
    return BackupOut(backup_id=point.id,state=point.state,filename=point.filename,sha256=point.sha256,verified_at=point.verified_at,sync_state=point.sync_state,remote_path=point.remote_path)

@router.get('/status')
def backup_status(user:User=Depends(current_user),db:Session=Depends(db_session)):
    latest=db.scalar(select(BackupPoint).where(BackupPoint.branch_id==user.branch_id,BackupPoint.state=='VERIFIED').order_by(BackupPoint.verified_at.desc()).limit(1))
    out = {
        'status': 'VERIFIED' if latest else 'NO_VERIFIED_BACKUP',
        'last_backup_time': latest.verified_at if latest else None,
    }
    if user.role.code.upper() == 'ADMIN':     # Requirements 15: Cashier sees Backup Status + Last Backup Time only
        out['sync_state'] = latest.sync_state if latest else None
        out['filename'] = latest.filename if latest else None
    return out

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
    db.close()
    try:
        backup_path=Path(point.storage_target)/point.filename
        safety=Path(settings.backup_root)/f'pre-restore-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.ltbak'
        restore_postgres_backup(pg_dump=settings.pg_dump_bin,pg_restore=settings.pg_restore_bin,psql=settings.psql_bin,database_url=settings.database_url,encrypted_backup=backup_path,safety_output=safety,secret=settings.secret_key)
        journal=Path(settings.backup_root)/'restore-journal.log'; journal.parent.mkdir(parents=True,exist_ok=True); journal.open('a',encoding='utf-8').write(f"{datetime.now(timezone.utc).isoformat()} RESTORE_SUCCEEDED backup={backup_id} actor={user.id} safety={safety}\n")
        return {'backup_id':str(point.id),'status':'SUCCEEDED','safety_backup':str(safety)}
    except Exception as exc:
        journal=Path(settings.backup_root)/'restore-journal.log'; journal.parent.mkdir(parents=True,exist_ok=True); journal.open('a',encoding='utf-8').write(f"{datetime.now(timezone.utc).isoformat()} RESTORE_FAILED backup={backup_id} actor={user.id} error={str(exc)[:500]}\n")
        raise HTTPException(500,f'Restore failed and was not reported successful: {exc}')



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
