from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User, Item, ItemBarcode, WarrantyDefault
from app.models.inventory import StockMovement

router=APIRouter(prefix="/inventory",tags=["inventory"])

@router.get("/items/search")
def search_items(q:str=Query(default="",max_length=120),limit:int=20,user:User=Depends(require_permission("STOCK_VIEW")),db:Session=Depends(db_session)):
    q=q.strip()
    stmt=select(Item).where(Item.is_active.is_(True))
    if q:
        stmt=stmt.outerjoin(ItemBarcode,ItemBarcode.item_id==Item.id).where((Item.item_code.ilike(f"%{q}%")) | (Item.description.ilike(f"%{q}%")) | (Item.brand.ilike(f"%{q}%")) | (Item.model.ilike(f"%{q}%")) | (ItemBarcode.barcode==q))
    stock_expr = func.coalesce(select(func.sum(StockMovement.quantity_delta)).where(StockMovement.branch_id==user.branch_id, StockMovement.item_id==Item.id).scalar_subquery(), 0)
    rows=db.scalars(stmt.order_by((stock_expr <= 0), Item.description).limit(min(limit,50))).all()
    result=[]
    for item in rows:
        stock=Decimal(db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_delta),0)).where(StockMovement.branch_id==user.branch_id,StockMovement.item_id==item.id)) or 0)
        warranty = db.scalar(select(WarrantyDefault).where(WarrantyDefault.item_id==item.id, WarrantyDefault.is_active.is_(True)).order_by(WarrantyDefault.created_at.desc()))
        result.append({"item_id":str(item.id),"item_code":item.item_code,"description":item.description,"brand":item.brand,"model":item.model,"sale_price":item.master_sale_price,"stock":stock,
                       "warranty_default": ({"warranty_type": warranty.warranty_type, "duration_value": warranty.duration_value, "custom_rule": warranty.custom_rule} if warranty else None)})
    return result

@router.get("/summary")
def stock_summary(user:User=Depends(require_permission("STOCK_VIEW")),db:Session=Depends(db_session)):
    rows=db.execute(select(Item.id,Item.item_code,Item.description,func.coalesce(func.sum(StockMovement.quantity_delta),0).label("stock")).outerjoin(StockMovement,(StockMovement.item_id==Item.id)&(StockMovement.branch_id==user.branch_id)).where(Item.is_active.is_(True)).group_by(Item.id).order_by(Item.description)).all()
    return [{"item_id":str(r.id),"item_code":r.item_code,"description":r.description,"stock":Decimal(r.stock or 0)} for r in rows]


@router.get("/serialized/search")
def search_serialized(q: str, user: User = Depends(require_permission("STOCK_VIEW")), db: Session = Depends(db_session)):
    from app.models.inventory import SerializedUnit
    stmt = select(SerializedUnit, Item).join(Item, Item.id == SerializedUnit.item_id).where(SerializedUnit.branch_id == user.branch_id, SerializedUnit.serial_number.ilike(f"%{q.strip()}%"))
    rows = db.execute(stmt.order_by(SerializedUnit.serial_number).limit(50)).all()
    return [{"serialized_unit_id": str(u.id), "serial_number": u.serial_number, "status": u.status, "item_id": str(u.item_id), "item_code": i.item_code, "description": i.description} for u, i in rows]

