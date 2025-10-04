def test_endpoint_index_includes_original_article_link(flask_app_client, article_factory):
    target_url = "https://example.com/original-resource"
    article_factory(title="Link Article", url=target_url)

    response = flask_app_client.get("/")
    html = response.data.decode()

    assert response.status_code == 200
    assert f'href="{target_url}"' in html
