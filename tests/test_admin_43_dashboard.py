import datetime

import pytest

from newsreader import flask_app as flask_module


def _login_as_admin(client, user_factory):
    admin_user = user_factory(username="admin")
    response = client.post(
        "/login",
        data={"username": admin_user["username"], "password": admin_user["password"]},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return admin_user


def test_admin_dashboard_requires_login(flask_app_client):
    response = flask_app_client.get("/admin")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_dashboard_lists_users(flask_app_client, user_factory, db_manager):
    _login_as_admin(flask_app_client, user_factory)
    other_user = user_factory()
    db_manager.create_session(other_user["id"])

    response = flask_app_client.get("/admin")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Admin Dashboard" in body
    assert other_user["username"] in body
    assert "Login Count" in body


def test_admin_delete_article(flask_app_client, user_factory, article_factory, db_manager):
    _login_as_admin(flask_app_client, user_factory)
    article_id = article_factory()
    assert db_manager.get_article_count() == 1

    response = flask_app_client.post(f"/admin/articles/delete/{article_id}")
    assert response.status_code == 302
    assert db_manager.get_article_count() == 0


def test_admin_purge_refresh_articles(monkeypatch, flask_app_client, user_factory, article_factory, db_manager):
    _login_as_admin(flask_app_client, user_factory)
    first_article = article_factory()
    assert db_manager.get_article_count() == 1

    created_articles = {}

    class DummyFetcher:
        def __init__(self, db_manager_instance, sources_file=None):
            self.db = db_manager_instance

        def fetch_all_sources(self):
            article_id = self.db.save_article(
                "Refetched Title",
                "Some content",
                "Some summary",
                "https://example.com/refetched",
                "ExampleSource",
                datetime.datetime.now(datetime.UTC),
                None,
            )
            created_articles["id"] = article_id

    monkeypatch.setattr(flask_module, "NewsFetcher", DummyFetcher)

    response = flask_app_client.post("/admin/articles/purge-refresh", follow_redirects=True)
    assert response.status_code == 200
    assert db_manager.get_article_count() == 1
    assert created_articles["id"] is not None


def test_admin_geo_refresh(monkeypatch, flask_app_client, user_factory, article_factory, db_manager):
    _login_as_admin(flask_app_client, user_factory)
    article_id = article_factory()
    db_manager.save_geo_tags(article_id, [{
        "tag": "InitialCity",
        "label": "CITY",
        "confidence": 0.5,
        "lat": 1.0,
        "lon": 2.0,
    }])

    class DummyNLP:
        def extract_geo_tags(self, text, title=None, summary=None, db_manager=None, not_found_callback=None):
            return [{
                "tag": "RefreshedCity",
                "label": "CITY",
                "confidence": 0.9,
                "lat": 3.0,
                "lon": 4.0,
            }]

    monkeypatch.setattr(flask_module, "NLPProcessor", lambda: DummyNLP())

    response = flask_app_client.post("/admin/articles/geo-refresh", follow_redirects=True)
    assert response.status_code == 200

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tag, lat, lon FROM geo_tags")
        rows = cursor.fetchall()

    assert rows
    assert any(row[0] == "RefreshedCity" for row in rows)
