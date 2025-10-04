def test_database_initializes_default_excluded_tags(db_manager):
    tags = db_manager.get_excluded_tags()

    assert "Man" in tags
    assert len(tags) > 0
