from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import uuid

from sqlalchemy import literal, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.shop_identity import ShopIdentity


class ShopIdentityStatus(StrEnum):
    EMPTY = "EMPTY"
    PRESENT = "PRESENT"
    ENROLLMENT_REQUIRED = "ENROLLMENT_REQUIRED"
    INVALID = "INVALID"


class ShopIdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShopIdentityInspection:
    status: ShopIdentityStatus
    shop_id: uuid.UUID | None = None


_PRESEEDED_CATALOGS = {"roles", "permissions"}
_MIGRATION_MANAGED_STATE_TABLES = {"document_counters"}


def inspect_shop_identity(db: Session) -> ShopIdentityInspection:
    """Inspect canonical shop metadata without creating or inferring identity."""
    try:
        rows = db.execute(
            text(
                "SELECT identity_key, shop_id, identity_version "
                "FROM shop_identity"
            )
        ).all()
    except SQLAlchemyError as exc:
        raise ShopIdentityError("Unable to inspect shop identity metadata.") from exc

    if rows:
        if len(rows) != 1:
            return ShopIdentityInspection(ShopIdentityStatus.INVALID)
        identity_key, raw_shop_id, identity_version = rows[0]
        if identity_key != "primary" or identity_version != 1:
            return ShopIdentityInspection(ShopIdentityStatus.INVALID)
        try:
            shop_id = uuid.UUID(str(raw_shop_id))
        except (AttributeError, TypeError, ValueError):
            return ShopIdentityInspection(ShopIdentityStatus.INVALID)
        return ShopIdentityInspection(ShopIdentityStatus.PRESENT, shop_id)

    try:
        for table in Base.metadata.sorted_tables:
            if table.name in _PRESEEDED_CATALOGS | {"shop_identity"}:
                continue
            if db.execute(select(literal(1)).select_from(table).limit(1)).first():
                return ShopIdentityInspection(ShopIdentityStatus.ENROLLMENT_REQUIRED)

        for table_name in _MIGRATION_MANAGED_STATE_TABLES:
            state = db.execute(
                text(f"SELECT 1 FROM {table_name} LIMIT 1")
            ).first()
            if state:
                return ShopIdentityInspection(ShopIdentityStatus.ENROLLMENT_REQUIRED)
    except SQLAlchemyError as exc:
        raise ShopIdentityError(
            "Unable to verify whether shop identity enrollment is required."
        ) from exc

    return ShopIdentityInspection(ShopIdentityStatus.EMPTY)


def initialize_shop_identity(db: Session) -> uuid.UUID:
    """Create canonical identity only for an empty database; repeat calls are idempotent."""
    inspection = inspect_shop_identity(db)
    if inspection.status is ShopIdentityStatus.PRESENT:
        if inspection.shop_id is None:
            raise ShopIdentityError("Stored shop identity is malformed.")
        return inspection.shop_id
    if inspection.status is not ShopIdentityStatus.EMPTY:
        raise ShopIdentityError(
            "Shop identity enrollment is required; identity was not created."
        )

    shop_id = uuid.uuid4()
    db.add(ShopIdentity(shop_id=shop_id))
    db.flush()
    return shop_id
