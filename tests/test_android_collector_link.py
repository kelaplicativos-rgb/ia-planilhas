from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from bling_app_zero.core.android_collector_link import (
    DEFAULT_ANDROID_COLLECTOR_APK_URL,
    android_collector_apk_source,
    android_collector_apk_url,
)


class TestAndroidCollectorLink(unittest.TestCase):
    def test_default_apk_url_points_to_github_release_asset(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(android_collector_apk_url(), DEFAULT_ANDROID_COLLECTOR_APK_URL)
            self.assertIn('/releases/download/android-coletor-latest/', android_collector_apk_url())
            self.assertTrue(android_collector_apk_url().endswith('.apk'))
            self.assertEqual(android_collector_apk_source(), 'default_github_release_android_coletor_latest')

    def test_env_overrides_apk_url(self) -> None:
        custom = 'https://example.com/download'
        with patch.dict(os.environ, {'MAPEIAAI_ANDROID_COLLECTOR_APK_URL': custom}, clear=True):
            self.assertEqual(android_collector_apk_url(), custom)
            self.assertEqual(android_collector_apk_source(), 'MAPEIAAI_ANDROID_COLLECTOR_APK_URL')


if __name__ == '__main__':
    unittest.main()
