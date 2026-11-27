"""Invoice / receipt template CRUD (Session 3C-2).

The branded "Software by Lovely Tech" line is NOT configurable here. It is
appended by the receipt builder after all template content.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_any_permission, require_permission
from app.models.invoice_template import InvoiceTemplate
from app.models.master import User
from app.models.security import AuditLog
from app.schemas.invoice_template import (
    InvoiceTemplateCreate,
    InvoiceTemplateOut,
    InvoiceTemplateUpdate,
)

router = APIRouter(prefix='/invoice-templates', tags=['invoice-templates'])

_SNAPSHOT_FIELDS = (
    'name', 'paper_size', 'is_default', 'is_active',
    'show_logo', 'header_text', 'show_address', 'show_phone', 'show_email',
    'show_customer_name', 'show_customer_phone', 'show_item_description',
    'show_item_code', 'show_unit_price', 'show_warranty_info',
    'show_repair_details', 'show_payment_method', 'show_cashier',
    'show_customer_notes', 'logo_monochrome',
    'footer_text', 'warranty_terms', 'show_footer_note',
)


def _snapshot(template: InvoiceTemplate) -> dict:
    data: dict = {'id': str(template.id)}
    for field in _SNAPSHOT_FIELDS:
        data[field] = getattr(template, field)
    data['created_by'] = str(template.created_by) if template.created_by else None
    return data


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_name(value: str) -> str:
    name = (value or '').strip()
    if not name:
        raise HTTPException(400, 'Template name is required')
    return name


def _get_template(db: Session, template_id: UUID, lock: bool = False) -> InvoiceTemplate:
    stmt = select(InvoiceTemplate).where(InvoiceTemplate.id == template_id)
    if lock:
        stmt = stmt.with_for_update()
    template = db.scalar(stmt)
    if template is None:
        raise HTTPException(404, 'Invoice template not found')
    return template


def _audit(
    db: Session,
    user: User,
    *,
    action: str,
    template_id: UUID,
    before: dict | None,
    after: dict | None,
) -> None:
    db.add(AuditLog(
        branch_id=user.branch_id,
        actor_user_id=user.id,
        action_type=action,
        entity_type='INVOICE_TEMPLATE',
        entity_id=template_id,
        timestamp=datetime.now(timezone.utc),
        before_json=before,
        after_json=after,
        source_transaction_id=template_id,
    ))


@router.get('', response_model=list[InvoiceTemplateOut])
def list_invoice_templates(
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    templates = db.scalars(
        select(InvoiceTemplate).order_by(
            InvoiceTemplate.paper_size,
            InvoiceTemplate.is_default.desc(),
            InvoiceTemplate.name,
        )
    ).all()
    return templates


@router.get('/default', response_model=InvoiceTemplateOut)
def get_default_invoice_template(
    paper_size: Literal['80mm', 'A4'] = Query(default='80mm'),
    user: User = Depends(require_any_permission('SALE_CREATE', 'RETURN_CREATE', 'ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    """Print-time lookup for cashiers. Falls back to frontend defaults on 404."""
    template = db.scalar(select(InvoiceTemplate).where(
        InvoiceTemplate.paper_size == paper_size,
        InvoiceTemplate.is_default.is_(True),
        InvoiceTemplate.is_active.is_(True),
    ))
    if template is None:
        raise HTTPException(404, f'No active default {paper_size} template')
    return template


@router.post('', response_model=InvoiceTemplateOut)
def create_invoice_template(
    payload: InvoiceTemplateCreate,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    now = datetime.now(timezone.utc)
    template = InvoiceTemplate(
        name=_clean_name(payload.name),
        paper_size=payload.paper_size,
        is_default=False,
        is_active=payload.is_active,
        show_logo=payload.show_logo,
        header_text=_clean_text(payload.header_text),
        show_address=payload.show_address,
        show_phone=payload.show_phone,
        show_email=payload.show_email,
        show_customer_name=payload.show_customer_name,
        show_customer_phone=payload.show_customer_phone,
        show_item_description=payload.show_item_description,
        show_item_code=payload.show_item_code,
        show_unit_price=payload.show_unit_price,
        show_warranty_info=payload.show_warranty_info,
        show_repair_details=payload.show_repair_details,
        show_payment_method=payload.show_payment_method,
        show_cashier=payload.show_cashier,
        show_customer_notes=payload.show_customer_notes,
        logo_monochrome=payload.logo_monochrome,
        footer_text=_clean_text(payload.footer_text),
        warranty_terms=_clean_text(payload.warranty_terms),
        show_footer_note=payload.show_footer_note,
        created_at=now,
        updated_at=now,
        created_by=user.id,
    )
    db.add(template)
    db.flush()
    _audit(
        db, user,
        action='INVOICE_TEMPLATE_CREATED',
        template_id=template.id,
        before=None,
        after=_snapshot(template),
    )
    db.commit()
    return template


@router.get('/{template_id}', response_model=InvoiceTemplateOut)
def get_invoice_template(
    template_id: UUID,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    return _get_template(db, template_id)


@router.put('/{template_id}', response_model=InvoiceTemplateOut)
def update_invoice_template(
    template_id: UUID,
    payload: InvoiceTemplateUpdate,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    template = _get_template(db, template_id, lock=True)
    before = _snapshot(template)
    data = payload.model_dump(exclude_unset=True)

    if 'name' in data:
        template.name = _clean_name(data['name'])

    if 'paper_size' in data and data['paper_size'] is not None:
        new_paper = data['paper_size']
        if new_paper != template.paper_size:
            if template.is_default:
                existing_default = db.scalar(select(InvoiceTemplate.id).where(
                    InvoiceTemplate.paper_size == new_paper,
                    InvoiceTemplate.is_default.is_(True),
                    InvoiceTemplate.is_active.is_(True),
                    InvoiceTemplate.id != template.id,
                ))
                if existing_default is not None:
                    raise HTTPException(
                        409,
                        f'An active default {new_paper} template already exists; '
                        'set this template as default after changing the paper size.',
                    )
            template.paper_size = new_paper

    if data.get('is_active') is False and template.is_default:
        raise HTTPException(409, 'The default template cannot be deactivated. Set another template as default first.')

    for field in ('is_active', 'show_logo', 'show_address', 'show_phone',
                  'show_email', 'show_customer_name', 'show_customer_phone',
                  'show_item_description', 'show_item_code', 'show_unit_price',
                  'show_warranty_info', 'show_repair_details', 'show_footer_note',
                  'show_payment_method', 'show_cashier', 'show_customer_notes',
                  'logo_monochrome'):
        if field in data and data[field] is not None:
            setattr(template, field, data[field])

    for field in ('header_text', 'footer_text', 'warranty_terms'):
        if field in data:
            setattr(template, field, _clean_text(data[field]))

    template.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit(
        db, user,
        action='INVOICE_TEMPLATE_UPDATED',
        template_id=template.id,
        before=before,
        after=_snapshot(template),
    )
    db.commit()
    return template


@router.delete('/{template_id}')
def delete_invoice_template(
    template_id: UUID,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    template = _get_template(db, template_id, lock=True)
    if template.is_default:
        raise HTTPException(409, 'Cannot delete the default template. Set another template as default first.')

    total = db.scalar(select(func.count()).select_from(InvoiceTemplate)) or 0
    if total <= 1:
        raise HTTPException(409, 'At least one invoice template must remain.')

    before = _snapshot(template)
    _audit(
        db, user,
        action='INVOICE_TEMPLATE_DELETED',
        template_id=template.id,
        before=before,
        after=None,
    )
    db.delete(template)
    db.commit()
    return {'deleted': True, 'id': str(template_id)}


@router.post('/{template_id}/set-default', response_model=InvoiceTemplateOut)
def set_default_invoice_template(
    template_id: UUID,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    template = _get_template(db, template_id, lock=True)
    if not template.is_active:
        raise HTTPException(409, 'Activate this template before making it the default.')

    now = datetime.now(timezone.utc)
    previous = db.scalar(select(InvoiceTemplate).where(
        InvoiceTemplate.paper_size == template.paper_size,
        InvoiceTemplate.is_default.is_(True),
        InvoiceTemplate.id != template.id,
    ))
    before = {'default_id': str(previous.id) if previous else None,
              'default_name': previous.name if previous else None}

    db.execute(update(InvoiceTemplate).where(
        InvoiceTemplate.paper_size == template.paper_size,
        InvoiceTemplate.is_default.is_(True),
        InvoiceTemplate.id != template.id,
    ).values(is_default=False, updated_at=now))

    template.is_default = True
    template.updated_at = now
    db.flush()
    _audit(
        db, user,
        action='INVOICE_TEMPLATE_DEFAULT_SET',
        template_id=template.id,
        before=before,
        after={'default_id': str(template.id), 'default_name': template.name,
               'paper_size': template.paper_size},
    )
    db.commit()
    return template
