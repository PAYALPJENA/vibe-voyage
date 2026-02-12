"""
RAG Engine for Find My Vibe
Improvements applied:
- Lazy-load embedding model
- Store normalized embeddings as float32 bytes
- Read embeddings from DB instead of re-encoding descriptions
- Use context managers for DB access and enable WAL for concurrency
- Add indexes, logging, and type hints
"""

import os
import sqlite3
import logging
from typing import List, Tuple, Optional, Dict, Any

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # tests or environments may not have this

# ==============================
# 🧠 RAG SETUP
# ==============================

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "places_cache.db")

# Lazy-loaded embedding model
_embedding_model = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_embedding_model():
    """Lazily load and return the embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        if SentenceTransformer is None:
            raise RuntimeError("SentenceTransformer not available in this environment")
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def _normalize_vector(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float32)
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def get_embedding(text: str) -> np.ndarray:
    """Return a normalized embedding (float32) for input text."""
    model = get_embedding_model()
    emb = model.encode(text, convert_to_numpy=True)
    return _normalize_vector(np.asarray(emb, dtype=np.float32))


def get_embeddings(texts: List[str]) -> np.ndarray:
    """Batch embedding support."""
    model = get_embedding_model()
    arr = model.encode(texts, convert_to_numpy=True)
    arr = np.asarray(arr, dtype=np.float32)
    # normalize rows
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def init_db() -> None:
    """Initialize SQLite database and indexes, enabling WAL for concurrency."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS cached_places (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                latitude REAL,
                longitude REAL,
                rating REAL,
                reviews INTEGER,
                category TEXT,
                vibe_embedding BLOB,
                vibe_keywords TEXT
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                place_name TEXT,
                vibe TEXT,
                user_rating INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                location TEXT,
                FOREIGN KEY(place_name) REFERENCES cached_places(name)
            )
            """
        )

        # Indexes for performance
        c.execute("CREATE INDEX IF NOT EXISTS idx_cached_places_name ON cached_places(name);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cached_places_category ON cached_places(category);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_place ON feedback(place_name);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_vibe ON feedback(vibe);")
        # Wishlist table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY,
                place_name TEXT UNIQUE,
                place_data TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()


def _blob_to_embedding(blob: Optional[bytes]) -> Optional[np.ndarray]:
    if not blob:
        return None
    try:
        arr = np.frombuffer(blob, dtype=np.float32)
        if arr.size == 0:
            return None
        return _normalize_vector(arr)
    except Exception:
        logger.exception("Failed to load embedding from blob")
        return None


def add_wishlist_item(place_name: str, place_data: Dict[str, Any]) -> bool:
    """Add a place to the wishlist (stored as JSON text)."""
    try:
        import json as _json
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO wishlist (place_name, place_data) VALUES (?, ?)",
                (place_name, _json.dumps(place_data)),
            )
            conn.commit()
        return True
    except Exception:
        logger.exception("Add wishlist error")
        return False


def remove_wishlist_item(place_name: str) -> bool:
    """Remove a place from the wishlist by name."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM wishlist WHERE place_name = ?", (place_name,))
            conn.commit()
        return True
    except Exception:
        logger.exception("Remove wishlist error")
        return False


def get_wishlist() -> List[Dict[str, Any]]:
    """Return all wishlist items as a list of dicts."""
    try:
        import json as _json
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT place_name, place_data, added_at FROM wishlist ORDER BY added_at DESC")
            rows = c.fetchall()

        out = []
        for r in rows:
            try:
                data = _json.loads(r['place_data'])
            except Exception:
                data = {}
            out.append({
                'place_name': r['place_name'],
                'place_data': data,
                'added_at': r['added_at']
            })
        return out
    except Exception:
        logger.exception("Get wishlist error")
        return []


def get_top_places_for_vibe(vibe: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get top places for a vibe based on feedback and rating."""
    try:
        pattern = f"%{vibe}%"
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                """
                SELECT cp.name, cp.description, cp.latitude, cp.longitude, cp.rating, cp.reviews, AVG(f.user_rating) as avg_vibe_rating, COUNT(f.user_rating) as vibe_count
                FROM cached_places cp
                JOIN feedback f ON cp.name = f.place_name
                WHERE f.vibe LIKE ?
                GROUP BY cp.name
                ORDER BY avg_vibe_rating DESC, vibe_count DESC
                LIMIT ?
                """,
                (pattern, limit),
            )
            rows = c.fetchall()

        out = []
        for r in rows:
            out.append({
                'name': r['name'],
                'description': r['description'],
                'latitude': r['latitude'],
                'longitude': r['longitude'],
                'rating': r['rating'],
                'reviews': r['reviews'],
                'avg_vibe_rating': float(r['avg_vibe_rating']) if r['avg_vibe_rating'] is not None else 0.0,
                'vibe_count': int(r['vibe_count'])
            })
        return out
    except Exception:
        logger.exception("get_top_places_for_vibe error")
        return []


def cache_place(place_data: Dict[str, Any], vibe_keywords: str) -> None:
    """Cache a place in the database.

    Embedding is normalized and stored as float32 bytes.
    """
    try:
        emb = get_embedding(place_data.get('description', '') + ' ' + (vibe_keywords or ''))
        blob = emb.tobytes()
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT OR IGNORE INTO cached_places 
                (name, description, latitude, longitude, rating, reviews, category, vibe_embedding, vibe_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    place_data.get('name'),
                    place_data.get('description'),
                    place_data.get('latitude'),
                    place_data.get('longitude'),
                    place_data.get('rating'),
                    place_data.get('reviews'),
                    place_data.get('category'),
                    sqlite3.Binary(blob),
                    vibe_keywords,
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("Cache error")


def retrieve_similar_places(vibe_query: str, limit: int = 5) -> List[Tuple[float, str, str, str]]:
    """Retrieve similar places from cache using stored embeddings and feedback weighting."""
    try:
        q_emb = get_embedding(vibe_query)
        rows = []
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT name, description, category, vibe_keywords, vibe_embedding FROM cached_places LIMIT 1000")
            rows = c.fetchall()

        if not rows:
            return []

        similarities = []

        # Batch fetch feedback stats for all candidates to reduce DB roundtrips
        names = [r['name'] for r in rows]
        stats_map = get_feedback_stats_for_places(names)

        for r in rows:
            name = r['name']
            desc = r['description']
            category = r['category']
            emb_blob = r['vibe_embedding']

            stored_emb = _blob_to_embedding(emb_blob)
            if stored_emb is None:
                continue

            sim = float(np.dot(q_emb, stored_emb))

            feedback_stats = stats_map.get(name)
            feedback_weight = 1.0
            if feedback_stats:
                feedback_quality = float(feedback_stats['avg_rating']) / 5.0
                feedback_count_weight = min(feedback_stats['count'] / 10.0, 1.0)
                feedback_weight = (feedback_quality * 0.6) + (feedback_count_weight * 0.4)

            weighted_similarity = sim * (0.7 + (feedback_weight * 0.3))
            similarities.append((weighted_similarity, name, desc, category))

        similarities.sort(reverse=True, key=lambda x: x[0])
        return similarities[:limit]
    except Exception:
        logger.exception("Retrieval error")
        return []


# ==============================
# 📊 FEEDBACK FUNCTIONS
# ==============================


def save_feedback(place_name: str, vibe: str, user_rating: int, location: Optional[str]) -> bool:
    """Save user feedback for a place."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO feedback (place_name, vibe, user_rating, location) VALUES (?, ?, ?, ?)",
                (place_name, vibe, int(user_rating), location),
            )
            conn.commit()
        return True
    except Exception:
        logger.exception("Feedback save error")
        return False


def get_place_feedback_stats(place_name: str) -> Optional[Dict[str, Any]]:
    """Get feedback statistics for a place."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT AVG(user_rating) as avg_rating, COUNT(*) as count, MIN(user_rating) as min_rating, MAX(user_rating) as max_rating FROM feedback WHERE place_name = ?",
                (place_name,),
            )
            result = c.fetchone()

        if result and result[1] > 0:
            return {
                "avg_rating": float(result[0]) if result[0] is not None else 0.0,
                "count": int(result[1]),
                "min_rating": int(result[2]) if result[2] is not None else None,
                "max_rating": int(result[3]) if result[3] is not None else None,
            }
        return None
    except Exception:
        logger.exception("Feedback stats error")
        return None


def get_vibe_place_rating(place_name: str, vibe: str) -> Tuple[float, int]:
    """Get average rating and count for a specific place-vibe combination."""
    try:
        pattern = f"%{vibe}%"
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT AVG(user_rating) as avg_rating, COUNT(*) as count FROM feedback WHERE place_name = ? AND vibe LIKE ?",
                (place_name, pattern),
            )
            result = c.fetchone()

        if result and result[1] > 0:
            return float(result[0]) if result[0] is not None else 0.0, int(result[1])
        return 0.0, 0
    except Exception:
        logger.exception("Vibe-place rating error")
        return 0.0, 0


def get_recommendation_confidence(results: List[Dict[str, Any]], vibe: str, location: Optional[str]) -> List[Dict[str, Any]]:
    """Calculate confidence score based on feedback history"""
    # Batch fetch stats to avoid repeated DB queries
    names = [p['name'] for p in results]
    stats_map = get_feedback_stats_for_places(names)

    for place in results:
        name = place['name']
        stats = stats_map.get(name)
        vibe_rating, vibe_count = get_vibe_place_rating(name, vibe)

        if stats:
            feedback_confidence = min(stats['count'] / 10.0, 1.0)
            feedback_quality = float(stats['avg_rating']) / 5.0
            place['feedback_confidence'] = round((feedback_confidence + feedback_quality) / 2.0, 2)
            place['feedback_avg_rating'] = round(float(stats['avg_rating']), 2)
            place['feedback_count'] = int(stats['count'])
        else:
            place['feedback_confidence'] = 0.0
            place['feedback_avg_rating'] = 0.0
            place['feedback_count'] = 0

        if vibe_count > 0:
            place['vibe_specific_rating'] = round(float(vibe_rating), 2)

    return results


def get_feedback_stats_for_places(names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Batch fetch feedback stats for a list of place names.

    Returns a mapping name -> stats dict.
    """
    if not names:
        return {}
    try:
        placeholders = ','.join('?' for _ in names)
        query = f"SELECT place_name, AVG(user_rating) as avg_rating, COUNT(*) as count FROM feedback WHERE place_name IN ({placeholders}) GROUP BY place_name"
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(query, tuple(names))
            rows = c.fetchall()

        stats_map: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            pname = row[0]
            stats_map[pname] = {
                'avg_rating': float(row[1]) if row[1] is not None else 0.0,
                'count': int(row[2])
            }
        return stats_map
    except Exception:
        logger.exception("Batch feedback stats error")
        return {}


# ==============================
# 🧠 FEEDBACK-BASED LEARNING
# ==============================


def filter_negative_feedback(places: List[Dict[str, Any]], vibe: str, threshold: float = 2.5) -> List[Dict[str, Any]]:
    """Filter out places with low ratings for similar vibes (negative feedback filtering)."""
    filtered = []
    for place in places:
        vibe_rating, vibe_count = get_vibe_place_rating(place['name'], vibe)
        if vibe_count >= 2:
            if vibe_rating < threshold:
                logger.info("Filtering %s: low vibe rating %.2f for vibe '%s'", place['name'], vibe_rating, vibe)
                continue
        filtered.append(place)
    return filtered


def get_vibe_place_associations(vibe: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Learn which place types work best for a specific vibe (vibe-place learning)."""
    try:
        # simple validation
        if not vibe:
            return []
        pattern = f"%{vibe}%"
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                """
                SELECT cp.name, cp.category, AVG(f.user_rating) as avg_rating, COUNT(f.user_rating) as count
                FROM cached_places cp
                JOIN feedback f ON cp.name = f.place_name
                WHERE f.vibe LIKE ?
                GROUP BY cp.category
                ORDER BY avg_rating DESC, count DESC
                LIMIT ?
                """,
                (pattern, limit),
            )
            results = c.fetchall()

        associations = []
        for row in results:
            associations.append({
                "place": row['name'],
                "category": row['category'],
                "avg_rating": round(float(row['avg_rating']), 2),
                "feedback_count": int(row['count']),
            })
        return associations
    except Exception:
        logger.exception("Vibe-place association error")
        return []


def rank_by_feedback(results: List[Dict[str, Any]], vibe: str, location: Optional[str]) -> List[Dict[str, Any]]:
    """Dynamic re-ranking: Use feedback scores to re-weight and sort places."""
    # Batch feedback stats
    names = [p['name'] for p in results]
    stats_map = get_feedback_stats_for_places(names)

    for place in results:
        name = place['name']
        stats = stats_map.get(name)
        vibe_rating, vibe_count = get_vibe_place_rating(name, vibe)
        base_rating = float(place.get('rating', 0.0)) / 5.0

        if stats and stats['count'] > 0:
            if vibe_count > 0:
                vibe_performance = (float(vibe_rating) / 5.0) * 0.6
            else:
                vibe_performance = (float(stats['avg_rating']) / 5.0) * 0.3

            review_confidence = min(stats['count'] / 15.0, 1.0)

            place['feedback_rank_score'] = round(
                (base_rating * 0.5) + (vibe_performance * 0.4) + (review_confidence * 0.1), 2
            )
        else:
            place['feedback_rank_score'] = round(base_rating, 2)

    return results


# Initialize database on module load
init_db()
