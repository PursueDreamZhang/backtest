from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.etf_universe import load_etf_universe
from research.reporting import summarize_latest_state


def main():
    parser = argparse.ArgumentParser(description='输出市场阶段研究结果的最新 top5 与主线方向摘要')
    parser.add_argument('--universe', required=True, help='ETF 代理池配置文件')
    parser.add_argument('--result-dir', required=True, help='research 输出目录，包含 daily_state.csv 与 leaderboard.csv')
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    daily_state = pd.read_csv(result_dir / 'daily_state.csv')
    leaderboard = pd.read_csv(result_dir / 'leaderboard.csv')
    universe = load_etf_universe(args.universe)

    summary = summarize_latest_state(daily_state, leaderboard, universe)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
