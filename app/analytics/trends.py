from datetime import datetime, timezone


def calculate_trend_score(
    views: int,
    likes: int,
    comments: int,
    shares: int,
    created_at: str,
) -> float:
    created = datetime.fromisoformat(
        created_at.replace("Z", "+00:00")
    )

    now = datetime.now(timezone.utc)
    age_hours = max((now - created).total_seconds() / 3600, 1)

    engagement = (
        likes
        + comments * 2
        + shares * 3
    )

    engagement_rate = engagement / max(views, 1)

    freshness = 1 / (1 + age_hours / 24)

    popularity = views ** 0.5

    score = popularity * engagement_rate * freshness

    return round(score, 4)
