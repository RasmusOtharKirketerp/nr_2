def test_endpoint_api_geo_tags_returns_data(flask_app_client, article_factory, db_manager):
    article_id = article_factory(title="Geo Tagged", url="https://example.com/geo-tagged")
    db_manager.save_geo_tags(
        article_id,
        [
            {
                "tag": "Odense",
                "confidence": 0.82,
                "label": "test",
                "lat": 55.4038,
                "lon": 10.4024,
            }
        ],
    )

    response = flask_app_client.get("/api/geo_tags")
    data = response.get_json()

    assert response.status_code == 200
    assert any(entry["tag"] == "Odense" for entry in data["geo_tags"])
