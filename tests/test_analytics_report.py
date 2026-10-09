import numpy as np

from app.analytics.data import create_charts, load_content_frame, summary, trends
from app.analytics.scoring import calculate_trend_scores


def test_demo_pipeline_uses_safe_data_and_creates_all_charts(tmp_path):
    frame = load_content_frame()

    assert {"platform_group", "trend_score", "normalized_views", "engagement_rate"} <= set(frame.columns)
    assert summary(frame)["total_items"] == len(frame)
    assert len(trends(frame)) >= 1

    charts = create_charts(frame, tmp_path)
    assert set(charts) == {"line", "categories", "scatter"}
    assert all((tmp_path / path.split("/")[-1]).is_file() for path in charts.values())


def test_numba_and_numpy_paths_have_the_same_scores():
    values = (
        np.array([100, 1000]),
        np.array([10, 100]),
        np.array([2, 20]),
        np.array([1, 10]),
        np.array([4, 24]),
    )
    fallback = calculate_trend_scores(*values, use_numba=False)
    accelerated = calculate_trend_scores(*values, use_numba=True)

    np.testing.assert_allclose(accelerated, fallback)
