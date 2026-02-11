"""
RAG Engine for Find My Vibe
Handles embeddings, caching, retrieval, and feedback-based learning
"""

import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer

# ==============================
# 🧠 RAG SETUP
# ==============================

DB_PATH = "places_cache.db"
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


def init_db():
    """Initialize SQLite database for caching places"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
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
    """)
    
    # ==============================
    # 📊 FEEDBACK TABLE
    # ==============================
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY,
            place_name TEXT,
            vibe TEXT,
            user_rating INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            location TEXT,
            FOREIGN KEY(place_name) REFERENCES cached_places(name)
        )
    """)
    
    conn.commit()
    conn.close()


def get_embedding(text):
    """Generate embedding for text"""
    return embedding_model.encode(text, convert_to_numpy=True)


def cache_place(place_data, vibe_keywords):
    """Cache a place in the database"""
    try:
        embedding = get_embedding(place_data['description'] + " " + vibe_keywords)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO cached_places 
            (name, description, latitude, longitude, rating, reviews, category, vibe_embedding, vibe_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            place_data['name'],
            place_data['description'],
            place_data['latitude'],
            place_data['longitude'],
            place_data['rating'],
            place_data['reviews'],
            place_data['category'],
            embedding.tobytes(),
            vibe_keywords
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Cache error: {e}")


def retrieve_similar_places(vibe_query, limit=5):
    """Retrieve similar places from cache using embeddings + feedback weighting"""
    try:
        query_embedding = get_embedding(vibe_query)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name, description, category, vibe_keywords FROM cached_places LIMIT 100")
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return []
        
        similarities = []
        for name, desc, category, keywords in rows:
            stored_embedding = embedding_model.encode(desc + " " + keywords, convert_to_numpy=True)
            similarity = np.dot(query_embedding, stored_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding) + 1e-8)
            
            # 📊 Get feedback score for this place
            feedback_stats = get_place_feedback_stats(name)
            feedback_weight = 1.0
            
            if feedback_stats:
                # Weight by feedback quality: avg_rating / 5.0 gives 0-1 score
                feedback_quality = feedback_stats['avg_rating'] / 5.0
                # Weight by feedback count: more reviews = higher confidence
                feedback_count_weight = min(feedback_stats['count'] / 10.0, 1.0)
                # Combined feedback weight: prioritize highly-rated places with multiple reviews
                feedback_weight = (feedback_quality * 0.6) + (feedback_count_weight * 0.4)
            
            # Combine semantic similarity with feedback weight
            weighted_similarity = similarity * (0.7 + (feedback_weight * 0.3))
            
            similarities.append((weighted_similarity, name, desc, category, feedback_weight))
        
        similarities.sort(reverse=True, key=lambda x: x[0])
        # Return without feedback_weight - keep format compatible
        return [(sim, name, desc, cat) for sim, name, desc, cat, _ in similarities[:limit]]
    except Exception as e:
        print(f"Retrieval error: {e}")
        return []


# ==============================
# 📊 FEEDBACK FUNCTIONS
# ==============================

def save_feedback(place_name, vibe, user_rating, location):
    """Save user feedback for a place"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO feedback (place_name, vibe, user_rating, location)
            VALUES (?, ?, ?, ?)
        """, (place_name, vibe, user_rating, location))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Feedback save error: {e}")
        return False


def get_place_feedback_stats(place_name):
    """Get feedback statistics for a place"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT AVG(user_rating) as avg_rating, COUNT(*) as count, 
                   MIN(user_rating) as min_rating, MAX(user_rating) as max_rating
            FROM feedback WHERE place_name = ?
        """, (place_name,))
        result = c.fetchone()
        conn.close()
        
        if result and result[1] > 0:
            return {
                "avg_rating": result[0],
                "count": result[1],
                "min_rating": result[2],
                "max_rating": result[3]
            }
        return None
    except Exception as e:
        print(f"Feedback stats error: {e}")
        return None


def get_vibe_place_rating(place_name, vibe):
    """Get average rating for a specific place-vibe combination"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT AVG(user_rating) as avg_rating, COUNT(*) as count
            FROM feedback WHERE place_name = ? AND vibe LIKE ?
        """, (place_name, f"%{vibe}%"))
        result = c.fetchone()
        conn.close()
        
        if result and result[1] > 0:
            return result[0], result[1]  # avg_rating, count
        return 0, 0
    except Exception as e:
        print(f"Vibe-place rating error: {e}")
        return 0, 0


def get_recommendation_confidence(results, vibe, location):
    """Calculate confidence score based on feedback history"""
    for place in results:
        stats = get_place_feedback_stats(place['name'])
        vibe_rating, vibe_count = get_vibe_place_rating(place['name'], vibe)
        
        # Confidence based on: feedback count + feedback ratings quality
        if stats:
            feedback_confidence = min(stats['count'] / 10, 1.0)  # 0-1, capped at 10 reviews
            feedback_quality = stats['avg_rating'] / 5.0  # 0-1, normalized to 5-star scale
            place['feedback_confidence'] = round((feedback_confidence + feedback_quality) / 2, 2)
            place['feedback_avg_rating'] = round(stats['avg_rating'], 2)
            place['feedback_count'] = stats['count']
        else:
            place['feedback_confidence'] = 0
            place['feedback_avg_rating'] = 0
            place['feedback_count'] = 0
        
        if vibe_count > 0:
            place['vibe_specific_rating'] = round(vibe_rating, 2)
    
    return results


# ==============================
# 🧠 FEEDBACK-BASED LEARNING
# ==============================

def filter_negative_feedback(places, vibe, threshold=2.5):
    """Filter out places with low ratings for similar vibes (negative feedback filtering)"""
    filtered = []
    for place in places:
        _, vibe_count = get_vibe_place_rating(place['name'], vibe)
        
        # Only filter if we have significant vibe-specific feedback
        if vibe_count >= 2:  # At least 2 ratings for this specific vibe
            vibe_rating, _ = get_vibe_place_rating(place['name'], vibe)
            if vibe_rating < threshold:
                print(f"⚠️ Filtering {place['name']}: low vibe rating {vibe_rating:.2f} for vibe '{vibe}'")
                continue
        
        filtered.append(place)
    
    return filtered


def get_vibe_place_associations(vibe, limit=5):
    """Learn which place types work best for a specific vibe (vibe-place learning)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get all places rated for this vibe
        c.execute("""
            SELECT cp.name, cp.category, AVG(f.user_rating) as avg_rating, COUNT(f.user_rating) as count
            FROM cached_places cp
            JOIN feedback f ON cp.name = f.place_name
            WHERE f.vibe LIKE ?
            GROUP BY cp.category
            ORDER BY avg_rating DESC, count DESC
            LIMIT ?
        """, (f"%{vibe}%", limit))
        
        results = c.fetchall()
        conn.close()
        
        if results:
            associations = []
            for name, category, avg_rating, count in results:
                associations.append({
                    "place": name,
                    "category": category,
                    "avg_rating": round(avg_rating, 2),
                    "feedback_count": count
                })
            return associations
        return []
    except Exception as e:
        print(f"Vibe-place association error: {e}")
        return []


def rank_by_feedback(results, vibe, location):
    """
    Dynamic re-ranking: Use feedback scores to re-weight and sort places
    Combines: vibe similarity + feedback quality + vibe-specific performance
    """
    for place in results:
        stats = get_place_feedback_stats(place['name'])
        vibe_rating, vibe_count = get_vibe_place_rating(place['name'], vibe)
        
        # Calculate feedback-based ranking score
        base_rating = place.get('rating', 0) / 5.0  # Google rating normalized
        
        if stats and stats['count'] > 0:
            # Higher weight to vibe-specific performance
            if vibe_count > 0:
                vibe_performance = (vibe_rating / 5.0) * 0.6
            else:
                vibe_performance = (stats['avg_rating'] / 5.0) * 0.3
            
            # Account for review volume
            review_confidence = min(stats['count'] / 15.0, 1.0)
            
            # Combined score: 50% google rating + 50% user feedback adjusted by volume
            place['feedback_rank_score'] = round(
                (base_rating * 0.5) + 
                (vibe_performance * 0.4) + 
                (review_confidence * 0.1),
                2
            )
        else:
            # No feedback yet - use only Google rating
            place['feedback_rank_score'] = round(base_rating, 2)
    
    return results


# Initialize database on module load
init_db()
