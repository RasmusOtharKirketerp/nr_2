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
    """Delete all geo_tags rows from the configured database."""
    settings = get_settings()
    db_path = settings.default_db_path

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute('DELETE FROM geo_tags')
        conn.commit()

    print(f"All geo_tags deleted from {db_path}.")


if __name__ == "__main__":
    main()
