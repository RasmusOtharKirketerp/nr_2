from .settings import get_settings

SETTINGS = get_settings()

# --- Login Route ---





from flask import abort
from flask import Flask, render_template, redirect, url_for, request, session, flash
import logging
from .database import DatabaseManager
from .scorer import ArticleScorer
from .auth import AuthManager
from .fetcher import NewsFetcher
from .nlp_processor import NLPProcessor
import os


app = Flask(__name__, template_folder=str(SETTINGS.templates_dir))
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key')
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    handlers=[
                        logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a'),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger("geo-api-debug")
info_logger = logging.getLogger("geo-api-info")
info_logger.setLevel(logging.INFO)

db = DatabaseManager()
auth = AuthManager(db)
scorer = ArticleScorer(db)


def _get_admin_user_or_redirect():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in as admin to access this page.', 'danger')
        return None, redirect(url_for('login'))

    username = session.get('username')
    user = db.get_user_by_username(username) if username else None
    if not user or user.get('username') != 'admin':
        abort(403)

    return user, None

# --- Login Route ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        success, message, session_token = auth.login_user(username, password)
        logger.debug("Login attempt result for %s: success=%s message=%s", username, success, message)
        if success:
            user = db.get_user_by_username(username)
            session['user_id'] = user['id']
            session['username'] = user['username']
            # Recalculate article scores for this user on login
            scorer.score_all_articles(user_id=user['id'])
            flash('Login successful! Article scores updated for your preferences.', 'success')
            flash('Welcome, user', 'success')
            return redirect(url_for('index'))
        else:
            flash(message, 'danger')
    return render_template('login.html')

# --- Heatmap UI route ---
@app.route('/heatmap')
def heatmap():
    logger.debug("Rendering heatmap UI page.")
    info_logger.info("Rendering heatmap UI page.")
    username = session.get('username', '')
    return render_template('heatmap.html', username=username)


# --- API: Geo-tags for heat-map ---
@app.route('/api/geo_tags')
def api_geo_tags():
    """Return all geo-tags with coordinates for heat-map visualization. Excludes tags in excluded_tags table."""
    excluded = db.get_excluded_tags()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if excluded:
            placeholders = ','.join(['?'] * len(excluded))
            query = f"SELECT article_id, tag, lat, lon, confidence, source FROM geo_tags WHERE lat IS NOT NULL AND lon IS NOT NULL AND tag NOT IN ({placeholders}) ORDER BY article_id DESC"
            cursor.execute(query, excluded)
        else:
            cursor.execute("SELECT article_id, tag, lat, lon, confidence, source FROM geo_tags WHERE lat IS NOT NULL AND lon IS NOT NULL ORDER BY article_id DESC")
        geo_tags = [
            {
                'article_id': row[0],
                'tag': row[1],
                'lat': row[2],
                'lon': row[3],
                'confidence': row[4],
                'source': row[5]
            }
            for row in cursor.fetchall()
        ]
    logger.debug(f"API /api/geo_tags returning {len(geo_tags)} geo-tags.")
    info_logger.info(f"API /api/geo_tags returning {len(geo_tags)} geo-tags.")
    return {'geo_tags': geo_tags}


# --- Admin: Excluded Tags Management ---
@app.route('/excluded-tags', methods=['GET', 'POST'])
def excluded_tags():
    admin_user, redirect_response = _get_admin_user_or_redirect()
    if redirect_response:
        return redirect_response
    if request.method == 'POST':
        tag = request.form.get('tag', '').strip()
        if tag:
            db.add_excluded_tag(tag)
            flash(f'Added excluded tag: {tag}', 'success')
        else:
            flash('Tag cannot be empty.', 'danger')
        return redirect(url_for('excluded_tags'))
    tags = db.get_excluded_tags()
    return render_template('excluded_tags.html', tags=tags, user_id=admin_user['id'], username=admin_user['username'])


@app.route('/admin', methods=['GET'])
def admin_dashboard():
    admin_user, redirect_response = _get_admin_user_or_redirect()
    if redirect_response:
        return redirect_response

    article_count = db.get_article_count()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM geo_tags")
        geo_tag_count = cursor.fetchone()[0]

    user_stats = db.get_user_usage_stats()
    latest_login = max((stat['last_login_at'] for stat in user_stats if stat['last_login_at']), default=None)

    return render_template(
        'admin_dashboard.html',
        article_count=article_count,
        geo_tag_count=geo_tag_count,
        user_stats=user_stats,
        latest_login=latest_login,
        user_id=admin_user['id'],
        username=admin_user['username']
    )


@app.route('/admin/articles/delete/<int:article_id>', methods=['POST'])
def admin_delete_article(article_id):
    admin_user, redirect_response = _get_admin_user_or_redirect()
    if redirect_response:
        return redirect_response

    if db.delete_article(article_id):
        scorer.score_all_articles()
        flash(f'Deleted article {article_id}.', 'success')
    else:
        flash('Article not found or already deleted.', 'warning')

    return redirect(request.referrer or url_for('index'))


@app.route('/admin/articles/purge-refresh', methods=['POST'])
def admin_purge_refresh_articles():
    admin_user, redirect_response = _get_admin_user_or_redirect()
    if redirect_response:
        return redirect_response

    deleted = db.delete_all_articles()
    try:
        fetcher = NewsFetcher(db)
        fetcher.fetch_all_sources()
        scorer.score_all_articles()
        new_total = db.get_article_count()
        flash(f'Deleted {deleted} articles and fetched {new_total} fresh articles.', 'success')
    except Exception as exc:
        logging.getLogger(__name__).exception('Failed to refresh articles')
        flash(f'Failed to refresh articles: {exc}', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/articles/geo-refresh', methods=['POST'])
def admin_rerun_geo_tags():
    admin_user, redirect_response = _get_admin_user_or_redirect()
    if redirect_response:
        return redirect_response

    cleared = db.clear_geo_tags(reset_not_found=True)
    try:
        nlp = NLPProcessor()
        db.geo_tag_all_articles(nlp)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM geo_tags")
            new_total = cursor.fetchone()[0]
        flash(f'Regenerated geo-tags for {new_total} entries (cleared {cleared}).', 'success')
    except Exception as exc:
        logging.getLogger(__name__).exception('Failed to regenerate geo-tags')
        flash(f'Failed to regenerate geo-tags: {exc}', 'danger')

    return redirect(url_for('admin_dashboard'))

# --- Recalculate Scores Route ---

@app.route('/recalc_scores', methods=['POST'])
def recalc_scores():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to recalculate scores.', 'danger')
        return redirect(url_for('login'))
    scorer.score_all_articles(user_id=user_id)
    flash('Scores recalculated for your preferences.', 'success')
    return redirect(url_for('index'))



# --- Scoring Words Management ---
@app.route('/score-words', methods=['GET'])
def score_words():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to manage scoring words.', 'danger')
        return redirect(url_for('login'))
    score_words = db.get_score_words(user_id)
    return render_template('score_words.html', score_words=score_words, user_id=user_id, username=session.get('username'))

@app.route('/score-words/add', methods=['POST'])
def add_score_word():
    user_id = session.get('user_id')
    if not user_id:
        abort(403)
    word = request.form['word'].strip()
    try:
        weight = int(request.form['weight'])
        if not (1 <= weight <= 10):
            raise ValueError
    except Exception:
        flash('Weight must be an integer between 1 and 10.', 'danger')
        return redirect(url_for('score_words'))
    if not word:
        flash('Word cannot be empty.', 'danger')
        return redirect(url_for('score_words'))
    db.add_score_word(user_id, word, weight)
    flash(f'Added/updated word "{word}" with weight {weight}.', 'success')
    return redirect(url_for('score_words'))

@app.route('/score-words/edit/<word>', methods=['POST'])
def edit_score_word(word):
    user_id = session.get('user_id')
    if not user_id:
        abort(403)
    new_word = request.form['word'].strip()
    try:
        weight = int(request.form['weight'])
        if not (1 <= weight <= 10):
            raise ValueError
    except Exception:
        flash('Weight must be an integer between 1 and 10.', 'danger')
        return redirect(url_for('score_words'))
    if not new_word:
        flash('Word cannot be empty.', 'danger')
        return redirect(url_for('score_words'))
    # Remove old word if changed
    if new_word != word:
        db.add_score_word(user_id, new_word, weight)
        db.add_score_word(user_id, word, 0)  # Set old to 0 (or delete)
        db.delete_score_word(user_id, word)
    else:
        db.add_score_word(user_id, new_word, weight)
    flash(f'Updated word "{new_word}" with weight {weight}.', 'success')
    return redirect(url_for('score_words'))

@app.route('/score-words/delete/<word>', methods=['POST'])
def delete_score_word(word):
    user_id = session.get('user_id')
    if not user_id:
        abort(403)
    db.delete_score_word(user_id, word)
    flash(f'Deleted word "{word}".', 'info')
    return redirect(url_for('score_words'))


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if db.get_user_by_username(username):
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        hashed_pw = auth.hash_password(password)
        db.create_user(username, hashed_pw, email)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/')
def index():
    user_id = session.get('user_id')
    articles = db.get_articles(limit=50, user_id=user_id)
    # Add matched score words for tooltip
    score_words = db.get_score_words(user_id) if user_id else db.get_default_score_words()
    for article in articles:
        text = (article.get('title', '') + ' ' + article.get('summary', '') + ' ' + article.get('content', '')).lower()
        matched = []
        for entry in score_words:
            word = entry.get('word', '').lower()
            if word and word in text:
                count = text.count(word)
                matched.append(f"{word} (x{count})")
        article['matched_words'] = ', '.join(matched) if matched else 'No score words found'

    return render_template('index.html', articles=articles, user_id=user_id, username=session.get('username'))


# --- API: Articles by Geo-tag ---
@app.route('/api/articles_by_tag')
def api_articles_by_tag():
    tag = request.args.get('tag', '').strip()
    if not tag:
        return {'error': 'Missing tag parameter'}, 400
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.title, a.summary, a.url, a.published_date, a.source
            FROM articles a
            JOIN geo_tags g ON a.id = g.article_id
            WHERE g.tag = ?
            ORDER BY a.published_date DESC
        """, (tag,))
        articles = [
            {
                'id': row[0],
                'title': row[1],
                'summary': row[2],
                'url': row[3],
                'published_date': row[4],
                'source': row[5]
            }
            for row in cursor.fetchall()
        ]
    return {'articles': articles}




if __name__ == '__main__':
    app.run(debug=True)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    articles = db.get_articles(limit=1, offset=article_id-1)
    if not articles:
        flash('Article not found', 'danger')
        return redirect(url_for('index'))
    article = articles[0]
    return render_template('article_detail.html', article=article, user_id=session.get('user_id'), username=session.get('username'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view your profile.', 'danger')
        return redirect(url_for('login'))
    user = db.get_user_by_username(session.get('username'))
    if request.method == 'POST':
        new_email = request.form['email']
        db.update_user_email(user_id, new_email)
        flash('Email updated successfully.', 'success')
        user = db.get_user_by_username(session.get('username'))  # Refresh user from DB
    return render_template('profile.html', user=user, user_id=user_id, username=session.get('username'))

if __name__ == '__main__':
    app.run(debug=True)
