from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchlist_backtest.engine import run_watchlist_backtest


def main():
    parser = argparse.ArgumentParser(description="回测观察池执行策略")
    parser.add_argument("--config", required=True, help="观察池配置文件")
    parser.add_argument("--start-date", required=True, help="开始日期 YYYYMMDD")
    parser.add_argument("--end-date", required=True, help="结束日期 YYYYMMDD")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--max-positions", type=int, default=8)
    parser.add_argument("--position-size-pct", type=float, default=0.10)
    parser.add_argument("--max-hold-days", type=int, default=10)
    args = parser.parse_args()

    result = run_watchlist_backtest(
        config_path=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        initial_cash=args.initial_cash,
        max_positions=args.max_positions,
        position_size_pct=args.position_size_pct,
        max_hold_days=args.max_hold_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

