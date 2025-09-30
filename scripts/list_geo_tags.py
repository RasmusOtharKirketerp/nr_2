from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from newsreader.settings import get_settings


def list_geo_tags_by_count(db_path: str | None = None) -> None:
    settings = get_settings()
    resolved_db = Path(db_path).expanduser() if db_path else settings.default_db_path

    with sqlite3.connect(str(resolved_db)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tag, count(*) FROM geo_tags WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY tag ORDER BY count(*) DESC"
        )
        for tag, count in cursor.fetchall():
            print(f"{tag}: {count}")


def main() -> None:
    list_geo_tags_by_count()


if __name__ == "__main__":
    main()
