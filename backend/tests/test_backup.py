import uuid

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.backup.service import (
    BackupError,
    decrypt_backup,
    encrypt_backup,
    validate_backup_envelope_metadata,
)
from app.api.routes.backup import _backup_envelope_metadata
from app.models.shop_identity import ShopIdentity

def test_backup_encrypt_roundtrip():
    blob = encrypt_backup(b"postgres-dump", secret="secret")
    meta, raw = decrypt_backup(blob, secret="secret")
    assert raw == b"postgres-dump"
    assert meta["size"] == len(raw)

def test_backup_wrong_secret_fails():
    blob = encrypt_backup(b"x", secret="a")
    try:
        decrypt_backup(blob, secret="b")
    except BackupError:
        pass
    else:
        raise AssertionError("wrong secret must fail")


def test_backup_identity_metadata_validation_accepts_uuid():
    expected_shop_id = uuid.uuid4()
    metadata = {"format": "LTPOS-BACKUP-V1", "shop_id": str(expected_shop_id)}

    assert validate_backup_envelope_metadata(metadata) == expected_shop_id


@pytest.mark.parametrize(
    "metadata",
    [
        {"format": "LTPOS-BACKUP-V1"},
        {"format": "LTPOS-BACKUP-V1", "shop_id": "not-a-uuid"},
    ],
)
def test_backup_identity_metadata_validation_fails_closed(metadata):
    with pytest.raises(BackupError):
        validate_backup_envelope_metadata(metadata)


def test_tampered_backup_metadata_fails_authentication():
    blob = bytearray(
        encrypt_backup(
            b"postgres-dump",
            secret="secret",
            metadata={"shop_id": str(uuid.uuid4())},
        )
    )
    blob[-1] ^= 1

    with pytest.raises(BackupError, match="authentication failed"):
        decrypt_backup(bytes(blob), secret="secret")


def test_backup_envelope_includes_authenticated_shop_identity(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'backup-identity.sqlite3'}")
    ShopIdentity.__table__.create(engine)
    expected_shop_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(ShopIdentity(shop_id=expected_shop_id))
        db.commit()
        metadata = _backup_envelope_metadata(db, uuid.uuid4())

    blob = encrypt_backup(b"postgres-dump", secret="secret", metadata=metadata)
    authenticated_metadata, raw = decrypt_backup(blob, secret="secret")

    assert engine.url.get_backend_name() == "sqlite"
    assert authenticated_metadata["shop_id"] == str(expected_shop_id)
    assert authenticated_metadata["backup_point_id"] == metadata["backup_point_id"]
    assert raw == b"postgres-dump"
    engine.dispose()


def test_backup_status_route_exists():
    from app.api.routes.backup import backup_status
    assert callable(backup_status)
