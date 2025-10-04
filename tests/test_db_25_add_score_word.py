def test_database_adds_score_word_for_user(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("scoreword", password_hash, "scoreword@example.com")

    db_manager.add_score_word(user_id, "climate", 4)
    words = db_manager.get_score_words(user_id)

    assert any(word["word"] == "climate" and word["weight"] == 4 for word in words)
