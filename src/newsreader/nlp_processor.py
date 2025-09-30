import nltk
import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
import math
from .settings import get_settings

SETTINGS = get_settings()


# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

class NLPProcessor:
    def __init__(self):
        import spacy
        import logging
        import subprocess
        # Set up logging once for the class
        try:
            logging.basicConfig(level=logging.DEBUG,
                                format='%(asctime)s %(levelname)s %(name)s %(message)s',
                                handlers=[
                                    logging.FileHandler(str(SETTINGS.daemon_log_path), mode='a'),
                                    logging.StreamHandler()
                                ])
        except Exception:
            pass  # If logging is already configured, ignore
        self.logger = getattr(self, 'logger', logging.getLogger("geo-debug"))
        self.info_logger = getattr(self, 'info_logger', logging.getLogger("geo-info"))
        self.info_logger.setLevel(logging.INFO)
        # Ensure spaCy models are loaded (download if missing)
        def ensure_spacy_model(model_name):
            try:
                spacy.load(model_name)
            except OSError:
                self.logger.info(f"Downloading spaCy model: {model_name}")
                subprocess.run(["python", "-m", "spacy", "download", model_name], check=True)
        ensure_spacy_model('da_core_news_lg')
        ensure_spacy_model('en_core_web_sm')
        # Try Danish model, fallback to English
        try:
            self.nlp = spacy.load('da_core_news_lg')
            self.model_used = 'da_core_news_lg'
            self.logger.info("Loaded spaCy model: da_core_news_lg")
        except Exception:
            self.nlp = spacy.load('en_core_web_sm')
            self.model_used = 'en_core_web_sm'
            self.logger.info("Loaded spaCy model: en_core_web_sm (fallback)")
        self.logger.info(f"spaCy NER model in use: {self.model_used}")
        import nltk
        self.stop_words = set(nltk.corpus.stopwords.words('english'))
        # Add common news-specific stop words
        self.stop_words.update(['said', 'would', 'could', 'also', 'one', 'two', 'three', 'first', 'second', 'new'])

    def extract_geo_tags(self, text: str, title: str = None, summary: str = None, db_manager=None, not_found_callback=None) -> List[dict]:
        """Extract location names (geo-tags) from text, title, and summary by direct matching against a list of cities and countries. Only tags if found in the list. Skips all other entity types."""
        import json
        import logging
        from geopy.geocoders import Nominatim
        import time
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger("geo-debug")
        if not hasattr(self, 'info_logger'):
            self.info_logger = logging.getLogger("geo-info")
            self.info_logger.setLevel(logging.INFO)
        logger = self.logger
        info_logger = self.info_logger
        # Load city/country list
        with open(SETTINGS.default_geo_places_path, 'r', encoding='utf-8') as f:
            geo_places = set(json.load(f))
        all_texts = []
        if title:
            all_texts.append(title)
        if summary:
            all_texts.append(summary)
        if text:
            all_texts.append(text)
        combined_text = "\n".join(all_texts)
        tags = []
        seen = set()
        logger.debug(f"Extracting geo-tags from text: {combined_text[:200]}...")
        info_logger.info(f"Extracting geo-tags from text (first 200 chars): {combined_text[:200]}...")
        if db_manager is None:
            raise ValueError("db_manager must be provided to extract_geo_tags to avoid DB lock issues during batch operations.")
        db = db_manager
        geolocator = Nominatim(user_agent="newsreader-geo")
        # For each place, check if it appears in the text (case-insensitive, word-boundary)
        import re
        for place in geo_places:
            if place.lower() in seen:
                continue
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(place) + r'\b'
            if re.search(pattern, combined_text, re.IGNORECASE):
                seen.add(place.lower())
                # Check not-found cache
                if db.is_geo_tag_not_found(place):
                    logger.debug(f"Skipping {place} (previously not found)")
                    continue
                lat, lon, osm_conf = None, None, None
                try:
                    logger.debug(f"Requesting OSM geocode for: {place}")
                    info_logger.info(f"Requesting OSM geocode for: {place}")
                    location = geolocator.geocode(place, addressdetails=True, timeout=10)
                    if location:
                        lat = location.latitude
                        lon = location.longitude
                        osm_conf = location.raw.get('importance')
                        logger.debug(f"OSM result for '{place}': lat={lat}, lon={lon}, importance={osm_conf}")
                        info_logger.info(f"OSM result for '{place}': lat={lat}, lon={lon}, importance={osm_conf}")
                    else:
                        logger.debug(f"No OSM result for '{place}'")
                        info_logger.info(f"No OSM result for '{place}'")
                        if not_found_callback:
                            not_found_callback(place)
                        else:
                            db.add_geo_tag_not_found(place)
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error geocoding '{place}': {e}")
                    info_logger.info(f"Error geocoding '{place}': {e}")
                    if not_found_callback:
                        not_found_callback(place)
                    else:
                        db.add_geo_tag_not_found(place)
                # Only add tag if lat/lon found
                if lat is not None and lon is not None:
                    tags.append({
                        'tag': place,
                        'label': 'CITY_OR_COUNTRY',
                        'confidence': osm_conf,
                        'lat': lat,
                        'lon': lon
                    })
        logger.debug(f"Extracted geo-tags: {tags}")
        info_logger.info(f"Extracted geo-tags: {tags}")
        return tags
    def __init__(self):
        self.stop_words = set(nltk.corpus.stopwords.words('english'))
        # Add common news-specific stop words
        self.stop_words.update(['said', 'would', 'could', 'also', 'one', 'two', 'three', 'first', 'second', 'new'])

    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis"""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Remove special characters and digits (keep basic punctuation for sentence splitting)
        text = re.sub(r'[^a-zA-Z\s\.\!\?\-]', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def tokenize_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        try:
            return nltk.sent_tokenize(text)
        except:
            # Fallback: simple sentence splitting
            return re.split(r'[.!?]+', text)

    def tokenize_words(self, text: str) -> List[str]:
        """Split text into words"""
        try:
            return nltk.word_tokenize(text)
        except:
            # Fallback: simple word splitting
            return text.split()

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[Tuple[str, int]]:
        """Extract important keywords from text"""
        preprocessed = self.preprocess_text(text)
        words = self.tokenize_words(preprocessed)

        # Filter out stop words and short words
        filtered_words = [
            word for word in words
            if word not in self.stop_words and len(word) > 2
        ]

        # Count word frequencies
        word_freq = Counter(filtered_words)

        # Return most common keywords with their frequencies
        return word_freq.most_common(max_keywords)

    def calculate_readability(self, text: str) -> Dict[str, float]:
        """Calculate basic readability metrics"""
        sentences = self.tokenize_sentences(text)
        words = self.tokenize_words(text)

        if not sentences or not words:
            return {'flesch_score': 0.0, 'avg_words_per_sentence': 0.0}

        # Average words per sentence
        avg_words_per_sentence = len(words) / len(sentences)

        # Simplified Flesch Reading Ease score
        # Formula: 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
        # Using approximation without syllable counting
        flesch_score = max(0, 206.835 - 1.015 * avg_words_per_sentence)

        return {
            'flesch_score': flesch_score,
            'avg_words_per_sentence': avg_words_per_sentence,
            'sentence_count': len(sentences),
            'word_count': len(words)
        }

    def generate_summary(self, text: str, max_sentences: int = 3, method: str = 'extractive') -> str:
        """Generate a summary of the text"""
        if method == 'extractive':
            return self._extractive_summary(text, max_sentences)
        elif method == 'abstractive':
            # Placeholder for abstractive summarization
            return self._extractive_summary(text, max_sentences)
        else:
            return self._extractive_summary(text, max_sentences)

    def _extractive_summary(self, text: str, max_sentences: int = 3) -> str:
        """Generate extractive summary using sentence scoring"""
        preprocessed = self.preprocess_text(text)
        sentences = self.tokenize_sentences(preprocessed)

        if len(sentences) <= max_sentences:
            return text

        # Score sentences based on word frequency
        word_freq = self._calculate_word_frequencies(preprocessed)
        sentence_scores = self._score_sentences(sentences, word_freq)

        # Select top sentences
        top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:max_sentences]
        top_sentences.sort(key=lambda x: sentences.index(x[0]))  # Maintain original order

        summary = ' '.join([sentence for sentence, score in top_sentences])
        return summary

    def _calculate_word_frequencies(self, text: str) -> Dict[str, float]:
        """Calculate word frequencies for scoring"""
        words = self.tokenize_words(text)
        filtered_words = [word for word in words if word not in self.stop_words and len(word) > 2]

        word_freq = Counter(filtered_words)
        max_freq = max(word_freq.values()) if word_freq else 1

        # Normalize frequencies
        return {word: freq / max_freq for word, freq in word_freq.items()}

    def _score_sentences(self, sentences: List[str], word_freq: Dict[str, float]) -> Dict[str, float]:
        """Score sentences based on word importance"""
        sentence_scores = {}

        for sentence in sentences:
            words = self.tokenize_words(sentence.lower())
            score = sum(word_freq.get(word, 0) for word in words if word not in self.stop_words)
            sentence_scores[sentence] = score

        return sentence_scores

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Basic sentiment analysis (placeholder - would need proper sentiment lexicon)"""
        # This is a simplified implementation
        # In a real application, you'd use a proper sentiment analysis library

        positive_words = {'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'best', 'love'}
        negative_words = {'bad', 'terrible', 'awful', 'horrible', 'worst', 'hate', 'disappointing', 'poor'}

        words = self.tokenize_words(self.preprocess_text(text))
        word_set = set(words)

        positive_count = len(word_set.intersection(positive_words))
        negative_count = len(word_set.intersection(negative_words))

        total_sentiment_words = positive_count + negative_count

        if total_sentiment_words == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (positive_count - negative_count) / total_sentiment_words

        # Normalize to -1 to 1 range
        sentiment_score = max(-1.0, min(1.0, sentiment_score))

        return {
            'sentiment_score': sentiment_score,
            'positive_words': positive_count,
            'negative_words': negative_count,
            'classification': 'positive' if sentiment_score > 0.1 else 'negative' if sentiment_score < -0.1 else 'neutral'
        }

    def get_text_stats(self, text: str) -> Dict[str, any]:
        """Get comprehensive text statistics"""
        preprocessed = self.preprocess_text(text)
        sentences = self.tokenize_sentences(preprocessed)
        words = self.tokenize_words(preprocessed)

        return {
            'char_count': len(text),
            'word_count': len(words),
            'sentence_count': len(sentences),
            'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
            'avg_sentence_length': len(words) / len(sentences) if sentences else 0,
            'keywords': self.extract_keywords(text, 5),
            'readability': self.calculate_readability(text),
            'sentiment': self.analyze_sentiment(text)
        }

    def improve_summary(self, original_summary: str, full_text: str) -> str:
        """Improve an existing summary by adding context or key points"""
        # Extract keywords from full text
        keywords = self.extract_keywords(full_text, 3)
        keyword_list = [kw[0] for kw in keywords]

        # If summary doesn't contain important keywords, add them
        summary_words = set(self.tokenize_words(original_summary.lower()))
        missing_keywords = [kw for kw in keyword_list if kw.lower() not in summary_words]

        if missing_keywords and len(original_summary.split()) < 50:
            # Add missing keywords to the end
            improved = original_summary.rstrip('.')
            improved += f" Key topics include: {', '.join(missing_keywords)}."
            return improved

        return original_summary