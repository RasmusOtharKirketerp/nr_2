from datetime import datetime


def test_database_saves_geo_tags(db_manager):
    article_id = db_manager.save_article(
        title="Geo Article",
        content="",
        summary="",
        url="https://example.com/geo",
        source="GeoSource",
        published_date=datetime.utcnow(),
        thumbnail_url=None,
    )

    db_manager.save_geo_tags(article_id, [
        {"tag": "Copenhagen", "confidence": 0.95, "label": "model", "lat": 55.6761, "lon": 12.5683}
    ])

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tag, lat, lon FROM geo_tags WHERE article_id = ?", (article_id,))
        rows = cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "Copenhagen"
