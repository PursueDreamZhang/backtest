from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MAX_RISK_TO_STOP_PCT = 12.0


@dataclass(frozen=True)
class OpenDecision:
    allowed: bool
    reason: str
    entry_price: float | None = None


@dataclass(frozen=True)
class CloseDecision:
    should_close: bool
    reason: str
    exit_price: float | None = None


def should_open_position(
    signal_row: dict,
    next_open_price: float | None,
    *,
    max_risk_to_stop_pct: float = DEFAULT_MAX_RISK_TO_STOP_PCT,
) -> OpenDecision:
    if signal_row.get("group") != "触发买点":
        return OpenDecision(False, "not_triggered")
    stop_loss = signal_row.get("stop_loss")
    if next_open_price in (None, 0) or stop_loss in (None, 0):
        return OpenDecision(False, "missing_price_or_stop")
    risk_to_stop_pct = (float(next_open_price) / float(stop_loss) - 1.0) * 100.0
    if risk_to_stop_pct > max_risk_to_stop_pct:
        return OpenDecision(False, "too_far_from_stop")
    return OpenDecision(True, "ok", float(next_open_price))


def should_open_position_by_price_touch(
    signal_row: dict,
    market_row: dict | None,
    *,
    max_risk_to_stop_pct: float = DEFAULT_MAX_RISK_TO_STOP_PCT,
) -> OpenDecision:
    if signal_row.get("group") != "触发买点":
        return OpenDecision(False, "not_triggered")
    if market_row is None:
        return OpenDecision(False, "missing_market_data")

    trigger_price = signal_row.get("trigger_price")
    stop_loss = signal_row.get("stop_loss")
    day_low = market_row.get("low")
    day_high = market_row.get("high")
    if trigger_price in (None, 0) or stop_loss in (None, 0) or day_low is None or day_high is None:
        return OpenDecision(False, "missing_price_or_stop")

    trigger_price = float(trigger_price)
    if not (float(day_low) <= trigger_price <= float(day_high)):
        return OpenDecision(False, "trigger_not_touched")

    risk_to_stop_pct = (trigger_price / float(stop_loss) - 1.0) * 100.0
    if risk_to_stop_pct > max_risk_to_stop_pct:
        return OpenDecision(False, "too_far_from_stop")
    return OpenDecision(True, "ok", trigger_price)


def should_close_position(
    position: dict,
    market_row: dict | None,
    latest_signal_row: dict | None,
    *,
    max_hold_days: int,
) -> CloseDecision:
    if market_row is None:
        return CloseDecision(False, "missing_market_data")

    stop_loss = float(position["stop_loss"])
    day_low = market_row.get("low")
    if day_low is not None and float(day_low) <= stop_loss:
        return CloseDecision(True, "stop_loss", stop_loss)

    if latest_signal_row is not None and latest_signal_row.get("group") == "排除观察":
        exit_price = market_row.get("open") or market_row.get("close")
        return CloseDecision(True, "excluded", float(exit_price) if exit_price is not None else None)

    if int(position["holding_days"]) >= max_hold_days:
        exit_price = market_row.get("close")
        return CloseDecision(True, "max_hold_days", float(exit_price) if exit_price is not None else None)

    return CloseDecision(False, "hold")


def should_close_position_tplus1(
    position: dict,
    market_row: dict | None,
    latest_signal_row: dict | None,
    *,
    max_hold_days: int,
) -> CloseDecision:
    if market_row is None:
        return CloseDecision(False, "missing_market_data")

    stop_loss = float(position["stop_loss"])
    if int(position.get("holding_days", 0)) > 0:
        day_open = market_row.get("open")
        if day_open is not None and float(day_open) <= stop_loss:
            return CloseDecision(True, "stop_loss", float(day_open))

        day_low = market_row.get("low")
        if day_low is not None and float(day_low) <= stop_loss:
            return CloseDecision(True, "stop_loss", stop_loss)

    if latest_signal_row is not None and latest_signal_row.get("group") == "排除观察":
        exit_price = market_row.get("open") or market_row.get("close")
        return CloseDecision(True, "excluded", float(exit_price) if exit_price is not None else None)

    if int(position["holding_days"]) >= max_hold_days:
        exit_price = market_row.get("close")
        return CloseDecision(True, "max_hold_days", float(exit_price) if exit_price is not None else None)

    return CloseDecision(False, "hold")


def rank_candidates(signal_rows: list[dict]) -> list[dict]:
    return sorted(
        signal_rows,
        key=lambda row: (
            -int(row.get("score", 0)),
            float(row.get("risk_to_stop_pct") or 999999.0),
            str(row.get("symbol", "")),
        ),
    )
