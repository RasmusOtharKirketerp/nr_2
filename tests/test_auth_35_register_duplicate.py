def test_auth_rejects_duplicate_registration(auth_manager):
    auth_manager.register_user("dupuser", "ValidPass123")
    success, message = auth_manager.register_user("dupuser", "ValidPass123")

    assert not success
    assert "exists" in message.lower()
