from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from newsreader.settings import get_settings


def main() -> None:
    """Ensure the per-user score words table exists."""
    settings = get_settings()
    db_path = settings.default_db_path

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_score_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                weight INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, word)
            )
            '''
        )
        conn.commit()

    print(f"user_score_words table available at {db_path}.")


if __name__ == "__main__":
    main()
