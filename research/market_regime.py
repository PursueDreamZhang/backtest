from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _pct_return(series: pd.Series, window: int) -> pd.Series:
    return series / series.shift(window) - 1.0


def _safe_nanmean(values: list[float]) -> float:
    filtered = [value for value in values if pd.notna(value)]
    if not filtered:
        return np.nan
    return float(np.mean(filtered))


def build_feature_table(
    frames: dict[str, pd.DataFrame],
    benchmark_symbol: str,
    params: dict[str, Any],
) -> pd.DataFrame:
    benchmark = frames[benchmark_symbol].copy().sort_index()
    benchmark_returns = {
        window: _pct_return(benchmark['close'], window)
        for window in params['relative_strength_windows']
    }

    rows: list[dict[str, Any]] = []
    for symbol, df in frames.items():
        work = df.copy().sort_index()
        work['ma_short'] = work['close'].rolling(params['short_ma']).mean()
        work['ma_long'] = work['close'].rolling(params['long_ma']).mean()
        work['vol_short'] = work['volume'].rolling(params['short_volume_window']).mean()
        work['vol_long'] = work['volume'].rolling(params['long_volume_window']).mean()

        relative_returns = {
            window: _pct_return(work['close'], window).reindex(work.index) - benchmark_returns[window].reindex(work.index)
            for window in params['relative_strength_windows']
        }
        momentum_returns = {
            window: _pct_return(work['close'], window)
            for window in params['momentum_windows']
        }

        for date in work.index:
            row = {'date': date, 'symbol': symbol}

            rs_values = []
            for window, series in relative_returns.items():
                value = series.loc[date]
                row[f'rs_{window}'] = value
                rs_values.append(value)
            row['relative_strength_score'] = _safe_nanmean(rs_values)

            mom_values = []
            for window, series in momentum_returns.items():
                value = series.loc[date]
                row[f'mom_{window}'] = value
                mom_values.append(value)
            row['momentum_score'] = _safe_nanmean(mom_values)

            vol_long = work['vol_long'].loc[date]
            vol_ratio = work['vol_short'].loc[date] / vol_long if pd.notna(vol_long) and vol_long != 0 else np.nan
            row['volume_price_score'] = vol_ratio
            row['trend_support_score'] = float(
                work['close'].loc[date] > work['ma_short'].loc[date]
            ) + float(work['ma_short'].loc[date] > work['ma_long'].loc[date])
            row['stability_score'] = 0.0
            rows.append(row)

    feature_table = pd.DataFrame(rows).dropna().sort_values(['date', 'symbol']).reset_index(drop=True)
    return feature_table


def build_leaderboard(feature_table: pd.DataFrame) -> pd.DataFrame:
    work = feature_table.copy()
    weights = {
        'relative_strength_score': 0.30,
        'momentum_score': 0.25,
        'volume_price_score': 0.25,
        'trend_support_score': 0.10,
        'stability_score': 0.10,
    }
    for column in weights:
        work[column] = work.groupby('date')[column].rank(pct=True)

    work['composite_score'] = sum(work[column] * weight for column, weight in weights.items())
    work['rank'] = work.groupby('date')['composite_score'].rank(method='first', ascending=False)
    work['is_leader_candidate'] = work['rank'] <= 3
    return work


def build_daily_state(
    frames: dict[str, pd.DataFrame],
    leaderboard: pd.DataFrame,
    benchmark_symbol: str,
    params: dict[str, Any],
) -> pd.DataFrame:
    benchmark = frames[benchmark_symbol].copy().sort_index()
    benchmark['ma_short'] = benchmark['close'].rolling(params['short_ma']).mean()
    benchmark['ma_long'] = benchmark['close'].rolling(params['long_ma']).mean()
    benchmark['ret_10'] = benchmark['close'].pct_change(10)
    benchmark['ret_20'] = benchmark['close'].pct_change(20)
    benchmark['dd_10'] = benchmark['close'] / benchmark['close'].rolling(10).max() - 1.0

    states = []
    for date, group in leaderboard.groupby('date'):
        top = group.sort_values('rank').head(3).reset_index(drop=True)
        breadth_close_above_short = float((group['trend_support_score'] > 0.5).mean())
        volume_confirmation = float((group['volume_price_score'] > 0.5).mean())
        trend_score = float(
            (benchmark.loc[date, 'close'] > benchmark.loc[date, 'ma_short'])
            + (benchmark.loc[date, 'ma_short'] > benchmark.loc[date, 'ma_long'])
        ) / 2.0
        cooldown_risk = float(abs(min(benchmark.loc[date, 'dd_10'], 0.0)))
        leader_gap = float(top.iloc[0]['composite_score'] - top.iloc[1]['composite_score']) if len(top) > 1 else 0.0
        leader_stability = float(top['symbol'].nunique() <= 3)
        market_stage_score = (
            trend_score * params['market_weights']['trend']
            + breadth_close_above_short * params['market_weights']['breadth']
            + volume_confirmation * params['market_weights']['volume_confirmation']
            + (1.0 - cooldown_risk) * params['market_weights']['cooldown_risk']
        )

        if market_stage_score >= 0.75 and cooldown_risk < 0.08:
            stage = '主升'
        elif market_stage_score >= 0.60 and cooldown_risk < 0.12:
            stage = '启动'
        elif cooldown_risk >= 0.15:
            stage = '退潮'
        else:
            stage = '混沌'

        can_open = stage in {'启动', '主升'} and leader_gap > 0.02
        states.append(
            {
                'date': date,
                'market_stage': stage,
                'market_stage_score': market_stage_score,
                'market_trend_score': trend_score,
                'market_breadth_score': breadth_close_above_short,
                'volume_confirmation_score': volume_confirmation,
                'cooldown_risk_score': cooldown_risk,
                'leader_etf_top1': top.iloc[0]['symbol'],
                'leader_etf_top2': top.iloc[1]['symbol'] if len(top) > 1 else None,
                'leader_etf_top3': top.iloc[2]['symbol'] if len(top) > 2 else None,
                'leader_strength_score': float(top.iloc[0]['composite_score']),
                'leader_gap_score': leader_gap,
                'leader_stability_score': leader_stability,
                'can_open_new_position': can_open,
                'open_position_reason': (
                    'stage_ok_and_leader_gap_positive'
                    if can_open
                    else 'stage_or_leader_gap_not_enough'
                ),
            }
        )
    return pd.DataFrame(states).sort_values('date').reset_index(drop=True)


def build_summary(
    daily_state: pd.DataFrame,
    leaderboard: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    forward_windows: list[int],
) -> dict[str, Any]:
    del leaderboard
    del benchmark_frame
    del forward_windows

    summary: dict[str, Any] = {'stages': {}, 'open_signal': {}, 'leader_switch_count': 0}

    top1_series = daily_state['leader_etf_top1'].fillna('')
    summary['leader_switch_count'] = int((top1_series != top1_series.shift(1)).sum())

    for stage, group in daily_state.groupby('market_stage'):
        summary['stages'][stage] = {'count': int(len(group))}

    for flag, group in daily_state.groupby('can_open_new_position'):
        summary['open_signal'][str(bool(flag))] = {'count': int(len(group))}

    return summary
