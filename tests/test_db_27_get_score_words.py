def test_database_returns_score_words_for_user(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("listscore", password_hash, "listscore@example.com")

    db_manager.add_score_word(user_id, "economy", 5)
    db_manager.add_score_word(user_id, "technology", 2)

    words = db_manager.get_score_words(user_id)
    collected = {word["word"] for word in words}

    assert {"economy", "technology"}.issubset(collected)
