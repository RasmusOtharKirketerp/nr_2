def test_database_creates_session_token(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("sessionuser", password_hash, "session@example.com")

    token = db_manager.create_session(user_id)

    assert isinstance(token, str)
    assert len(token) == 64
