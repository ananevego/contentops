from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ContentSourceIn(BaseModel):
    """Nested source metadata used by the content creation API."""

    platform: str = Field(min_length=2, max_length=50, examples=["tiktok"])
    category: str = Field(default="general", min_length=2, max_length=50)


class ContentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: ContentSourceIn
    external_id: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=10_000)
    transcript: str | None = Field(default=None, max_length=50_000)
    views: int = Field(ge=0)
    likes: int = Field(ge=0)
    comments: int = Field(ge=0)
    shares: int = Field(ge=0)
    url: HttpUrl
    created_at: datetime

    @model_validator(mode="after")
    def validate_engagement_and_date(self):
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        interactions = self.likes + self.comments + self.shares
        if self.views and interactions > self.views * 2:
            raise ValueError("engagement metrics are inconsistent with views")
        if self.created_at > datetime.now(timezone.utc):
            raise ValueError("created_at cannot be in the future")
        return self


class ContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    author: str
    text: str
    views: int
    likes: int
    comments: int
    shares: int
    url: str
    created_at: str
    trend_score: float | None


class AnalyticsSummary(BaseModel):
    total_items: int = Field(ge=0)
    total_views: int = Field(ge=0)
    average_engagement_rate: float = Field(ge=0)
    top_platform: str | None
    category_totals: dict[str, int]


class TrendPoint(BaseModel):
    date: str
    average_trend_score: float
    normalized_views: float = Field(ge=0, le=1)


class ChartLinks(BaseModel):
    line: str
    categories: str
    scatter: str
