import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from watchlist.pipeline import run_watchlist_strategy
from watchlist.reporting import write_reports
from watchlist.signals import SignalResult


class WatchlistReportingTests(unittest.TestCase):
    def test_should_write_json_csv_and_markdown(self):
        result = SignalResult(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            mode="intraday",
            group="盘中触发",
            signal_timing="intraday",
            confidence="provisional",
            score=82,
            setup="MA40 弹簧盘中松开",
            latest_price=1.236,
            support=1.21,
            stop_loss=1.174,
            risk_to_stop_pct=5.02,
            signals=("实时价重新站上 MA5",),
            action="盘中优先盯",
            invalid_if="跌破止损",
            needs_close_confirmation=("收盘是否站上 MA5",),
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_reports(
                output_dir=tmp,
                direction="机器人",
                thesis="观察二次探底",
                mode="intraday",
                results=[result],
                run_date="2026-04-27",
            )

            payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "intraday")
            self.assertEqual(payload["summary"]["intraday_triggered"], 1)
            self.assertTrue(Path(paths["csv"]).exists())
            self.assertTrue(Path(paths["markdown"]).exists())


class WatchlistPipelineTests(unittest.TestCase):
    def test_should_run_pipeline_with_injected_data(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )

            result = run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260427",
                mode="close_confirmed",
                frame_loader=lambda symbols, start_date, end_date: {"159770": frame},
                realtime_quote_loader=None,
            )

            self.assertTrue(Path(result["json"]).exists())
            self.assertTrue(Path(result["csv"]).exists())
            self.assertTrue(Path(result["markdown"]).exists())

    def test_should_pass_cache_only_to_frame_loader_when_supported(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )
        captured = {}

        def loader(symbols, start_date, end_date, **kwargs):
            captured["kwargs"] = kwargs
            return {"159770": frame}

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )

            run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260427",
                mode="close_confirmed",
                frame_loader=loader,
                realtime_quote_loader=None,
                cache_only=True,
            )

            self.assertEqual(captured["kwargs"], {"cache_only": True})

    def test_should_run_multiple_watchlists_into_direction_subdirectories(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlists.json"
            config_path.write_text(
                """
                {
                  "watchlists": [
                    {"direction":"半导体","symbols":[{"symbol":"688012","type":"stock"}]},
                    {"direction":"商业航天","symbols":[{"symbol":"001270","type":"stock"}]}
                  ]
                }
                """,
                encoding="utf-8",
            )

            result = run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260427",
                mode="close_confirmed",
                frame_loader=lambda symbols, start_date, end_date: {
                    "688012": frame,
                    "001270": frame,
                },
                realtime_quote_loader=None,
            )

            self.assertTrue(Path(result["半导体"]["json"]).exists())
            self.assertTrue(Path(result["商业航天"]["json"]).exists())


if __name__ == "__main__":
    unittest.main()
