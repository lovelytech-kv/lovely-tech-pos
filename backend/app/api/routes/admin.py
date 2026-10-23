from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User, Role, Permission, RolePermission, Target
from app.models.sales import Expense, OtherIncome
from app.models.master import ExpenseCategory
from app.models.security import AuditLog, IdempotencyKey
from app.schemas.api import ExpenseIn, OtherIncomeIn, TargetIn, RolePermissionUpdateIn, UserRoleUpdateIn, CashierResetIn, UserDiscountLimitIn, ReauthIn
from app.security.reauth import require_admin_reauth

router=APIRouter(prefix='/admin', tags=['admin'])

def admin_user(user: User = Depends(require_permission('ADMIN_PANEL'))): return user

def _expense_request_hash(payload: ExpenseIn) -> str:
    import hashlib, json
    raw = json.dumps({
        "category_id": str(payload.category_id),
        "expense_date": str(payload.expense_date),
        "amount": str(payload.amount),
        "payment_method": payload.payment_method,
        "description": payload.description,
    }, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def _other_income_request_hash(payload: OtherIncomeIn) -> str:
    import hashlib, json
    raw = json.dumps({
        "income_date": str(payload.income_date),
        "amount": str(payload.amount),
        "payment_method": payload.payment_method,
        "description": payload.description,
    }, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def _expense_response(row: Expense) -> dict:
    return {"expense_id": str(row.id), "status": row.status, "version": row.version}

def _other_income_response(row: OtherIncome) -> dict:
    return {"other_income_id": str(row.id), "status": row.status, "version": row.version}

def _reserve_expense_idempotency(db: Session, *, key: str | None, user_id: uuid.UUID, request_hash: str, response: dict):
    if not key:
        return
    row = IdempotencyKey(key=key, user_id=user_id, request_hash=request_hash, created_at=datetime.now(timezone.utc), response_json=response, completed_at=datetime.now(timezone.utc))
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key).with_for_update())
        if existing is None or existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was already used for a different request")
        raise HTTPException(409, "Idempotency request has already completed")

def _get_expense_idempotent_replay(db: Session, *, key: str | None, request_hash: str) -> dict | None:
    if not key:
        return None
    existing = db.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key).with_for_update())
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        raise HTTPException(409, "Idempotency key was already used for a different request")
    if not existing.completed_at or not existing.response_json:
        raise HTTPException(409, "The same request is currently being completed; retry after transaction finishes")
    return existing.response_json

@router.get('/users')
def users(user: User=Depends(admin_user), db: Session=Depends(db_session)):
    rows=db.scalars(select(User).where(User.branch_id==user.branch_id).order_by(User.username)).all()
    return [{'user_id':str(x.id),'username':x.username,'display_name':x.display_name,'role':x.role.code,'is_active':x.is_active,'version':x.version,'must_change_password':x.must_change_password,'discount_limit_percent':x.discount_limit_percent,'version':x.version} for x in rows]


@router.put('/users/{user_id}/discount-limit')
def update_discount_limit(user_id:str, payload:UserDiscountLimitIn, user:User=Depends(admin_user), db:Session=Depends(db_session)):
    target=db.scalar(select(User).where(User.id==user_id,User.branch_id==user.branch_id).with_for_update())
    if not target: raise HTTPException(404,'User not found')
    if payload.version is None: raise HTTPException(409,'User version is required; reload the record')
    if target.version != payload.version: raise HTTPException(409,'User changed; reload before editing')
    old=target.discount_limit_percent; target.discount_limit_percent=payload.discount_limit_percent; target.version += 1
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='USER_DISCOUNT_LIMIT_CHANGED',entity_type='USER',entity_id=target.id,timestamp=datetime.now(timezone.utc),before_json={'discount_limit_percent':str(old)},after_json={'discount_limit_percent':str(target.discount_limit_percent)},source_transaction_id=target.id))
    db.commit(); return {'user_id':str(target.id),'discount_limit_percent':target.discount_limit_percent}

@router.get('/roles')
def roles(user: User=Depends(admin_user), db: Session=Depends(db_session)):
    rows=db.scalars(select(Role).order_by(Role.code)).all()
    out=[]
    for r in rows:
        codes=db.scalars(select(Permission.code).join(RolePermission,RolePermission.permission_id==Permission.id).where(RolePermission.role_id==r.id).order_by(Permission.code)).all()
        out.append({'role_id':str(r.id),'code':r.code,'name':r.name,'permissions':codes})
    return out

@router.put('/roles/{role_id}/permissions')
def update_role_permissions(role_id:str,payload:RolePermissionUpdateIn,user:User=Depends(admin_user),db:Session=Depends(db_session),admin_password: str | None = None):
    require_admin_reauth(user=user,password=admin_password,db=db,action='permission changes')
    role=db.get(Role,role_id)
    if not role: raise HTTPException(404,'Role not found')
    if role.code.upper()=='ADMIN': raise HTTPException(400,'System Admin role permissions cannot be reduced')
    perms={p.code:p for p in db.scalars(select(Permission)).all()}
    unknown=[c for c in payload.permission_codes if c not in perms]
    if unknown: raise HTTPException(400,f'Unknown permissions: {", ".join(unknown)}')
    db.execute(delete(RolePermission).where(RolePermission.role_id==role.id))
    for code in sorted(set(payload.permission_codes)):
        db.add(RolePermission(role_id=role.id,permission_id=perms[code].id))
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='PERMISSIONS_CHANGED',entity_type='ROLE',entity_id=role.id,timestamp=datetime.now(timezone.utc),after_json={'permissions':sorted(set(payload.permission_codes))},source_transaction_id=role.id))
    db.commit(); return {'role_id':str(role.id),'permissions':sorted(set(payload.permission_codes))}

@router.put('/users/{user_id}/role')
def update_user_role(user_id:str,payload:UserRoleUpdateIn,user:User=Depends(admin_user),db:Session=Depends(db_session)):
    target=db.scalar(select(User).where(User.id==user_id,User.branch_id==user.branch_id).with_for_update())
    role=db.scalar(select(Role).where(Role.code==payload.role_code.upper()))
    if not target or not role: raise HTTPException(404,'User or role not found')
    if payload.version is None: raise HTTPException(409,'User version is required; reload the record')
    if target.version != payload.version: raise HTTPException(409,'User changed; reload before editing')
    if target.id==user.id: raise HTTPException(400,'Admin cannot change own role')
    before=target.role.code; target.role_id=role.id; target.version += 1
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='USER_ROLE_CHANGED',entity_type='USER',entity_id=target.id,timestamp=datetime.now(timezone.utc),before_json={'role':before},after_json={'role':role.code},source_transaction_id=target.id))
    db.commit(); return {'user_id':str(target.id),'role':role.code}

@router.get('/permissions')
def permissions(user: User=Depends(admin_user), db: Session=Depends(db_session)):
    rows=db.scalars(select(Permission).order_by(Permission.code)).all()
    return [{'code':p.code,'name':p.name,'description':p.description} for p in rows]

@router.post('/expenses')
def expense(payload:ExpenseIn,user:User=Depends(require_permission('EXPENSE_ENTRY')),db:Session=Depends(db_session)):
    request_hash=_expense_request_hash(payload)
    replay=_get_expense_idempotent_replay(db, key=payload.idempotency_key, request_hash=request_hash)
    if replay is not None:
        return replay
    status='APPROVED' if user.role.code.upper()=='ADMIN' else 'PENDING_APPROVAL'
    row=Expense(branch_id=user.branch_id,category_id=payload.category_id,expense_date=payload.expense_date,amount=payload.amount,payment_method=payload.payment_method,description=payload.description,status=status,entered_by=user.id,approved_by=user.id if status=='APPROVED' else None)
    db.add(row); db.flush()
    response=_expense_response(row)
    _reserve_expense_idempotency(db, key=payload.idempotency_key, user_id=user.id, request_hash=request_hash, response=response)
    db.commit()
    return response

@router.post('/other-income')
def other_income(payload:OtherIncomeIn,user:User=Depends(require_permission('OTHER_INCOME_ENTRY')),db:Session=Depends(db_session)):
    request_hash=_other_income_request_hash(payload)
    replay=_get_expense_idempotent_replay(db, key=payload.idempotency_key, request_hash=request_hash)
    if replay is not None:
        return replay
    status='APPROVED' if user.role.code.upper()=='ADMIN' else 'PENDING_APPROVAL'
    row=OtherIncome(branch_id=user.branch_id,income_date=payload.income_date,amount=payload.amount,payment_method=payload.payment_method,description=payload.description,status=status,entered_by=user.id,approved_by=user.id if status=='APPROVED' else None)
    db.add(row); db.flush()
    response=_other_income_response(row)
    _reserve_expense_idempotency(db, key=payload.idempotency_key, user_id=user.id, request_hash=request_hash, response=response)
    db.commit()
    return response

@router.get('/expense-categories')
def expense_categories(user:User=Depends(require_permission('EXPENSE_ENTRY')),db:Session=Depends(db_session)):
    rows=db.scalars(select(ExpenseCategory).where(ExpenseCategory.is_active.is_(True)).order_by(ExpenseCategory.name)).all()
    return [{'id':str(x.id),'name':x.name} for x in rows]

@router.get('/approvals')
def approvals(user:User=Depends(admin_user),db:Session=Depends(db_session)):
    from app.models.security import ApprovalRequest
    rows=db.scalars(select(ApprovalRequest).where(ApprovalRequest.branch_id==user.branch_id).order_by(ApprovalRequest.requested_at.desc()).limit(200)).all()
    return [{'approval_id':str(x.id),'action_type':x.action_type,'status':x.status,'requester_user_id':str(x.requester_user_id),'reviewer_user_id':str(x.reviewer_user_id) if x.reviewer_user_id else None,'requested_at':x.requested_at,'reviewed_at':x.reviewed_at,'payload':x.payload_json,'reject_reason':x.reject_reason,'approval_action_id':x.approval_action_id,'version':x.version} for x in rows]

@router.get('/pending-expenses')
def pending_expenses(user:User=Depends(admin_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Expense).where(Expense.branch_id==user.branch_id,Expense.status=='PENDING_APPROVAL').order_by(Expense.expense_date.desc(),Expense.created_at.desc()).limit(200)).all()
    return [{'expense_id':str(x.id),'category_id':str(x.category_id),'expense_date':x.expense_date,'amount':x.amount,'payment_method':x.payment_method,'description':x.description,'entered_by':str(x.entered_by),'status':x.status,'version':x.version} for x in rows]

@router.post('/expenses/{expense_id}/decision')
def expense_decision(expense_id:str,approve:bool,reason:str|None=None,version:int|None=None,user:User=Depends(admin_user),db:Session=Depends(db_session)):
    row=db.scalar(select(Expense).where(Expense.id==expense_id,Expense.branch_id==user.branch_id).with_for_update())
    if not row: raise HTTPException(404,'Expense not found')
    if row.status!='PENDING_APPROVAL': raise HTTPException(400,'Expense is not pending approval')
    if row.entered_by==user.id: raise HTTPException(400,'Requester cannot approve own expense')
    if version is None: raise HTTPException(409,'Expense version is required; reload the record')
    if row.version != version: raise HTTPException(409,'Expense changed; reload before editing')
    row.status='APPROVED' if approve else 'REJECTED'
    row.approved_by=user.id if approve else None
    row.version += 1
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='EXPENSE_APPROVAL_REVIEWED',entity_type='EXPENSE',entity_id=row.id,timestamp=datetime.now(timezone.utc),reason=reason,after_json={'status':row.status,'version':row.version},source_transaction_id=row.id))
    db.commit()
    return {'expense_id':str(row.id),'status':row.status,'version':row.version}

@router.get('/audit')
def audit(user:User=Depends(admin_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(AuditLog).where(AuditLog.branch_id==user.branch_id).order_by(AuditLog.timestamp.desc()).limit(300)).all()
    return [{'audit_id':str(x.id),'timestamp':x.timestamp,'actor_user_id':str(x.actor_user_id) if x.actor_user_id else None,'action_type':x.action_type,'entity_type':x.entity_type,'entity_id':str(x.entity_id) if x.entity_id else None,'reason':x.reason,'before':x.before_json,'after':x.after_json,'source_transaction_id':str(x.source_transaction_id) if x.source_transaction_id else None} for x in rows]

@router.get('/pending-other-income')
def pending_other_income(user:User=Depends(admin_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(OtherIncome).where(OtherIncome.branch_id==user.branch_id,OtherIncome.status=='PENDING_APPROVAL').order_by(OtherIncome.income_date.desc())).all()
    return [{'other_income_id':str(x.id),'income_date':x.income_date,'amount':x.amount,'payment_method':x.payment_method,'description':x.description,'entered_by':str(x.entered_by),'status':x.status,'version':x.version} for x in rows]

@router.post('/other-income/{other_income_id}/decision')
def other_income_decision(other_income_id:str,approve:bool,reason:str|None=None,version:int|None=None,user:User=Depends(admin_user),db:Session=Depends(db_session)):
    row=db.scalar(select(OtherIncome).where(OtherIncome.id==other_income_id,OtherIncome.branch_id==user.branch_id).with_for_update())
    if not row: raise HTTPException(404,'Other income not found')
    if row.status!='PENDING_APPROVAL': raise HTTPException(400,'Other income is not pending approval')
    if row.entered_by==user.id: raise HTTPException(400,'Requester cannot approve own other income')
    if version is None: raise HTTPException(409,'Other income version is required; reload the record')
    if row.version != version: raise HTTPException(409,'Other income changed; reload before editing')
    row.status='APPROVED' if approve else 'REJECTED'
    row.approved_by=user.id if approve else None
    row.version += 1
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='OTHER_INCOME_APPROVAL_REVIEWED',entity_type='OTHER_INCOME',entity_id=row.id,timestamp=datetime.now(timezone.utc),reason=reason,after_json={'status':row.status,'version':row.version},source_transaction_id=row.id))
    db.commit()
    return {'other_income_id':str(row.id),'status':row.status,'version':row.version}

@router.post('/targets')
def target(payload:TargetIn,user:User=Depends(require_permission('TARGET_MANAGE')),db:Session=Depends(db_session)):
    if payload.period_end < payload.period_start: raise HTTPException(400,'Period end cannot be before start')
    row=Target(branch_id=user.branch_id,**payload.model_dump()); db.add(row); db.commit(); return {'target_id':str(row.id)}

@router.get('/targets')
def targets(user:User=Depends(require_permission('TARGET_MANAGE')),db:Session=Depends(db_session)):
    rows=db.scalars(select(Target).where(Target.branch_id==user.branch_id).order_by(Target.period_start.desc())).all()
    return [{'target_id':str(x.id),'target_type':x.target_type,'target_value':x.target_value,'period_type':x.period_type,'period_start':x.period_start,'period_end':x.period_end} for x in rows]


@router.post('/users/reset-password')
def reset_user_password(payload: CashierResetIn, user: User=Depends(admin_user), db: Session=Depends(db_session)):
    target=db.scalar(select(User).where(User.id==payload.user_id, User.branch_id==user.branch_id).with_for_update())
    if not target: raise HTTPException(404, 'User not found')
    from app.services.recovery import RecoveryService, RecoveryError
    try:
        RecoveryService(db).reset_cashier_by_admin(target_user=target, admin_user=user, admin_password=payload.admin_password, new_password=payload.new_password)
    except RecoveryError as exc:
        raise HTTPException(400, str(exc))
    db.commit()
    return {'user_id':str(target.id),'must_change_password':True}

@router.post('/expense-categories')
def create_expense_category(payload:dict,user:User=Depends(admin_user),db:Session=Depends(db_session)):
    name=str(payload.get('name','')).strip()
    if not name: raise HTTPException(400,'Category name is required')
    row=ExpenseCategory(name=name,is_system=False,is_active=True); db.add(row); db.commit(); return {'id':str(row.id),'name':row.name}

@router.post('/suppliers')
def create_supplier(payload:dict,user:User=Depends(admin_user),db:Session=Depends(db_session)):
    from app.models.master import Supplier
    name=str(payload.get('name','')).strip()
    if not name: raise HTTPException(400,'Supplier name is required')
    row=Supplier(name=name,contact_no=payload.get('contact_no'),address=payload.get('address'),is_active=True); db.add(row); db.commit(); return {'supplier_id':str(row.id),'name':row.name,'contact_no':row.contact_no,'address':row.address}

@router.get('/suppliers')
def suppliers(user:User=Depends(admin_user),db:Session=Depends(db_session)):
    from app.models.master import Supplier
    rows=db.scalars(select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.name)).all()
    return [{'supplier_id':str(x.id),'name':x.name,'contact_no':x.contact_no,'address':x.address} for x in rows]
