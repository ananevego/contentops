import unittest

from app.telegram.handlers import is_tiktok_url


class TikTokLinkTests(unittest.TestCase):
    def test_accepts_regular_and_short_tiktok_links(self):
        self.assertTrue(is_tiktok_url("https://www.tiktok.com/@creator/video/123"))
        self.assertTrue(is_tiktok_url("https://vm.tiktok.com/ZM123/"))

    def test_rejects_non_tiktok_and_incomplete_links(self):
        self.assertFalse(is_tiktok_url("https://example.com/video/123"))
        self.assertFalse(is_tiktok_url("https://tiktok.com"))
        self.assertFalse(is_tiktok_url("tiktok.com/@creator/video/123"))
