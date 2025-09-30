# moved from project root
default_encoding = 'utf-8'

import unittest
from newsreader.fetcher import NewsFetcher
from newsreader.database import DatabaseManager

class TestFetcherThumbnail(unittest.TestCase):
    """Unit tests for NewsFetcher thumbnail extraction."""

    def setUp(self):
        """Set up file-based temp database and NewsFetcher instance, with all required tables."""
        import sqlite3, tempfile, os
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        conn = sqlite3.connect(self.temp_db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY, title TEXT, content TEXT, summary TEXT, url TEXT, source TEXT, published_date TEXT, fetched_at TEXT, score REAL, thumbnail_url TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS geo_tags (id INTEGER PRIMARY KEY, article_id INTEGER, tag TEXT, confidence REAL, source TEXT, lat REAL, lon REAL)''')
        conn.commit()
        conn.close()
        self.db = DatabaseManager(self.temp_db_path)
        self.fetcher = NewsFetcher(self.db)

    def tearDown(self):
        import os
        if hasattr(self, 'temp_db_path') and os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_fetch_thumbnail_url(self):
        """Test that fetch_article_content returns a dict with a valid thumbnail_url field."""
        url = "https://nyheder.tv2.dk/business/2025-09-28-priserne-rasler-ned-paa-elbiler"
        article = self.fetcher.fetch_article_content(url)
        self.assertIsNotNone(article, msg="fetch_article_content() should not return None for a valid URL")
        self.assertIn('thumbnail_url', article, msg="Returned article dict should contain 'thumbnail_url' key")
        # The thumbnail_url should be a string (possibly empty) or None if not found
        self.assertTrue(
            article['thumbnail_url'] is None or isinstance(article['thumbnail_url'], str),
            msg="'thumbnail_url' should be a string or None"
        )

if __name__ == "__main__":
    unittest.main()
