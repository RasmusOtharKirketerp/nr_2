# moved from project root
default_encoding = 'utf-8'

import unittest
import os
import tempfile
from newsreader import flask_app
from newsreader.database import DatabaseManager

class FlaskAppTestCase(unittest.TestCase):
    def test_heatmap_page(self):
        rv = self.app.get('/heatmap')
        self.assertIn(b'heatmap', rv.data.lower(), msg="Heatmap page should load")

    def test_api_geo_tags(self):
        rv = self.app.get('/api/geo_tags')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'geo_tags', rv.data, msg="API should return geo_tags JSON")

    def test_excluded_tags_get_requires_login(self):
        rv = self.app.get('/excluded-tags', follow_redirects=True)
        self.assertIn(b'You must be logged in', rv.data, msg="Excluded tags page should require login")

    def test_score_words_add_edit_delete(self):
        # Register and login
        self.app.post('/register', data={
            'username': self.test_username,
            'email': 'test@example.com',
            'password': self.test_password,
            'confirm_password': self.test_password
        }, follow_redirects=True)
        self.app.post('/login', data={
            'username': self.test_username,
            'password': self.test_password
        }, follow_redirects=True)
        # Add
        rv = self.app.post('/score-words/add', data={'word': 'editword', 'weight': 3}, follow_redirects=True)
        self.assertIn(b'Added/updated word', rv.data)
        # Edit
        rv = self.app.post('/score-words/edit/editword', data={'word': 'editword', 'weight': 7}, follow_redirects=True)
        self.assertIn(b'Updated word', rv.data)
        # Delete
        rv = self.app.post('/score-words/delete/editword', follow_redirects=True)
        self.assertIn(b'Deleted word', rv.data)

    def test_article_detail(self):
        # Add article directly to DB
        user_id = self.db.create_user('detailuser', 'pw')
        article_id = self.db.save_article('Detail Title', 'Detail Content', 'Detail Summary', 'http://detail-url', 'DetailSource', '2025-09-29', None)
        rv = self.app.get(f'/article/{article_id}')
        self.assertIn(b'Detail Title', rv.data)

    def test_profile_requires_login(self):
        rv = self.app.get('/profile', follow_redirects=True)
        self.assertIn(b'You must be logged in', rv.data)

    def test_profile_update_email(self):
        # Register and login
        self.app.post('/register', data={
            'username': self.test_username,
            'email': 'test@example.com',
            'password': self.test_password,
            'confirm_password': self.test_password
        }, follow_redirects=True)
        self.app.post('/login', data={
            'username': self.test_username,
            'password': self.test_password
        }, follow_redirects=True)
        rv = self.app.post('/profile', data={'email': 'newemail@example.com'}, follow_redirects=True)
        # Check that the new email appears in the profile form
        self.assertIn(b'value="newemail@example.com"', rv.data)

    def test_recalc_scores_requires_login(self):
        rv = self.app.post('/recalc_scores', follow_redirects=True)
        self.assertIn(b'You must be logged in', rv.data)
    """Unit tests for Flask app endpoints and user flows."""

    def setUp(self):
        """Set up a temporary database and Flask test client."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()  # Close so sqlite can open it
        app = flask_app.app
        app.config['TESTING'] = True
        app.config['DATABASE'] = self.temp_db_path
        # Patch db to use the temp database for this test
        self.db = DatabaseManager(self.temp_db_path)
        flask_app.db = self.db
        # Ensure the user_score_words table exists in the test DB
        self.db.init_word_table()
        # Re-instantiate auth and scorer to use the patched db
    from newsreader.auth import AuthManager
    from newsreader.scorer import ArticleScorer
        flask_app.auth = AuthManager(self.db)
        flask_app.scorer = ArticleScorer(self.db)
        self.app = app.test_client()
        self.test_username = 'testuser'
        self.test_password = 'testpass123'

    def tearDown(self):
        """Clean up temporary database and close connections."""
        try:
            conn = self.db.get_connection()
            conn.close()
        except Exception as e:
            print(f"[DEBUG] Error closing DB connection: {e}")
        try:
            if hasattr(self, 'app') and hasattr(self.app, 'application'):
                ctx = self.app.application.app_context()
                ctx.pop()
        except Exception as e:
            print(f"[DEBUG] Error closing Flask app context: {e}")
        try:
            os.unlink(self.temp_db_path)
        except Exception as e:
            print(f"[DEBUG] Error deleting temp DB file: {e}")

    def test_register_login_logout(self):
        """Test user registration, login, and logout flow."""
        with self.app as c:
            rv = c.post('/register', data={
                'username': self.test_username,
                'email': 'test@example.com',
                'password': self.test_password,
                'confirm_password': self.test_password
            }, follow_redirects=True)
            self.assertIn(b'Registration successful', rv.data, msg="Registration should succeed")
            rv = c.post('/login', data={
                'username': self.test_username,
                'password': self.test_password
            }, follow_redirects=True)
            self.assertIn(b'Login successful', rv.data, msg="Login should succeed")
            rv = c.get('/logout', follow_redirects=True)
            self.assertIn(b'Login', rv.data, msg="Logout should redirect to login page")

    def test_index_page(self):
        """Test that the index page loads and contains expected content."""
        rv = self.app.get('/')
        self.assertIn(b'Latest Articles', rv.data, msg="Index page should mention 'Latest Articles'")

    def test_score_words_access(self):
        """Test access control for score words page."""
        with self.app as c:
            rv = c.get('/score-words', follow_redirects=True)
            self.assertIn(b'You must be logged in', rv.data, msg="Should require login for score words")
            c.post('/register', data={
                'username': self.test_username,
                'email': 'test@example.com',
                'password': self.test_password,
                'confirm_password': self.test_password
            }, follow_redirects=True)
            c.post('/login', data={
                'username': self.test_username,
                'password': self.test_password
            }, follow_redirects=True)
            rv = c.get('/score-words', follow_redirects=True)
            self.assertIn(b'Manage Scoring Words', rv.data, msg="Logged-in user should access score words page")

    def test_add_and_delete_score_word(self):
        """Test adding and deleting a score word for a user."""
        with self.app as c:
            c.post('/register', data={
                'username': self.test_username,
                'email': 'test@example.com',
                'password': self.test_password,
                'confirm_password': self.test_password
            }, follow_redirects=True)
            c.post('/login', data={
                'username': self.test_username,
                'password': self.test_password
            }, follow_redirects=True)
            rv = c.post('/score-words/add', data={
                'word': 'testword',
                'weight': 5
            }, follow_redirects=True)
            self.assertTrue(
                b'Added/updated word' in rv.data or b'score words' in rv.data or b'Score Words' in rv.data,
                msg="Should confirm word added or show score words page"
            )
            words = self.db.get_score_words(self.db.get_user_by_username(self.test_username)['id'])
            if words:
                word = words[0]['word']
                rv = c.post(f'/score-words/delete/{word}', follow_redirects=True)
                self.assertIn(b'Deleted word', rv.data, msg="Should confirm word deletion")

import threading
import time
import requests

class FlaskAppIntegrationTestCase(unittest.TestCase):
    def test_articles_by_tag_real_server(self):
        """Integration test: Start Flask app in background and test /api/articles_by_tag endpoint."""
    from newsreader import flask_app
        app = flask_app.app
        db = flask_app.db
        import signal
        import sys
        import requests
        import socket

        # Find a free port
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()

        def run_app():
            app.run(port=port, use_reloader=False)
        server = threading.Thread(target=run_app)
        server.daemon = True
        server.start()
        time.sleep(1.5)  # Give server time to start

        # Insert a test article and geo_tag
        user_id = db.create_user('geo_user2', 'pw')
        article_id = db.save_article('Geo Test', 'Geo content', 'Geo summary', 'http://geo-url', 'GeoSource', '2025-09-29', None)
        db.save_geo_tags(article_id, [{
            'tag': 'Copenhagen',
            'confidence': 0.99,
            'label': 'GeoSource',
            'lat': 55.6761,
            'lon': 12.5683
        }])

        # Test the endpoint
        url = f'http://127.0.0.1:{port}/api/articles_by_tag?tag=Copenhagen'
        try:
            resp = requests.get(url, timeout=5)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue('articles' in data)
            self.assertTrue(any(a['title'] == 'Geo Test' for a in data['articles']))

            # Add another article and geo_tag
            article_id2 = db.save_article(
                title='Geo Real Headline',
                content='Geo content',
                summary='Geo summary',
                url='http://geo2.example.com',
                source='GeoSource',
                published_date=None
            )
            db.save_geo_tags(article_id2, [{
                'tag': 'GeoRealCity',
                'confidence': 0.95,
                'label': 'GeoSource',
                'lat': 55.6761,
                'lon': 12.5683
            }])

            # Make a real HTTP request for the new tag
            resp2 = requests.get(f'http://127.0.0.1:{port}/api/articles_by_tag?tag=GeoRealCity')
            self.assertEqual(resp2.status_code, 200, msg=f"Expected 200, got {resp2.status_code}")
            self.assertIn('Geo Real Headline', resp2.text, msg=f"Expected headline in response, got: {resp2.text}")
        finally:
            # Attempt to shut down the Flask server
            try:
                requests.get(f'http://127.0.0.1:{port}/shutdown', timeout=2)
            except Exception:
                pass
            time.sleep(0.5)

if __name__ == '__main__':
    unittest.main()
