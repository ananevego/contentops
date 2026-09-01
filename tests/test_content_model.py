import pytest
from app.models.content import ContentItem

def test_content_item():
    item = ContentItem(
        source="Telegram",
        external_id="12345",
        author="Ivan Ivanov",
        text="Hello world!",
        views=100,
        likes=10,
        comments=2,
        shares=1,
)

    assert item.source == "Telegram"
    assert item.views == 100

