def test_auth_returns_current_user_from_session(auth_manager):
    auth_manager.register_user("sessioncurrent", "ValidPass123")
    success, _, token = auth_manager.login_user("sessioncurrent", "ValidPass123")
    assert success

    current = auth_manager.get_current_user(token)

    assert current is not None
    assert current["username"] == "sessioncurrent"
