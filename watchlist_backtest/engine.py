from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime

import pandas as pd

from .portfolio import Portfolio
from .reporting import build_summary, write_backtest_reports
from .rules import rank_candidates, should_close_position, should_open_position
from .signal_diary import build_signal_diary


def _trade_calendar(frames: dict[str, pd.DataFrame], start_date: str, end_date: str) -> list[str]:
    dates: set[str] = set()
    for frame in frames.values():
        for trade_dt in frame.index:
            trade_date = pd.Timestamp(trade_dt).strftime("%Y%m%d")
            if start_date <= trade_date <= end_date:
                dates.add(trade_date)
    return sorted(dates)


def _market_row(frame: pd.DataFrame, trade_date: str) -> dict | None:
    ts = pd.Timestamp(f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}")
    if ts not in frame.index:
        return None
    row = frame.loc[ts]
    return {key: (float(value) if pd.notna(value) else None) for key, value in row.items()}


def run_watchlist_backtest(
    *,
    config_path: str,
    start_date: str,
    end_date: str,
    output_dir: str,
    initial_cash: float = 1_000_000,
    max_positions: int = 8,
    position_size_pct: float = 0.10,
    max_hold_days: int = 10,
    fee_rate: float = 0.0003,
    sell_tax_rate: float = 0.001,
    slippage_rate: float = 0.002,
) -> dict[str, str]:
    signal_diary, frames = build_signal_diary(config_path, start_date, end_date)
    calendar = _trade_calendar(frames, start_date, end_date)
    signal_by_date: dict[str, list[dict]] = defaultdict(list)
    signal_by_date_symbol: dict[tuple[str, str], dict] = {}
    for row in signal_diary.to_dict("records"):
        signal_by_date[row["trade_date"]].append(row)
        signal_by_date_symbol[(row["trade_date"], row["symbol"])] = row

    portfolio = Portfolio(
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        sell_tax_rate=sell_tax_rate,
        slippage_rate=slippage_rate,
    )

    for trade_index, trade_date in enumerate(calendar):
        # First process exits using current-day data.
        for symbol in list(portfolio.positions.keys()):
            position = portfolio.positions[symbol]
            position.holding_days += 1
            market = _market_row(frames[symbol], trade_date)
            latest_signal = signal_by_date_symbol.get((trade_date, symbol))
            decision = should_close_position(
                asdict(position),
                market,
                latest_signal,
                max_hold_days=max_hold_days,
            )
            if decision.should_close and decision.exit_price is not None:
                portfolio.close_position(
                    symbol,
                    exit_date=trade_date,
                    exit_price=float(decision.exit_price),
                    exit_reason=decision.reason,
                )

        # Then process entries from previous signal day at today's open.
        if trade_index > 0:
            prev_trade_date = calendar[trade_index - 1]
            candidates: list[tuple[dict, float]] = []
            for signal_row in signal_by_date.get(prev_trade_date, []):
                symbol = signal_row["symbol"]
                if portfolio.has_position(symbol):
                    continue
                market = _market_row(frames[symbol], trade_date)
                next_open = None if market is None else market.get("open")
                decision = should_open_position(signal_row, next_open)
                if decision.allowed:
                    candidates.append((signal_row, float(next_open)))

            available_slots = max(0, max_positions - len(portfolio.positions))
            target_capital = initial_cash * position_size_pct
            open_price_by_symbol = {
                candidate_row["symbol"]: open_price for candidate_row, open_price in candidates
            }
            ranked_candidates = rank_candidates([item[0] for item in candidates])[:available_slots]
            for signal_row in ranked_candidates:
                market_open = open_price_by_symbol[signal_row["symbol"]]
                portfolio.open_position(
                    symbol=signal_row["symbol"],
                    name=signal_row["name"],
                    direction=signal_row["direction"],
                    setup=signal_row["setup"],
                    signal_date=prev_trade_date,
                    entry_date=trade_date,
                    open_price=market_open,
                    stop_loss=float(signal_row["stop_loss"]),
                    target_capital=target_capital,
                )

        close_prices = {}
        for symbol, frame in frames.items():
            market = _market_row(frame, trade_date)
            close_prices[symbol] = None if market is None else market.get("close")
        portfolio.mark_to_market(trade_date, close_prices)

    trades_df = pd.DataFrame(portfolio.trades)
    equity_curve_df = pd.DataFrame(portfolio.equity_curve)
    summary = build_summary(trades_df, equity_curve_df, signal_diary, initial_cash=initial_cash)
    return write_backtest_reports(
        output_dir=output_dir,
        trades=trades_df,
        equity_curve=equity_curve_df,
        signal_diary=signal_diary,
        summary=summary,
    )
