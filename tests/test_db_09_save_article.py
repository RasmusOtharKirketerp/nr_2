from datetime import UTC, datetime


def test_database_saves_article(db_manager):
    article_id = db_manager.save_article(
        title="Breaking News",
        content="Full content",
        summary="Short summary",
        url="https://example.com/breaking",
        source="UnitTest",
    published_date=datetime.now(UTC),
        thumbnail_url="https://example.com/thumb.jpg",
    )

    articles = db_manager.get_articles(limit=10)
    saved = next((a for a in articles if a["id"] == article_id), None)

    assert saved is not None
    assert saved["title"] == "Breaking News"
    assert saved["url"] == "https://example.com/breaking"
