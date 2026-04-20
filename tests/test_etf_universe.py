import json
import tempfile
import unittest

from research.etf_universe import EtfUniverseEntry, load_etf_universe


class TestEtfUniverse(unittest.TestCase):
    def test_should_load_entries_and_split_market_and_theme_flags(self):
        payload = {
            'etfs': [
                {
                    'symbol': '510300',
                    'name': '沪深300ETF',
                    'tags': ['宽基', '大盘'],
                    'is_market_proxy': True,
                    'is_theme_proxy': False,
                },
                {
                    'symbol': '512480',
                    'name': '半导体ETF',
                    'tags': ['科技', '半导体'],
                    'is_market_proxy': False,
                    'is_theme_proxy': True,
                },
            ]
        }

        with tempfile.NamedTemporaryFile('w+', suffix='.json', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()

            result = load_etf_universe(f.name)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[0],
            EtfUniverseEntry(
                symbol='510300',
                name='沪深300ETF',
                tags=('宽基', '大盘'),
                is_market_proxy=True,
                is_theme_proxy=False,
            ),
        )


if __name__ == '__main__':
    unittest.main()
