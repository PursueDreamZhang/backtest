from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .etf_universe import EtfUniverseEntry


GENERIC_DIRECTION_TAGS = {
    '市场代理',
    '宽基',
    '核心宽基',
    '核心龙头',
    '大盘蓝筹',
    '大盘龙头',
    '中盘',
    '微盘',
}


def _pct_return(series: pd.Series, window: int) -> pd.Series:
    return series / series.shift(window) - 1.0


def _safe_nanmean(values: list[float]) -> float:
    filtered = [value for value in values if pd.notna(value)]
    if not filtered:
        return np.nan
    return float(np.mean(filtered))


def _build_symbol_tag_map(universe: list[EtfUniverseEntry] | None) -> dict[str, tuple[str, ...]]:
    if not universe:
        return {}
    return {item.symbol: item.tags for item in universe}


def _resolve_leader_directions(
    top: pd.DataFrame,
    symbol_tag_map: dict[str, tuple[str, ...]],
) -> tuple[str | None, str | None, str]:
    if top.empty or not symbol_tag_map:
        return None, None, ''

    scores: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    weights = [5, 4, 3, 2, 1]

    for idx, row in enumerate(top.itertuples(index=False)):
        tags = symbol_tag_map.get(str(row.symbol), ())
        weight = weights[idx] if idx < len(weights) else 1
        for tag in tags:
            if tag in GENERIC_DIRECTION_TAGS:
                continue
            scores[tag] = scores.get(tag, 0) + weight
            first_seen.setdefault(tag, idx)

    if not scores:
        return None, None, ''

    ordered_tags = sorted(scores, key=lambda tag: (-scores[tag], first_seen[tag], tag))
    top1 = ordered_tags[0]
    top2 = ordered_tags[1] if len(ordered_tags) > 1 else None
    summary = ' / '.join(ordered_tags[:3])
    return top1, top2, summary


def _classify_market_stage(
    market_stage_score: float,
    trend_score: float,
    breadth_close_above_short: float,
    cooldown_risk: float,
) -> str:
    is_retreat = cooldown_risk >= 0.08 and (
        trend_score <= 0.5 or breadth_close_above_short <= 0.20
    )

    if market_stage_score >= 0.75 and cooldown_risk < 0.08:
        return '主升'
    if is_retreat:
        return '退潮'
    if market_stage_score >= 0.60 and cooldown_risk < 0.12:
        return '启动'
    return '混沌'


def build_composite_benchmark(
    frames: dict[str, pd.DataFrame],
    market_proxy_symbols: list[str],
) -> pd.DataFrame:
    normalized_frames: list[pd.DataFrame] = []
    for symbol in market_proxy_symbols:
        frame = frames[symbol].copy().sort_index()
        if frame.empty:
            continue

        base_close = frame['close'].dropna().iloc[0]
        if pd.isna(base_close) or base_close == 0:
            continue

        normalized = frame[['open', 'high', 'low', 'close', 'volume']].copy()
        for column in ['open', 'high', 'low', 'close']:
            normalized[column] = normalized[column] / base_close
        normalized_frames.append(normalized)

    if not normalized_frames:
        raise ValueError('至少需要一个有效的 market proxy 用于构造 composite benchmark')

    combined = pd.concat(normalized_frames, keys=range(len(normalized_frames)), names=['proxy_id', 'date'])
    benchmark = combined.groupby('date').agg(
        {
            'open': 'mean',
            'high': 'mean',
            'low': 'mean',
            'close': 'mean',
            'volume': 'mean',
        }
    )
    return benchmark.sort_index()


def build_feature_table(
    frames: dict[str, pd.DataFrame],
    benchmark_frame: pd.DataFrame,
    params: dict[str, Any],
) -> pd.DataFrame:
    benchmark = benchmark_frame.copy().sort_index()
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
            daily_return = work['close'].pct_change().loc[date]
            open_to_close_return = (
                work['close'].loc[date] / work['open'].loc[date] - 1.0
                if pd.notna(work['open'].loc[date]) and work['open'].loc[date] != 0
                else np.nan
            )
            high_to_close_gap = (
                work['high'].loc[date] / work['close'].loc[date] - 1.0
                if pd.notna(work['close'].loc[date]) and work['close'].loc[date] != 0
                else np.nan
            )
            row['daily_return'] = daily_return
            row['daily_return_pct'] = daily_return * 100 if pd.notna(daily_return) else np.nan
            row['open_to_close_return'] = open_to_close_return
            row['high_to_close_gap'] = high_to_close_gap

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
            row['volume_price_score_raw'] = vol_ratio
            row['trend_support_score'] = float(
                work['close'].loc[date] > work['ma_short'].loc[date]
            ) + float(work['ma_short'].loc[date] > work['ma_long'].loc[date])
            row['trend_support_score_raw'] = row['trend_support_score']
            row['stability_score'] = 0.0
            rows.append(row)

    feature_table = pd.DataFrame(rows).dropna().sort_values(['date', 'symbol']).reset_index(drop=True)
    return feature_table


def build_leaderboard(feature_table: pd.DataFrame, params: dict[str, Any] | None = None) -> pd.DataFrame:
    work = feature_table.copy()
    weights = (
        params.get('weights')
        if params and params.get('weights')
        else {
            'relative_strength_score': 0.30,
            'momentum_score': 0.25,
            'volume_price_score': 0.25,
            'trend_support_score': 0.10,
            'stability_score': 0.10,
        }
    )
    for column in weights:
        work[f'{column}_raw'] = work[column]
        work[column] = work.groupby('date')[column].rank(pct=True)

    work['composite_score'] = sum(work[column] * weight for column, weight in weights.items())
    work['rank'] = work.groupby('date')['composite_score'].rank(method='first', ascending=False)
    work['is_leader_candidate'] = work['rank'] <= 5
    return work


def build_daily_state(
    frames: dict[str, pd.DataFrame],
    leaderboard: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    params: dict[str, Any],
    universe: list[EtfUniverseEntry] | None = None,
) -> pd.DataFrame:
    del frames

    benchmark = benchmark_frame.copy().sort_index()
    benchmark['ma_short'] = benchmark['close'].rolling(params['short_ma']).mean()
    benchmark['ma_long'] = benchmark['close'].rolling(params['long_ma']).mean()
    benchmark['ret_10'] = benchmark['close'].pct_change(10)
    benchmark['ret_20'] = benchmark['close'].pct_change(20)
    benchmark['dd_10'] = benchmark['close'] / benchmark['close'].rolling(10).max() - 1.0
    symbol_tag_map = _build_symbol_tag_map(universe)

    states = []
    for date, group in leaderboard.groupby('date'):
        top = group.sort_values('rank').head(5).reset_index(drop=True)
        breadth_close_above_short = float((group['trend_support_score_raw'] > 1.0).mean())
        volume_confirmation = float((group['volume_price_score_raw'] > 1.0).mean())
        trend_score = (
            float(benchmark.loc[date, 'close'] > benchmark.loc[date, 'ma_short'])
            + float(benchmark.loc[date, 'ma_short'] > benchmark.loc[date, 'ma_long'])
        ) / 2.0
        cooldown_risk = float(abs(min(benchmark.loc[date, 'dd_10'], 0.0)))
        leader_gap = float(top.iloc[0]['composite_score'] - top.iloc[1]['composite_score']) if len(top) > 1 else 0.0
        leader_stability = float(top['symbol'].nunique() <= 5)
        leader_direction_top1, leader_direction_top2, leader_direction_summary = _resolve_leader_directions(
            top,
            symbol_tag_map,
        )
        market_stage_score = (
            trend_score * params['market_weights']['trend']
            + breadth_close_above_short * params['market_weights']['breadth']
            + volume_confirmation * params['market_weights']['volume_confirmation']
            + (1.0 - cooldown_risk) * params['market_weights']['cooldown_risk']
        )

        stage = _classify_market_stage(
            market_stage_score=market_stage_score,
            trend_score=trend_score,
            breadth_close_above_short=breadth_close_above_short,
            cooldown_risk=cooldown_risk,
        )

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
                'leader_etf_top4': top.iloc[3]['symbol'] if len(top) > 3 else None,
                'leader_etf_top5': top.iloc[4]['symbol'] if len(top) > 4 else None,
                'leader_direction_top1': leader_direction_top1,
                'leader_direction_top2': leader_direction_top2,
                'leader_direction_summary': leader_direction_summary,
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
