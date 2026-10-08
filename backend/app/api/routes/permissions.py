from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, current_user
from app.models.master import Permission, RolePermission, User
from app.schemas.api import PermissionOut

router = APIRouter(prefix="/permissions", tags=["permissions"])

@router.get("/mine", response_model=list[PermissionOut])
def mine(user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role.code.upper() == "ADMIN":
        rows = db.scalars(select(Permission).order_by(Permission.code)).all()
    else:
        rows = db.scalars(select(Permission).join(RolePermission, RolePermission.permission_id == Permission.id).where(RolePermission.role_id == user.role_id).order_by(Permission.code)).all()
    return [PermissionOut(code=x.code, name=x.name, description=x.description) for x in rows]
