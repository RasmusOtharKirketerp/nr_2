def test_endpoint_score_words_crud_flow(flask_app_client, login_user, db_manager):
    user = login_user()

    add_response = flask_app_client.post(
        "/score-words/add",
        data={"word": "pytest", "weight": "4"},
        follow_redirects=True,
    )
    assert add_response.status_code == 200
    assert b"Added/updated word" in add_response.data

    edit_response = flask_app_client.post(
        "/score-words/edit/pytest",
        data={"word": "pytest", "weight": "6"},
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert b"Updated word" in edit_response.data

    delete_response = flask_app_client.post(
        "/score-words/delete/pytest",
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    assert b"Deleted word" in delete_response.data

    words = db_manager.get_score_words(user["id"])
    assert all(word["word"] != "pytest" for word in words)
