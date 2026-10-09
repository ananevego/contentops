from datetime import datetime
from pathlib import Path
import os

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.analytics.data import create_charts, load_content_frame, summary, trends
from app.api.dependencies import get_db
from app.api.schemas import AnalyticsSummary, ChartLinks, ContentCreate, ContentRead, TrendPoint
from app.repositories.content import create_content, list_content

router = APIRouter()

@router.get("/")
def root():
    return {"message": "ContentOps is running"}

@router.get("/health")
def root():
    return {"status": "ok",
    "service": "contentops-api"}

@router.get("/hello")
def root():
    return {"message": "Hello from ContentOps"}

@router.get("/config")
def root():
    return {"app_name": os.getenv("APP_NAME"), "environment": os.getenv("ENVIRONMENT")}


@router.get("/analytics/summary", response_model=AnalyticsSummary, tags=["analytics"])
def analytics_summary():
    """Returns a reproducible summary built from the synthetic, safe CSV sample."""
    return summary(load_content_frame())


@router.get("/analytics/trends", response_model=list[TrendPoint], tags=["analytics"])
def analytics_trends():
    return trends(load_content_frame())


@router.get("/analytics/charts", response_model=ChartLinks, tags=["analytics"])
def analytics_charts():
    """Builds ignored PNG artifacts on demand; response contains their local paths."""
    return create_charts(load_content_frame(), Path("artifacts"))


@router.post(
    "/content",
    response_model=ContentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["content"],
)
def create_content_item(payload: ContentCreate, session: Session = Depends(get_db)):
    return create_content(
        session,
        source=payload.source.platform,
        external_id=payload.external_id,
        author=payload.author,
        text=payload.text,
        transcript=payload.transcript,
        views=payload.views,
        likes=payload.likes,
        comments=payload.comments,
        shares=payload.shares,
        url=str(payload.url),
        created_at=payload.created_at,
        category=payload.source.category,
    )


@router.get("/content", response_model=list[ContentRead], tags=["content"])
def read_content(
    platform: str | None = Query(default=None, max_length=50),
    category: str | None = Query(default=None, max_length=50),
    created_after: datetime | None = None,
    min_trend_score: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db),
):
    return list_content(
        session,
        platform=platform,
        category=category,
        created_after=created_after,
        min_trend_score=min_trend_score,
        limit=limit,
    )
