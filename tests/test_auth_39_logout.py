def test_auth_logs_out_user(auth_manager, db_manager):
    auth_manager.register_user("logoutuser", "ValidPass123")
    success, _, token = auth_manager.login_user("logoutuser", "ValidPass123")
    assert success

    assert auth_manager.logout_user(token)
    assert db_manager.validate_session(token) is None
