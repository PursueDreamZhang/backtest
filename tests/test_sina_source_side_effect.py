import importlib
import os
import unittest
from unittest import mock

import data.sina_source as sina_source


class TestSinaSourceSideEffect(unittest.TestCase):
    def test_import_should_not_override_proxy_environment(self):
        old_http = os.environ.get('HTTP_PROXY')
        old_https = os.environ.get('HTTPS_PROXY')

        os.environ['HTTP_PROXY'] = 'http://proxy.local:8080'
        os.environ['HTTPS_PROXY'] = 'http://proxy.local:8080'

        importlib.reload(sina_source)

        self.assertEqual(os.environ.get('HTTP_PROXY'), 'http://proxy.local:8080')
        self.assertEqual(os.environ.get('HTTPS_PROXY'), 'http://proxy.local:8080')

        if old_http is None:
            os.environ.pop('HTTP_PROXY', None)
        else:
            os.environ['HTTP_PROXY'] = old_http

        if old_https is None:
            os.environ.pop('HTTPS_PROXY', None)
        else:
            os.environ['HTTPS_PROXY'] = old_https

    def test_should_not_create_cache_dir_when_cache_is_disabled(self):
        with mock.patch('data.sina_source.os.makedirs') as mock_makedirs:
            source = sina_source.SinaDataSource()
            mock_makedirs.assert_not_called()

        with mock.patch.object(source, '_fetch_from_sina', return_value='ok') as mock_fetch:
            result = source.get_data('510300', '20240101', '20240131', use_cache=False)

        self.assertEqual(result, 'ok')
        mock_fetch.assert_called_once_with('510300', '20240101', '20240131')


if __name__ == '__main__':
    unittest.main()
