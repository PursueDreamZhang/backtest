from __future__ import annotations

from dataclasses import dataclass


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


@dataclass
class Position:
    symbol: str
    name: str
    direction: str
    setup: str
    signal_date: str
    entry_date: str
    entry_price: float
    stop_loss: float
    shares: int
    holding_days: int = 0


class Portfolio:
    def __init__(
        self,
        *,
        initial_cash: float,
        fee_rate: float,
        sell_tax_rate: float,
        slippage_rate: float,
    ) -> None:
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.fee_rate = float(fee_rate)
        self.sell_tax_rate = float(sell_tax_rate)
        self.slippage_rate = float(slippage_rate)
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def open_position(
        self,
        *,
        symbol: str,
        name: str,
        direction: str,
        setup: str,
        signal_date: str,
        entry_date: str,
        open_price: float,
        stop_loss: float,
        target_capital: float,
    ) -> bool:
        executed_price = float(open_price) * (1.0 + self.slippage_rate)
        gross_budget = min(float(target_capital), self.cash)
        if gross_budget <= 0 or executed_price <= 0:
            return False
        shares = int(gross_budget / (executed_price * (1.0 + self.fee_rate)))
        if shares <= 0:
            return False
        gross_amount = shares * executed_price
        fee = gross_amount * self.fee_rate
        total_cost = gross_amount + fee
        if total_cost > self.cash:
            return False
        self.cash -= total_cost
        self.positions[symbol] = Position(
            symbol=symbol,
            name=name,
            direction=direction,
            setup=setup,
            signal_date=signal_date,
            entry_date=entry_date,
            entry_price=executed_price,
            stop_loss=float(stop_loss),
            shares=shares,
        )
        return True

    def close_position(
        self,
        symbol: str,
        *,
        exit_date: str,
        exit_price: float,
        exit_reason: str,
    ) -> None:
        position = self.positions.pop(symbol)
        executed_price = float(exit_price) * (1.0 - self.slippage_rate)
        gross_amount = position.shares * executed_price
        fee = gross_amount * self.fee_rate
        tax = gross_amount * self.sell_tax_rate
        net_amount = gross_amount - fee - tax
        self.cash += net_amount

        entry_amount = position.shares * position.entry_price
        entry_fee = entry_amount * self.fee_rate
        cost_basis = entry_amount + entry_fee
        pnl = net_amount - cost_basis
        net_return = pnl / cost_basis if cost_basis else 0.0

        self.trades.append(
            {
                "symbol": position.symbol,
                "name": position.name,
                "direction": position.direction,
                "setup": position.setup,
                "signal_date": position.signal_date,
                "entry_date": position.entry_date,
                "entry_price": round(position.entry_price, 6),
                "stop_loss_at_entry": round(position.stop_loss, 6),
                "exit_date": exit_date,
                "exit_price": round(executed_price, 6),
                "exit_reason": exit_reason,
                "holding_days": position.holding_days,
                "shares": position.shares,
                "gross_pnl": round(pnl, 6),
                "net_return": round(net_return, 6),
            }
        )

    def mark_to_market(self, trade_date: str, close_prices: dict[str, float | None]) -> dict:
        market_value = 0.0
        for symbol, position in self.positions.items():
            price = _safe_float(close_prices.get(symbol), position.entry_price)
            market_value += position.shares * price
        equity = self.cash + market_value
        row = {
            "trade_date": trade_date,
            "cash": round(self.cash, 6),
            "market_value": round(market_value, 6),
            "equity": round(equity, 6),
            "positions": len(self.positions),
        }
        self.equity_curve.append(row)
        return row

