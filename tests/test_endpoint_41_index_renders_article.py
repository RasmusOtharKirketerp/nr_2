def test_endpoint_index_lists_articles(flask_app_client, article_factory):
    article_factory(title="Index News", url="https://example.com/index-news")

    response = flask_app_client.get("/")

    assert response.status_code == 200
    assert b"Index News" in response.data
