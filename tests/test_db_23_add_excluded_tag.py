def test_database_allows_adding_excluded_tags(db_manager):
    db_manager.add_excluded_tag("NewCity")

    assert "NewCity" in db_manager.get_excluded_tags()
