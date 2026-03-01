from __future__ import annotations

import os
import pickle
import uuid
from pathlib import Path
from typing import Optional

from app.config import get_settings

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.svm import LinearSVC
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import LabelEncoder
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


class TaxonomyClassifier:
    """TF-IDF + LinearSVC classifier for taxonomy suggestion."""

    _MODEL_FILENAME = "taxonomy_classifier.pkl"

    def __init__(self):
        self._pipeline: Optional[object] = None
        self._label_encoder: Optional[object] = None
        self._model_path = Path(get_settings().MODEL_DIR) / self._MODEL_FILENAME

    def _feature(self, merchant: str, description: str) -> str:
        return f"{merchant.lower()} {description.lower()}"

    def train(self, examples: list) -> None:
        """
        Train on a list of LearningExample ORM objects.
        Each must have .merchant, .description_normalized, .chosen_taxonomy_id.
        """
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn is not installed")
        if not examples:
            return

        X = [self._feature(e.merchant, e.description_normalized) for e in examples]
        y = [str(e.chosen_taxonomy_id) for e in examples]

        if len(set(y)) < 2:
            # Can't train a classifier with only one class
            return

        le = LabelEncoder()
        y_enc = le.fit_transform(y)

        pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
                ("clf", LinearSVC(max_iter=2000)),
            ]
        )
        pipeline.fit(X, y_enc)

        self._pipeline = pipeline
        self._label_encoder = le
        self._save()

    def predict(self, merchant: str, description: str) -> tuple[Optional[str], float]:
        """
        Returns (taxonomy_id_str, confidence).
        confidence is 0.0 if model not available.
        """
        if self._pipeline is None:
            self._load()
        if self._pipeline is None:
            return None, 0.0

        feat = self._feature(merchant, description)
        try:
            pred_enc = self._pipeline.predict([feat])[0]
            taxonomy_id = self._label_encoder.inverse_transform([pred_enc])[0]
            # LinearSVC doesn't give probabilities; use decision function distance as proxy
            decision = self._pipeline.decision_function([feat])
            if hasattr(decision[0], "__len__"):
                conf = float(max(decision[0])) / 10.0  # rough normalization
            else:
                conf = min(abs(float(decision[0])) / 5.0, 1.0)
            return taxonomy_id, min(conf, 1.0)
        except Exception:
            return None, 0.0

    def _save(self) -> None:
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._model_path, "wb") as f:
            pickle.dump(
                {"pipeline": self._pipeline, "label_encoder": self._label_encoder}, f
            )

    def _load(self) -> None:
        if not self._model_path.exists():
            return
        with open(self._model_path, "rb") as f:
            data = pickle.load(f)  # noqa: S301
        self._pipeline = data.get("pipeline")
        self._label_encoder = data.get("label_encoder")
