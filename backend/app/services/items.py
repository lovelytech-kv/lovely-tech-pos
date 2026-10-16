from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.master import Item, ItemBarcode, Category, ItemType
from app.models.security import AuditLog
from app.schemas.items import ItemCreateIn
from app.services.numbering import NumberingService


class ItemCreationError(ValueError):
    """Raised when item creation fails due to validation or conflict."""
    pass


@dataclass(frozen=True)
class ItemCreationInput:
    """Input data for item creation, decoupled from HTTP layer."""
    item_code: Optional[str]
    description: str
    category_id: uuid.UUID
    item_type_id: uuid.UUID
    brand: Optional[str] = None
    model: Optional[str] = None
    master_sale_price: Optional[Decimal] = None
    barcode: Optional[str] = None


@dataclass(frozen=True)
class ItemCreationResult:
    """Result of item creation, containing the created item and its barcodes."""
    item: Item
    barcodes: tuple[ItemBarcode, ...]


class ItemService:
    """Business logic for item operations.

    This service operates within the caller's database transaction.
    It does not commit; the caller (API layer or import workflow)
    owns the transaction boundary.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_item(
        self,
        input_data: ItemCreationInput,
        *,
        branch_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_admin: bool,
    ) -> ItemCreationResult:
        """Create a new item with optional primary barcode and audit log.

        Args:
            input_data: Validated item creation input.
            branch_id: Branch ID for numbering and audit log.
            actor_user_id: User ID of the actor creating the item.
            is_admin: Whether the actor is an admin (allows explicit item_code).

        Returns:
            ItemCreationResult with the created item and its barcodes.

        Raises:
            ItemCreationError: If validation fails or item_code conflicts.
        """
        # Validate references
        if not self.session.get(Category, input_data.category_id):
            raise ItemCreationError("Category not found")
        if not self.session.get(ItemType, input_data.item_type_id):
            raise ItemCreationError("Item type not found")

        # Determine item_code
        if input_data.item_code:
            if not is_admin:
                raise ItemCreationError("Preserving an imported item code is Admin-only")
            code = input_data.item_code.strip()
        else:
            code = NumberingService.next_number(self.session, "ITEM", str(branch_id))

        # Check for duplicate item_code
        if self.session.scalar(select(Item.id).where(Item.item_code == code)):
            raise ItemCreationError("Item code already exists")

        # Create item
        item = Item(
            item_code=code,
            description=input_data.description.strip(),
            brand=input_data.brand,
            model=input_data.model,
            category_id=input_data.category_id,
            item_type_id=input_data.item_type_id,
            master_sale_price=input_data.master_sale_price,
        )
        self.session.add(item)
        self.session.flush()

        # Create primary barcode if provided
        barcodes: list[ItemBarcode] = []
        if input_data.barcode:
            barcode_obj = ItemBarcode(
                item_id=item.id,
                barcode=input_data.barcode.strip(),
                is_primary=True,
            )
            self.session.add(barcode_obj)
            barcodes.append(barcode_obj)

        # Audit log
        self.session.add(
            AuditLog(
                branch_id=branch_id,
                actor_user_id=actor_user_id,
                action_type="ITEM_CREATED",
                entity_type="ITEM",
                entity_id=item.id,
                timestamp=datetime.now(timezone.utc),
                after_json={"item_code": code, "description": item.description},
            )
        )

        return ItemCreationResult(item=item, barcodes=tuple(barcodes))


def create_item_from_schema(
    session: Session,
    payload: ItemCreateIn,
    *,
    branch_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    is_admin: bool,
) -> ItemCreationResult:
    """Convenience function to create item from API schema.

    This is a thin wrapper for the existing API route to call the service
    without duplicating the schema-to-input mapping logic.
    """
    service = ItemService(session)
    return service.create_item(
        ItemCreationInput(
            item_code=payload.item_code,
            description=payload.description,
            category_id=payload.category_id,
            item_type_id=payload.item_type_id,
            brand=payload.brand,
            model=payload.model,
            master_sale_price=payload.master_sale_price,
            barcode=payload.barcode,
        ),
        branch_id=branch_id,
        actor_user_id=actor_user_id,
        is_admin=is_admin,
    )