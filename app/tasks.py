"""Celery tasks kept separate from API imports so Redis is never contacted at import time."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
from celery import Celery
from sqlalchemy import select

from app.analytics.report import build_analytics_report
from app.analytics.scoring import calculate_trend_scores
from app.database import SessionLocal
from app.models.content_db import ContentItemDB

celery_app = Celery(
    "contentops",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@celery_app.task(name="contentops.recalculate_trend_scores")
def recalculate_trend_scores() -> dict[str, int]:
    """Bulk score computation: DB reads/writes remain outside the Numba kernel."""
    with SessionLocal() as session:
        items = list(session.scalars(select(ContentItemDB)))
        if not items:
            return {"updated": 0}
        now = datetime.now(timezone.utc)
        ages = np.array([
            max((now - datetime.fromisoformat(item.created_at.replace("Z", "+00:00"))).total_seconds() / 3600, 1)
            for item in items
        ])
        scores = calculate_trend_scores(
            np.array([item.views for item in items]),
            np.array([item.likes for item in items]),
            np.array([item.comments for item in items]),
            np.array([item.shares for item in items]),
            ages,
        )
        for item, score in zip(items, scores, strict=True):
            item.trend_score = float(score)
        session.commit()
        return {"updated": len(items)}


@celery_app.task(name="contentops.build_analytics_report")
def build_report_task(output_dir: str = "artifacts") -> dict:
    """Generates an analytics report; calling .delay requires a reachable Redis broker."""
    return build_analytics_report(output_dir)
