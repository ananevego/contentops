import unittest

from app.telegram.handlers import remove_video_from_current_trends, user_trends


class TrendExclusionTests(unittest.TestCase):
    def test_removes_only_selected_video_from_current_trends(self):
        user_id = 987654
        user_trends[user_id] = [
            {"video": {"id": "keep"}, "score": 10},
            {"video": {"id": "hide"}, "score": 9},
        ]

        remove_video_from_current_trends(user_id, "hide")

        self.assertEqual(
            [trend["video"]["id"] for trend in user_trends[user_id]],
            ["keep"],
        )
        user_trends.pop(user_id, None)
