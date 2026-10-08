from app.backup.service import encrypt_backup, decrypt_backup, BackupError

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


def test_backup_status_route_exists():
    from app.api.routes.backup import backup_status
    assert callable(backup_status)
