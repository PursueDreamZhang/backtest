from __future__ import annotations

from typing import Any

import pandas as pd

from .etf_universe import EtfUniverseEntry


def summarize_latest_state(
    daily_state: pd.DataFrame,
    leaderboard: pd.DataFrame,
    universe: list[EtfUniverseEntry],
) -> dict[str, Any]:
    if daily_state.empty:
        raise ValueError('daily_state 为空，无法生成摘要')

    latest_row = daily_state.copy()
    latest_row['date'] = pd.to_datetime(latest_row['date'])
    latest_row = latest_row.sort_values('date').iloc[-1]
    latest_date = latest_row['date'].strftime('%Y-%m-%d')

    universe_map = {item.symbol: item for item in universe}
    latest_board = leaderboard[leaderboard['date'] == latest_date].sort_values('rank').head(5)

    top5: list[dict[str, Any]] = []
    for row in latest_board.itertuples(index=False):
        item = universe_map.get(str(row.symbol))
        top5.append(
            {
                'rank': int(row.rank),
                'symbol': str(row.symbol),
                'name': item.name if item else str(row.symbol),
                'tags': list(item.tags) if item else [],
                'composite_score': float(row.composite_score),
                'daily_return': float(getattr(row, 'daily_return', 0.0)),
                'daily_return_pct': float(getattr(row, 'daily_return_pct', 0.0)),
                'open_to_close_return': float(getattr(row, 'open_to_close_return', 0.0)),
                'high_to_close_gap': float(getattr(row, 'high_to_close_gap', 0.0)),
            }
        )

    return {
        'date': latest_date,
        'market_stage': str(latest_row['market_stage']),
        'market_stage_score': float(latest_row['market_stage_score']),
        'can_open_new_position': bool(latest_row['can_open_new_position']),
        'open_position_reason': str(latest_row['open_position_reason']),
        'leader_direction_top1': str(latest_row.get('leader_direction_top1') or ''),
        'leader_direction_top2': str(latest_row.get('leader_direction_top2') or ''),
        'leader_direction_summary': str(latest_row.get('leader_direction_summary') or ''),
        'top5': top5,
    }
