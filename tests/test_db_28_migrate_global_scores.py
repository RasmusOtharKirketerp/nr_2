from datetime import UTC, datetime


def test_database_migrates_global_scores_to_user_scores(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    user_id = db_manager.create_user("migrate", password_hash, "migrate@example.com")
    article_id = db_manager.save_article(
        title="Migration Story",
        content="",
        summary="",
        url="https://example.com/migrate",
        source="ScoreSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    db_manager.update_article_score(article_id, 6.6)
    db_manager.migrate_global_scores_to_user_scores()

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT score FROM user_article_scores WHERE user_id = ? AND article_id = ?",
            (user_id, article_id),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 6.6
