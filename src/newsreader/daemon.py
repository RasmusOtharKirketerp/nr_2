
import time
import logging
import json
import signal
import sys
import os
from datetime import datetime
from pathlib import Path
import schedule
from typing import Optional
from .settings import get_settings

SETTINGS = get_settings()


from .database import DatabaseManager
from .fetcher import NewsFetcher
from .scorer import ArticleScorer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Force reconfiguration of logging
)
logger = logging.getLogger(__name__)

# Ensure immediate flushing for file handler
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.FileHandler):
        handler.flush()


class NewsDaemon:
    LOCKFILE = SETTINGS.var_dir / "news_daemon.pid"

    def __init__(self, sources_file: Optional[str] = None):
        self.sources_file = Path(sources_file).expanduser() if sources_file else SETTINGS.default_sources_path
        self.running = False
        self.db = DatabaseManager()
        self.fetcher = NewsFetcher(self.db, self.sources_file)
        self.scorer = ArticleScorer(self.db)
        self.lockfile_path = Path(self.LOCKFILE)
        self.lockfile_path.parent.mkdir(parents=True, exist_ok=True)

        # Lock file logic
        self._acquire_lock()

        # Load configuration
        self.config = self.load_config()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def _acquire_lock(self):
        if self.lockfile_path.exists():
            try:
                with self.lockfile_path.open('r') as f:
                    pid = int(f.read().strip())
                # Check if process is running
                if pid != os.getpid() and self._pid_running(pid):
                    logger.error(f"Another NewsDaemon is already running with PID {pid}. Exiting.")
                    print(f"Another NewsDaemon is already running with PID {pid}. Exiting.")
                    sys.exit(1)
            except Exception as e:
                logger.warning(f"Could not verify existing lock file: {e}")
                print(f"Could not verify existing lock file: {e}")
                sys.exit(1)
        # Write our PID
        with self.lockfile_path.open('w') as f:
            f.write(str(os.getpid()))

    def _pid_running(self, pid):
        if pid <= 0:
            return False
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            pass
        if os.name == 'nt':
            # Windows: use ctypes to check process existence
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        else:
            try:
                os.kill(pid, 0)
            except OSError:
                return False
            else:
                return True

    def load_config(self) -> dict:
        """Load daemon configuration from sources.json"""
        try:
            with self.sources_file.open('r', encoding='utf-8') as f:
                config = json.load(f)
                return {
                    'fetch_interval_minutes': config.get('fetch_interval_minutes', 30),
                    'max_articles_per_source': config.get('max_articles_per_source', 10),
                    'cleanup_days': config.get('cleanup_days', 30),
                    'enabled': config.get('daemon_enabled', True)
                }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load daemon config: {e}")
            return {
                'fetch_interval_minutes': 30,
                'max_articles_per_source': 10,
                'cleanup_days': 30,
                'enabled': True
            }

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self._release_lock()

    def fetch_news_job(self):
        """Job to fetch news from all sources"""
        try:
            logger.info("Starting scheduled news fetch")
            start_time = datetime.now()


            # Log how many articles are already in the DB before fetching
            pre_count = self.db.get_article_count()
            logger.info(f"Articles in DB before fetch: {pre_count}")

            # Fetch articles from all sources and count how many were skipped as already in DB
            if hasattr(self.fetcher, 'fetch_all_sources'):
                # Try to get skipped count if fetcher returns it, else fallback
                try:
                    result = self.fetcher.fetch_all_sources(self.config['max_articles_per_source'])
                    if isinstance(result, dict) and 'skipped_existing' in result:
                        skipped = result['skipped_existing']
                        logger.info(f"Articles skipped (already in DB): {skipped}")
                    else:
                        logger.info("Articles skipped (already in DB): (count not available)")
                except TypeError:
                    # If fetch_all_sources does not return skipped count
                    self.fetcher.fetch_all_sources(self.config['max_articles_per_source'])
                    logger.info("Articles skipped (already in DB): (count not available)")
            else:
                logger.info("Fetcher does not support fetch_all_sources method.")

            # Update article scores
            self.scorer.score_all_articles()

            duration = datetime.now() - start_time
            logger.info(f"News fetch completed in {duration.total_seconds():.1f} seconds")

        except Exception as e:
            logger.error(f"Error in news fetch job: {e}")

    def cleanup_job(self):
        """Job to clean up old articles"""
        try:
            logger.info("Starting article cleanup")
            deleted_count = self.fetcher.cleanup_old_articles(self.config['cleanup_days'])
            logger.info(f"Cleanup completed, removed {deleted_count} old articles")

        except Exception as e:
            logger.error(f"Error in cleanup job: {e}")

    def stats_job(self):
        """Job to log system statistics"""
        try:
            article_count = self.db.get_article_count()
            source_stats = self.fetcher.get_source_stats()

            logger.info(f"System stats: {article_count} total articles")
            for source, count in source_stats.items():
                logger.info(f"  {source}: {count} articles")

        except Exception as e:
            logger.error(f"Error in stats job: {e}")

    def setup_schedule(self):
        """Setup the job schedule"""
        interval = self.config['fetch_interval_minutes']

        # Main news fetching job
        schedule.every(interval).minutes.do(self.fetch_news_job)
        logger.info(f"Scheduled news fetch every {interval} minutes")

        # Cleanup job (run daily)
        schedule.every().day.at("02:00").do(self.cleanup_job)
        logger.info("Scheduled daily cleanup at 02:00")

        # Stats logging (run hourly)
        schedule.every().hour.do(self.stats_job)
        logger.info("Scheduled hourly stats logging")

    def run_once(self):
        """Run all jobs once (for testing)"""
        logger.info("Running all jobs once...")
        self.fetch_news_job()
        self.cleanup_job()
        self.stats_job()

    def run(self):
        """Main daemon loop"""
        if not self.config['enabled']:
            logger.info("Daemon is disabled in configuration")
            return

        logger.info("Starting News Reader Daemon")
        logger.info(f"Configuration: {self.config}")

        # Setup job schedule
        self.setup_schedule()

        # Run initial fetch
        logger.info("Running initial news fetch...")
        self.fetch_news_job()

        self.running = True
        logger.info("Daemon started successfully. Press Ctrl+C to stop.")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute

        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in daemon: {e}")
        finally:
            logger.info("Daemon shutting down")
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'db'):
                # Close database connections if needed
                pass
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        self._release_lock()

    def _release_lock(self):
        try:
            if self.lockfile_path.exists():
                self.lockfile_path.unlink()
                logger.info(f"Removed lock file {self.lockfile_path}")
        except Exception as e:
            logger.warning(f"Failed to remove lock file: {e}")

def main():
    """Main entry point for the daemon"""
    import argparse

    parser = argparse.ArgumentParser(description='News Reader Daemon')
    parser.add_argument('--config', type=Path, default=None, help='Configuration file path')
    parser.add_argument('--once', action='store_true', help='Run jobs once and exit (for testing)')

    args = parser.parse_args()

    daemon = NewsDaemon(args.config)

    if args.once:
        daemon.run_once()
    else:
        daemon.run()

if __name__ == "__main__":
    main()
