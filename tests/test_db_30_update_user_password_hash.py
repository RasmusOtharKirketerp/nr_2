def test_database_updates_user_password_hash(db_manager, auth_manager):
    original_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("passwordhash", original_hash, "hash@example.com")

    new_password = "NewPass456"
    new_hash = auth_manager.hash_password(new_password)
    db_manager.update_user_password_hash(user_id, new_hash)

    user = db_manager.get_user_by_username("passwordhash")
    assert auth_manager.verify_password(new_password, user["password_hash"])
