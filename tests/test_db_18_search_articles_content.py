from datetime import datetime


def test_database_searches_articles_by_content(db_manager):
    db_manager.save_article(
        title="Generic",
        content="This article mentions renewable energy policies extensively.",
        summary="",
        url="https://example.com/energy",
        source="SearchSource",
        published_date=datetime.utcnow(),
        thumbnail_url=None,
    )

    results = db_manager.search_articles("renewable", limit=5)

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/energy"
