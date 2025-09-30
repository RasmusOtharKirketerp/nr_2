"""Script to retroactively geo-tag all existing articles."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from newsreader.database import DatabaseManager
from newsreader.nlp_processor import NLPProcessor


def main() -> None:
    db = DatabaseManager()
    nlp = NLPProcessor()
    print("Extracting and saving geo-tags for all articles...")
    db.geo_tag_all_articles(nlp)
    print("Geo-tagging complete.")


if __name__ == "__main__":
    main()
