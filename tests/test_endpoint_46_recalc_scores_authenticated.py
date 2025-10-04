def test_endpoint_recalc_scores_authenticated(flask_app_client, login_user):
    login_user()

    response = flask_app_client.post("/recalc_scores", follow_redirects=True)

    assert response.status_code == 200
    assert b"Scores recalculated" in response.data
