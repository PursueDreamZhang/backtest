import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import render_market_regime_dashboard as dashboard_script


class RenderMarketRegimeDashboardTests(unittest.TestCase):
    def test_should_load_frames_from_cache_only_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result_dir = Path(tmpdir) / "result"
            result_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "date": ["2024-01-02", "2024-01-03"],
                    "market_stage": ["启动", "主升"],
                }
            ).to_csv(result_dir / "daily_state.csv", index=False)

            captured = {}

            def fake_load_symbol_frames(symbols, start_date, end_date, **kwargs):
                captured["symbols"] = symbols
                captured["start_date"] = start_date
                captured["end_date"] = end_date
                captured["kwargs"] = kwargs
                return {
                    "510050": pd.DataFrame(
                        {"close": [1.0, 1.1]},
                        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
                    )
                }

            with patch.object(dashboard_script, "load_etf_universe") as mock_universe, patch.object(
                dashboard_script, "load_symbol_frames", side_effect=fake_load_symbol_frames
            ), patch.object(dashboard_script, "render_dashboard_html") as mock_render:
                mock_universe.return_value = [
                    type(
                        "Entry",
                        (),
                        {
                            "symbol": "510050",
                            "name": "上证50ETF华夏",
                            "tags": ("市场代理",),
                            "is_market_proxy": True,
                            "is_theme_proxy": False,
                        },
                    )()
                ]
                mock_render.return_value = result_dir / "market_regime_dashboard.html"

                with patch(
                    "sys.argv",
                    [
                        "render_market_regime_dashboard.py",
                        "--universe",
                        "config/etf_universe.example.json",
                        "--result-dir",
                        str(result_dir),
                    ],
                ):
                    dashboard_script.main()

            self.assertEqual(captured["start_date"], "20240102")
            self.assertEqual(captured["end_date"], "20240103")
            self.assertTrue(captured["kwargs"]["use_cache"])
            self.assertTrue(captured["kwargs"]["cache_only"])


if __name__ == "__main__":
    unittest.main()
