#!/bin/sh

set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
CONFIG_PATH="${CONFIG_PATH:-$PROJECT_ROOT/config/watchlists.json}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
OUTPUT_BASE="${OUTPUT_BASE:-$PROJECT_ROOT/tmp}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "配置文件不存在: $CONFIG_PATH" >&2
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python 不可执行: $PYTHON_BIN" >&2
  exit 1
fi

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  shift
fi

if [ "$#" -gt 0 ]; then
  echo "用法: sh scripts/run_watchlist_today.sh [--dry-run]" >&2
  exit 1
fi

TODAY="$(date '+%Y%m%d')"
NOW_HM="$(date '+%H%M')"
WEEKDAY="$(date '+%u')"
START_DATE="${START_DATE:-$(date -v-180d '+%Y%m%d')}"
END_DATE="${END_DATE:-$TODAY}"

MODE="close_confirmed"
OUTPUT_DIR="$OUTPUT_BASE/watchlists_close_${END_DATE}"

if [ "$WEEKDAY" -le 5 ]; then
  if [ "$NOW_HM" -ge 0915 ] && [ "$NOW_HM" -lt 1130 ]; then
    MODE="intraday"
  elif [ "$NOW_HM" -ge 1300 ] && [ "$NOW_HM" -lt 1500 ]; then
    MODE="intraday"
  fi
fi

if [ "$MODE" = "intraday" ]; then
  OUTPUT_DIR="$OUTPUT_BASE/watchlists_intraday_${END_DATE}_${NOW_HM}"
fi

CMD="$PYTHON_BIN scripts/run_watchlist_strategy.py --config $CONFIG_PATH --start-date $START_DATE --end-date $END_DATE --mode $MODE --output-dir $OUTPUT_DIR"

echo "模式: $MODE"
echo "开始日期: $START_DATE"
echo "结束日期: $END_DATE"
echo "输出目录: $OUTPUT_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run:"
  echo "$CMD"
  exit 0
fi

cd "$PROJECT_ROOT"
"$PYTHON_BIN" scripts/run_watchlist_strategy.py \
  --config "$CONFIG_PATH" \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --mode "$MODE" \
  --output-dir "$OUTPUT_DIR"

echo
echo "总览页面: $OUTPUT_DIR/overview.html"
