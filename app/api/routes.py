from datetime import datetime
from pathlib import Path
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.analytics.data import create_charts, load_content_frame, summary, trends
from app.api.dependencies import get_db
from app.api.schemas import (
    AnalyticsSummary,
    ChartLinks,
    ContentCreate,
    ContentRead,
    ContentUpdate,
    TrendPoint,
)
from app.repositories.content import create_content, delete_content, get_content, list_content, update_content

router = APIRouter()


def _content_response(item) -> ContentRead:
    return ContentRead(
        id=item.id,
        source=item.source,
        external_id=item.external_id,
        author=item.author,
        text=item.text,
        views=item.views,
        likes=item.likes,
        comments=item.comments,
        shares=item.shares,
        url=item.url,
        created_at=datetime.fromisoformat(item.created_at.replace("Z", "+00:00")),
        trend_score=item.trend_score,
        tags=[tag.name for tag in item.tags],
    )

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
    item = create_content(
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
        tags=payload.tags.root,
    )
    return _content_response(item)


@router.get("/content", response_model=list[ContentRead], tags=["content"])
def read_content(
    platform: str | None = Query(default=None, max_length=50),
    category: str | None = Query(default=None, max_length=50),
    created_after: datetime | None = None,
    min_trend_score: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db),
):
    return [_content_response(item) for item in list_content(
        session,
        platform=platform,
        category=category,
        created_after=created_after,
        min_trend_score=min_trend_score,
        limit=limit,
    )]


@router.patch("/content/{content_id}", response_model=ContentRead, tags=["content"])
def patch_content_item(
    content_id: int,
    payload: ContentUpdate,
    session: Session = Depends(get_db),
):
    item = get_content(session, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    changes = payload.model_dump(exclude_unset=True, exclude={"tags"})
    if "url" in changes:
        changes["url"] = str(changes["url"])
    if "created_at" in changes:
        changes["created_at"] = changes["created_at"].isoformat()
    item = update_content(
        session,
        item,
        changes,
        tags=payload.tags.root if payload.tags is not None else None,
    )
    return _content_response(item)


@router.delete("/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["content"])
def delete_content_item(content_id: int, session: Session = Depends(get_db)) -> Response:
    item = get_content(session, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    delete_content(session, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
