from app.analytics.data import load_content_frame
from app.shiny_dashboard import filter_content


def test_shiny_filter_function_applies_platform_and_category():
    frame = load_content_frame()
    filtered = filter_content(frame, ["tiktok"], ["fitness"])

    assert not filtered.empty
    assert set(filtered["platform"]) == {"tiktok"}
    assert set(filtered["category"]) == {"fitness"}
