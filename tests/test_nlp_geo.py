# moved from project root
default_encoding = 'utf-8'

import unittest
from newsreader.nlp_processor import NLPProcessor

class DummyDB:
    def is_geo_tag_not_found(self, name):
        return False
    def add_geo_tag_not_found(self, name):
        pass

class TestGeoTagging(unittest.TestCase):
    """Unit tests for geo-tag extraction in NLPProcessor."""

    def setUp(self):
        """Set up NLPProcessor and dummy DB for geo-tagging tests."""
        self.nlp = NLPProcessor()
        self.db = DummyDB()

    def test_extract_geo_tags(self):
        """Test that extract_geo_tags finds expected locations in text."""
        text = "Copenhagen is the capital of Denmark. Paris is in France."
        tags = self.nlp.extract_geo_tags(text, db_manager=self.db)
        tag_names = {tag['tag'] for tag in tags}
        expected = {'Copenhagen', 'Denmark', 'Paris', 'France'}
        found = tag_names & expected
        # Pass if at least 2 expected locations are found
        self.assertGreaterEqual(
            len(found), 2,
            msg=f"Expected at least 2 of {expected}, got {tag_names}"
        )

if __name__ == "__main__":
    unittest.main()
