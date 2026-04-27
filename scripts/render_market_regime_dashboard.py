from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.data_loader import load_symbol_frames
from research.etf_universe import load_etf_universe
from research.visualization import build_dashboard_payload, render_dashboard_html


def _infer_date_range(daily_state: pd.DataFrame) -> tuple[str, str]:
    work = daily_state.copy()
    work['date'] = pd.to_datetime(work['date'])
    return (
        work['date'].min().strftime('%Y%m%d'),
        work['date'].max().strftime('%Y%m%d'),
    )


def main():
    parser = argparse.ArgumentParser(description='把市场阶段研究结果渲染为交互式 HTML 可视化面板')
    parser.add_argument('--universe', required=True, help='ETF 代理池配置文件')
    parser.add_argument('--result-dir', required=True, help='research 输出目录，包含 daily_state.csv')
    parser.add_argument('--output', help='输出 html 文件路径，默认写入 result-dir/market_regime_dashboard.html')
    parser.add_argument(
        '--refresh-data',
        action='store_true',
        help='允许在渲染时联网补齐价格数据；默认只使用缓存',
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    daily_state_path = result_dir / 'daily_state.csv'
    leaderboard_path = result_dir / 'leaderboard.csv'
    if not daily_state_path.exists():
        raise FileNotFoundError(f'未找到 daily_state.csv: {daily_state_path}')
    if not leaderboard_path.exists():
        raise FileNotFoundError(f'未找到 leaderboard.csv: {leaderboard_path}')

    daily_state = pd.read_csv(daily_state_path)
    leaderboard = pd.read_csv(leaderboard_path)
    start_date, end_date = _infer_date_range(daily_state)
    universe = load_etf_universe(args.universe)
    frames = load_symbol_frames(
        [item.symbol for item in universe],
        start_date,
        end_date,
        use_cache=True,
        cache_only=not args.refresh_data,
    )

    payload = build_dashboard_payload(
        universe=universe,
        frames=frames,
        daily_state=daily_state,
        leaderboard=leaderboard,
        title=f'市场阶段与 ETF 走势总览 {start_date} - {end_date}',
    )
    output_path = Path(args.output) if args.output else result_dir / 'market_regime_dashboard.html'
    html_path = render_dashboard_html(payload, output_path)
    print(json.dumps({'dashboard_path': str(html_path)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
