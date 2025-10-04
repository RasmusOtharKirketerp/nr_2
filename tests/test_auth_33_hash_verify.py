def test_auth_hash_and_verify_password(auth_manager):
    hashed = auth_manager.hash_password("ValidPass123")

    assert auth_manager.verify_password("ValidPass123", hashed)
    assert not auth_manager.verify_password("WrongPass123", hashed)
