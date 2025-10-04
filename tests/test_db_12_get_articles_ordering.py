from datetime import datetime


def test_database_orders_articles_by_score(db_manager):
    first_id = db_manager.save_article(
        title="Low Score",
        content="",
        summary="",
        url="https://example.com/low",
        source="OrderSource",
        published_date=datetime.utcnow(),
        thumbnail_url=None,
    )
    second_id = db_manager.save_article(
        title="High Score",
        content="",
        summary="",
        url="https://example.com/high",
        source="OrderSource",
        published_date=datetime.utcnow(),
        thumbnail_url=None,
    )

    db_manager.update_article_score(first_id, 1.0)
    db_manager.update_article_score(second_id, 9.0)

    articles = db_manager.get_articles(limit=2)
    ids = [article["id"] for article in articles]

    assert ids == [second_id, first_id]
