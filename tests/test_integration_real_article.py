"""Network-enabled integration test capturing full ingestion pipeline for a single article.

Run with environment variables:
- RUN_REAL_ARTICLE_TEST=1 to enable the test (otherwise it is skipped by default).
- REAL_ARTICLE_URL=<https-url> to override the article under test (optional).

Example (PowerShell):

    $env:RUN_REAL_ARTICLE_TEST = "1"
    pytest tests/test_integration_real_article.py -k real_article
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

from newsreader.fetcher import NewsFetcher
from newsreader.nlp_processor import NLPProcessor
from newsreader.settings import get_settings

# Fallback article chosen for its stable public availability and clear geographic references.
DEFAULT_REAL_ARTICLE_URL = (
    "https://www.reuters.com/world/europe/denmark-parliament-approves-new-defense-bill-2023-12-07/"
)


@pytest.mark.skipif(
    not os.getenv("RUN_REAL_ARTICLE_TEST"),
    reason="Set RUN_REAL_ARTICLE_TEST=1 to execute the live article ingestion test.",
)
def test_real_article_end_to_end(db_manager) -> None:
    """Fetch a live article, persist it, and snapshot the resulting database + NLP artifacts."""

    settings = get_settings()

    # Ensure geo lookup data exists inside the temp test environment.
    geo_places_path = settings.default_geo_places_path
    geo_places_path.parent.mkdir(parents=True, exist_ok=True)
    geo_places: List[str] = [
        "Copenhagen",
        "Denmark",
        "Greenland",
        "Europe",
        "London",
        "Paris",
        "Berlin",
        "Stockholm",
        "New York",
    ]
    geo_places_path.write_text(json.dumps(geo_places, ensure_ascii=False, indent=2), encoding="utf-8")

    real_url = os.getenv("REAL_ARTICLE_URL", DEFAULT_REAL_ARTICLE_URL)

    fetcher = NewsFetcher(db_manager)
    article_data = fetcher.fetch_article_content(real_url)

    if not article_data:
        pytest.skip(f"Could not download article from {real_url}; check that the URL is reachable.")

    article_data.setdefault("summary", fetcher.generate_simple_summary(article_data.get("content", "")))
    article_data["source"] = article_data.get("source") or "integration-test"

    saved_count = fetcher.save_articles_to_db([article_data])
    assert saved_count == 1, "Expected the pipeline to persist exactly one article"

    snapshot: Dict[str, Any] = {"input_url": real_url}

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE url = ?", (real_url,))
        row = cursor.fetchone()
        assert row is not None, "Article should be present in the articles table"

        article_id = row["id"]
        article_record = {key: row[key] for key in row.keys()}
        snapshot["article_record"] = article_record

        cursor.execute(
            "SELECT tag, confidence, source, lat, lon FROM geo_tags WHERE article_id = ?",
            (article_id,),
        )
        geo_rows = cursor.fetchall()
        snapshot["geo_tags"] = [
            {
                "tag": geo_row["tag"],
                "confidence": geo_row["confidence"],
                "source": geo_row["source"],
                "lat": geo_row["lat"],
                "lon": geo_row["lon"],
            }
            for geo_row in geo_rows
        ]

        cursor.execute("SELECT tag FROM geo_tag_not_found ORDER BY tag")
        snapshot["geo_tags_not_found"] = [record["tag"] for record in cursor.fetchall()]

    nlp_processor = NLPProcessor()
    text_stats = nlp_processor.get_text_stats(snapshot["article_record"]["content"])
    snapshot["text_stats"] = text_stats
    snapshot["summary"] = snapshot["article_record"].get("summary")
    snapshot["article_id"] = snapshot["article_record"]["id"]

    # Print a JSON snapshot so the user can inspect the full payload via pytest -s
    print(json.dumps(snapshot, indent=2, default=str))

    assert snapshot["article_record"]["id"] == article_id
    assert snapshot["article_record"]["title"]
    assert snapshot["article_record"]["summary"]