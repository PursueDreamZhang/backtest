from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import pandas as pd

from .indicators import enrich_daily_indicators


@dataclass(frozen=True)
class SignalResult:
    symbol: str
    name: str
    instrument_type: str
    mode: str
    group: str
    signal_timing: str
    confidence: str
    score: int
    setup: str
    latest_price: float
    support: float | None
    stop_loss: float | None
    risk_to_stop_pct: float | None
    signals: tuple[str, ...]
    action: str
    invalid_if: str
    needs_close_confirmation: tuple[str, ...] = ()


def _finite(value: Any) -> bool:
    return value is not None and pd.notna(value) and math.isfinite(float(value))


def _risk_to_stop_pct(price: float, stop_loss: float | None) -> float | None:
    if stop_loss in (None, 0):
        return None
    return (price / stop_loss - 1.0) * 100


def _pct_change(price: float | None, base: float | None) -> float | None:
    if not _finite(price) or not _finite(base) or float(base) == 0:
        return None
    return float(price) / float(base) - 1.0


def _stop_loss_for(instrument_type: str, support: float | None) -> float | None:
    if support is None:
        return None
    if instrument_type == "etf":
        return support * 0.97
    return support * 0.94


def _result(
    *,
    symbol: str,
    name: str,
    instrument_type: str,
    mode: str,
    group: str,
    score: int,
    setup: str,
    latest_price: float,
    support: float | None,
    stop_loss: float | None,
    signals: list[str],
    action: str,
    invalid_if: str,
    needs_close_confirmation: tuple[str, ...] = (),
) -> SignalResult:
    confidence = "provisional" if mode == "intraday" else "confirmed"
    signal_timing = "intraday" if mode == "intraday" else "close_confirmed"
    return SignalResult(
        symbol=symbol,
        name=name,
        instrument_type=instrument_type,
        mode=mode,
        group=group,
        signal_timing=signal_timing,
        confidence=confidence,
        score=score,
        setup=setup,
        latest_price=float(latest_price),
        support=float(support) if support is not None else None,
        stop_loss=float(stop_loss) if stop_loss is not None else None,
        risk_to_stop_pct=_risk_to_stop_pct(float(latest_price), stop_loss),
        signals=tuple(signals),
        action=action,
        invalid_if=invalid_if,
        needs_close_confirmation=needs_close_confirmation,
    )


def _latest_values(frame: pd.DataFrame, mode: str, realtime_quote: dict | None) -> dict[str, float | None]:
    latest = frame.iloc[-1]
    if mode == "intraday":
        if realtime_quote is None:
            raise ValueError("intraday mode requires realtime_quote")
        return {
            "price": realtime_quote.get("price"),
            "open": realtime_quote.get("open"),
            "high": realtime_quote.get("high"),
            "low": realtime_quote.get("low"),
            "previous_close": realtime_quote.get("previous_close"),
            "volume": realtime_quote.get("volume"),
            "ma5": latest.get("ma5"),
            "ma20": latest.get("ma20"),
            "ma40": latest.get("ma40"),
            "vol20": latest.get("vol20"),
            "high20": latest.get("high20"),
            "low60": latest.get("low60"),
        }
    return {
        "price": latest.get("close"),
        "open": latest.get("open"),
        "high": latest.get("high"),
        "low": latest.get("low"),
        "previous_close": frame.iloc[-2].get("close") if len(frame) >= 2 else None,
        "volume": latest.get("volume"),
        "ma5": latest.get("ma5"),
        "ma20": latest.get("ma20"),
        "ma40": latest.get("ma40"),
        "vol20": latest.get("vol20"),
        "high20": latest.get("high20"),
        "low60": latest.get("low60"),
    }


def evaluate_symbol(
    *,
    symbol: str,
    name: str,
    instrument_type: str,
    frame: pd.DataFrame,
    mode: str,
    realtime_quote: dict | None = None,
) -> SignalResult:
    if frame is None or len(frame) < 60:
        return _result(
            symbol=symbol,
            name=name,
            instrument_type=instrument_type,
            mode=mode,
            group="数据不足",
            score=0,
            setup="历史数据不足",
            latest_price=0.0,
            support=None,
            stop_loss=None,
            signals=("历史数据不足 60 个交易日",),
            action="跳过正式筛选",
            invalid_if="补齐历史数据后重新评估",
        )

    enriched = enrich_daily_indicators(frame)
    values = _latest_values(enriched, mode, realtime_quote)
    price = values["price"]
    ma5 = values["ma5"]
    ma20 = values["ma20"]
    ma40 = values["ma40"]
    previous_close = values["previous_close"]
    volume = values["volume"]
    vol20 = values["vol20"]

    if not _finite(price):
        return _result(
            symbol=symbol,
            name=name,
            instrument_type=instrument_type,
            mode=mode,
            group="数据不足",
            score=0,
            setup="价格数据缺失",
            latest_price=0.0,
            support=None,
            stop_loss=None,
            signals=("最新价格缺失",),
            action="跳过正式筛选",
            invalid_if="补齐行情数据后重新评估",
        )

    price = float(price)
    support = float(ma40) if _finite(ma40) else None
    stop_loss = _stop_loss_for(instrument_type, support)
    signals: list[str] = []

    if stop_loss is not None and price < stop_loss:
        group = "盘中失效" if mode == "intraday" else "排除观察"
        return _result(
            symbol=symbol,
            name=name,
            instrument_type=instrument_type,
            mode=mode,
            group=group,
            score=25,
            setup="跌破关键支撑",
            latest_price=price,
            support=support,
            stop_loss=stop_loss,
            signals=["价格跌破止损位"],
            action="收盘不能收回支撑则排除",
            invalid_if=f"价格跌破 {stop_loss:.3f}",
            needs_close_confirmation=("收盘是否收回支撑位",) if mode == "intraday" else (),
        )

    ma40_near = support is not None and support * 0.98 <= price <= support * 1.03
    drawdown20 = enriched.iloc[-1].get("drawdown20")
    had_pullback = _finite(drawdown20) and float(drawdown20) <= -0.05
    shrink_volume = _finite(volume) and _finite(vol20) and float(volume) <= float(vol20) * 0.9
    turn_up = False
    if _finite(ma5) and price > float(ma5):
        turn_up = True
    if _finite(previous_close) and price > float(previous_close):
        turn_up = True

    if ma40_near and had_pullback and shrink_volume:
        signals.extend(
            [
                "价格进入 MA40 附近",
                "近20日经历过至少5%回撤",
                "成交量低于近20日均量",
            ]
        )
        if turn_up:
            group = "盘中触发" if mode == "intraday" else "触发买点"
            return _result(
                symbol=symbol,
                name=name,
                instrument_type=instrument_type,
                mode=mode,
                group=group,
                score=86 if mode == "close_confirmed" else 82,
                setup="MA40 弹簧压紧后松开",
                latest_price=price,
                support=support,
                stop_loss=stop_loss,
                signals=signals + ["价格重新转强"],
                action="优先盯盘；高开过多不追",
                invalid_if=f"跌破 {stop_loss:.3f}" if stop_loss is not None else "跌破关键支撑",
                needs_close_confirmation=("收盘是否站上 MA5", "全天成交量是否满足条件") if mode == "intraday" else (),
            )
        group = "盘中预警" if mode == "intraday" else "重点观察"
        return _result(
            symbol=symbol,
            name=name,
            instrument_type=instrument_type,
            mode=mode,
            group=group,
            score=74,
            setup="MA40 弹簧压紧",
            latest_price=price,
            support=support,
            stop_loss=stop_loss,
            signals=signals,
            action="等待重新站上 MA5 或放量转强",
            invalid_if=f"跌破 {stop_loss:.3f}" if stop_loss is not None else "跌破关键支撑",
        )

    # MA20 first pullback fallback.
    if _finite(ma20) and _finite(ma40) and float(ma20) > float(ma40):
        ma20_price = float(ma20)
        near_ma20 = ma20_price * 0.97 <= price <= ma20_price * 1.03
        if near_ma20:
            group = "盘中触发" if mode == "intraday" and turn_up else "盘中预警" if mode == "intraday" else "重点观察"
            return _result(
                symbol=symbol,
                name=name,
                instrument_type=instrument_type,
                mode=mode,
                group=group,
                score=72,
                setup="MA20 第一次回档",
                latest_price=price,
                support=ma20_price,
                stop_loss=ma20_price * 0.95,
                signals=["MA20 高于 MA40", "价格进入 MA20 附近"],
                action="等待右侧确认" if "预警" in group or group == "重点观察" else "盘中优先盯",
                invalid_if=f"跌破 {ma20_price * 0.95:.3f}",
                needs_close_confirmation=("收盘是否站上 MA5",) if mode == "intraday" else (),
            )

    # Launch candle after range compression.
    prior20 = enriched.iloc[-21:-1] if len(enriched) >= 21 else pd.DataFrame()
    if not prior20.empty:
        range_compressed = (prior20["high"].max() / prior20["low"].min() - 1.0) <= 0.15
        day_return = _pct_change(price, previous_close)
        volume_expand = _finite(volume) and _finite(enriched.iloc[-1].get("vol5")) and float(volume) >= float(enriched.iloc[-1].get("vol5")) * 1.5
        prior_high20 = float(prior20["high"].max())
        price_breakout = price > prior_high20
        if range_compressed and day_return is not None and day_return >= 0.05 and volume_expand and price_breakout:
            group = "盘中触发" if mode == "intraday" else "触发买点"
            support = float(prior20["low"].min())
            stop_loss = support
            return _result(
                symbol=symbol,
                name=name,
                instrument_type=instrument_type,
                mode=mode,
                group=group,
                score=80,
                setup="整理后第一根启动阳线",
                latest_price=price,
                support=support,
                stop_loss=stop_loss,
                signals=["近20日振幅收敛", "涨幅超过5%", "放量突破近20日高点"],
                action="轻仓试错，等待确认延续",
                invalid_if="启动阳线实体被吞没或跌回平台",
                needs_close_confirmation=("收盘是否突破平台", "全天成交量是否放大") if mode == "intraday" else (),
            )

    # Double-bottom / second compression.
    last60 = enriched.tail(60)
    if len(last60) >= 40:
        first_half = last60.iloc[:30]
        second_half = last60.iloc[30:]
        first_low = float(first_half["low"].min())
        second_low = float(second_half["low"].min())
        second_low_holds = second_low >= first_low * 0.97
        recovers_ma5 = _finite(ma5) and price > float(ma5)
        no_heavy_break = True
        if _finite(vol20):
            recent = enriched.tail(10).copy()
            daily_drop = recent["close"].pct_change()
            no_heavy_break = not bool(((daily_drop <= -0.03) & (recent["volume"] >= float(vol20) * 1.3)).any())
        if second_low_holds and recovers_ma5 and no_heavy_break:
            group = "盘中触发" if mode == "intraday" else "触发买点"
            support = second_low
            stop_loss = support * 0.97
            return _result(
                symbol=symbol,
                name=name,
                instrument_type=instrument_type,
                mode=mode,
                group=group,
                score=82,
                setup="双底或二次压紧",
                latest_price=price,
                support=support,
                stop_loss=stop_loss,
                signals=["第二个低点未有效跌破第一个低点", "价格重新站上 MA5"],
                action="依托双底低点观察右侧延续",
                invalid_if=f"跌破 {stop_loss:.3f}",
                needs_close_confirmation=("收盘是否站上 MA5",) if mode == "intraday" else (),
            )

    group = "盘中等待" if mode == "intraday" else "等待回调"
    return _result(
        symbol=symbol,
        name=name,
        instrument_type=instrument_type,
        mode=mode,
        group=group,
        score=50,
        setup="尚未进入买点区域",
        latest_price=price,
        support=support,
        stop_loss=stop_loss,
        signals=["未满足核心买点模型"],
        action="等待回到 MA20、MA40 或前低支撑附近",
        invalid_if="跌破关键支撑或进入下降通道",
    )
