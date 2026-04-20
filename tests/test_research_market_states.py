import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd

from scripts.research_market_states import load_symbol_frames, run_research


def _frame(base_step):
    idx = pd.date_range('2026-01-01', periods=90, freq='B')
    values = [100 + i * base_step for i in range(90)]
    return pd.DataFrame(
        {
            'open': values,
            'high': [x * 1.01 for x in values],
            'low': [x * 0.99 for x in values],
            'close': values,
            'volume': [1000 + i * 5 for i in range(90)],
        },
        index=idx,
    )


class TestResearchMarketStates(unittest.TestCase):
    def test_should_export_daily_state_leaderboard_and_summary(self):
        universe = {
            'etfs': [
                {'symbol': '510300', 'name': '沪深300ETF', 'tags': ['宽基'], 'is_market_proxy': True, 'is_theme_proxy': False},
                {'symbol': '512480', 'name': '半导体ETF', 'tags': ['科技'], 'is_market_proxy': False, 'is_theme_proxy': True},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            universe_path = os.path.join(tmpdir, 'universe.json')
            with open(universe_path, 'w', encoding='utf-8') as f:
                json.dump(universe, f, ensure_ascii=False)

            output_dir = os.path.join(tmpdir, 'out')

            fake_frames = {
                '510300': _frame(0.3),
                '512480': _frame(0.8),
            }

            with mock.patch('scripts.research_market_states.load_symbol_frames', return_value=fake_frames):
                result = run_research(
                    universe_path=universe_path,
                    output_dir=output_dir,
                    start_date='20260101',
                    end_date='20260630',
                )

            self.assertTrue(os.path.exists(result['daily_state_path']))
            self.assertTrue(os.path.exists(result['leaderboard_path']))
            self.assertTrue(os.path.exists(result['summary_path']))

    def test_should_show_help_when_executed_as_script(self):
        project_root = pathlib.Path(__file__).resolve().parent.parent
        script_path = project_root / 'scripts' / 'research_market_states.py'

        result = subprocess.run(
            [sys.executable, str(script_path), '--help'],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('运行市场阶段与主线 ETF 离线研究', result.stdout)

    def test_should_use_project_tmp_cache_for_symbol_loading(self):
        fake_source = mock.Mock()
        fake_source.get_data.return_value = _frame(0.3)

        with mock.patch('scripts.research_market_states.FallbackDataSource', return_value=fake_source) as mock_source_cls:
            load_symbol_frames(['510300'], '20260101', '20260630')

        _, kwargs = mock_source_cls.call_args
        self.assertIn('cache_dir', kwargs)
        self.assertTrue(str(kwargs['cache_dir']).endswith('tmp/fallback_cache'))


if __name__ == '__main__':
    unittest.main()
