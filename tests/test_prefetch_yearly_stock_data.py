import unittest
import os
import sys
import json
import tempfile

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from prefetch_yearly_stock_data import _classify_item_availability, _load_from_fallback_cache, build_parser, prefetch


class TestPrefetchYearlyStockData(unittest.TestCase):
    def test_prefetch_should_default_to_yearly_market_data(self):
        parser = build_parser()

        args = parser.parse_args([])

        self.assertEqual(args.output_dir, 'data/yearly_market_data')

    def test_should_skip_symbol_when_not_listed_yet_for_target_year(self):
        item = {'ts_code': '301000.SZ', 'list_date': '20200115'}

        reason = _classify_item_availability(item, '20180101', '20181231')

        self.assertEqual(reason, 'not_listed_yet')

    def test_should_skip_symbol_when_delisted_before_target_year(self):
        item = {'ts_code': '000013.SZ', 'list_date': '19920101', 'delist_date': '20170630'}

        reason = _classify_item_availability(item, '20190101', '20191231')

        self.assertEqual(reason, 'delisted_before_range')

    def test_should_keep_symbol_when_listed_during_requested_range(self):
        item = {'ts_code': '300750.SZ', 'list_date': '20180611'}

        reason = _classify_item_availability(item, '20190101', '20191231')

        self.assertIsNone(reason)

    def test_should_load_requested_slice_from_fallback_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, 'fallback_000001.pkl')
            df = pd.DataFrame(
                {
                    'open': [1.0, 2.0, 3.0],
                    'high': [1.1, 2.1, 3.1],
                    'low': [0.9, 1.9, 2.9],
                    'close': [1.0, 2.0, 3.0],
                    'volume': [100, 200, 300],
                },
                index=pd.to_datetime(['2019-01-02', '2019-01-03', '2019-01-04']),
            )
            df.to_pickle(cache_file)

            class DummyDataSource:
                cache_dir = tmpdir

                @staticmethod
                def _slice(source_df, start_date, end_date):
                    start = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
                    end = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'
                    return source_df.loc[start:end]

            result = _load_from_fallback_cache(DummyDataSource(), '000001', '20190103', '20190104')

            self.assertEqual(list(result.index.strftime('%Y-%m-%d')), ['2019-01-03', '2019-01-04'])

    def test_should_prefetch_from_cache_only_without_hitting_network(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_json = os.path.join(tmpdir, 'input.json')
            output_dir = os.path.join(tmpdir, 'output')
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir, exist_ok=True)

            with open(input_json, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        'years': [
                            {
                                'year': 2019,
                                'companies': [{'ts_code': '000001.SZ'}],
                            }
                        ]
                    },
                    f,
                    ensure_ascii=False,
                )

            df = pd.DataFrame(
                {
                    'open': [10.0, 11.0],
                    'high': [10.5, 11.5],
                    'low': [9.5, 10.5],
                    'close': [10.2, 11.2],
                    'volume': [1000, 1200],
                },
                index=pd.to_datetime(['2019-01-02', '2019-01-03']),
            )
            df.to_pickle(os.path.join(cache_dir, 'fallback_000001.pkl'))

            from unittest import mock

            with mock.patch('prefetch_yearly_stock_data.BACKTEST_CONFIG', {'data_source_priority': ['yfinance']}):
                with mock.patch('prefetch_yearly_stock_data.FallbackDataSource') as mock_ds_cls:
                    mock_ds = mock.MagicMock()
                    mock_ds.cache_dir = cache_dir
                    mock_ds._slice.side_effect = lambda source_df, start_date, end_date: source_df.loc['2019-01-01':'2019-12-31']
                    mock_ds_cls.return_value = mock_ds

                    prefetch(
                        input_json=input_json,
                        output_dir=output_dir,
                        retries=1,
                        checkpoint_every=1,
                        cache_only=True,
                    )

            self.assertTrue(os.path.exists(os.path.join(output_dir, '2019', '000001.pkl')))
            mock_ds.get_data.assert_not_called()


if __name__ == '__main__':
    unittest.main()
