def test_database_deletes_score_word_for_user(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("deleteword", password_hash, "deleteword@example.com")

    db_manager.add_score_word(user_id, "remove", 5)
    db_manager.delete_score_word(user_id, "remove")

    words = db_manager.get_score_words(user_id)
    assert all(word["word"] != "remove" for word in words)
