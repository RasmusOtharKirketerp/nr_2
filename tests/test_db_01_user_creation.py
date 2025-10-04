def test_database_creates_user_record(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("alice", password_hash, "alice@example.com")

    user = db_manager.get_user_by_username("alice")
    assert user is not None
    assert user["id"] == user_id
    assert user["email"] == "alice@example.com"
