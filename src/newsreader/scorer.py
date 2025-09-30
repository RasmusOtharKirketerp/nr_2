import math
from datetime import datetime, timedelta
from typing import Dict, List
from .database import DatabaseManager

class ArticleScorer:
    def calculate_word_score(self, article: Dict, score_words: List[Dict]) -> float:
        """Score based on user words and weights"""
        text = (article.get('title', '') + ' ' + article.get('summary', '') + ' ' + article.get('content', '')).lower()
        score = 0.0
        for entry in score_words:
            # Defensive: handle missing keys gracefully
            word = entry.get('word')
            weight = entry.get('weight', 1)
            if not word:
                continue
            word = word.lower()
            count = text.count(word)
            score += count * weight
        return score
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.source_reliability = self._load_source_reliability()

    def _load_source_reliability(self) -> Dict[str, float]:
        """Load source reliability scores (higher = more reliable)"""
        # This could be loaded from a config file or database
        # For now, using hardcoded values based on common perceptions
        return {
            'BBC News': 0.95,
            'Reuters': 0.95,
            'The New York Times': 0.90,
            'The Guardian': 0.85,
            'CNN': 0.80,
            'TechCrunch': 0.75,
            'Wired': 0.75,
            # Default for unknown sources
            'default': 0.60
        }

    def calculate_recency_score(self, published_date: str) -> float:
        """Calculate recency score (0-1, higher = more recent)"""
        if not published_date:
            return 0.5  # Neutral score for undated articles

        try:
            pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()

            # Calculate hours since publication
            time_diff = now - pub_date
            hours_old = time_diff.total_seconds() / 3600

            # Exponential decay: score = e^(-hours_old/24)
            # This gives ~0.37 for 24h old, ~0.14 for 48h old, etc.
            return math.exp(-hours_old / 24)

        except (ValueError, AttributeError):
            return 0.5  # Neutral score for invalid dates

    def calculate_length_score(self, content: str) -> float:
        """Calculate content length score (0-1, higher = better length)"""
        if not content:
            return 0.0

        word_count = len(content.split())

        # Optimal article length is around 300-800 words
        # Score peaks at 500 words, decreases for very short or very long articles
        if word_count < 50:
            return word_count / 50 * 0.3  # Linear increase for very short articles
        elif word_count <= 500:
            return 0.3 + (word_count - 50) / 450 * 0.7  # Peak at 500 words
        elif word_count <= 1500:
            return 1.0 - (word_count - 500) / 1000 * 0.3  # Gradual decline
        else:
            return 0.7 - min((word_count - 1500) / 2000, 0.7)  # Minimum score

    def calculate_source_reliability_score(self, source: str) -> float:
        """Calculate source reliability score"""
        return self.source_reliability.get(source, self.source_reliability['default'])

    def calculate_overall_score(self, article: Dict, score_words: List[Dict]) -> float:
        """Calculate overall article score based on user words/weights"""
        return self.calculate_word_score(article, score_words)

    def score_all_articles(self, user_id: int = None):
        """Score all articles in database for a specific user or with default words"""
        articles = self.db.get_articles(limit=10000)
        if user_id:
            score_words = self.db.get_score_words(user_id)
            for article in articles:
                score = self.calculate_overall_score(article, score_words)
                self.db.update_article_score(article['id'], score, user_id=user_id)
        else:
            score_words = self.db.get_default_score_words()
            for article in articles:
                score = self.calculate_overall_score(article, score_words)
                self.db.update_article_score(article['id'], score)

    def get_scoring_explanation(self, article: Dict, user_preferences: List[Dict]) -> Dict:
        """Get detailed scoring breakdown for an article"""
        scores = {
            'recency': self.calculate_recency_score(article.get('published_date')),
            'length': self.calculate_length_score(article.get('content', '')),
            'source_reliability': self.calculate_source_reliability_score(article.get('source', ''))
        }

        breakdown = {}
        total_score = 0.0
        total_weight = 0.0

        for pref in user_preferences:
            criteria = pref['criteria']
            weight = pref['weight']

            if criteria in scores:
                contribution = scores[criteria] * weight
                breakdown[criteria] = {
                    'raw_score': scores[criteria],
                    'weight': weight,
                    'contribution': contribution
                }
                total_score += contribution
                total_weight += weight

        return {
            'total_score': total_score / total_weight if total_weight > 0 else 0.0,
            'breakdown': breakdown,
            'article_info': {
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'published_date': article.get('published_date', ''),
                'word_count': len(article.get('content', '').split()) if article.get('content') else 0
            }
        }

    def update_user_preferences(self, user_id: int, preferences: Dict[str, float]):
        """Update scoring preferences for a user"""
        for criteria, weight in preferences.items():
            if 0.0 <= weight <= 1.0:  # Validate weight range
                self.db.update_user_preference(user_id, criteria, weight)

    def get_default_preferences(self) -> List[Dict]:
        """Get default scoring preferences"""
        return [
            {'criteria': 'recency', 'weight': 0.3},
            {'criteria': 'length', 'weight': 0.2},
            {'criteria': 'source_reliability', 'weight': 0.5}
        ]

    def get_available_criteria(self) -> List[str]:
        """Get list of available scoring criteria"""
        return ['recency', 'length', 'source_reliability']