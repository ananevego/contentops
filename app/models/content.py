from pydantic import BaseModel
from typing import Optional

class ContentItem(BaseModel):
    source: str
    external_id: str
    author: str
    text: str
    views: int
    likes: int
    comments: int
    shares: int
