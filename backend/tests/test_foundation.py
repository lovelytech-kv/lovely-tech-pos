from app.security.passwords import hash_password, verify_password

def test_password_hash_roundtrip():
    hashed = hash_password("Test-Password-123!")
    assert hashed != "Test-Password-123!"
    assert verify_password(hashed, "Test-Password-123!")
    assert not verify_password(hashed, "wrong")
