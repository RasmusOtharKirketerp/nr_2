# moved from project root
default_encoding = 'utf-8'

import unittest
from newsreader import flask_app
app = flask_app.app
db = flask_app.db
auth = flask_app.auth

class FlaskAuthTestCase(unittest.TestCase):
    """Unit tests for Flask authentication (login/logout) endpoints."""

    def setUp(self):
        """Set up Flask test client and create a test user in a fresh DB."""
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        app.config['TESTING'] = True
        app.config['DATABASE'] = self.temp_db_path
        # Patch db to use the temp database for this test
        from newsreader.database import DatabaseManager
        db = DatabaseManager(self.temp_db_path)
        from newsreader.auth import AuthManager
        from newsreader.scorer import ArticleScorer
        from newsreader import flask_app
        flask_app.db = db
        flask_app.auth = AuthManager(db)
        flask_app.scorer = ArticleScorer(db)
        self.app = flask_app.app.test_client()
        self.app.testing = True
        # Ensure the user_score_words table exists in the test DB
        db.init_word_table()
        # Create a test user
        db.create_user('testuser', flask_app.auth.hash_password('TestPass123'))

    def tearDown(self):
        """Remove the test user from the database."""
        user = db.get_user_by_username('testuser')
        if user:
            with db.get_connection() as conn:
                conn.execute('DELETE FROM users WHERE username = ?', ('testuser',))
                conn.commit()

    def test_login_logout(self):
        """Test login page, login (wrong/correct), and logout flow."""
        rv = self.app.get('/login')
        self.assertIn(b'Login', rv.data, msg="Login page should load")

        rv = self.app.post('/login', data=dict(username='testuser', password='wrong'), follow_redirects=True)
        self.assertIn(b'Invalid', rv.data, msg="Should show invalid login for wrong password")

        rv = self.app.post('/login', data=dict(username='testuser', password='TestPass123'), follow_redirects=True)
        self.assertIn(b'Login successful', rv.data, msg="Should show login successful for correct password")
        self.assertIn(b'Logged in as <strong>testuser</strong>', rv.data, msg="Should show logged in user display")

        rv = self.app.get('/logout', follow_redirects=True)
        self.assertIn(b'Logged out successfully', rv.data, msg="Should show logout success message")

if __name__ == '__main__':
    unittest.main()
