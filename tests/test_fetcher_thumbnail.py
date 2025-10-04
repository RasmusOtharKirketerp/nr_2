import pytest

from newsreader.fetcher import NewsFetcher


class _StubArticle:
    def __init__(self, url: str, *, top_image=None, meta_img_url=None, html=""):
        self.url = url
        self.top_image = top_image
        self.meta_img_url = meta_img_url
        self.html = html
        self.title = "Stub Title"
        self.text = "Stub content"
        self.summary = "Stub summary"
        self.publish_date = None
        self.authors = []

    def download(self):
        return None

    def parse(self):
        return None

    def nlp(self):
        return None


@pytest.fixture
def stub_fetcher(monkeypatch, db_manager):
    fetcher = NewsFetcher(db_manager)

    def factory(*, top_image=None, meta_img=None, html=""):
        def _article_constructor(url):
            return _StubArticle(url, top_image=top_image, meta_img_url=meta_img, html=html)

        monkeypatch.setattr("newsreader.fetcher.Article", _article_constructor)
        return fetcher

    return factory


def test_fetch_article_prefers_top_image(stub_fetcher):
    fetcher = stub_fetcher(top_image="https://example.com/top.png")
    article = fetcher.fetch_article_content("https://example.com/test")

    assert article is not None
    assert article["thumbnail_url"] == "https://example.com/top.png"


def test_fetch_article_uses_meta_image_when_no_top(monkeypatch, stub_fetcher):
    fetcher = stub_fetcher(top_image=None, meta_img="https://example.com/meta.png")
    article = fetcher.fetch_article_content("https://example.com/test-meta")

    assert article is not None
    assert article["thumbnail_url"] == "https://example.com/meta.png"


def test_fetch_article_falls_back_to_first_img(stub_fetcher):
    html = '<html><body><img src="https://example.com/fallback.jpg" /></body></html>'
    fetcher = stub_fetcher(top_image=None, meta_img=None, html=html)
    article = fetcher.fetch_article_content("https://example.com/test-fallback")

    assert article is not None
    assert article["thumbnail_url"] == "https://example.com/fallback.jpg"
