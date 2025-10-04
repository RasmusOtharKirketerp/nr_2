import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Dict, Optional

import pytest  # type: ignore[import]

from newsreader.auth import AuthManager
from newsreader.database import DatabaseManager
from newsreader.scorer import ArticleScorer
from newsreader.settings import get_settings


DEFAULT_PASSWORD = "ValidPass123"


@pytest.fixture(autouse=True)
def _reset_settings(tmp_path, monkeypatch):
    """Isolate filesystem-dependent settings for each test."""
    monkeypatch.setenv("NEWSREADER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NEWSREADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NEWSREADER_VAR_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("NEWSREADER_TEMPLATE_DIR", str(tmp_path / "templates"))
    monkeypatch.setenv("NEWSREADER_DB_PATH", str(tmp_path / "var" / "newsreader.db"))
    monkeypatch.setenv("NEWSREADER_LOG_DIR", str(tmp_path / "var" / "logs"))
    monkeypatch.setenv("NEWSREADER_DAEMON_LOG", str(tmp_path / "var" / "logs" / "news_daemon.log"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def temp_db_path(tmp_path) -> str:
    path = tmp_path / "test_db.sqlite"
    return str(path)


@pytest.fixture
def db_manager(temp_db_path):
    manager = DatabaseManager(temp_db_path)
    yield manager
    manager.close()
    try:
        Path(temp_db_path).unlink()
    except OSError:
        pass


@pytest.fixture
def auth_manager(db_manager) -> AuthManager:
    return AuthManager(db_manager)


@pytest.fixture
def scorer(db_manager) -> ArticleScorer:
    return ArticleScorer(db_manager)


@pytest.fixture
def user_factory(auth_manager, db_manager) -> Callable[..., Dict]:
    counter = {"value": 0}

    def _create_user(
        username: Optional[str] = None,
        password: str = DEFAULT_PASSWORD,
        email: Optional[str] = None,
    ) -> Dict:
        counter["value"] += 1
        unique_suffix = counter["value"]
        username = username or f"user_{unique_suffix}"
        email = email or f"user_{unique_suffix}@example.com"
        password_hash = auth_manager.hash_password(password)
        user_id = db_manager.create_user(username, password_hash, email)
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "password": password,
        }

    return _create_user


@pytest.fixture
def article_factory(db_manager) -> Callable[..., int]:
    counter = {"value": 0}

    def _create_article(
        title: Optional[str] = None,
        summary: str = "Sample summary",
        content: str = "Sample content body",
        url: Optional[str] = None,
        source: str = "TestSource",
        published_date: Optional[datetime] = None,
        thumbnail_url: Optional[str] = "https://example.com/thumb.jpg",
    ) -> int:
        counter["value"] += 1
        idx = counter["value"]
        article_title = title or f"Article Title {idx}"
        article_url = url or f"https://example.com/article-{idx}"
        pub_date = published_date or datetime.now(UTC)
        return db_manager.save_article(
            article_title,
            content,
            summary,
            article_url,
            source,
            pub_date,
            thumbnail_url,
        )

    return _create_article


@pytest.fixture
def score_word_factory(db_manager) -> Callable[[int, str, int], None]:
    def _add_score_word(user_id: int, word: str = "economy", weight: int = 3) -> None:
        db_manager.add_score_word(user_id, word, weight)

    return _add_score_word


@pytest.fixture
def flask_app_client(db_manager, auth_manager, scorer):
    from newsreader import flask_app as flask_module

    original_db = flask_module.db
    original_auth = flask_module.auth
    original_scorer = flask_module.scorer

    flask_module.db = db_manager
    flask_module.auth = auth_manager
    flask_module.scorer = scorer

    app = flask_module.app
    app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
    })

    with app.test_client() as client:
        with app.app_context():
            yield client

    flask_module.db = original_db
    flask_module.auth = original_auth
    flask_module.scorer = original_scorer


@pytest.fixture
def login_user(flask_app_client, user_factory):
    def _login(username: Optional[str] = None, password: Optional[str] = None):
        user = user_factory(username=username, password=password or DEFAULT_PASSWORD)
        response = flask_app_client.post(
            "/login",
            data={"username": user["username"], "password": password or DEFAULT_PASSWORD},
            follow_redirects=True,
        )
        assert response.status_code == 200
        return user

    return _login
