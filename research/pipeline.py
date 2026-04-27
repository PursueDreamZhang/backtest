from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data_loader import load_symbol_frames
from .etf_universe import load_etf_universe
from .market_regime import (
    build_composite_benchmark,
    build_daily_state,
    build_feature_table,
    build_leaderboard,
    build_summary,
)
from .settings import MARKET_REGIME_PARAMS


def run_research(
    universe_path: str,
    output_dir: str,
    start_date: str,
    end_date: str,
    *,
    params: dict[str, Any] | None = None,
):
    active_params = dict(MARKET_REGIME_PARAMS)
    if params:
        active_params.update(params)

    universe = load_etf_universe(universe_path)
    symbols = [item.symbol for item in universe]
    market_proxies = [item.symbol for item in universe if item.is_market_proxy]
    if not market_proxies:
        raise ValueError('ETF universe 中至少需要一个 is_market_proxy=true 的标的')

    frames = load_symbol_frames(symbols, start_date, end_date)
    benchmark_frame = build_composite_benchmark(frames, market_proxies)
    features = build_feature_table(frames, benchmark_frame=benchmark_frame, params=active_params)
    leaderboard = build_leaderboard(features, params=active_params)
    daily_state = build_daily_state(
        frames,
        leaderboard,
        benchmark_frame=benchmark_frame,
        params=active_params,
        universe=universe,
    )
    summary = build_summary(
        daily_state,
        leaderboard,
        benchmark_frame,
        active_params['forward_windows'],
    )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    daily_state_path = output / 'daily_state.csv'
    leaderboard_path = output / 'leaderboard.csv'
    summary_path = output / 'summary.json'

    daily_state.to_csv(daily_state_path, index=False)
    leaderboard.to_csv(leaderboard_path, index=False)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'daily_state_path': str(daily_state_path),
        'leaderboard_path': str(leaderboard_path),
        'summary_path': str(summary_path),
    }
