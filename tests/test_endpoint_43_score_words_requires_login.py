def test_endpoint_score_words_requires_login(flask_app_client):
    response = flask_app_client.get("/score-words", follow_redirects=True)

    assert response.status_code == 200
    assert b"You must be logged in" in response.data
