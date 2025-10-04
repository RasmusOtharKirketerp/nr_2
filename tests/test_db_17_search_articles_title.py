from datetime import datetime


def test_database_searches_articles_by_title(db_manager):
    db_manager.save_article(
        title="Economy Headline",
        content="",
        summary="",
        url="https://example.com/economy",
        source="SearchSource",
        published_date=datetime.utcnow(),
        thumbnail_url=None,
    )
    db_manager.save_article(
        title="Sports Update",
        content="",
        summary="",
        url="https://example.com/sports",
        source="SearchSource",
        published_date=datetime.utcnow(),
        thumbnail_url=None,
    )

    results = db_manager.search_articles("Economy", limit=5)

    assert any(article["title"] == "Economy Headline" for article in results)
