import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import newspaper
from newspaper import Article

from .database import DatabaseManager
from .settings import get_settings

SETTINGS = get_settings()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
geo_fetcher_info_logger = logging.getLogger("geo-fetcher-info")
geo_fetcher_info_logger.setLevel(logging.INFO)

class NewsFetcher:
    def __init__(self, db_manager: DatabaseManager, sources_file: Optional[str] = None):
        self.db = db_manager
        self.sources_file = Path(sources_file).expanduser() if sources_file else SETTINGS.default_sources_path
        self.sources = self.load_sources()

    def load_sources(self) -> List[Dict]:
        """Load news sources from configuration file"""
        try:
            with self.sources_file.open('r', encoding='utf-8') as f:
                config = json.load(f)
                self.config = config  # Store config for later use
                return [source for source in config.get('sources', []) if source.get('enabled', True)]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load sources configuration: {e}")
            self.config = {'max_articles_per_source': 10}  # Default fallback
            return []

    def fetch_article_content(self, url: str) -> Optional[Dict]:
        """Fetch and parse a single article, including thumbnail image with fallbacks"""
        logger.debug(f"Fetching article content from {url}")
        try:
            article = Article(url)
            article.download()
            article.parse()

            # Try to fetch the top image (thumbnail) with fallbacks
            thumbnail_url = None
            try:
                article.nlp()  # This will extract summary and keywords, and sometimes image
                if hasattr(article, 'top_image') and article.top_image:
                    thumbnail_url = article.top_image
                elif hasattr(article, 'meta_img_url') and article.meta_img_url:
                    thumbnail_url = article.meta_img_url
                # Fallback: parse first <img> from HTML if still no image
                if not thumbnail_url and hasattr(article, 'html') and article.html:
                    import re
                    match = re.search(r'<img[^>]+src=["\\\']([^"\\\']+)["\\\']', article.html)
                    if match:
                        thumbnail_url = match.group(1)
            except Exception as e:
                logger.debug(f"Failed to extract thumbnail for {url}: {e}")

            # Skip if article has no content or title
            if not article.title or not article.text:
                return None

            return {
                'title': article.title,
                'content': article.text,
                'url': url,
                'published_date': article.publish_date,
                'authors': article.authors,
                'summary': article.summary if hasattr(article, 'summary') and article.summary else None,
                'thumbnail_url': thumbnail_url
            }
        except Exception as e:
            logger.warning(f"Failed to fetch article {url}: {e}")
            return None


    def fetch_source_articles(self, source: Dict, max_articles: int = 10) -> List[Dict]:
        """Fetch articles from a single news source, skipping already-saved articles and enforcing base URL match. Adds debug logging and skips non-article URLs."""
        import re
        source_url = source['url']
        source_name = source['name']

        logger.info(f"Fetching up to {max_articles} articles from {source_name} ({source_url})")

        # Patterns to skip (feeds, policy, help, etc.)
        skip_patterns = [
            r'/feed', r'/feeds', r'/rss', r'/privatlivspolitik', r'/policy', r'/help', r'/hjaelp', r'/about', r'/kontakt', r'/terms', r'/betingelser', r'/cookies', r'/support', r'/faq', r'/article/\d{4}/\d{2}/\d{2}/rss', r'/podcast/'
        ]
        skip_regex = re.compile('|'.join(skip_patterns), re.IGNORECASE)

        try:
            # Build newspaper source
            source_start_time = time.time()
            news_source = newspaper.build(source_url, memoize_articles=False, language='da')
            source_build_time = time.time() - source_start_time

            logger.info(f"Found {len(news_source.articles)} potential articles from {source_name} (source build time: {source_build_time:.2f}s)")

            # Limit to max_articles or available articles, whichever is smaller
            articles_to_fetch = min(max_articles, len(news_source.articles))

            articles = []
            successful_fetches = 0
            failed_fetches = 0
            total_fetch_time = 0
            checked = 0


            for i, article in enumerate(news_source.articles):
                if len(articles) >= articles_to_fetch:
                    break
                article_url = article.url

                logger.debug(f"[DEBUG] Considering article URL: {article_url}")

                # Enforce that article_url starts with the source base URL
                if not article_url.startswith(source_url):
                    logger.debug(f"[SKIP] Not matching base URL: {article_url}")
                    continue

                # Skip non-article URLs by pattern
                if skip_regex.search(article_url):
                    logger.debug(f"[SKIP] Non-article URL by pattern: {article_url}")
                    continue

                # Check if article already exists in DB before fetching
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM articles WHERE url = ?", (article_url,))
                    if cursor.fetchone():
                        logger.debug(f"[SKIP] Already-saved article: {article_url}")
                        continue  # Skip fetching this article

                article_start_time = time.time()
                if checked > 0:  # Don't sleep before first article
                    time.sleep(1)  # Add delay to be respectful to the source
                checked += 1

                logger.info(f"[{source_name}] Fetching article {len(articles)+1}/{articles_to_fetch}: {article_url}")

                try:
                    article_data = self.fetch_article_content(article_url)
                except Exception as e:
                    logger.error(f"[ERROR] Exception in fetch_article_content for {article_url}: {e}")
                    article_data = None

                article_fetch_time = time.time() - article_start_time
                total_fetch_time += article_fetch_time

                if article_data:
                    # Log successful fetch with details
                    content_length = len(article_data.get('content', ''))
                    title = article_data.get('title', 'No title')[:50]  # Truncate long titles
                    logger.info(f"[{source_name}] SUCCESS: '{title}' ({content_length} chars) - {article_fetch_time:.2f}s")
                    article_data['source'] = source_name
                    articles.append(article_data)
                    successful_fetches += 1
                else:
                    # Try to diagnose why it failed
                    logger.warning(f"[{source_name}] FAILED: {article_url} - {article_fetch_time:.2f}s")
                    # Try to fetch again and log details
                    try:
                        article = Article(article_url)
                        article.download()
                        article.parse()
                        if not article.title:
                            logger.warning(f"[DEBUG] Article has no title: {article_url}")
                        if not article.text:
                            logger.warning(f"[DEBUG] Article has no text: {article_url}")
                    except Exception as e:
                        logger.warning(f"[DEBUG] Exception during manual article parse: {article_url} - {e}")
                    failed_fetches += 1

            avg_fetch_time = total_fetch_time / len(articles) if articles else 0
            logger.info(f"[{source_name}] Fetch complete: {successful_fetches} successful, {failed_fetches} failed, avg time: {avg_fetch_time:.2f}s per article")
            return articles

        except Exception as e:
            logger.error(f"Failed to fetch from {source_name}: {e}")
            return []

    def save_articles_to_db(self, articles: List[Dict]):
        """Save fetched articles to database and extract/save geo-tags. Includes debug/info logging for geo-tagging."""
        from .nlp_processor import NLPProcessor
        nlp = NLPProcessor()
        saved_count = 0
        duplicate_count = 0
        error_count = 0

        logger.info(f"Attempting to save {len(articles)} articles to database")
        geo_fetcher_info_logger.info(f"Attempting to save {len(articles)} articles to database")

        for article in articles:
            try:
                article_url = article.get('url', 'unknown')
                article_title = article.get('title', 'No title')[:50]  # Truncate for logging

                # Check if article already exists
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM articles WHERE url = ?", (article_url,))
                    row = cursor.fetchone()
                    if row:
                        logger.debug(f"Skipping duplicate article: {article_title}")
                        duplicate_count += 1
                        continue  # Skip duplicate

                # Generate summary if not provided
                summary = article.get('summary') or self.generate_simple_summary(article['content'])

                # Save article
                article_id = self.db.save_article(
                    title=article['title'],
                    content=article['content'],
                    summary=summary,
                    url=article_url,
                    source=article['source'],
                    published_date=article.get('published_date'),
                    thumbnail_url=article.get('thumbnail_url')
                )

                # Extract and save geo-tags
                logger.debug(f"Extracting geo-tags for article {article_id} ('{article_title}')")
                geo_fetcher_info_logger.info(f"Extracting geo-tags for article {article_id} ('{article_title}')")
                geo_tags = nlp.extract_geo_tags(
                    article.get('content'),
                    title=article.get('title'),
                    summary=summary,
                    db_manager=self.db
                )
                logger.debug(f"Geo-tags for article {article_id}: {geo_tags}")
                geo_fetcher_info_logger.info(f"Geo-tags for article {article_id}: {geo_tags}")
                if geo_tags:
                    logger.debug(f"Saving geo-tags for article {article_id}")
                    geo_fetcher_info_logger.info(f"Saving geo-tags for article {article_id}")
                    self.db.save_geo_tags(article_id, geo_tags)

                logger.debug(f"Saved new article: '{article_title}' (ID: {article_id})")
                saved_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Failed to save article '{article.get('title', 'unknown')[:30]}...': {e}")

        logger.info(f"Database save complete: {saved_count} new articles saved, {duplicate_count} duplicates skipped, {error_count} errors")
        return saved_count

    def generate_simple_summary(self, content: str, max_sentences: int = 3) -> str:
        """Generate a simple summary by taking first few sentences"""
        if not content:
            return ""

        sentences = content.split('.')
        summary_sentences = []

        for sentence in sentences[:max_sentences]:
            sentence = sentence.strip()
            if sentence:
                summary_sentences.append(sentence)

        return '. '.join(summary_sentences) + ('.' if summary_sentences else '')

    def fetch_all_sources(self, max_articles_per_source: Optional[int] = None):
        """Fetch articles from all configured sources"""
        # Use config value if no parameter provided
        if max_articles_per_source is None:
            max_articles_per_source = self.config.get('max_articles_per_source', 10)

        total_start_time = time.time()
        logger.info(f"Starting news fetch from {len(self.sources)} sources (max {max_articles_per_source} articles per source)")

        total_articles = 0
        successful_sources = 0
        failed_sources = 0

        for i, source in enumerate(self.sources, 1):
            source_name = source['name']
            source_start_time = time.time()

            logger.info(f"Processing source {i}/{len(self.sources)}: {source_name}")

            try:
                articles = self.fetch_source_articles(source, max_articles_per_source)
                saved_count = self.save_articles_to_db(articles) if articles else 0

                if articles and saved_count > 0:
                    total_articles += saved_count
                    successful_sources += 1

                    source_time = time.time() - source_start_time
                    logger.info(f"[{source_name}] Source complete: {len(articles)} fetched, {saved_count} saved, time: {source_time:.2f}s")
                elif articles and saved_count == 0:
                    # Articles fetched but all were duplicates
                    successful_sources += 1
                    source_time = time.time() - source_start_time
                    logger.info(f"[{source_name}] Source complete: {len(articles)} fetched, {saved_count} saved (all duplicates), time: {source_time:.2f}s")
                else:
                    failed_sources += 1
                    source_time = time.time() - source_start_time
                    logger.warning(f"[{source_name}] Source failed or returned no articles (time: {source_time:.2f}s)")

            except Exception as e:
                failed_sources += 1
                source_time = time.time() - source_start_time
                logger.error(f"[{source_name}] Source error: {e} (time: {source_time:.2f}s)")

            # Add delay between sources to be respectful
            if i < len(self.sources):  # Don't sleep after the last source
                time.sleep(2)

        total_time = time.time() - total_start_time
        avg_time_per_source = total_time / len(self.sources) if self.sources else 0

        logger.info(f"News fetch completed: {total_articles} total articles saved, {successful_sources} sources successful, {failed_sources} sources failed")
        logger.info(f"Total time: {total_time:.2f}s, average {avg_time_per_source:.2f}s per source")

    def update_article_scores(self):
        """Update scores for all articles (to be called after fetching)"""
        # This will be implemented in the scorer module
        pass

    def get_source_stats(self) -> Dict:
        """Get statistics about articles per source"""
        stats = {}
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source")
            for row in cursor.fetchall():
                stats[row[0]] = row[1]
        return stats

    def cleanup_old_articles(self, days_to_keep: int = 30):
        """Remove articles older than specified days"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        logger.info(f"Starting cleanup of articles older than {days_to_keep} days (cutoff: {cutoff_date.date()})")

        # Get count before cleanup for reporting
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles WHERE fetched_at < ?", (cutoff_date,))
            old_articles_count = cursor.fetchone()[0]

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM articles WHERE fetched_at < ?", (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()

        # Get stats about what was cleaned up
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT source, COUNT(*) FROM articles WHERE fetched_at < ? GROUP BY source", (cutoff_date,))
            deleted_by_source = dict(cursor.fetchall())

        logger.info(f"Cleanup completed: removed {deleted_count} articles older than {days_to_keep} days")
        if deleted_by_source:
            logger.info("Articles removed by source:")
            for source, count in deleted_by_source.items():
                logger.info(f"  {source}: {count} articles")

        return deleted_count
    

if __name__ == "__main__":
    db_manager = DatabaseManager("single_run_news.db")
    fetcher = NewsFetcher(db_manager)
    fetcher.fetch_all_sources()
    fetcher.update_article_scores()
    deleted_count = fetcher.cleanup_old_articles(days_to_keep=30)
    if deleted_count > 0:
        logger.info(f"Cleanup removed {deleted_count} old articles.")
