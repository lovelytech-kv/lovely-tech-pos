from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import db_session, require_permission, require_any_permission
from app.models.master import User, Item, ItemBarcode, Category, ItemType, WarrantyDefault
from app.models.inventory import Purchase, PurchaseLine, StockMovement
from app.models.sales import Repair, RepairPart
from app.models.security import AuditLog
from app.schemas.items import BarcodeIn, ItemCreateIn, ItemReviewIn, ItemUpdateIn, PendingReviewItemOut, WarrantyDefaultIn
from app.services.numbering import NumberingService

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/admin-list")
def admin_list_items(q: str = "", active_only: bool = False, user: User = Depends(require_any_permission("ITEM_EDIT", "STOCK_VIEW")), db: Session = Depends(db_session)):
    term = q.strip()
    stmt = select(Item).options(
        selectinload(Item.barcodes),
        selectinload(Item.warranty_defaults),
    )
    if active_only:
        stmt = stmt.where(Item.is_active.is_(True))
    if term:
        like = f"%{term}%"
        from sqlalchemy import or_
        stmt = stmt.where(or_(Item.item_code.ilike(like), Item.description.ilike(like), Item.brand.ilike(like), Item.model.ilike(like), Item.compatible_models.ilike(like)))
    rows = db.scalars(stmt.order_by(Item.item_code).limit(200)).all()
    out=[]
    for item in rows:
        bars=sorted(item.barcodes, key=lambda b: (not b.is_primary, b.barcode))
        item._warranty_default = next(
            (w for w in sorted(item.warranty_defaults, key=lambda w: w.created_at, reverse=True) if w.is_active),
            None,
        )
        out.append(_out(item,bars))
    return out

@router.get("/masters")
def item_masters(user: User = Depends(require_any_permission("ITEM_EDIT", "STOCK_VIEW")), db: Session = Depends(db_session)):
    cats = db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
    types = db.scalars(select(ItemType).where(ItemType.is_active.is_(True)).order_by(ItemType.name)).all()
    return {"categories":[{"id":str(x.id),"name":x.name,"parent_id":str(x.parent_id) if x.parent_id else None} for x in cats],
            "item_types":[{"id":str(x.id),"code":x.code,"name":x.name,"is_serialized":x.is_serialized} for x in types]}


@router.get("/pending-review", response_model=list[PendingReviewItemOut])
def pending_review_items(user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    """Admin queue: items whose buy cost is still unknown (cashier purchases)."""
    if user.role.code.upper() != "ADMIN":
        raise HTTPException(403, "Admin only")
    rows = db.execute(
        select(Item, Category)
        .outerjoin(Category, Category.id == Item.category_id)
        .where(Item.needs_admin_review.is_(True), Item.is_active.is_(True))
        .order_by(Item.created_at)
    ).all()
    creators: dict = {}
    if rows:
        creator_rows = db.execute(
            select(AuditLog.entity_id, User.display_name)
            .join(User, User.id == AuditLog.actor_user_id)
            .where(AuditLog.action_type == "ITEM_CREATED", AuditLog.entity_id.in_([item.id for item, _ in rows]))
        ).all()
        creators = {entity_id: name for entity_id, name in creator_rows}
    return [
        PendingReviewItemOut(
            item_id=item.id, item_code=item.item_code, description=item.description,
            category_name=category.name if category else None,
            created_by=creators.get(item.id), created_at=item.created_at,
            buy_cost=item.buy_cost, low_stock_threshold=item.low_stock_threshold,
        ) for item, category in rows
    ]


@router.get("/check-name")
def check_item_name(name: str = "", exclude_id: str | None = None,
                    user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    """Cheap existence probe used by the item form while typing (case-insensitive)."""
    term = name.strip()
    if not term:
        return {"exists": False}
    stmt = select(Item.id).where(func.lower(Item.description) == term.lower())
    if exclude_id:
        try:
            stmt = stmt.where(Item.id != uuid.UUID(exclude_id))
        except ValueError:
            pass
    return {"exists": db.scalar(stmt) is not None}


@router.patch("/{item_id}/review")
def review_item_cost(item_id: str, payload: ItemReviewIn, user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    """Admin enters the missing buy cost and clears the review flag (audited)."""
    if user.role.code.upper() != "ADMIN":
        raise HTTPException(403, "Admin only")
    item = db.scalar(select(Item).where(Item.id == item_id).with_for_update())
    if not item:
        raise HTTPException(404, "Item not found")
    before = {
        "buy_cost": str(item.buy_cost) if item.buy_cost is not None else None,
        "needs_admin_review": item.needs_admin_review,
    }
    item.buy_cost = payload.buy_cost
    item.needs_admin_review = False
    item.version += 1
    db.add(AuditLog(
        branch_id=user.branch_id, actor_user_id=user.id, action_type="ITEM_COST_REVIEWED",
        entity_type="ITEM", entity_id=item.id, timestamp=datetime.now(timezone.utc),
        before_json=before, after_json={"buy_cost": str(payload.buy_cost), "needs_admin_review": False},
    ))
    db.commit()
    return {
        "item_id": str(item.id), "buy_cost": item.buy_cost,
        "needs_admin_review": item.needs_admin_review, "version": item.version,
    }


def _out(item, barcodes):
    # Admin item-master responses may include the active default warranty. Never expose
    # purchase cost or profit through this endpoint.
    default = getattr(item, "_warranty_default", None)
    return {"item_id": str(item.id), "item_code": item.item_code, "description": item.description,
            "brand": item.brand, "model": item.model, "compatible_models": item.compatible_models, "category_id": str(item.category_id),
            "item_type_id": str(item.item_type_id), "master_sale_price": item.master_sale_price,
            "low_stock_threshold": item.low_stock_threshold,
            "version": item.version, "is_active": item.is_active,
            "barcodes": [b.barcode for b in barcodes],
            "warranty_default": (
                {"warranty_type": default.warranty_type, "duration_value": default.duration_value,
                 "custom_rule": default.custom_rule, "is_active": default.is_active}
                if default else None
            )}

@router.post("")
def create_item(payload: ItemCreateIn, user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    if not db.get(Category, payload.category_id) or not db.get(ItemType, payload.item_type_id):
        raise HTTPException(400, "Category or item type not found")
    description = payload.description.strip()
    if db.scalar(select(Item.id).where(func.lower(Item.description) == description.lower())):
        raise HTTPException(422, "Item with this name already exists")
    if payload.item_code and user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Preserving an imported item code is Admin-only')
    if payload.item_code:
        code = payload.item_code.strip()
    else:
        # Imported items may already own codes such as LVT0042: skip any number that is taken.
        for _ in range(10000):
            code = NumberingService.next_number(db, "ITEM", str(user.branch_id), label="LVT", sep="", width=4)
            if not db.scalar(select(Item.id).where(Item.item_code == code)):
                break
        else:
            raise HTTPException(500, "Could not allocate a free item code")
    if db.scalar(select(Item.id).where(Item.item_code==code)):
        raise HTTPException(409, 'Item code already exists')
    item = Item(item_code=code, description=description, brand=payload.brand, model=payload.model, compatible_models=(payload.compatible_models or None),
                category_id=payload.category_id, item_type_id=payload.item_type_id,
                master_sale_price=payload.master_sale_price, low_stock_threshold=payload.low_stock_threshold)
    db.add(item); db.flush()
    if payload.barcode:
        db.add(ItemBarcode(item_id=item.id, barcode=payload.barcode.strip(), is_primary=True))
    db.add(AuditLog(branch_id=user.branch_id, actor_user_id=user.id, action_type="ITEM_CREATED",
                    entity_type="ITEM", entity_id=item.id, timestamp=datetime.now(timezone.utc),
                    after_json={"item_code": code, "description": item.description}))
    db.commit()
    return _out(item, list(item.barcodes) if hasattr(item, "barcodes") else list(db.scalars(select(ItemBarcode).where(ItemBarcode.item_id == item.id)).all()))

@router.put("/{item_id}")
def update_item(item_id: str, payload: ItemUpdateIn, user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    item = db.scalar(select(Item).where(Item.id == item_id).with_for_update())
    if not item: raise HTTPException(404, "Item not found")
    if item.version != payload.version: raise HTTPException(409, "Item was changed by another user; reload before editing")
    description = payload.description.strip()
    duplicate = db.scalar(
        select(Item.id).where(func.lower(Item.description) == description.lower(), Item.id != item.id)
    )
    if duplicate:
        raise HTTPException(422, "Item with this name already exists")
    before = {"description": item.description, "brand": item.brand, "model": item.model,
              "category_id": str(item.category_id), "item_type_id": str(item.item_type_id),
              "master_sale_price": str(item.master_sale_price) if item.master_sale_price is not None else None,
              "low_stock_threshold": item.low_stock_threshold}
    item.description = description; item.brand = payload.brand; item.model = payload.model; item.compatible_models = (payload.compatible_models or None)
    item.category_id = payload.category_id; item.item_type_id = payload.item_type_id
    item.master_sale_price = payload.master_sale_price
    item.low_stock_threshold = payload.low_stock_threshold
    item.version += 1
    db.add(AuditLog(branch_id=user.branch_id, actor_user_id=user.id, action_type="ITEM_EDITED",
                    entity_type="ITEM", entity_id=item.id, timestamp=datetime.now(timezone.utc),
                    before_json=before, after_json={"version": item.version, "low_stock_threshold": item.low_stock_threshold}))
    db.commit()
    bars=list(db.scalars(select(ItemBarcode).where(ItemBarcode.item_id == item.id)).all())
    return _out(item,bars)

@router.delete('/{item_id}')
def deactivate_item(item_id: str, user: User = Depends(require_permission('ITEM_EDIT')), db: Session = Depends(db_session)):
    """Soft delete: hide from POS/masters but keep history. Admin only."""
    if user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Admin only')
    item = db.scalar(select(Item).where(Item.id == item_id).with_for_update())
    if not item:
        raise HTTPException(404, 'Item not found')
    if not item.is_active:
        return {'item_id': str(item.id), 'is_active': False, 'already_inactive': True}
    stock = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_delta), 0)).where(StockMovement.item_id == item.id)) or 0
    if stock > 0:
        raise HTTPException(409, f'Cannot deactivate: {stock} unit(s) in stock')
    pending_lines = db.scalar(
        select(func.count(PurchaseLine.id))
        .join(Purchase, Purchase.id == PurchaseLine.purchase_id)
        .where(PurchaseLine.item_id == item.id, Purchase.status == 'PENDING_COST')
    ) or 0
    if pending_lines:
        raise HTTPException(409, f'Cannot deactivate: item is on {pending_lines} purchase line(s) awaiting cost review')
    pending_repairs = db.scalar(
        select(func.count(RepairPart.id))
        .join(Repair, Repair.id == RepairPart.repair_id)
        .where(RepairPart.item_id == item.id, Repair.status.notin_(['DELIVERED', 'RETURNED TO CUSTOMER', 'CANCELLED']))
    ) or 0
    if pending_repairs:
        raise HTTPException(409, f'Cannot deactivate: item is used by {pending_repairs} open repair(s)')
    item.is_active = False
    item.version += 1
    db.add(AuditLog(
        branch_id=user.branch_id, actor_user_id=user.id, action_type='ITEM_DEACTIVATED',
        entity_type='ITEM', entity_id=item.id, timestamp=datetime.now(timezone.utc),
        before_json={'item_code': item.item_code, 'description': item.description, 'is_active': True},
        after_json={'is_active': False, 'stock': str(stock)},
    ))
    db.commit()
    return {'item_id': str(item.id), 'is_active': False}


@router.post('/{item_id}/reactivate')
def reactivate_item(item_id: str, user: User = Depends(require_permission('ITEM_EDIT')), db: Session = Depends(db_session)):
    """Restore a soft-deleted item to the active master. Admin only, audited."""
    if user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Admin only')
    item = db.scalar(select(Item).where(Item.id == item_id).with_for_update())
    if not item:
        raise HTTPException(404, 'Item not found')
    if item.is_active:
        return {'item_id': str(item.id), 'is_active': True, 'already_active': True}
    item.is_active = True
    item.version += 1
    db.add(AuditLog(
        branch_id=user.branch_id, actor_user_id=user.id, action_type='ITEM_REACTIVATED',
        entity_type='ITEM', entity_id=item.id, timestamp=datetime.now(timezone.utc),
        before_json={'item_code': item.item_code, 'description': item.description, 'is_active': False},
        after_json={'is_active': True, 'needs_admin_review': item.needs_admin_review},
    ))
    db.commit()
    return {'item_id': str(item.id), 'is_active': True}


@router.post("/{item_id}/barcodes")
def add_barcode(item_id: str, payload: BarcodeIn, user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    item=db.scalar(select(Item).where(Item.id==item_id).with_for_update())
    if not item: raise HTTPException(404,"Item not found")
    existing=db.scalar(select(ItemBarcode).where(ItemBarcode.barcode==payload.barcode.strip()))
    if existing and existing.item_id != item.id: raise HTTPException(409,"Barcode already belongs to another item")
    if existing: raise HTTPException(409,"Barcode already exists for this item")
    if payload.is_primary:
        for b in db.scalars(select(ItemBarcode).where(ItemBarcode.item_id==item.id).with_for_update()).all(): b.is_primary=False
    b=ItemBarcode(item_id=item.id, barcode=payload.barcode.strip(), is_primary=payload.is_primary)
    db.add(b); db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type="ITEM_BARCODE_ADDED",entity_type="ITEM_BARCODE",entity_id=b.id,timestamp=datetime.now(timezone.utc),after_json={"barcode":b.barcode}))
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"Barcode already exists")
    return {"barcode":b.barcode,"is_primary":b.is_primary}


@router.put('/{item_id}/warranty-default')
def set_warranty_default(item_id: str, payload: WarrantyDefaultIn,
                         user: User = Depends(require_permission('ITEM_EDIT')),
                         db: Session = Depends(db_session)):
    if user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Admin only')
    allowed = {'NONE', 'DAYS', 'MONTHS', 'CHECKING ONLY', 'CUSTOM'}
    wt = payload.warranty_type.strip().upper()
    if wt not in allowed:
        raise HTTPException(400, 'Unsupported warranty type')
    if wt in {'NONE', 'CHECKING ONLY'} and (payload.duration_value is not None or payload.custom_rule):
        raise HTTPException(400, 'This warranty type cannot have a duration/custom rule')
    if wt in {'DAYS', 'MONTHS'} and payload.duration_value is None:
        raise HTTPException(400, 'Duration is required for calendar warranty')
    if wt == 'CUSTOM' and not (payload.custom_rule or '').strip():
        raise HTTPException(400, 'Custom rule is required for CUSTOM warranty')
    item = db.scalar(select(Item).where(Item.id == item_id, Item.is_active.is_(True)).with_for_update())
    if not item:
        raise HTTPException(404, 'Item not found')
    defaults = db.scalars(select(WarrantyDefault).where(WarrantyDefault.item_id == item.id, WarrantyDefault.is_active.is_(True)).with_for_update()).all()
    for row in defaults:
        row.is_active = False
    row = WarrantyDefault(item_id=item.id, warranty_type=wt, duration_value=payload.duration_value, custom_rule=payload.custom_rule, is_active=True)
    db.add(row); db.flush()
    from app.models.security import AuditLog
    from datetime import datetime, timezone
    db.add(AuditLog(branch_id=user.branch_id, actor_user_id=user.id, action_type='ITEM_WARRANTY_DEFAULT_CHANGED',
                    entity_type='ITEM', entity_id=item.id, timestamp=datetime.now(timezone.utc),
                    before_json={'active_count': len(defaults)},
                    after_json={'warranty_type': wt, 'duration_value': payload.duration_value, 'custom_rule': payload.custom_rule}))
    db.commit()
    return {'item_id': str(item.id), 'warranty_default': {'warranty_type': wt, 'duration_value': payload.duration_value, 'custom_rule': payload.custom_rule, 'is_active': True}}

@router.get('/{item_id}/variants')
def variants(item_id:str,user:User=Depends(require_permission('STOCK_VIEW')),db:Session=Depends(db_session)):
    from app.models.master import Variant
    rows=db.scalars(select(Variant).where(Variant.item_id==item_id).order_by(Variant.name,Variant.value)).all()
    return [{'variant_id':str(x.id),'name':x.name,'value':x.value} for x in rows]

@router.post('/{item_id}/variants')
def add_variant(item_id:str,payload:dict,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    from app.models.master import Variant
    name=str(payload.get('name','')).strip(); value=str(payload.get('value','')).strip()
    if not name or not value: raise HTTPException(400,'Variant name and value are required')
    item=db.get(Item,item_id)
    if not item: raise HTTPException(404,'Item not found')
    if db.scalar(select(Variant.id).where(Variant.item_id==item.id,Variant.name==name,Variant.value==value)): raise HTTPException(409,'Variant already exists')
    row=Variant(item_id=item.id,name=name,value=value); db.add(row); db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='ITEM_VARIANT_ADDED',entity_type='ITEM_VARIANT',entity_id=row.id,timestamp=datetime.now(timezone.utc),after_json={'name':name,'value':value},source_transaction_id=item.id)); db.commit(); return {'variant_id':str(row.id),'name':name,'value':value}

@router.post('/categories')
def create_category(payload:dict,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    name=str(payload.get('name','')).strip(); parent_id=payload.get('parent_id')
    if not name: raise HTTPException(400,'Category name is required')
    if len(name) > 120: raise HTTPException(400,'Category name is too long (max 120 characters)')
    if parent_id and not db.get(Category, parent_id): raise HTTPException(400,'Parent category not found')
    row=Category(name=name,parent_id=parent_id or None); db.add(row); db.flush()
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='CATEGORY_CREATED',entity_type='CATEGORY',entity_id=row.id,timestamp=datetime.now(timezone.utc),after_json={'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}))
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Category name already exists under this parent')
    return {'id':str(row.id),'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}


@router.put('/categories/{category_id}')
def update_category(category_id:str,payload:dict,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    row=db.get(Category,category_id)
    if not row: raise HTTPException(404,'Category not found')
    name=str(payload.get('name','')).strip()
    if not name: raise HTTPException(400,'Category name is required')
    if len(name) > 120: raise HTTPException(400,'Category name is too long (max 120 characters)')
    parent_raw=payload.get('parent_id') or None
    parent_id=None
    if parent_raw:
        if str(parent_raw)==str(row.id): raise HTTPException(400,'A category cannot be its own parent')
        parent=db.get(Category,parent_raw)
        if not parent: raise HTTPException(400,'Parent category not found')
        cursor=parent; seen:set[str]=set()
        while cursor is not None and str(cursor.id) not in seen:
            if cursor.id==row.id: raise HTTPException(400,'Category parent would create a loop')
            seen.add(str(cursor.id))
            cursor=db.get(Category,cursor.parent_id) if cursor.parent_id else None
        parent_id=parent.id
    before={'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}
    row.name=name; row.parent_id=parent_id; row.version += 1
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='CATEGORY_UPDATED',entity_type='CATEGORY',entity_id=row.id,timestamp=datetime.now(timezone.utc),before_json=before,after_json={'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}))
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Category name already exists under this parent')
    return {'id':str(row.id),'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}


@router.delete('/categories/{category_id}')
def delete_category(category_id:str,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    row=db.get(Category,category_id)
    if not row: raise HTTPException(404,'Category not found')
    item_count=db.scalar(select(func.count(Item.id)).where(Item.category_id==row.id)) or 0
    if item_count: raise HTTPException(409,f'{item_count} item(s) use this category')
    child_count=db.scalar(select(func.count(Category.id)).where(Category.parent_id==row.id)) or 0
    if child_count: raise HTTPException(409,f'Category has {child_count} child categor{"y" if child_count==1 else "ies"}')
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='CATEGORY_DELETED',entity_type='CATEGORY',entity_id=row.id,timestamp=datetime.now(timezone.utc),before_json={'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}))
    db.delete(row); db.commit()
    return {'id':str(row.id),'deleted':True}


@router.post('/item-types')
def create_item_type(payload:dict,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    code=str(payload.get('code','')).strip(); name=str(payload.get('name','')).strip(); serialized=bool(payload.get('is_serialized',False))
    if not code or not name: raise HTTPException(400,'Item type code and name are required')
    if len(code) > 50 or len(name) > 120: raise HTTPException(400,'Item type code or name is too long')
    if db.scalar(select(ItemType.id).where(func.lower(ItemType.code) == code.lower())):
        raise HTTPException(409,'Item type code already exists')
    row=ItemType(code=code,name=name,is_serialized=serialized); db.add(row); db.flush()
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='ITEM_TYPE_CREATED',entity_type='ITEM_TYPE',entity_id=row.id,timestamp=datetime.now(timezone.utc),after_json={'code':row.code,'name':row.name,'is_serialized':row.is_serialized}))
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Item type code already exists')
    return {'id':str(row.id),'code':row.code,'name':row.name,'is_serialized':row.is_serialized}


@router.put('/item-types/{type_id}')
def update_item_type(type_id:str,payload:dict,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    row=db.get(ItemType,type_id)
    if not row: raise HTTPException(404,'Item type not found')
    code=str(payload.get('code',row.code)).strip(); name=str(payload.get('name',row.name)).strip()
    serialized=bool(payload.get('is_serialized',row.is_serialized))
    if not code or not name: raise HTTPException(400,'Item type code and name are required')
    if len(code) > 50 or len(name) > 120: raise HTTPException(400,'Item type code or name is too long')
    duplicate=db.scalar(select(ItemType.id).where(func.lower(ItemType.code)==code.lower(),ItemType.id!=row.id))
    if duplicate: raise HTTPException(409,'Item type code already exists')
    item_count=db.scalar(select(func.count(Item.id)).where(Item.item_type_id==row.id)) or 0
    warning=None
    if serialized != row.is_serialized and item_count:
        warning=f'{item_count} item(s) already use this type; changing the serialized setting can affect IMEI handling.'
    before={'code':row.code,'name':row.name,'is_serialized':row.is_serialized}
    row.code=code; row.name=name; row.is_serialized=serialized
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='ITEM_TYPE_UPDATED',entity_type='ITEM_TYPE',entity_id=row.id,timestamp=datetime.now(timezone.utc),before_json=before,after_json={'code':row.code,'name':row.name,'is_serialized':row.is_serialized,'item_count':int(item_count)}))
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Item type code already exists')
    return {'id':str(row.id),'code':row.code,'name':row.name,'is_serialized':row.is_serialized,'warning':warning}


@router.delete('/item-types/{type_id}')
def delete_item_type(type_id:str,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    row=db.get(ItemType,type_id)
    if not row: raise HTTPException(404,'Item type not found')
    item_count=db.scalar(select(func.count(Item.id)).where(Item.item_type_id==row.id)) or 0
    if item_count: raise HTTPException(409,f'{item_count} item(s) use this item type')
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='ITEM_TYPE_DELETED',entity_type='ITEM_TYPE',entity_id=row.id,timestamp=datetime.now(timezone.utc),before_json={'code':row.code,'name':row.name,'is_serialized':row.is_serialized}))
    db.delete(row); db.commit()
    return {'id':str(row.id),'deleted':True}
