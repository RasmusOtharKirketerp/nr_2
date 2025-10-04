from datetime import UTC, datetime


def test_database_updates_global_article_score(db_manager):
    article_id = db_manager.save_article(
        title="Global Score",
        content="",
        summary="",
        url="https://example.com/global-score",
        source="ScoreSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    db_manager.update_article_score(article_id, 4.2)

    article = db_manager.get_articles(limit=1)[0]
    assert article["score"] == 4.2
