from datetime import datetime


def test_database_respects_article_limit(db_manager):
    for idx in range(3):
        db_manager.save_article(
            title=f"Article {idx}",
            content="",
            summary="",
            url=f"https://example.com/article-{idx}",
            source="LimitSource",
            published_date=datetime.utcnow(),
            thumbnail_url=None,
        )

    articles = db_manager.get_articles(limit=2)

    assert len(articles) == 2
