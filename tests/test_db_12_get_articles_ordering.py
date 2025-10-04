from datetime import UTC, datetime


def test_database_orders_articles_by_date_then_score(db_manager):
    older_id = db_manager.save_article(
        title="Older Newer Mix",
        content="",
        summary="",
        url="https://example.com/older",
        source="OrderSource",
        published_date=datetime(2023, 1, 1, tzinfo=UTC),
        thumbnail_url=None,
    )
    newer_low_score_id = db_manager.save_article(
        title="Newer Low Score",
        content="",
        summary="",
        url="https://example.com/newer-low",
        source="OrderSource",
        published_date=datetime(2024, 1, 2, tzinfo=UTC),
        thumbnail_url=None,
    )
    newer_high_score_id = db_manager.save_article(
        title="Newer High Score",
        content="",
        summary="",
        url="https://example.com/newer-high",
        source="OrderSource",
        published_date=datetime(2024, 1, 2, tzinfo=UTC),
        thumbnail_url=None,
    )

    db_manager.update_article_score(older_id, 9.0)
    db_manager.update_article_score(newer_low_score_id, 1.0)
    db_manager.update_article_score(newer_high_score_id, 5.0)

    articles = db_manager.get_articles(limit=3)
    ids = [article["id"] for article in articles]

    assert ids == [newer_high_score_id, newer_low_score_id, older_id]
