from app.models.content import ContentItem


def test_content_item():
    item = ContentItem(
        source="Telegram",
        external_id="12345",
        author="Ivan Ivanov",
        text="Hello world!",
        transcript=None,
        views=100,
        likes=10,
        comments=2,
        shares=1,
        url="https://example.com/video",
        created_at="2026-01-01T12:00:00Z",
    )

    assert item.source == "Telegram"
    assert item.views == 100
