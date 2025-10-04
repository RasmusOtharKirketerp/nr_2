def test_database_creates_default_preferences(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("prefuser", password_hash, "pref@example.com")

    preferences = db_manager.get_user_preferences(user_id)
    criteria = {pref["criteria"] for pref in preferences}

    assert len(preferences) == 3
    assert {"recency", "length", "source_reliability"} == criteria
