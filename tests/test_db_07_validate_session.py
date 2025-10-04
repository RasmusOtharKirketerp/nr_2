def test_database_validates_session_token(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("sessionvalidate", password_hash, "validate@example.com")

    token = db_manager.create_session(user_id)
    validated = db_manager.validate_session(token)

    assert validated == user_id
