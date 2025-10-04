from datetime import UTC, datetime


def test_database_sets_user_article_score(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("setscore", password_hash, "setscore@example.com")
    article_id = db_manager.save_article(
        title="User Score Set",
        content="",
        summary="",
        url="https://example.com/set-score",
        source="ScoreSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    db_manager.set_user_article_score(user_id, article_id, 2.5)

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT score FROM user_article_scores WHERE user_id = ? AND article_id = ?",
            (user_id, article_id),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 2.5
