def test_auth_logs_in_registered_user(auth_manager):
    auth_manager.register_user("loginuser", "ValidPass123")

    success, message, token = auth_manager.login_user("loginuser", "ValidPass123")

    assert success
    assert "login" in message.lower()
    assert token is not None
    assert len(token) == 64
