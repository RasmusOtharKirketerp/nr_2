def test_get_article_by_id_returns_saved_article(db_manager, article_factory):
    article_id = article_factory(title="Detailed Article")

    article = db_manager.get_article_by_id(article_id)

    assert article is not None
    assert article["id"] == article_id
    assert article["title"] == "Detailed Article"


def test_get_article_by_id_uses_user_score(db_manager, article_factory, user_factory):
    article_id = article_factory()
    user = user_factory()

    db_manager.set_user_article_score(user["id"], article_id, 7.25)

    article = db_manager.get_article_by_id(article_id, user_id=user["id"])

    assert article is not None
    assert article["score"] == 7.25
