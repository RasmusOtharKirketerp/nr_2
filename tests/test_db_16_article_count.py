from datetime import UTC, datetime


def test_database_reports_article_count(db_manager):
    for idx in range(2):
        db_manager.save_article(
            title=f"Count {idx}",
            content="",
            summary="",
            url=f"https://example.com/count-{idx}",
            source="CountSource",
            published_date=datetime.now(UTC),
            thumbnail_url=None,
        )

    assert db_manager.get_article_count() == 2
