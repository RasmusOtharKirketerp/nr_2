def test_database_updates_user_email(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("emailuser", password_hash, "old@example.com")

    db_manager.update_user_email(user_id, "new@example.com")
    updated = db_manager.get_user_by_username("emailuser")

    assert updated is not None
    assert updated["email"] == "new@example.com"
