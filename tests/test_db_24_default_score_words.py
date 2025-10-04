def test_database_returns_default_score_words(db_manager):
    score_words = db_manager.get_default_score_words()

    assert len(score_words) >= 5
    assert any(word["word"] == "danmark" for word in score_words)
