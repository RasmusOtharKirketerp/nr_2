def test_auth_rejects_invalid_login(auth_manager):
    auth_manager.register_user("wrongpass", "ValidPass123")

    success, message, token = auth_manager.login_user("wrongpass", "WrongPass123")

    assert not success
    assert token is None
    assert "invalid" in message.lower()
