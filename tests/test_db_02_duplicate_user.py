import sqlite3

import pytest


def test_database_rejects_duplicate_usernames(db_manager, auth_manager):
    password_hash = auth_manager.hash_password("ValidPass123")
    db_manager.create_user("duplicate", password_hash, "dup@example.com")

    with pytest.raises(sqlite3.IntegrityError):
        db_manager.create_user("duplicate", password_hash, "dup2@example.com")
