import sqlite3
import json
import logging
import tempfile
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from .settings import get_settings
from pathlib import Path


def _adapt_datetime(value: datetime) -> str:
    """Convert datetimes to an ISO-8601 string in UTC for SQLite storage."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _adapt_date(value: date) -> str:
    """Convert dates to ISO-8601 strings for SQLite storage."""

    return value.isoformat()


sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_adapter(date, _adapt_date)

SETTINGS = get_settings()


class DatabaseManager:
    def init_excluded_tags_table(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS excluded_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT NOT NULL UNIQUE
                )
            ''')
            # Insert initial tags if table is empty
            cursor.execute('SELECT COUNT(*) FROM excluded_tags')
            if cursor.fetchone()[0] == 0:
                initial_tags = [
                    'Man','Uden','Inden','Os','Lille','Side','Grad','Givet','August','Maj','April','Juni','Juli','Februar','Marts','September','Oktober','November','December','Grave','Mine','Satte','Rolle','Kampen','Ende','Galt','Time','Sang','Bo','Bruges','Taber','Center'
                ]
                cursor.executemany('INSERT OR IGNORE INTO excluded_tags (tag) VALUES (?)', [(tag,) for tag in initial_tags])
            conn.commit()

    def add_excluded_tag(self, tag: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO excluded_tags (tag) VALUES (?)', (tag,))
            conn.commit()

    def get_excluded_tags(self) -> list:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT tag FROM excluded_tags')
            return [row[0] for row in cursor.fetchall()]
    def init_geo_tag_not_found_table(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS geo_tag_not_found (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT NOT NULL UNIQUE,
                    last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def is_geo_tag_not_found(self, tag: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM geo_tag_not_found WHERE tag = ?', (tag.lower(),))
            return cursor.fetchone() is not None

    def add_geo_tag_not_found(self, tag: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO geo_tag_not_found (tag) VALUES (?)', (tag.lower(),))
            conn.commit()

    # Geo-tag management methods
    def save_geo_tags(self, article_id: int, tags: list):
        """Save geo-tags for an article, skipping excluded tags."""
        import logging
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s %(name)s %(message)s',
                            handlers=[
                                logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a'),
                                logging.StreamHandler()
                            ])
        logger = logging.getLogger("geo-db-debug")
        info_logger = logging.getLogger("geo-db-info")
        info_logger.setLevel(logging.INFO)
        excluded = set(self.get_excluded_tags())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for tag in tags:
                tag_name = tag.get('tag')
                if tag_name and tag_name in excluded:
                    logger.debug(f"Skipping excluded geo-tag for article {article_id}: {tag_name}")
                    continue
                logger.debug(f"Inserting geo-tag for article {article_id}: {tag}")
                info_logger.info(f"Inserting geo-tag for article {article_id}: {tag}")
                cursor.execute(
                    "INSERT INTO geo_tags (article_id, tag, confidence, source, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
                    (article_id, tag_name, tag.get('confidence'), tag.get('label'), tag.get('lat'), tag.get('lon'))
                )
            conn.commit()
            logger.debug(f"Committed geo-tags for article {article_id}")
            info_logger.info(f"Committed geo-tags for article {article_id}")

    def get_geo_tags_for_article(self, article_id: int) -> list:
        """Get geo-tags for a given article. Includes debug logging."""
        import logging
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s %(name)s %(message)s',
                            handlers=[
                                logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a'),
                                logging.StreamHandler()
                            ])
        logger = logging.getLogger("geo-db-debug")
        info_logger = logging.getLogger("geo-db-info")
        info_logger.setLevel(logging.INFO)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag, confidence, source FROM geo_tags WHERE article_id = ?", (article_id,))
            rows = cursor.fetchall()
            logger.debug(f"Fetched geo-tags for article {article_id}: {rows}")
            info_logger.info(f"Fetched geo-tags for article {article_id}: {rows}")
            return [
                {'tag': row[0], 'confidence': row[1], 'source': row[2]}
                for row in rows
            ]

    def geo_tag_all_articles(self, nlp_processor):
        """Extract and save geo-tags for all articles that do not have geo-tags yet. Includes debug logging. Buffers geo_tag_not_found writes to avoid DB locking."""
        import logging
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s %(name)s %(message)s',
                            handlers=[
                                logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a'),
                                logging.StreamHandler()
                            ])
        logger = logging.getLogger("geo-db-debug")
        info_logger = logging.getLogger("geo-db-info")
        info_logger.setLevel(logging.INFO)
        not_found_tags = set()
        def not_found_callback(tag):
            not_found_tags.add(tag)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content FROM articles")
            articles = cursor.fetchall()
            logger.debug(f"Found {len(articles)} articles for geo-tagging.")
            info_logger.info(f"Found {len(articles)} articles for geo-tagging.")
            processed_since_commit = 0
            for idx, (article_id, content) in enumerate(articles, 1):
                cursor.execute("SELECT COUNT(*) FROM geo_tags WHERE article_id = ?", (article_id,))
                if cursor.fetchone()[0] == 0:
                    logger.debug(f"Geo-tagging article {article_id}")
                    info_logger.info(f"Geo-tagging article {article_id}")
                    # Try to get title and summary if available (for better geo coverage)
                    cursor2 = conn.cursor()
                    cursor2.execute("SELECT title, summary FROM articles WHERE id = ?", (article_id,))
                    row = cursor2.fetchone()
                    title = row[0] if row else None
                    summary = row[1] if row else None
                    tags = nlp_processor.extract_geo_tags(content or "", title=title, summary=summary, db_manager=self, not_found_callback=not_found_callback)
                    logger.debug(f"Extracted tags for article {article_id}: {tags}")
                    info_logger.info(f"Extracted tags for article {article_id}: {tags}")
                    for tag in tags:
                        logger.debug(f"Inserting geo-tag for article {article_id}: {tag}")
                        info_logger.info(f"Inserting geo-tag for article {article_id}: {tag}")
                        cursor.execute(
                            "INSERT INTO geo_tags (article_id, tag, confidence, source, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
                            (article_id, tag.get('tag'), tag.get('confidence'), tag.get('label'), tag.get('lat'), tag.get('lon'))
                        )
                    processed_since_commit += 1
                    if processed_since_commit >= 10:
                        conn.commit()
                        logger.debug(f"Committed geo-tag inserts after {processed_since_commit} articles.")
                        info_logger.info(f"Committed geo-tag inserts after {processed_since_commit} articles.")
                        processed_since_commit = 0
            # Commit any remaining uncommitted changes
            if processed_since_commit > 0:
                conn.commit()
                logger.debug(f"Committed geo-tag inserts after final batch of {processed_since_commit} articles.")
                info_logger.info(f"Committed geo-tag inserts after final batch of {processed_since_commit} articles.")

        # After main transaction, write geo_tag_not_found tags
        if not_found_tags:
            logger.info(f"Writing {len(not_found_tags)} geo_tag_not_found tags after geo-tagging batch.")
            self._bulk_add_geo_tag_not_found(not_found_tags)

    def _bulk_add_geo_tag_not_found(self, tags):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for tag in tags:
                cursor.execute('INSERT OR IGNORE INTO geo_tag_not_found (tag) VALUES (?)', (tag.lower(),))
            conn.commit()
    def update_user_email(self, user_id: int, new_email: str):
        """Update a user's email address"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (new_email, user_id)
            )
            conn.commit()
    def migrate_global_scores_to_user_scores(self):
        """Copy global article scores to all users as their initial per-user score if not already set."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get all users
            cursor.execute("SELECT id FROM users")
            users = [row[0] for row in cursor.fetchall()]
            # Get all articles and their global scores
            cursor.execute("SELECT id, score FROM articles")
            articles = cursor.fetchall()
            # For each user and article, insert if not exists
            for user_id in users:
                for article_id, score in articles:
                    cursor.execute(
                        "INSERT OR IGNORE INTO user_article_scores (user_id, article_id, score) VALUES (?, ?, ?)",
                        (user_id, article_id, score)
                    )
            conn.commit()
    def set_user_article_score(self, user_id: int, article_id: int, score: float):
        """Set or update a user's score for an article"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_article_scores (user_id, article_id, score) VALUES (?, ?, ?)",
                (user_id, article_id, score)
            )
            conn.commit()

    def get_user_article_score(self, user_id: int, article_id: int) -> Optional[float]:
        """Get a user's score for an article, or None if not set"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT score FROM user_article_scores WHERE user_id = ? AND article_id = ?",
                (user_id, article_id)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def delete_score_word(self, user_id: int, word: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM user_score_words WHERE user_id = ? AND word = ?
            ''', (user_id, word))
            conn.commit()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM user_score_words WHERE user_id = ? AND word = ?
                ''', (user_id, word))
                conn.commit()
    # --- User scoring words management ---
    def init_word_table(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_score_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    word TEXT NOT NULL,
                    weight INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(user_id, word)
                )
            ''')
            conn.commit()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_score_words (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        word TEXT NOT NULL,
                        weight INTEGER NOT NULL DEFAULT 1,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE(user_id, word)
                    )
                ''')
                conn.commit()

    def add_score_word(self, user_id: int, word: str, weight: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_score_words (user_id, word, weight) VALUES (?, ?, ?)
            ''', (user_id, word, weight))
            conn.commit()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO user_score_words (user_id, word, weight) VALUES (?, ?, ?)
                ''', (user_id, word, weight))
                conn.commit()

    def get_score_words(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT word, weight FROM user_score_words WHERE user_id = ?
            ''', (user_id,))
            return [{'word': row[0], 'weight': row[1]} for row in cursor.fetchall()]
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT word, weight FROM user_score_words WHERE user_id = ?
                ''', (user_id,))
                return [{'word': row[0], 'weight': row[1]} for row in cursor.fetchall()]

    def get_default_score_words(self) -> List[Dict]:
        # Example default words/weights
        return [
            {'word': 'danmark', 'weight': 5},
            {'word': 'politik', 'weight': 4},
            {'word': 'økonomi', 'weight': 3},
            {'word': 'sport', 'weight': 2},
            {'word': 'teknologi', 'weight': 1}
        ]

    # Call this in __init__
    def __init__(self, db_path: Optional[str] = None):
        self._temp_db_file: Optional[Path] = None

        if db_path == ':memory:':
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            temp_file.close()
            resolved_db_path = Path(temp_file.name)
            self._temp_db_file = resolved_db_path
        elif db_path:
            resolved_db_path = Path(db_path).expanduser()
        else:
            resolved_db_path = SETTINGS.default_db_path

        self.db_path = resolved_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        self.init_word_table()
        self.init_geo_tag_not_found_table()
        self.init_excluded_tags_table()
        # Migrate global scores to per-user if needed
        self.migrate_global_scores_to_user_scores()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def close(self):
        if self._temp_db_file and self._temp_db_file.exists():
            try:
                self._temp_db_file.unlink()
            except OSError as exc:
                logging.getLogger(__name__).warning('Failed to remove temporary database %s: %s', self._temp_db_file, exc)

    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # --- MIGRATION: Ensure 'email' column exists ---
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'email' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
            conn.commit()

        # Articles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                published_date TIMESTAMP,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score REAL DEFAULT 0.0
            )
        ''')

        # User-article scores table (per-user article scores)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_article_scores (
                user_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (user_id, article_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        ''')

        # User preferences for scoring criteria
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                criteria_name TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, criteria_name)
            )
        ''')

        # User sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Geo-tags table for articles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geo_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                confidence REAL,
                source TEXT,
                lat REAL,
                lon REAL,
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        ''')
        # --- MIGRATION: Ensure lat/lon columns exist ---
        cursor.execute("PRAGMA table_info(geo_tags)")
        geo_columns = [row[1] for row in cursor.fetchall()]
        if 'lat' not in geo_columns:
            cursor.execute("ALTER TABLE geo_tags ADD COLUMN lat REAL")
        if 'lon' not in geo_columns:
            cursor.execute("ALTER TABLE geo_tags ADD COLUMN lon REAL")

        # Default scoring criteria for new users (removed hardcoded user_id)
        # This will be handled in create_user method
        pass

        conn.commit()

    # User management methods
    def create_user(self, username: str, password_hash: str, email: str = None) -> int:
        """Create a new user and return user ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            user_id = cursor.lastrowid

            # Add default preferences for new user
            default_criteria = [
                ('recency', 0.3),
                ('length', 0.2),
                ('source_reliability', 0.5)
            ]
            cursor.executemany(
                "INSERT INTO user_preferences (user_id, criteria_name, weight) VALUES (?, ?, ?)",
                [(user_id, name, weight) for name, weight in default_criteria]
            )
            conn.commit()
            return user_id

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username (safe to column order)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'username': row['username'],
                    'email': row['email'],
                    'password_hash': row['password_hash'],
                    'created_at': row['created_at']
                }
            return None

    def update_user_password_hash(self, user_id: int, password_hash: str) -> None:
        """Update stored password hash for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id)
            )
            conn.commit()

    def get_user_preferences(self, user_id: int) -> List[Dict]:
        """Get scoring preferences for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT criteria_name, weight FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            return [{'criteria': row[0], 'weight': row[1]} for row in cursor.fetchall()]

    def update_user_preference(self, user_id: int, criteria_name: str, weight: float):
        """Update a user's scoring preference"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, criteria_name, weight) VALUES (?, ?, ?)",
                (user_id, criteria_name, weight)
            )
            conn.commit()

    # Session management methods
    def create_session(self, user_id: int) -> str:
        """Create a new session for user and return session token"""
        import secrets
        session_token = secrets.token_hex(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
                (user_id, session_token, expires_at)
            )
            conn.commit()
        return session_token

    def validate_session(self, session_token: str) -> Optional[int]:
        """Validate session token and return user_id if valid"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM user_sessions WHERE session_token = ? AND expires_at > ?",
                (session_token, datetime.now(timezone.utc))
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def invalidate_session(self, session_token: str):
        """Invalidate a session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
            conn.commit()

    # Article management methods
    def save_article(self, title: str, content: str, summary: str, url: str, source: str, published_date: Optional[datetime] = None, thumbnail_url: Optional[str] = None) -> int:
        """Save an article to database, including thumbnail_url"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Add thumbnail_url column if not exists
            cursor.execute("PRAGMA table_info(articles)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'thumbnail_url' not in columns:
                cursor.execute("ALTER TABLE articles ADD COLUMN thumbnail_url TEXT")
            cursor.execute(
                "INSERT OR REPLACE INTO articles (title, content, summary, url, source, published_date, thumbnail_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, content, summary, url, source, published_date, thumbnail_url)
            )
            conn.commit()
            return cursor.lastrowid

    def get_articles(self, limit: int = 50, offset: int = 0, user_id: Optional[int] = None) -> List[Dict]:
        """Get articles sorted by user score (if user_id), else global score, including thumbnail_url. Excludes articles with only excluded geo-tags."""
        excluded = set(self.get_excluded_tags())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(articles)")
            columns = [row[1] for row in cursor.fetchall()]
            has_thumbnail = 'thumbnail_url' in columns
            select_cols = "a.id, a.title, a.content, a.summary, a.url, a.source, a.published_date, a.fetched_at, "
            if user_id is not None:
                select_cols += "COALESCE(uas.score, a.score) AS score"
            else:
                select_cols += "a.score"
            if has_thumbnail:
                select_cols += ", a.thumbnail_url"
            if user_id is not None:
                query = f"""
                    SELECT {select_cols}
                    FROM articles a
                    LEFT JOIN user_article_scores uas ON a.id = uas.article_id AND uas.user_id = ?
                    ORDER BY a.published_date DESC, score DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, (user_id, limit, offset))
            else:
                query = f"""
                    SELECT {select_cols}
                    FROM articles a
                    ORDER BY a.published_date DESC, a.score DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, (limit, offset))
            articles = []
            for row in cursor.fetchall():
                published_date = row[6]
                if isinstance(published_date, bytes):
                    published_date = published_date.decode('utf-8')
                elif isinstance(published_date, datetime):
                    published_date = published_date.isoformat()
                fetched_at = row[7]
                if isinstance(fetched_at, bytes):
                    fetched_at = fetched_at.decode('utf-8')
                elif isinstance(fetched_at, datetime):
                    fetched_at = fetched_at.isoformat()
                article = {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'summary': row[3],
                    'url': row[4],
                    'source': row[5],
                    'published_date': published_date,
                    'fetched_at': fetched_at,
                    'score': row[8]
                }
                if has_thumbnail:
                    article['thumbnail_url'] = row[9]
                # Exclude articles with only excluded geo-tags (if any geo-tags)
                cursor2 = conn.cursor()
                cursor2.execute("SELECT tag FROM geo_tags WHERE article_id = ?", (article['id'],))
                tags = [r[0] for r in cursor2.fetchall()]
                if tags and all(t in excluded for t in tags):
                    continue
                articles.append(article)
            return articles

    def get_article_by_id(self, article_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """Fetch a single article by its primary key, including per-user score if provided."""
        excluded = set(self.get_excluded_tags())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(articles)")
            columns = [row[1] for row in cursor.fetchall()]
            has_thumbnail = 'thumbnail_url' in columns

            select_cols = "a.id, a.title, a.content, a.summary, a.url, a.source, a.published_date, a.fetched_at, "
            if user_id is not None:
                select_cols += "COALESCE(uas.score, a.score) AS score"
            else:
                select_cols += "a.score"
            if has_thumbnail:
                select_cols += ", a.thumbnail_url"

            if user_id is not None:
                query = f"""
                    SELECT {select_cols}
                    FROM articles a
                    LEFT JOIN user_article_scores uas ON a.id = uas.article_id AND uas.user_id = ?
                    WHERE a.id = ?
                """
                cursor.execute(query, (user_id, article_id))
            else:
                query = f"""
                    SELECT {select_cols}
                    FROM articles a
                    WHERE a.id = ?
                """
                cursor.execute(query, (article_id,))

            row = cursor.fetchone()
            if not row:
                return None

            published_date = row[6]
            if isinstance(published_date, bytes):
                published_date = published_date.decode('utf-8')
            elif isinstance(published_date, datetime):
                published_date = published_date.isoformat()
            fetched_at = row[7]
            if isinstance(fetched_at, bytes):
                fetched_at = fetched_at.decode('utf-8')
            elif isinstance(fetched_at, datetime):
                fetched_at = fetched_at.isoformat()

            article = {
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'summary': row[3],
                'url': row[4],
                'source': row[5],
                'published_date': published_date,
                'fetched_at': fetched_at,
                'score': row[8]
            }
            if has_thumbnail:
                article['thumbnail_url'] = row[9]

            cursor2 = conn.cursor()
            cursor2.execute("SELECT tag FROM geo_tags WHERE article_id = ?", (article_id,))
            tags = [r[0] for r in cursor2.fetchall()]
            if tags and all(t in excluded for t in tags):
                return None

            return article

    def delete_article(self, article_id: int) -> bool:
        """Delete an article and all related records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM geo_tags WHERE article_id = ?", (article_id,))
            cursor.execute("DELETE FROM user_article_scores WHERE article_id = ?", (article_id,))
            cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted > 0

    def delete_all_articles(self) -> int:
        """Delete all articles and associated records from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM geo_tags")
            cursor.execute("DELETE FROM user_article_scores")
            cursor.execute("DELETE FROM geo_tag_not_found")
            cursor.execute("DELETE FROM articles")
            deleted_articles = cursor.rowcount
            conn.commit()
            return deleted_articles

    def clear_geo_tags(self, reset_not_found: bool = False) -> int:
        """Remove all stored geo-tags. Optionally reset the not-found cache."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM geo_tags")
            cleared = cursor.rowcount
            if reset_not_found:
                cursor.execute("DELETE FROM geo_tag_not_found")
            conn.commit()
            return cleared

    def get_user_usage_stats(self) -> List[Dict[str, Optional[str]]]:
        """Return usage statistics for all users including last login and login counts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    u.id AS user_id,
                    u.username,
                    u.email,
                    u.created_at,
                    MAX(s.created_at) AS last_login_at,
                    COUNT(s.id) AS login_count
                FROM users u
                LEFT JOIN user_sessions s ON u.id = s.user_id
                GROUP BY u.id, u.username, u.email, u.created_at
                ORDER BY u.username
                """
            )
            stats = []
            for row in cursor.fetchall():
                created_at = row[3]
                last_login = row[4]
                if isinstance(created_at, datetime):
                    created_at = created_at.isoformat()
                elif isinstance(created_at, bytes):
                    created_at = created_at.decode('utf-8')
                if isinstance(last_login, datetime):
                    last_login = last_login.isoformat()
                elif isinstance(last_login, bytes):
                    last_login = last_login.decode('utf-8')
                stats.append({
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'created_at': created_at,
                    'last_login_at': last_login,
                    'login_count': row[5]
                })
            return stats

    def update_article_score(self, article_id: int, score: float, user_id: Optional[int] = None):
        """Update article score globally or for a specific user"""
        if user_id is not None:
            self.set_user_article_score(user_id, article_id, score)
        else:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE articles SET score = ? WHERE id = ?", (score, article_id))
                conn.commit()

    def get_article_count(self) -> int:
        """Get total number of articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            return cursor.fetchone()[0]

    def search_articles(self, query: str, limit: int = 20) -> List[Dict]:
        """Search articles by title or content"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            search_query = f"%{query}%"
            cursor.execute(
                "SELECT id, title, content, summary, url, source, published_date, score FROM articles WHERE title LIKE ? OR content LIKE ? ORDER BY published_date DESC LIMIT ?",
                (search_query, search_query, limit)
            )
            return [{
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'summary': row[3],
                'url': row[4],
                'source': row[5],
                'published_date': row[6],
                'score': row[7]
            } for row in cursor.fetchall()]
