from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchlist.pipeline import run_watchlist_strategy


def main():
    parser = argparse.ArgumentParser(description="运行观察标的执行策略")
    parser.add_argument("--config", required=True, help="观察标的配置 JSON")
    parser.add_argument("--start-date", required=True, help="开始日期，格式 YYYYMMDD")
    parser.add_argument("--end-date", required=True, help="结束日期，格式 YYYYMMDD")
    parser.add_argument("--mode", choices=["intraday", "close_confirmed"], default="close_confirmed")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--cache-only", action="store_true", help="预留参数，后续用于限制历史行情只读缓存")
    args = parser.parse_args()

    result = run_watchlist_strategy(
        config_path=args.config,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        mode=args.mode,
        cache_only=args.cache_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
