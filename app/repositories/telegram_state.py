"""Хранение пользовательского состояния Telegram-бота в PostgreSQL."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_db import TelegramUserSettingsDB, UsedTikTokVideoDB


DEFAULT_SETTINGS = {
    "profiles": [],
    "hashtags": [],
    "results_count": 5,
    "min_video_date": None,
    "idea_prompt": None,
    "post_prompt": None,
    "allow_reparse_used_videos": False,
}


def _to_settings(record: TelegramUserSettingsDB) -> dict:
    return {
        "profiles": record.profiles or [],
        "hashtags": record.hashtags or [],
        "results_count": record.results_count,
        "min_video_date": record.min_video_date,
        "idea_prompt": record.idea_prompt,
        "post_prompt": record.post_prompt,
        "allow_reparse_used_videos": record.allow_reparse_used_videos,
    }


def get_user_settings(session: Session, telegram_user_id: int) -> dict:
    record = session.scalar(
        select(TelegramUserSettingsDB).where(
            TelegramUserSettingsDB.telegram_user_id == telegram_user_id,
        )
    )

    if record is None:
        record = TelegramUserSettingsDB(
            telegram_user_id=telegram_user_id,
            **DEFAULT_SETTINGS,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

    return _to_settings(record)


def save_user_settings(
    session: Session,
    telegram_user_id: int,
    settings: dict,
) -> None:
    record = session.scalar(
        select(TelegramUserSettingsDB).where(
            TelegramUserSettingsDB.telegram_user_id == telegram_user_id,
        )
    )

    if record is None:
        record = TelegramUserSettingsDB(telegram_user_id=telegram_user_id)
        session.add(record)

    for field, default in DEFAULT_SETTINGS.items():
        setattr(record, field, settings.get(field, default))

    session.commit()


def remember_used_video(
    session: Session,
    telegram_user_id: int,
    video: dict,
    content_id: int | None,
) -> None:
    video_id = str(video.get("id", ""))
    if not video_id:
        return

    existing = session.scalar(
        select(UsedTikTokVideoDB).where(
            UsedTikTokVideoDB.telegram_user_id == telegram_user_id,
            UsedTikTokVideoDB.tiktok_video_id == video_id,
        )
    )
    if existing:
        return

    author = video.get("authorMeta", {})
    session.add(
        UsedTikTokVideoDB(
            telegram_user_id=telegram_user_id,
            content_id=content_id,
            tiktok_video_id=video_id,
            author=author.get("uniqueId") or author.get("name"),
            url=video.get("webVideoUrl"),
        )
    )
    session.commit()


def get_used_video_ids(session: Session, telegram_user_id: int) -> set[str]:
    return set(
        session.scalars(
            select(UsedTikTokVideoDB.tiktok_video_id).where(
                UsedTikTokVideoDB.telegram_user_id == telegram_user_id,
            )
        )
    )


def list_used_videos(
    session: Session,
    telegram_user_id: int,
    limit: int = 20,
) -> list[UsedTikTokVideoDB]:
    return list(
        session.scalars(
            select(UsedTikTokVideoDB)
            .where(UsedTikTokVideoDB.telegram_user_id == telegram_user_id)
            .order_by(UsedTikTokVideoDB.used_at.desc())
            .limit(limit)
        )
    )
