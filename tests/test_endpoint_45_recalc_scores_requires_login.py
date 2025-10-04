def test_endpoint_recalc_scores_requires_login(flask_app_client):
    response = flask_app_client.post("/recalc_scores", follow_redirects=True)

    assert response.status_code == 200
    assert b"You must be logged in" in response.data
