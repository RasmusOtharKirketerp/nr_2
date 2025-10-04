from datetime import UTC, datetime


def test_database_persists_thumbnail_url(db_manager):
    db_manager.save_article(
        title="Thumb News",
        content="",
        summary="",
        url="https://example.com/thumb",
        source="ThumbSource",
    published_date=datetime.now(UTC),
        thumbnail_url="https://example.com/thumb.png",
    )

    article = db_manager.get_articles(limit=1)[0]

    assert article.get("thumbnail_url") == "https://example.com/thumb.png"
