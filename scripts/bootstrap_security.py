"""Create Lovely Tech system roles and the first admin/cashier users.

Usage (from backend):
  ADMIN_USERNAME=admin ADMIN_PASSWORD='...' [ADMIN_BRANCH_ID='uuid' | BRANCH_CODE=MAIN BRANCH_NAME='Lovely Tech'] \
  python ../scripts/bootstrap_security.py

Cashier is optional. No default passwords are embedded in source.
"""
from __future__ import annotations
import os, sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.master import Branch, Role, Permission, RolePermission, User, ExpenseCategory
from app.security.passwords import hash_password

PERMISSIONS = [
    ('SALE_CREATE','Create Sale','Complete normal POS sales'),
    ('RETURN_CREATE','Create Return','Process returns/exchanges'),
    ('REPAIR_CREATE','Create Repair','Create repair jobs'),
    ('REPAIR_UPDATE','Update Repair','Change repair status/final amounts'),
    ('REPAIR_PAYMENT','Repair Payment','Record repair payments'),
    ('WARRANTY_CREATE','Create Warranty Claim','Create warranty claims'),
    ('WARRANTY_DECIDE','Decide Warranty Claim','Admin warranty decision'),
    ('DAY_MANAGE','Manage Business Day','Start/continue/shift-end/day-end'),
    ('APPROVAL_REQUEST','Request Approval','Submit approval requests'),
    ('APPROVAL_REVIEW','Review Approval','Approve/reject requests'),
    ('CREDIT_SETTLE','Credit Settlement','Record customer credit settlements'),
    ('REPORT_VIEW','View Reports','View sales/profit/report data'),
    ('STOCK_VIEW','View Stock','View stock information'),
    ('STOCK_ADJUST','Adjust Stock','Admin stock adjustment'),
    ('PURCHASE_ENTRY','Purchase Entry','Enter purchase quantity'),
    ('ITEM_EDIT','Item Master Edit','Create and edit item master records and barcodes'),
    ('PURCHASE_COST','Purchase Cost','Enter/edit buy cost'),
    ('TARGET_MANAGE','Manage Targets','Create/update daily and monthly targets'),
    ('ADMIN_PANEL','Admin Panel','Manage users, roles and settings'),
    ('EXPENSE_ENTRY','Expense Entry','Enter shop expenses'),
    ('OTHER_INCOME_ENTRY','Other Income Entry','Enter other income'),
    ('BACKUP_MANAGE','Backup/Restore','Create and manage backups'),
    ('DOCUMENT_REPRINT','Document Reprint','Search and reprint documents'),
    ('CASH_HANDS_VIEW','Cash In Hands','View cash-in-hands projection'),
]

def env(name, required=True):
    v=os.getenv(name)
    if required and not v: raise SystemExit(f'Missing {name}')
    return v

factory=get_session_factory(); db=factory()
try:
    raw_branch=os.getenv('ADMIN_BRANCH_ID')
    if raw_branch:
        branch=db.get(Branch, uuid.UUID(raw_branch))
        if not branch: raise SystemExit('Branch not found')
    else:
        # First-time install: create the shop branch (BRANCH_CODE/BRANCH_NAME optional).
        code=os.getenv('BRANCH_CODE','MAIN')
        branch=db.scalar(select(Branch).where(Branch.code==code))
        if branch is None:
            branch=Branch(code=code,name=os.getenv('BRANCH_NAME','Lovely Tech'),is_active=True)
            db.add(branch); db.flush()
    branch_id=branch.id
    print(f'Branch: {branch.code} ({branch_id})')
    have={c.name for c in db.scalars(select(ExpenseCategory))}
    for n in ['Electricity','Rent','Internet','Transport','Repair Tools','Packing','Tea/Food','Other','Salaries']:
        if n not in have: db.add(ExpenseCategory(name=n,is_system=True,is_active=True))
    roles={r.code:r for r in db.scalars(select(Role))}
    admin=roles.get('ADMIN') or Role(code='ADMIN',name='Administrator',is_system=True)
    cashier=roles.get('CASHIER') or Role(code='CASHIER',name='Cashier',is_system=True)
    db.add_all([admin,cashier]); db.flush()
    perms={p.code:p for p in db.scalars(select(Permission))}
    for code,name,desc in PERMISSIONS:
        perms.setdefault(code, Permission(code=code,name=name,description=desc))
        db.add(perms[code])
    db.flush()
    existing={(rp.role_id,rp.permission_id) for rp in db.scalars(select(RolePermission))}
    for code,p in perms.items():
        if (admin.id,p.id) not in existing: db.add(RolePermission(role_id=admin.id,permission_id=p.id))
    db.execute(__import__('sqlalchemy').delete(RolePermission).where(RolePermission.role_id==cashier.id, RolePermission.permission_id.in_([perms['CREDIT_SETTLE'].id] if 'CREDIT_SETTLE' in perms else [])))
    cashier_codes={'SALE_CREATE','RETURN_CREATE','REPAIR_CREATE','REPAIR_UPDATE','REPAIR_PAYMENT','WARRANTY_CREATE','DAY_MANAGE','REPORT_VIEW','STOCK_VIEW','PURCHASE_ENTRY','ITEM_EDIT','APPROVAL_REQUEST','EXPENSE_ENTRY','OTHER_INCOME_ENTRY','DOCUMENT_REPRINT'}
    for code in cashier_codes:
        p=perms[code]
        if (cashier.id,p.id) not in existing: db.add(RolePermission(role_id=cashier.id,permission_id=p.id))
    def ensure_user(prefix, role, required):
        if not required: return
        username=env(prefix+'_USERNAME'); password=env(prefix+'_PASSWORD'); display=env(prefix+'_DISPLAY_NAME',False) or username
        user=db.scalar(select(User).where(User.username==username))
        if user is None:
            db.add(User(username=username,password_hash=hash_password(password),display_name=display,role_id=role.id,branch_id=branch_id,must_change_password=False,is_active=True))
    ensure_user('ADMIN',admin,True)
    ensure_user('CASHIER',cashier,bool(os.getenv('CASHIER_USERNAME')))
    db.commit(); print('Security bootstrap complete.')
finally:
    db.close()
