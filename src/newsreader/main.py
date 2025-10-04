#!/usr/bin/env python3
"""
News Reader Application

A comprehensive news reader application with the following features:
- User authentication and session management
- News article fetching from multiple sources using newspaper3k
- Article scoring based on user preferences
- NLP-powered content analysis and summarization
- Background daemon for periodic updates
- SQLite database for data persistence

Usage:
    python main.py --web             # Launch Flask web server
    python main.py --daemon           # Run background daemon
    python main.py --stack            # Run web and daemon together with supervision
    python main.py --fetch            # Fetch articles once
    python main.py --help             # Show help
"""

import argparse
import logging
import signal
import subprocess
import sys
import threading
import time
from collections import defaultdict

from .auth import AuthManager
from .daemon import NewsDaemon
from .database import DatabaseManager
from .fetcher import NewsFetcher
from .scorer import ArticleScorer
from .settings import get_settings

SETTINGS = get_settings()

def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a', encoding='utf-8')
        ]
    )

def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []

    try:
        import newspaper
    except ImportError:
        missing_deps.append("newspaper3k")

    try:
        import nltk
    except ImportError:
        missing_deps.append("nltk")

    try:
        import schedule
    except ImportError:
        missing_deps.append("schedule")

    try:
        import bcrypt
    except ImportError:
        missing_deps.append("bcrypt")

    if missing_deps:
        print("Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install them using:")
        print("pip install -r requirements.txt")
        return False

    # Download NLTK data if needed
    try:
        import nltk
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("Downloading NLTK punkt tokenizer...")
        nltk.download('punkt', quiet=True)

    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        print("Downloading NLTK stopwords...")
        nltk.download('stopwords', quiet=True)

    return True

def create_admin_user():
    """Create an admin user with admin/admin password"""
    db = DatabaseManager()
    auth = AuthManager(db)

    # Check if admin user already exists
    admin_user = db.get_user_by_username("admin")
    if admin_user:
        print("Admin user already exists!")
        return

    print("Creating admin user...")
    print("Username: admin")
    print("Password: admin123")

    success, message = auth.register_user("admin", "Admin123")
    if success:
        print("Admin user created successfully!")
        print("You can now login with username 'admin' and password 'admin123'")
    else:
        print(f"Failed to create admin user: {message}")

def create_default_user():
    """Create a default user if no users exist"""
    db = DatabaseManager()
    auth = AuthManager(db)

    # Check if any users exist
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("No users found. Creating default user...")
            print("Username: admin")
            print("Password: admin123")
            print("Please change the password after first login!")

            success, message = auth.register_user("admin", "admin123")
            if success:
                print("Default user created successfully!")
            else:
                print(f"Failed to create default user: {message}")

def launch_daemon():
    """Launch the background daemon"""
    print("Launching News Reader Daemon...")
    try:
        daemon = NewsDaemon()
        daemon.run()
    except Exception as e:
        print(f"Error launching daemon: {e}")
        logging.exception("Daemon launch error")
        sys.exit(1)



def launch_web(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Start the Flask web application."""
    from .flask_app import app

    logger = logging.getLogger("newsreader.web")
    logger.info("Starting Flask web server on %s:%s (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug)


def launch_stack(
    host: str = "0.0.0.0",
    port: int = 8000,
    debug: bool = False,
    verbose: bool = False,
    restart_delay: int = 5,
    max_restart_delay: int = 60,
    stable_reset_seconds: int = 300,
    shutdown_timeout: int = 20,
):
    """Run the daemon and web server together with automatic restarts."""

    logger = logging.getLogger("newsreader.stack")
    stop_event = threading.Event()
    processes = {}
    restart_counters = defaultdict(int)
    process_start_times = {}
    last_exit_codes = {}

    def command_for(name: str) -> list[str]:
        cmd = [sys.executable, "-m", "newsreader.main"]
        if name == "daemon":
            cmd.append("--daemon")
            if verbose:
                cmd.append("--verbose")
        elif name == "web":
            cmd.extend(["--web", "--host", str(host), "--port", str(port)])
            if debug:
                cmd.append("--debug")
            if verbose and "--verbose" not in cmd:
                cmd.append("--verbose")
        else:
            raise ValueError(f"Unknown component '{name}'")
        return cmd

    def spawn(name: str) -> None:
        cmd = command_for(name)
        logger.info("Launching %s process: %s", name, " ".join(cmd))
        process = subprocess.Popen(cmd)
        processes[name] = process
        process_start_times[name] = time.monotonic()

    def handle_signal(signum, frame):
        logger.info("Received signal %s, shutting down stack supervisor", signum)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_signal)
        except Exception:
            # Some environments (e.g., Windows service threads) may not support signal handlers
            pass

    try:
        spawn("daemon")
        spawn("web")
    except Exception:
        stop_event.set()
        raise

    try:
        while not stop_event.is_set():
            for name, process in list(processes.items()):
                if process.poll() is None:
                    uptime = time.monotonic() - process_start_times.get(name, 0.0)
                    if restart_counters[name] and uptime >= stable_reset_seconds:
                        logger.info("%s process stable for %.0f seconds; clearing restart backoff", name, uptime)
                        restart_counters[name] = 0
                    continue

                return_code = process.returncode
                last_exit_codes[name] = return_code
                uptime = time.monotonic() - process_start_times.get(name, time.monotonic())

                if stop_event.is_set():
                    continue

                if restart_counters[name] and uptime >= stable_reset_seconds:
                    restart_counters[name] = 0

                restart_counters[name] += 1
                delay = min(restart_delay * (2 ** (restart_counters[name] - 1)), max_restart_delay)

                logger.warning(
                    "%s process exited with code %s after %.1f seconds (restart #%d in %.1f seconds)",
                    name,
                    return_code,
                    uptime,
                    restart_counters[name],
                    delay,
                )

                if stop_event.wait(delay):
                    continue

                spawn(name)

            stop_event.wait(1.0)

    except KeyboardInterrupt:
        logger.info("Stack supervisor interrupted by user")
        stop_event.set()

    finally:
        logger.info("Shutting down stack supervisor")
        stop_event.set()
        for name, process in processes.items():
            if process.poll() is None:
                logger.info("Terminating %s process (pid=%s)", name, process.pid)
                process.terminate()

        deadline = time.monotonic() + shutdown_timeout
        for name, process in processes.items():
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(cmd=process.args, timeout=shutdown_timeout)
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning("%s process did not exit in time; forcing kill", name)
                process.kill()
                process.wait()

    if stop_event.is_set():
        return 0

    for code in last_exit_codes.values():
        if code not in (None, 0):
            return code

    return 0

def fetch_articles_once():
    """Fetch articles once and exit"""
    print("Fetching articles...")
    try:
        db = DatabaseManager()
        fetcher = NewsFetcher(db)
        scorer = ArticleScorer(db)

        # Fetch articles
        fetcher.fetch_all_sources()

        # Update scores
        scorer.score_all_articles()

        # Show stats
        article_count = db.get_article_count()
        source_stats = fetcher.get_source_stats()

        print(f"Fetch completed! Total articles: {article_count}")
        print("Articles by source:")
        for source, count in source_stats.items():
            print(f"  {source}: {count}")

    except Exception as e:
        print(f"Error fetching articles: {e}")
        logging.exception("Article fetch error")
        sys.exit(1)

def show_stats():
    """Show database statistics"""
    try:
        db = DatabaseManager()
        article_count = db.get_article_count()
        source_stats = db.get_connection().cursor().execute(
            "SELECT source, COUNT(*) FROM articles GROUP BY source"
        ).fetchall()

        user_count = db.get_connection().cursor().execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        print("News Reader Statistics:")
        print(f"Total users: {user_count}")
        print(f"Total articles: {article_count}")
        print("Articles by source:")
        for source, count in source_stats:
            print(f"  {source}: {count}")

    except Exception as e:
        print(f"Error getting stats: {e}")
        sys.exit(1)

def cleanup_articles():
    """Clear all articles from the database"""
    try:
        db = DatabaseManager()
        article_count = db.get_article_count()

        if article_count == 0:
            print("No articles to clean up.")
            return

        # Confirm deletion
        print(f"Found {article_count} articles in database.")
        response = input("Are you sure you want to delete all articles? (yes/no): ").strip().lower()

        if response not in ['yes', 'y']:
            print("Cleanup cancelled.")
            return

        # Delete all articles
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM articles")
            conn.commit()

        print(f"Successfully deleted {article_count} articles from database.")

    except Exception as e:
        print(f"Error during cleanup: {e}")
        sys.exit(1)

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description="News Reader Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --daemon     # Run background daemon
  python main.py --stack      # Run web + daemon with supervision
  python main.py --fetch      # Fetch articles once
  python main.py --stats      # Show database statistics
  python main.py --cleanup    # Clear all articles from database
  python main.py --create-admin  # Create admin user
        """
    )

    parser.add_argument(
        '--web', '--flask',
        dest='web',
        action='store_true',
        help='Start the Flask web server'
    )

    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host interface for the Flask web server (default: 0.0.0.0)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port for the Flask web server (default: 8000)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run the Flask web server in debug mode (implies --web)'
    )

    parser.add_argument(
        '--daemon', '-d',
        action='store_true',
        help='Run the background daemon for periodic article fetching'
    )

    parser.add_argument(
        '--stack',
        action='store_true',
        help='Run the web server and daemon together with automatic restarts'
    )

    parser.add_argument(
        '--fetch', '-f',
        action='store_true',
        help='Fetch articles once and exit'
    )

    parser.add_argument(
        '--stats', '-s',
        action='store_true',
        help='Show database statistics and exit'
    )

    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Clear all articles from database'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--create-admin',
        action='store_true',
        help='Create admin user with admin/admin credentials'
    )

    parser.add_argument(
        '--create-user',
        action='store_true',
        help='Create default user if none exists'
    )

    args = parser.parse_args()

    if args.debug:
        args.web = True

    # Setup logging
    log_level = logging.DEBUG if (args.verbose or args.debug) else logging.INFO
    setup_logging(log_level)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Handle different modes
    if args.create_admin:
        create_admin_user()
        return

    if args.create_user:
        create_default_user()
        return

    if args.stats:
        show_stats()
        return

    if args.cleanup:
        cleanup_articles()
        return

    if args.fetch:
        fetch_articles_once()
        return

    if args.stack:
        exit_code = launch_stack(
            host=args.host,
            port=args.port,
            debug=args.debug,
            verbose=args.verbose,
        )
        sys.exit(exit_code)

    if args.daemon:
        launch_daemon()
        return

    if args.web:
        launch_web(host=args.host, port=args.port, debug=args.debug)
        return

    print("No mode selected. Use --web, --daemon, --stack, --fetch, or one of the maintenance flags.")
    parser.print_help()

if __name__ == "__main__":
    main()








