from app.models.content import ContentItem

def normalize_tiktok(video: dict) -> ContentItem:
    return ContentItem(
        source="tiktok",
        external_id=video["id"],
        author=video["authorMeta"]["name"],
        text=video["text"],
        views=video["playCount"],
        likes=video["diggCount"],
        comments=video["commentCount"],
        shares=video["shareCount"],
        url=video["webVideoUrl"],
        created_at=video["createTimeISO"],
        )
