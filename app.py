from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import json
import sqlite3
import numpy as np
import os

# Import RAG functions
from rag_engine import (
    init_db, get_embedding, cache_place, retrieve_similar_places,
    save_feedback, get_place_feedback_stats, get_vibe_place_rating,
    get_recommendation_confidence, filter_negative_feedback,
    get_vibe_place_associations, rank_by_feedback, DB_PATH,
    add_wishlist_item, remove_wishlist_item, get_wishlist, get_top_places_for_vibe
)

app = Flask(__name__)
CORS(app)



# ==============================
# 🔑 CONFIG
# ==============================

GEMINI_API_KEY = "AIzaSyCRPz03CMRzRA36eVpvAAdWmiBSLNDkiZE"
GOOGLE_API_KEY = "AIzaSyCB8ugDH0XlhxJaud08gZepoYpkfvucTBI"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
GEMINI_MODEL = "gemini-1.5-pro"

# ==============================
# 🎭 EMOTION → PLACE TYPE MAPPING
# ==============================

EMOTION_PLACE_MAPPING = {
    # Nature & Exploration
    "nature": {
        "place_types": ["natural_feature", "park", "hiking_trail"],
        "keywords": ["scenic", "outdoor", "nature", "landscape"],
        "best_time": "Daytime"
    },
    "forest": {
        "place_types": ["natural_feature", "park"],
        "keywords": ["nature", "green", "peaceful", "scenic"],
        "best_time": "Morning"
    },
    "trekking": {
        "place_types": ["natural_feature", "park", "tourist_attraction"],
        "keywords": ["hiking", "trekking", "trails", "mountains", "scenic", "outdoor", "adventure"],
        "best_time": "Early Morning or Afternoon"
    },
    "hiking": {
        "place_types": ["natural_feature", "park", "tourist_attraction"],
        "keywords": ["trails", "mountains", "outdoor", "scenic", "hiking", "landscape"],
        "best_time": "Morning"
    },
    "mountaineering": {
        "place_types": ["natural_feature", "park", "tourist_attraction"],
        "keywords": ["mountains", "peaks", "trekking", "altitude", "adventure", "challenging"],
        "best_time": "Early Morning"
    },
    "adventure": {
        "place_types": ["natural_feature", "park", "tourist_attraction", "sports_complex"],
        "keywords": ["adventure", "thrilling", "outdoor", "trekking", "activity", "exploration"],
        "best_time": "Daytime"
    },
    "outdoor": {
        "place_types": ["natural_feature", "park", "tourist_attraction"],
        "keywords": ["outdoor", "nature", "scenic", "hiking", "fresh air"],
        "best_time": "Daytime"
    },
    "dark academia": {
        "place_types": ["library", "museum", "university"],
        "keywords": ["historical", "academic", "intellectual", "quiet"],
        "best_time": "Afternoon"
    },
    "urban": {
        "place_types": ["restaurant", "shopping_mall", "tourist_attraction"],
        "keywords": ["city", "vibrant", "modern", "busy"],
        "best_time": "Evening"
    },
    "mysterious": {
        "place_types": ["museum", "park", "library"],
        "keywords": ["intriguing", "hidden", "unique", "artistic"],
        "best_time": "Evening"
    },
    "cozy": {
        "place_types": ["cafe", "restaurant", "park"],
        "keywords": ["warm", "comfortable", "intimate", "relaxing"],
        "best_time": "Evening"
    },
    
    # Spiritual & Peaceful
    "spiritual": {
        "place_types": ["place_of_worship", "park", "natural_feature"],
        "keywords": ["temple", "meditation", "sacred", "peaceful", "nature"],
        "best_time": "Early Morning or Evening"
    },
    "peaceful": {
        "place_types": ["park", "garden", "natural_feature"],
        "keywords": ["quiet", "serene", "nature", "calm", "relaxing"],
        "best_time": "Morning or Evening"
    },
    "meditative": {
        "place_types": ["place_of_worship", "park", "library"],
        "keywords": ["quiet", "contemplative", "nature", "spiritual"],
        "best_time": "Early Morning"
    },
    
    # Happy & Excited
    "happy": {
        "place_types": ["amusement_park", "restaurant", "bar"],
        "keywords": ["fun", "lively", "celebration", "music", "social"],
        "best_time": "Evening or Night"
    },
    "excited": {
        "place_types": ["amusement_park", "night_club", "restaurant"],
        "keywords": ["adventure", "thrilling", "energetic", "lively"],
        "best_time": "Evening or Night"
    },
    "joyful": {
        "place_types": ["park", "restaurant", "amusement_park"],
        "keywords": ["colorful", "vibrant", "celebration", "fun"],
        "best_time": "Daytime"
    },
    
    # Sad & Melancholic
    "sad": {
        "place_types": ["park", "cafe", "place_of_worship"],
        "keywords": ["quiet", "reflective", "nature", "peaceful", "therapeutic"],
        "best_time": "Afternoon or Evening"
    },
    "melancholic": {
        "place_types": ["park", "library", "museum"],
        "keywords": ["artistic", "thoughtful", "quiet", "introspective"],
        "best_time": "Afternoon"
    },
    "lonely": {
        "place_types": ["cafe", "restaurant", "bar"],
        "keywords": ["social", "community", "warm", "friendly", "people"],
        "best_time": "Evening"
    },
    
    # Energetic & Active
    "energetic": {
        "place_types": ["gym", "sports_complex", "park", "dance class"],
        "keywords": ["active", "athletic", "outdoor", "fitness"],
        "best_time": "Morning or Evening"
    },
    "adventurous": {
        "place_types": ["park", "natural_feature", "tourist_attraction"],
        "keywords": ["hiking", "outdoor", "exploration", "nature"],
        "best_time": "Daytime"
    },
    "playful": {
        "place_types": ["amusement_park", "park", "recreational_area"],
        "keywords": ["fun", "games", "entertainment", "lighthearted"],
        "best_time": "Daytime"
    },
    
    # Romantic & Intimate
    "romantic": {
        "place_types": ["restaurant", "park", "tourist_attraction"],
        "keywords": ["intimate", "scenic", "candlelight", "peaceful"],
        "best_time": "Evening"
    },
    "intimate": {
        "place_types": ["restaurant", "cafe", "park"],
        "keywords": ["cozy", "quiet", "romantic", "private"],
        "best_time": "Evening"
    },
    
    # Contemplative & Thoughtful
    "contemplative": {
        "place_types": ["library", "museum", "park"],
        "keywords": ["quiet", "thoughtful", "artistic", "inspiring"],
        "best_time": "Afternoon"
    },
    "confused": {
        "place_types": ["park", "cafe", "place_of_worship"],
        "keywords": ["therapeutic", "peaceful", "clarity", "nature"],
        "best_time": "Morning or Afternoon"
    },
    "anxious": {
        "place_types": ["park", "spa", "garden"],
        "keywords": ["calming", "peaceful", "therapeutic", "nature"],
        "best_time": "Morning"
    },
    
    # Motivated & Focused
    "motivated": {
        "place_types": ["cafe", "library", "park"],
        "keywords": ["inspiring", "productive", "energizing", "focused"],
        "best_time": "Morning or Afternoon"
    },
    "creative": {
        "place_types": ["museum", "cafe", "park"],
        "keywords": ["artistic", "inspiring", "unique", "creative"],
        "best_time": "Afternoon"
    },
    
    # Nostalgic
    "nostalgic": {
        "place_types": ["museum", "park", "tourist_attraction"],
        "keywords": ["historical", "cultural", "heritage", "memories"],
        "best_time": "Afternoon"
    },
    "retro": {
        "place_types": ["museum", "cafe", "restaurant"],
        "keywords": ["vintage", "old-fashioned", "nostalgic", "classic"],
        "best_time": "Afternoon"
    },
    "vintage": {
        "place_types": ["museum", "cafe", "antique_market"],
        "keywords": ["old", "classic", "heritage", "traditional"],
        "best_time": "Afternoon"
    },
    "bohemian": {
        "place_types": ["cafe", "park", "museum"],
        "keywords": ["artistic", "eclectic", "creative", "alternative"],
        "best_time": "Afternoon or Evening"
    },
    "minimalist": {
        "place_types": ["museum", "park", "cafe"],
        "keywords": ["simple", "clean", "modern", "zen"],
        "best_time": "Afternoon"
    },
    "aesthetic": {
        "place_types": ["cafe", "museum", "park"],
        "keywords": ["beautiful", "photogenic", "artistic", "visually pleasing"],
        "best_time": "Golden Hour"
    },
    "dreamy": {
        "place_types": ["park", "cafe", "library"],
        "keywords": ["peaceful", "imaginative", "whimsical", "serene"],
        "best_time": "Sunset or Evening"
    },
    "moody": {
        "place_types": ["cafe", "library", "park"],
        "keywords": ["atmospheric", "contemplative", "artistic", "introspective"],
        "best_time": "Evening"
    }
}

def get_emotion_intent(vibe, age="", personality=""):
    """
    Map emotion/vibe to place types and keywords.
    Uses predefined mapping as primary source with Groq as enhancement.
    """
    vibe_lower = vibe.lower().strip()
    
    # Check if exact emotion exists in mapping
    if vibe_lower in EMOTION_PLACE_MAPPING:
        return EMOTION_PLACE_MAPPING[vibe_lower]
    
    # Check for partial matches (e.g., "i feel sad" → "sad")
    for emotion, mapping in EMOTION_PLACE_MAPPING.items():
        if emotion in vibe_lower:
            return mapping
    
    # Fallback: use Groq to interpret unknown emotion
    return None

# ==============================
# 🧭 ROUTES
# ==============================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/vibe")
def vibe():
    return render_template("vibe.html")

@app.route("/results")
def results():
    return render_template("results.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/passport")
def passport():
    return render_template("passport.html")

# ==============================
# 🌍 GEOCODING (BUG 2 FIXED)
# ==============================

def geocode_city(city):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": city,
        "key": GOOGLE_API_KEY,
        "region": "in",
        "components": "country:IN"
    }

    res = requests.get(url, params=params).json()

    if res.get("status") != "OK" or not res.get("results"):
        return None, None

    best = res["results"][0]

    # Accept the result only if it represents a locality/administrative area
    # This helps avoid accepting person names or ambiguous entity matches
    accepted_types = set([
        "locality",
        "postal_town",
        "sublocality",
        "neighborhood",
        "administrative_area_level_1",
        "administrative_area_level_2",
        "administrative_area_level_3",
        "country"
    ])

    result_types = set(best.get("types", []))
    if not (result_types & accepted_types):
        return None, None

    loc = best["geometry"]["location"]
    return loc["lat"], loc["lng"]

# ==============================
# 🏙️ GOOGLE PLACES SEARCH
# ==============================

def search_places(lat, lng, place_type, keyword, radius=12000):
    """Search nearby places with configurable radius (meters)."""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": int(radius),
        "type": place_type,
        "keyword": keyword,
        "key": GOOGLE_API_KEY
    }
    return requests.get(url, params=params).json()

# ==============================
# 📝 DESCRIPTION
# ==============================

def make_description(place, place_type):
    rating = place.get("rating", 0)
    reviews = place.get("user_ratings_total", 0)

    base = f"A well-known {place_type.replace('_', ' ')}"

    if rating >= 4.5 and reviews > 500:
        return base + " that is highly rated and loved by visitors."
    elif rating >= 4.0:
        return base + " with a good reputation among locals."
    else:
        return base + " offering a calm experience."

# ==============================
# 🤖 MAIN API
# ==============================

@app.route("/api/recommend", methods=["POST"])
def recommend():
    data = request.json

    vibe = data.get("vibe", "")
    location = data.get("location", "")
    age = data.get("age", "")
    personality = data.get("personality", "")
    # Optional personalization inputs from frontend
    coords = data.get("coords")           # {"lat":.., "lng":..}
    radius = data.get("radius")          # meters
    max_results = data.get("max_results")
    category_override = data.get("category_override")  # string or None

    # ---------- EMOTION MAPPING (PRIMARY SOURCE) ----------
    intent = get_emotion_intent(vibe, age, personality)
    
    if intent is not None:
        # ✅ Found emotion in mapping - use it directly
        print(f"✅ Using emotion mapping for: {vibe}")
        place_types = intent.get("place_types", [])
        keywords = intent.get("keywords", ["peaceful"])
        best_time = intent.get("best_time", "Day")
    else:
        # ---------- RAG: RETRIEVE SIMILAR PAST PLACES & VIBE ASSOCIATIONS ----------
        similar_places = retrieve_similar_places(vibe, limit=3)
        vibe_associations = get_vibe_place_associations(vibe, limit=3)
        
        context = ""
        if similar_places:
            context = "\n\nSimilar places people liked for this vibe:\n"
            for _, name, desc, category in similar_places:
                context += f"- {name} ({category}): {desc}\n"
        
        if vibe_associations:
            context += "\n📊 Popular place types for this vibe (user ratings):\n"
            for assoc in vibe_associations:
                context += f"- {assoc['category']}: {assoc['avg_rating']}/5 ({assoc['feedback_count']} ratings)\n"

        # ---------- GEMINI INTENT (WITH RAG CONTEXT & EMOTIONAL AWARENESS) ----------
        prompt = f"""
You are an emotional intelligence expert guiding people to the perfect place based on their emotional state.

IMPORTANT: Understand the emotional meaning behind the vibe and recommend EMOTIONALLY APPROPRIATE places, not generic tourist spots.

User's Emotional State:
- Vibe/Mood: {vibe}
- Age: {age if age else "unknown"}
- Personality: {personality if personality else "unknown"}

{context}

Based on the emotional state, recommend place types and keywords that will help fulfill that emotional need.

Examples:
- "Spiritual" → temples, meditation centers, nature, sacred places
- "Sad" → peaceful parks, quiet cafes, nature for reflection
- "Happy" → vibrant restaurants, entertainment, celebration venues
- "Energetic" → gyms, sports, outdoor activities
- "Romantic" → intimate restaurants, scenic parks, peaceful spots

Return ONLY valid JSON with emotionally appropriate recommendations:
{{
  "place_types": ["place_type1", "place_type2"],
  "keywords": ["keyword1", "keyword2"],
  "best_time": "Time of day"
}}
"""

        gemini_payload = {
            "contents": {
                "parts": [
                    {"text": prompt}
                ]
            },
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        intent = None
        try:
            gemini_url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
            gemini_res = requests.post(gemini_url, headers=headers, json=gemini_payload)
            if gemini_res.status_code == 200:
                response_data = gemini_res.json()
                raw = response_data["candidates"][0]["content"]["parts"][0]["text"]
                intent = json.loads(raw)
                print(f"✅ Gemini provided intent for: {vibe}")
            else:
                print(f"⚠️ Gemini API error: {gemini_res.status_code} - {gemini_res.text}")
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}")
        
        # Fallback if Gemini fails - mark used_fallback so we can reject
        used_fallback = False
        if intent is None:
            print(f"⚠️ Using generic fallback for: {vibe}")
            used_fallback = True
            intent = {
                "place_types": ["restaurant", "cafe", "park", "tourist_attraction"],
                "keywords": ["popular", "highly rated", "nearby"],
                "best_time": "Day"
            }

        place_types = intent.get("place_types", [])
        keywords = intent.get("keywords", ["peaceful"])
        best_time = intent.get("best_time", "Day")

        # ✅ Always proceed with intent (either from Gemini or fallback)
        # Even if Gemini failed, the fallback will search for generic popular places
        if used_fallback:
            print(f"⚠️ Using fallback intent for '{vibe}' - results may be less relevant")

    # ---------- GEOCODE / COORDS ----------
    if coords and isinstance(coords, dict) and coords.get("lat") and coords.get("lng"):
        lat = coords.get("lat")
        lng = coords.get("lng")
    else:
        lat, lng = geocode_city(location)
        if not lat:
            return jsonify({"error": "Invalid location"}), 400

    # ---------- GOOGLE PLACES (WITH RAG RE-RANKING) ----------
    results = []
    seen_place_ids = set()
    vibe_embedding = get_embedding(vibe)

    # Determine radius (fallback to 12000 meters)
    try:
        radius_val = int(radius) if radius else 12000
    except Exception:
        radius_val = 12000

    # If frontend provided a specific category, use it instead of model suggestion
    if category_override:
        place_types = [category_override]

    for ptype in place_types:
        places_data = search_places(lat, lng, ptype, keywords[0], radius=radius_val)

        for place in places_data.get("results", []):
            place_id = place.get("place_id")

            if not place_id or place_id in seen_place_ids:
                continue

            seen_place_ids.add(place_id)

            if place.get("rating", 0) < 3.8:
                continue
            if place.get("user_ratings_total", 0) < 20:
                continue

            photo_ref = None
            if place.get("photos"):
                photo_ref = place["photos"][0]["photo_reference"]

            place_info = {
                "name": place.get("name"),
                "description": make_description(place, ptype),
                "latitude": place["geometry"]["location"]["lat"],
                "longitude": place["geometry"]["location"]["lng"],
                "rating": place.get("rating", 0),
                "reviews": place.get("user_ratings_total", 0),
                "category": ptype,
                "best_time": best_time,
                "photo_ref": photo_ref,
                "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            }

            # RAG: Calculate vibe similarity score
            desc_embedding = get_embedding(place_info["description"] + " " + " ".join(keywords))
            vibe_score = np.dot(vibe_embedding, desc_embedding) / (np.linalg.norm(vibe_embedding) * np.linalg.norm(desc_embedding) + 1e-8)
            place_info["vibe_score"] = float(vibe_score)

            results.append(place_info)

            # RAG: Cache this place
            cache_place(place_info, " ".join(keywords))

    # 🧠 FEEDBACK-BASED LEARNING & FILTERING
    # Step 1: Filter out places with negative feedback for this vibe
    results = filter_negative_feedback(results, vibe, threshold=2.5)
    
    # Step 2: Sort by vibe relevance + rating (original sorting)
    results.sort(key=lambda x: (x["vibe_score"] * 0.6 + (x["rating"] / 5) * 0.4), reverse=True)

    # Step 3: Add feedback-enhanced confidence scores
    results = get_recommendation_confidence(results, vibe, location)
    
    # Step 4: Dynamic re-ranking using feedback
    results = rank_by_feedback(results, vibe, location)
    
    # Step 5: Final sort considering feedback rank score
    results.sort(key=lambda x: (x.get("feedback_rank_score", 0) * 0.5 + x.get("vibe_score", 0) * 0.5), reverse=True)

    # Apply max_results override from frontend if provided
    try:
        if max_results:
            max_n = int(max_results)
            return jsonify(results[:max_n])
    except Exception:
        pass

    return jsonify(results[:10])

# ==============================
# 📊 FEEDBACK API
# ==============================

@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    """
    Submit feedback for a recommendation
    
    Request body:
    {
        "place_name": "Place Name",
        "vibe": "user's vibe input",
        "user_rating": 4,  # 1-5 star rating
        "location": "City/Location"
    }
    """
    try:
        data = request.json
        place_name = data.get("place_name", "")
        vibe = data.get("vibe", "")
        user_rating = data.get("user_rating", 0)
        location = data.get("location", "")
        
        # Validate rating
        if not (1 <= user_rating <= 5):
            return jsonify({"error": "Rating must be between 1-5"}), 400
        
        # Save feedback
        success = save_feedback(place_name, vibe, user_rating, location)
        
        if success:
            # Get updated stats
            stats = get_place_feedback_stats(place_name)
            return jsonify({
                "success": True,
                "message": f"Feedback saved! This place now has {stats['count']} rating(s) with avg: {stats['avg_rating']:.2f}",
                "stats": stats
            }), 200
        else:
            return jsonify({"error": "Failed to save feedback"}), 500
            
    except Exception as e:
        print(f"Feedback endpoint error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/place-stats/<place_name>", methods=["GET"])
def get_place_stats(place_name):
    """Get feedback statistics for a specific place"""
    try:
        stats = get_place_feedback_stats(place_name)
        if stats:
            return jsonify(stats), 200
        else:
            return jsonify({"message": "No feedback data for this place"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/recommendations-with-feedback", methods=["POST"])
def recommendations_with_feedback():
    """Get recommendations with feedback-enhanced confidence scores"""
    data = request.json
    vibe = data.get("vibe", "")
    location = data.get("location", "")
    
    # This would call the normal recommend endpoint and enhance results
    # For now, returning a simple wrapper response
    return jsonify({
        "message": "Use /api/recommend endpoint - results now include feedback data",
        "feedback_fields": [
            "feedback_confidence: 0-1 score based on user feedback",
            "feedback_avg_rating: Average star rating from users",
            "feedback_count: Number of ratings received",
            "vibe_specific_rating: Rating for this specific vibe",
            "feedback_rank_score: Dynamic re-ranking score combining all factors"
        ]
    }), 200

@app.route("/api/vibe-insights/<vibe>", methods=["GET"])
def get_vibe_insights(vibe):
    """
    Get insights about what works for a specific vibe
    Shows which place types have highest ratings for this vibe
    """
    try:
        associations = get_vibe_place_associations(vibe, limit=10)
        if associations:
            return jsonify({
                "vibe": vibe,
                "insights": associations,
                "message": "These place types have the best ratings for this vibe"
            }), 200
        else:
            return jsonify({
                "vibe": vibe,
                "message": "No feedback data yet for this vibe. Submit feedback to build insights!"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/wishlist", methods=["GET", "POST", "DELETE"])
def api_wishlist():
    try:
        if request.method == 'GET':
            items = get_wishlist()
            return jsonify({'wishlist': items}), 200

        data = request.json or {}
        if request.method == 'POST':
            place_name = data.get('place_name')
            place_data = data.get('place_data', {})
            if not place_name:
                return jsonify({'error': 'place_name required'}), 400
            ok = add_wishlist_item(place_name, place_data)
            if ok:
                return jsonify({'success': True}), 200
            return jsonify({'error': 'failed to add'}), 500

        if request.method == 'DELETE':
            place_name = data.get('place_name')
            if not place_name:
                return jsonify({'error': 'place_name required'}), 400
            ok = remove_wishlist_item(place_name)
            if ok:
                return jsonify({'success': True}), 200
            return jsonify({'error': 'failed to remove'}), 500

    except Exception as e:
        print(f"Wishlist API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/passport-summary', methods=['GET'])
def api_passport_summary():
    try:
        # wishlist
        wishlist_items = get_wishlist()

        # top places per mood (limit small)
        vibes = list(EMOTION_PLACE_MAPPING.keys())[:6]  # limit to first 6 moods for summary
        top_by_vibe = {}
        for v in vibes:
            top_by_vibe[v] = get_top_places_for_vibe(v, limit=5)

        return jsonify({'wishlist': wishlist_items, 'top_by_vibe': top_by_vibe}), 200
    except Exception as e:
        print(f"Passport summary error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/learning-stats", methods=["GET"])
def get_learning_stats():
    """Get system learning statistics"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Total feedback submissions
        c.execute("SELECT COUNT(*) FROM feedback")
        total_feedback = c.fetchone()[0]
        
        # Total places cached
        c.execute("SELECT COUNT(*) FROM cached_places")
        total_places = c.fetchone()[0]
        
        # Average rating
        c.execute("SELECT AVG(user_rating) FROM feedback")
        avg_rating = c.fetchone()[0]
        
        # Most successful vibe
        c.execute("""
            SELECT vibe, AVG(user_rating) as avg_rating, COUNT(*) as count
            FROM feedback
            GROUP BY vibe
            ORDER BY avg_rating DESC
            LIMIT 1
        """)
        best_vibe = c.fetchone()
        
        conn.close()
        
        return jsonify({
            "total_feedback_submissions": total_feedback,
            "total_places_cached": total_places,
            "average_user_rating": round(avg_rating, 2) if avg_rating else 0,
            "best_performing_vibe": {
                "vibe": best_vibe[0],
                "avg_rating": round(best_vibe[1], 2),
                "feedback_count": best_vibe[2]
            } if best_vibe else None,
            "system_status": "Learning and improving from user feedback"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ==============================
# 🚀 RUN
# ==============================

if __name__ == "__main__":
    app.run(debug=True)