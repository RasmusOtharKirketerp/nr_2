def test_database_invalidates_session_token(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("sessioninvalidate", password_hash, "invalidate@example.com")

    token = db_manager.create_session(user_id)
    db_manager.invalidate_session(token)

    assert db_manager.validate_session(token) is None
