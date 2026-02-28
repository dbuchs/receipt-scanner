from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.retraining.retrain_classifier")
def retrain_classifier() -> dict:
    """
    Nightly task: fetch all LearningExamples from DB and retrain the classifier.
    """
    from app.database import SessionLocal
    from app.models.rules import LearningExample
    from app.services.classifier import TaxonomyClassifier

    db = SessionLocal()
    try:
        examples = db.query(LearningExample).all()
        count = len(examples)
        if count >= 2:
            classifier = TaxonomyClassifier()
            classifier.train(examples)
            return {"status": "trained", "examples": count}
        return {"status": "skipped", "examples": count, "reason": "not enough examples"}
    finally:
        db.close()
