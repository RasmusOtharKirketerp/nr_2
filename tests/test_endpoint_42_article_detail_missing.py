def test_endpoint_article_detail_redirects_when_missing(flask_app_client):
    response = flask_app_client.get("/article/999", follow_redirects=True)

    assert response.status_code == 200
    assert b"Article not found" in response.data
