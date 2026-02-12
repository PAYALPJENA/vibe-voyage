import os
import tempfile
import numpy as np

import rag_engine as rg


class DummyModel:
    def encode(self, texts, convert_to_numpy=True):
        # Return a deterministic small vector based on text length
        if isinstance(texts, list):
            out = []
            for t in texts:
                v = np.ones(8, dtype=np.float32) * (len(str(t)) % 10 + 1)
                out.append(v)
            return np.array(out)
        else:
            v = np.ones(8, dtype=np.float32) * (len(str(texts)) % 10 + 1)
            return v


def setup_in_memory_db():
    # Use a temporary file-backed DB to avoid separate in-memory connections
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    rg.DB_PATH = tf.name
    rg.init_db()


def test_cache_and_retrieve():
    setup_in_memory_db()
    # inject dummy model
    rg._embedding_model = DummyModel()

    place = {
        'name': 'Test Place',
        'description': 'A nice place to relax',
        'latitude': 12.0,
        'longitude': 77.0,
        'rating': 4.5,
        'reviews': 120,
        'category': 'park'
    }

    rg.cache_place(place, 'quiet nature')

    # retrieve similar
    sims = rg.retrieve_similar_places('calm nature', limit=3)
    assert isinstance(sims, list)
    assert len(sims) <= 3


def test_feedback_flow():
    setup_in_memory_db()
    rg._embedding_model = DummyModel()

    place = {
        'name': 'Cafe Blue',
        'description': 'Cozy cafe',
        'latitude': 10.0,
        'longitude': 10.0,
        'rating': 4.2,
        'reviews': 50,
        'category': 'cafe'
    }

    rg.cache_place(place, 'cozy')
    success = rg.save_feedback('Cafe Blue', 'calm', 5, 'TestCity')
    assert success

    stats = rg.get_place_feedback_stats('Cafe Blue')
    assert stats and stats['count'] == 1

    results = [{
        'name': 'Cafe Blue',
        'description': place['description'],
        'latitude': place['latitude'],
        'longitude': place['longitude'],
        'rating': place['rating'],
        'reviews': place['reviews'],
        'category': place['category'],
    }]

    conf = rg.get_recommendation_confidence(results, 'calm', 'TestCity')
    assert conf[0]['feedback_count'] == 1

    ranked = rg.rank_by_feedback(results, 'calm', 'TestCity')
    assert 'feedback_rank_score' in ranked[0]
