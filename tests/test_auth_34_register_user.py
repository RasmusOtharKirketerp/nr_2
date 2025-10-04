def test_auth_registers_new_user(auth_manager, db_manager):
    success, message = auth_manager.register_user("authuser", "ValidPass123")

    assert success
    assert "registered" in message.lower()
    assert db_manager.get_user_by_username("authuser") is not None
