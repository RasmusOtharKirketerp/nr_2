VALID_PASSWORD = "ValidPass123"


def test_flask_login_and_logout_flow(flask_app_client, user_factory):
    user = user_factory(username="flowuser")

    login_response = flask_app_client.post(
        "/login",
        data={"username": user["username"], "password": VALID_PASSWORD},
        follow_redirects=True,
    )
    assert login_response.status_code == 200
    assert b"Login successful" in login_response.data

    logout_response = flask_app_client.get("/logout", follow_redirects=True)
    assert logout_response.status_code == 200
    assert b"Logged out successfully" in logout_response.data


def test_flask_profile_update_email(flask_app_client, login_user, db_manager):
    user = login_user()

    response = flask_app_client.post(
        "/profile",
        data={"email": "updated@example.com"},
        follow_redirects=True,
    )

    assert response.status_code == 200

    updated = db_manager.get_user_by_username(user["username"])
    assert updated["email"] == "updated@example.com"


def test_flask_excluded_tags_requires_admin(flask_app_client, login_user):
    login_user()
    response = flask_app_client.get("/excluded-tags")

    assert response.status_code == 403


def test_flask_excluded_tags_allows_admin(flask_app_client, user_factory, db_manager):
    user_factory(username="admin")

    login_response = flask_app_client.post(
        "/login",
        data={"username": "admin", "password": VALID_PASSWORD},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    post_response = flask_app_client.post(
        "/excluded-tags",
        data={"tag": "TestAdminTag"},
        follow_redirects=True,
    )
    assert post_response.status_code == 200
    assert "TestAdminTag" in db_manager.get_excluded_tags()
