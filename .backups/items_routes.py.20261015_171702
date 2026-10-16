from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User, Item, ItemBarcode, Category, ItemType, WarrantyDefault
from app.models.security import AuditLog
from app.schemas.items import ItemCreateIn, ItemUpdateIn, BarcodeIn, WarrantyDefaultIn
from app.services.numbering import NumberingService

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/admin-list")
def admin_list_items(q: str = "", active_only: bool = False, user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    term = q.strip()
    stmt = select(Item)
    if active_only:
        stmt = stmt.where(Item.is_active.is_(True))
    if term:
        like = f"%{term}%"
        from sqlalchemy import or_
        stmt = stmt.where(or_(Item.item_code.ilike(like), Item.description.ilike(like), Item.brand.ilike(like), Item.model.ilike(like)))
    rows = db.scalars(stmt.order_by(Item.item_code).limit(200)).all()
    out=[]
    for item in rows:
        bars=db.scalars(select(ItemBarcode).where(ItemBarcode.item_id==item.id).order_by(ItemBarcode.is_primary.desc(), ItemBarcode.barcode)).all()
        item._warranty_default = db.scalar(
            select(WarrantyDefault).where(WarrantyDefault.item_id==item.id, WarrantyDefault.is_active.is_(True))
            .order_by(WarrantyDefault.created_at.desc())
        )
        out.append(_out(item,bars))
    return out

@router.get("/masters")
def item_masters(user: User = Depends(require_permission("ITEM_EDIT")), db: Session = Depends(db_session)):
    cats = db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
    types = db.scalars(select(ItemType).where(ItemType.is_active.is_(True)).order_by(ItemType.name)).all()
    return {"categories":[{"id":str(x.id),"name":x.name,"parent_id":str(x.parent_id) if x.parent_id else None} for x in cats],
            "item_types":[{"id":str(x.id),"code":x.code,"name":x.name,"is_serialized":x.is_serialized} for x in types]}


def _out(item, barcodes):
    # Admin item-master responses may include the active default warranty. Never expose
    # purchase cost or profit through this endpoint.
    default = getattr(item, "_warranty_default", None)
    return {"item_id": str(item.id), "item_code": item.item_code, "description": item.description,
            "brand": item.brand, "model": item.model, "category_id": str(item.category_id),
            "item_type_id": str(item.item_type_id), "master_sale_price": item.master_sale_price,
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
    if payload.item_code and user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Preserving an imported item code is Admin-only')
    code = payload.item_code.strip() if payload.item_code else NumberingService.next_number(db, "ITEM", str(user.branch_id))
    if db.scalar(select(Item.id).where(Item.item_code==code)):
        raise HTTPException(409, 'Item code already exists')
    item = Item(item_code=code, description=payload.description.strip(), brand=payload.brand, model=payload.model,
                category_id=payload.category_id, item_type_id=payload.item_type_id,
                master_sale_price=payload.master_sale_price)
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
    before = {"description": item.description, "brand": item.brand, "model": item.model,
              "category_id": str(item.category_id), "item_type_id": str(item.item_type_id),
              "master_sale_price": str(item.master_sale_price) if item.master_sale_price is not None else None}
    item.description = payload.description.strip(); item.brand = payload.brand; item.model = payload.model
    item.category_id = payload.category_id; item.item_type_id = payload.item_type_id
    item.master_sale_price = payload.master_sale_price; item.version += 1
    db.add(AuditLog(branch_id=user.branch_id, actor_user_id=user.id, action_type="ITEM_EDITED",
                    entity_type="ITEM", entity_id=item.id, timestamp=datetime.now(timezone.utc),
                    before_json=before, after_json={"version": item.version}))
    db.commit()
    bars=list(db.scalars(select(ItemBarcode).where(ItemBarcode.item_id == item.id)).all())
    return _out(item,bars)

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
    row=Category(name=name,parent_id=parent_id or None); db.add(row); db.commit(); return {'id':str(row.id),'name':row.name,'parent_id':str(row.parent_id) if row.parent_id else None}

@router.post('/item-types')
def create_item_type(payload:dict,user:User=Depends(require_permission('ITEM_EDIT')),db:Session=Depends(db_session)):
    if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Admin only')
    code=str(payload.get('code','')).strip(); name=str(payload.get('name','')).strip(); serialized=bool(payload.get('is_serialized',False))
    if not code or not name: raise HTTPException(400,'Item type code and name are required')
    row=ItemType(code=code,name=name,is_serialized=serialized); db.add(row); db.commit(); return {'id':str(row.id),'code':row.code,'name':row.name,'is_serialized':row.is_serialized}
