from app.normalizers.tiktok import normalize_tiktok


def test_normalize_tiktok():
    video = {
        "id": "123",
        "authorMeta": {
            "name": "test_author",
        },
        "text": "Test TikTok",
        "playCount": 1000,
        "diggCount": 100,
        "commentCount": 20,
        "shareCount": 10,
        "webVideoUrl": "https://www.tiktok.com/test",
        "createTimeISO": "2026-01-01T12:00:00.000Z",
    }

    result = normalize_tiktok(video)

    assert result.source == "tiktok"
    assert result.external_id == "123"
    assert result.author == "test_author"
    assert result.text == "Test TikTok"
    assert result.views == 1000
    assert result.likes == 100
    assert result.comments == 20
    assert result.shares == 10
    assert result.url == "https://www.tiktok.com/test"
