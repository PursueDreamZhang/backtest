from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.pipeline import run_research


def main():
    parser = argparse.ArgumentParser(description='运行市场阶段与主线 ETF 离线研究')
    parser.add_argument('--universe', required=True, help='ETF 代理池配置文件')
    parser.add_argument('--start-date', required=True, help='开始日期，格式 YYYYMMDD')
    parser.add_argument('--end-date', required=True, help='结束日期，格式 YYYYMMDD')
    parser.add_argument('--output-dir', required=True, help='输出目录')
    args = parser.parse_args()

    result = run_research(
        universe_path=args.universe,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
