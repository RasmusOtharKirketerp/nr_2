from datetime import UTC, datetime


def test_database_returns_user_specific_scores(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("scoreuser", password_hash, "score@example.com")
    article_id = db_manager.save_article(
        title="User Score",
        content="",
        summary="",
        url="https://example.com/score",
        source="ScoreSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    db_manager.set_user_article_score(user_id, article_id, 7.5)

    article = db_manager.get_articles(limit=1, user_id=user_id)[0]

    assert article["score"] == 7.5
