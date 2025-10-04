from datetime import UTC, datetime


def test_database_returns_geo_tags_for_article(db_manager):
    article_id = db_manager.save_article(
        title="Geo Fetch",
        content="",
        summary="",
        url="https://example.com/geo-fetch",
        source="GeoSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    db_manager.save_geo_tags(article_id, [
        {"tag": "Aarhus", "confidence": 0.88, "label": "model", "lat": 56.1629, "lon": 10.2039}
    ])

    tags = db_manager.get_geo_tags_for_article(article_id)

    assert len(tags) == 1
    assert tags[0]["tag"] == "Aarhus"
