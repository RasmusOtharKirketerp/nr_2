from datetime import UTC, datetime


def test_database_updates_user_specific_article_score(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("userarticle", password_hash, "userarticle@example.com")
    article_id = db_manager.save_article(
        title="User Update",
        content="",
        summary="",
        url="https://example.com/user-update",
        source="ScoreSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    db_manager.update_article_score(article_id, 8.3, user_id=user_id)

    article = db_manager.get_articles(limit=1, user_id=user_id)[0]
    assert article["score"] == 8.3
