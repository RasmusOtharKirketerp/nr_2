def test_auth_changes_password(auth_manager):
    auth_manager.register_user("changepass", "ValidPass123")
    success, _, token = auth_manager.login_user("changepass", "ValidPass123")
    assert success

    result, message = auth_manager.change_password(token, "ValidPass123", "NewPass123")

    assert result
    assert "success" in message.lower()

    login_success, _, new_token = auth_manager.login_user("changepass", "NewPass123")
    assert login_success
    assert new_token is not None
