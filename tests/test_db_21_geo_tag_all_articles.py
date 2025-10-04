from datetime import UTC, datetime


class StubNLP:
    def __init__(self):
        self.calls = 0

    def extract_geo_tags(self, content, title=None, summary=None, db_manager=None, not_found_callback=None):
        self.calls += 1
        if not_found_callback:
            not_found_callback("Unknownville")
        return [
            {
                "tag": "Odense",
                "confidence": 0.77,
                "label": "stub",
                "lat": 55.4038,
                "lon": 10.4024,
            }
        ]


def test_database_geo_tag_all_articles_inserts_tags(db_manager):
    article_id = db_manager.save_article(
        title="Geo Pipeline",
        content="This mentions Odense.",
        summary="",
        url="https://example.com/geo-pipeline",
        source="GeoSource",
    published_date=datetime.now(UTC),
        thumbnail_url=None,
    )

    processor = StubNLP()
    db_manager.geo_tag_all_articles(processor)

    tags = db_manager.get_geo_tags_for_article(article_id)

    assert processor.calls >= 1
    assert any(tag["tag"] == "Odense" for tag in tags)
