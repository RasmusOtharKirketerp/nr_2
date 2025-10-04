def test_endpoint_api_articles_by_tag_returns_articles(flask_app_client, article_factory, db_manager):
    article_id = article_factory(title="Tagged Article", url="https://example.com/tagged")
    db_manager.save_geo_tags(
        article_id,
        [
            {
                "tag": "Copenhagen",
                "confidence": 0.9,
                "label": "test",
                "lat": 55.6761,
                "lon": 12.5683,
            }
        ],
    )

    response = flask_app_client.get("/api/articles_by_tag", query_string={"tag": "Copenhagen"})

    assert response.status_code == 200
    payload = response.get_json()
    assert any(article["title"] == "Tagged Article" for article in payload["articles"])
