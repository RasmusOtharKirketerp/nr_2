def test_database_updates_user_preference(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("prefupdate", password_hash, "prefupdate@example.com")

    db_manager.update_user_preference(user_id, "recency", 0.9)
    preferences = {pref["criteria"]: pref["weight"] for pref in db_manager.get_user_preferences(user_id)}

    assert preferences["recency"] == 0.9
