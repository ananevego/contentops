from typing import Optional
from pydantic import BaseModel

class ContentItem(BaseModel):
    source: str
    external_id: str
    author: str
    text: str
    transcript: str | None
    views: int
    likes: int
    comments: int
    shares: int
    url: str
    created_at: str
