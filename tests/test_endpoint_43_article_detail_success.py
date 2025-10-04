def test_endpoint_article_detail_renders_article(flask_app_client, article_factory):
    article_id = article_factory(title="Visible Article", summary="Summary", content="Full content")

    response = flask_app_client.get(f"/article/{article_id}")

    assert response.status_code == 200
    assert b"Visible Article" in response.data
    assert b"Full content" in response.data
