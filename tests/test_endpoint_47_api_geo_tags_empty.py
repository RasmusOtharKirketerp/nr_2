def test_endpoint_api_geo_tags_empty(flask_app_client):
    response = flask_app_client.get("/api/geo_tags")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {"geo_tags": []}
