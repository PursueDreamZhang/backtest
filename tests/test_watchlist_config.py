import tempfile
import unittest
from pathlib import Path

from watchlist.config import load_watchlist_config


class WatchlistConfigTests(unittest.TestCase):
    def test_should_load_watchlist_config_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.json"
            path.write_text(
                """
                {
                  "direction": "机器人",
                  "thesis": "观察二次探底",
                  "symbols": [
                    {"symbol": "159770", "name": "机器人ETF", "type": "etf"},
                    {"symbol": "300124"}
                  ]
                }
                """,
                encoding="utf-8",
            )

            config = load_watchlist_config(path)

            self.assertEqual(config.direction, "机器人")
            self.assertEqual(config.thesis, "观察二次探底")
            self.assertEqual([item.symbol for item in config.symbols], ["159770", "300124"])
            self.assertEqual(config.symbols[1].name, "")
            self.assertEqual(config.symbols[1].instrument_type, "stock")
            self.assertEqual(config.symbols[1].role, "")

    def test_should_load_multiple_watchlists_and_pad_symbol_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlists.json"
            path.write_text(
                """
                {
                  "watchlists": [
                    {
                      "direction": "商业航天",
                      "thesis": "中期炒作",
                      "symbols": [
                        {"symbol": "1270", "name": "铖昌科技", "type": "stock", "role": "标的"},
                        {"symbol": "002115", "name": "三维通信", "type": "stock", "role": "标的"}
                      ]
                    },
                    {
                      "direction": "半导体",
                      "thesis": "中期炒作",
                      "symbols": [
                        {"symbol": "688012", "name": "中微公司", "type": "stock", "role": "标的"}
                      ]
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            configs = load_watchlist_config(path)

            self.assertEqual([config.direction for config in configs], ["商业航天", "半导体"])
            self.assertEqual(configs[0].symbols[0].symbol, "001270")


if __name__ == "__main__":
    unittest.main()
