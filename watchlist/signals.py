from __future__ import annotations

from dataclasses import dataclass, replace
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


TRIGGER_GROUPS = {"盘中触发", "触发买点"}
FOCUS_GROUPS = {"盘中预警", "重点观察"}
WAIT_GROUPS = {"盘中等待", "等待回调"}
TRIGGER_TO_FOCUS = {"盘中触发": "盘中预警", "触发买点": "重点观察"}
TRIGGER_OR_FOCUS_TO_WAIT = {
    "盘中触发": "盘中等待",
    "触发买点": "等待回调",
    "盘中预警": "盘中等待",
    "重点观察": "等待回调",
}


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


def _avg_volume(frame: pd.DataFrame, start: int, end: int) -> float | None:
    window = frame.iloc[start:end]
    if window.empty:
        return None
    value = window["volume"].mean()
    if not _finite(value):
        return None
    return float(value)


def _is_local_trough(frame: pd.DataFrame, index: int, span: int = 2) -> bool:
    start = max(0, index - span)
    end = min(len(frame), index + span + 1)
    center = float(frame.iloc[index]["low"])
    window = frame.iloc[start:end]["low"]
    return center == float(window.min())


def _count_true_clusters(flags: list[bool]) -> int:
    clusters = 0
    in_cluster = False
    for flag in flags:
        if flag and not in_cluster:
            clusters += 1
            in_cluster = True
        elif not flag:
            in_cluster = False
    return clusters


def _double_bottom_candidate(frame: pd.DataFrame) -> dict[str, float | int] | None:
    last60 = frame.tail(60).reset_index(drop=True)
    if len(last60) < 40:
        return None

    best: dict[str, float | int] | None = None
    last_index = len(last60) - 1
    trough_indices = [index for index in range(5, len(last60) - 1) if _is_local_trough(last60, index)]
    for trough_pos in range(len(trough_indices) - 1):
        first_idx = trough_indices[trough_pos]
        second_idx = trough_indices[trough_pos + 1]
        if second_idx - first_idx < 10:
            continue
        first_low = float(last60.iloc[first_idx]["low"])
        second_low = float(last60.iloc[second_idx]["low"])
        relative_diff = second_low / first_low - 1.0
        if relative_diff < -0.01 or relative_diff > 0.03:
            continue

        # A valid double bottom must use the latest consecutive effective
        # troughs. Once a lower low appears, the earlier left bottom is invalid.
        intervening = last60.iloc[first_idx + 1 : second_idx]
        if not intervening.empty:
            intervening_low = float(intervening["low"].min())
            if intervening_low < first_low:
                continue

        middle_high = float(last60.iloc[first_idx + 1 : second_idx]["high"].max())
        rebound = middle_high / max(first_low, second_low) - 1.0
        if rebound < 0.06:
            continue

        if second_idx < len(last60) - 15:
            continue

        first_leg_volume = _avg_volume(last60, max(0, first_idx - 5), first_idx + 1)
        second_leg_volume = _avg_volume(last60, max(0, second_idx - 5), second_idx + 1)
        if (
            first_leg_volume is not None
            and second_leg_volume is not None
            and second_leg_volume > first_leg_volume * 0.85
        ):
            continue

        recent_high = float(last60.iloc[second_idx + 1 : last_index]["high"].max()) if second_idx + 1 < last_index else None
        candidate = {
            "first_idx": first_idx,
            "second_idx": second_idx,
            "first_low": first_low,
            "second_low": second_low,
            "relative_diff": relative_diff,
            "rebound": rebound,
            "recent_high": recent_high,
        }
        if best is None:
            best = candidate
            continue
        if (candidate["second_idx"], -abs(candidate["relative_diff"])) > (
            best["second_idx"],
            -abs(best["relative_diff"]),
        ):
            best = candidate
    return best


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
    result = SignalResult(
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
    return _apply_risk_guardrail(result)


def _apply_risk_guardrail(result: SignalResult) -> SignalResult:
    risk = result.risk_to_stop_pct
    if risk is None:
        return result

    risk_signal = f"当前价距离止损位 {risk:.2f}%"
    if risk > 18.0 and result.group in TRIGGER_OR_FOCUS_TO_WAIT:
        return replace(
            result,
            group=TRIGGER_OR_FOCUS_TO_WAIT[result.group],
            score=min(result.score, 58),
            signals=result.signals + (f"{risk_signal}，赔率不合适",),
            action="离止损过远，等待回到 MA20、MA40 或前低支撑附近再评估",
            needs_close_confirmation=(),
        )

    if risk > 12.0:
        if result.group in TRIGGER_TO_FOCUS:
            return replace(
                result,
                group=TRIGGER_TO_FOCUS[result.group],
                score=min(result.score, 74),
                signals=result.signals + (f"{risk_signal}，已经偏离理想试错区",),
                action="结构成立，但离止损偏远，等更贴近支撑或下一次右侧确认",
            )
        if result.group in FOCUS_GROUPS:
            return replace(
                result,
                score=min(result.score, 74),
                signals=result.signals + (f"{risk_signal}，已经偏离理想试错区",),
                action="离止损偏远，优先等更贴近支撑的位置",
            )

    return result


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


_ENRICHED_COLUMNS = {
    "ma5",
    "ma20",
    "ma40",
    "vol5",
    "vol20",
    "ret20",
    "ret40",
    "high20",
    "low60",
    "drawdown20",
}


def _ensure_enriched(frame: pd.DataFrame) -> pd.DataFrame:
    if _ENRICHED_COLUMNS.issubset(frame.columns):
        return frame
    return enrich_daily_indicators(frame)


def evaluate_symbol(
    *,
    symbol: str,
    name: str,
    instrument_type: str,
    frame: pd.DataFrame,
    mode: str,
    realtime_quote: dict | None = None,
    expected_end_date: str | None = None,
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

    if mode == "close_confirmed" and expected_end_date is not None:
        expected_ts = pd.Timestamp(
            f"{expected_end_date[:4]}-{expected_end_date[4:6]}-{expected_end_date[6:]}"
        )
        latest_ts = pd.Timestamp(frame.index[-1]).normalize()
        if latest_ts < expected_ts:
            return _result(
                symbol=symbol,
                name=name,
                instrument_type=instrument_type,
                mode=mode,
                group="数据不足",
                score=0,
                setup="缺少当日收盘数据",
                latest_price=0.0,
                support=None,
                stop_loss=None,
                signals=(f"最新日线停留在 {latest_ts.date().isoformat()}",),
                action="等待补齐当日收盘数据后再评估",
                invalid_if=f"补齐 {expected_ts.date().isoformat()} 收盘数据后重新评估",
            )

    enriched = _ensure_enriched(frame)
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
    prior_high = float(enriched.iloc[-2]["high"]) if len(enriched) >= 2 else None
    prior5_high = float(enriched.iloc[-6:-1]["high"].max()) if len(enriched) >= 6 else prior_high
    recent3 = enriched.tail(3)
    recent5 = enriched.tail(5)
    recent10 = enriched.tail(10)
    recent20 = enriched.tail(20)
    recent40 = enriched.tail(40)

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

    recent_swing_low = float(recent10["low"].min()) if not recent10.empty else None
    if support is not None and recent_swing_low is not None and recent_swing_low >= support * 0.97:
        support = max(support, recent_swing_low)
        stop_loss = _stop_loss_for(instrument_type, support)

    ret40 = enriched.iloc[-1].get("ret40")
    ma40_trend_up = _finite(ma40) and len(enriched) >= 6 and _finite(enriched.iloc[-6].get("ma40")) and float(ma40) >= float(enriched.iloc[-6].get("ma40"))
    above_ma40_ratio = 0.0
    recent40_valid = recent40.dropna(subset=["ma40"])
    if len(recent40_valid) >= 20:
        above_ma40_ratio = float((recent40_valid["close"] >= recent40_valid["ma40"]).mean())
    trend_selected = _finite(ret40) and float(ret40) > 0 and ma40_trend_up and above_ma40_ratio >= 0.70

    ma40_recent_low = float(recent3["low"].min()) if not recent3.empty else None
    ma40_edge = (
        support is not None
        and _finite(ma40)
        and ma40_recent_low is not None
        and ma40_recent_low <= float(ma40) * 1.05
        and ma40_recent_low >= float(ma40) * 0.97
        and price >= float(ma40) * 0.97
    )
    drawdown20 = enriched.iloc[-1].get("drawdown20")
    had_pullback = _finite(drawdown20) and float(drawdown20) <= -0.05
    vol5 = enriched.iloc[-1].get("vol5")
    shrink_volume = _finite(vol5) and _finite(vol20) and float(vol5) <= float(vol20) * 0.9
    range5 = ((recent5["high"] - recent5["low"]) / recent5["close"]).mean() if not recent5.empty else None
    range20 = ((recent20["high"] - recent20["low"]) / recent20["close"]).mean() if not recent20.empty else None
    volatility_compressed = _finite(range5) and _finite(range20) and float(range5) <= float(range20) * 0.9
    day_return = _pct_change(price, previous_close)
    turn_up = (
        _finite(ma5)
        and price > float(ma5)
        and day_return is not None
        and day_return > 0.05
        and (
            (_finite(prior_high) and price > float(prior_high))
            or (_finite(prior5_high) and price > float(prior5_high))
        )
    )

    if trend_selected and ma40_edge and had_pullback and shrink_volume and volatility_compressed:
        signals.extend(
            [
                "近40日涨幅为正且 MA40 维持上行",
                "过去40日大部分收盘价位于 MA40 上方",
                "最近3日回踩到 MA40 / 前低支撑边缘",
                "近20日经历过至少5%回撤",
                "近5日均量低于近20日均量",
                "近5日波动率低于近20日平均波动率",
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
                signals=signals + ["价格重新站上 MA5", "突破前一日高点或近5日小平台", "当日涨幅超过5%"],
                action="优先盯盘；高开过多不追",
                invalid_if=f"跌破 {stop_loss:.3f}" if stop_loss is not None else "跌破关键支撑",
                needs_close_confirmation=("收盘是否站上 MA5", "收盘是否突破右侧小平台", "全天成交量是否满足条件") if mode == "intraday" else (),
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
            action="等待站上 MA5 并突破右侧小平台",
            invalid_if=f"跌破 {stop_loss:.3f}" if stop_loss is not None else "跌破关键支撑",
        )

    # MA20 first pullback fallback.
    if _finite(ma20) and _finite(ma40) and float(ma20) > float(ma40):
        ma20_price = float(ma20)
        near_ma20 = ma20_price * 0.97 <= price <= ma20_price * 1.03
        ret20 = enriched.iloc[-1].get("ret20")
        ma20_trend_up = len(enriched) >= 6 and _finite(enriched.iloc[-6].get("ma20")) and ma20_price >= float(enriched.iloc[-6].get("ma20"))
        trend_started = _finite(ret20) and float(ret20) >= 0.12 and ma20_trend_up
        recent20_valid = recent20.dropna(subset=["ma20"])
        stretch_flags: list[bool] = []
        first_stretch_index = None
        if not recent20_valid.empty:
            stretch_flags = (recent20_valid["high"] >= recent20_valid["ma20"] * 1.08).tolist()
            first_stretch_index = next((index for index, flag in enumerate(stretch_flags) if flag), None)
        stretched_from_ma20 = first_stretch_index is not None
        touch_window = recent20_valid.iloc[first_stretch_index + 1 :] if first_stretch_index is not None else pd.DataFrame()
        touch_flags: list[bool] = []
        current_touch = False
        touch_clusters = 0
        if not touch_window.empty:
            touch_series = (touch_window["low"] <= touch_window["ma20"] * 1.03) & (touch_window["low"] >= touch_window["ma20"] * 0.97)
            touch_flags = touch_series.tolist()
            current_touch = bool(touch_flags[-1])
            touch_clusters = _count_true_clusters(touch_flags)
        pullback_low = float(recent3["low"].min()) if not recent3.empty else price
        if mode == "intraday" and _finite(values["low"]):
            pullback_low = min(pullback_low, float(values["low"]))
        shallow_pullback = pullback_low >= ma20_price * 0.97
        recent8_valid = enriched.tail(8).dropna(subset=["ma20"])
        below_ma20_count = int((recent8_valid["close"] < recent8_valid["ma20"]).sum()) if not recent8_valid.empty else 0
        limited_retests = below_ma20_count <= 2
        no_heavy_ma20_break = True
        if _finite(vol20):
            recent10_valid = recent10.dropna(subset=["ma20"]).copy()
            daily_drop = recent10_valid["close"].pct_change()
            heavy_break = (
                ((recent10_valid["close"] < recent10_valid["ma20"] * 0.97) & (recent10_valid["volume"] >= float(vol20) * 1.3))
                | ((daily_drop <= -0.03) & (recent10_valid["volume"] >= float(vol20) * 1.3))
            ).any()
            no_heavy_ma20_break = not bool(heavy_break)
        first_pullback = trend_started and stretched_from_ma20 and current_touch and touch_clusters == 1 and shallow_pullback and limited_retests and no_heavy_ma20_break
        b_turn_up = (
            (_finite(ma5) and price > float(ma5))
            or (_finite(prior_high) and price > float(prior_high))
        )
        if near_ma20 and first_pullback:
            group = "盘中预警" if mode == "intraday" else "重点观察"
            if b_turn_up:
                group = "盘中触发" if mode == "intraday" else "触发买点"
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
                signals=[
                    "MA20 高于 MA40 且继续上行",
                    "近20日已有一段明显启动走势",
                    "启动后首次回到 MA20 附近",
                    "回踩未深度跌穿 MA20，且没有反复来回穿透",
                ],
                action="等待右侧确认" if "预警" in group or group == "重点观察" else "盘中优先盯",
                invalid_if=f"跌破 {ma20_price * 0.95:.3f}",
                needs_close_confirmation=("收盘是否站上 MA5",) if mode == "intraday" else (),
            )

    # Launch candle after range compression.
    prior10 = enriched.iloc[-11:-1] if len(enriched) >= 11 else pd.DataFrame()
    if not prior10.empty:
        range_compressed = (prior10["high"].max() / prior10["low"].min() - 1.0) <= 0.15
        day_return = _pct_change(price, previous_close)
        volume_expand = _finite(volume) and _finite(enriched.iloc[-1].get("vol5")) and float(volume) >= float(enriched.iloc[-1].get("vol5")) * 1.5
        prior_high10 = float(prior10["high"].max())
        price_breakout = price > prior_high10
        previous_launch_day = False
        if len(enriched) >= 12:
            prev_window = enriched.iloc[-12:-2]
            prev_close = enriched.iloc[-2].get("close")
            prev_previous_close = enriched.iloc[-3].get("close") if len(enriched) >= 3 else None
            prev_volume = enriched.iloc[-2].get("volume")
            prev_vol5 = enriched.iloc[-2].get("vol5")
            if not prev_window.empty:
                prev_range_compressed = (prev_window["high"].max() / prev_window["low"].min() - 1.0) <= 0.15
                prev_day_return = _pct_change(prev_close, prev_previous_close)
                prev_volume_expand = _finite(prev_volume) and _finite(prev_vol5) and float(prev_volume) >= float(prev_vol5) * 1.5
                prev_price_breakout = _finite(prev_close) and float(prev_close) > float(prev_window["high"].max())
                previous_launch_day = (
                    prev_range_compressed
                    and prev_day_return is not None
                    and prev_day_return >= 0.05
                    and prev_volume_expand
                    and prev_price_breakout
                )
        first_breakout_day = not previous_launch_day
        if range_compressed and day_return is not None and day_return >= 0.05 and volume_expand and price_breakout and first_breakout_day:
            group = "盘中触发" if mode == "intraday" else "触发买点"
            support = float(prior10["low"].min())
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
                signals=["近10日振幅收敛", "涨幅超过5%", "放量突破近10日高点"],
                action="轻仓试错，等待确认延续",
                invalid_if="启动阳线实体被吞没或跌回平台",
                needs_close_confirmation=("收盘是否突破平台", "全天成交量是否放大") if mode == "intraday" else (),
            )

    # Double-bottom / second compression.
    candidate = _double_bottom_candidate(enriched)
    if candidate is not None:
        support = float(candidate["second_low"])
        stop_loss = support * 0.97
        recent_high = candidate["recent_high"]
        recovers_ma5 = _finite(ma5) and price > float(ma5)
        breaks_recent_high = recent_high is not None and price > float(recent_high)
        no_heavy_break = True
        if _finite(vol20):
            recent = enriched.tail(10).copy()
            daily_drop = recent["close"].pct_change()
            heavy_break = (
                ((recent["close"] < float(candidate["first_low"]) * 0.99) & (recent["volume"] >= float(vol20) * 1.3))
                | ((daily_drop <= -0.03) & (recent["volume"] >= float(vol20) * 1.3))
            ).any()
            no_heavy_break = not bool(heavy_break)

        structure_signals = [
            "近60日内形成两个间隔至少10日的低点",
            "第二低点相对第一低点在 -1% 到 +3% 之间",
            "双底中间反弹幅度至少6%",
            "第二次回踩阶段量能弱于第一次下跌阶段",
        ]
        if recovers_ma5 and breaks_recent_high and no_heavy_break:
            group = "盘中触发" if mode == "intraday" else "触发买点"
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
                signals=structure_signals + ["价格重新站上 MA5", "突破第二低点后近5日高点"],
                action="依托双底低点观察右侧延续",
                invalid_if=f"跌破 {stop_loss:.3f}",
                needs_close_confirmation=("收盘是否站上 MA5", "收盘是否突破右侧小平台") if mode == "intraday" else (),
            )

        if no_heavy_break:
            group = "盘中预警" if mode == "intraday" else "重点观察"
            return _result(
                symbol=symbol,
                name=name,
                instrument_type=instrument_type,
                mode=mode,
                group=group,
                score=74,
                setup="双底或二次压紧待确认",
                latest_price=price,
                support=support,
                stop_loss=stop_loss,
                signals=structure_signals,
                action="等待站上 MA5 并突破右侧小平台",
                invalid_if=f"跌破 {stop_loss:.3f}",
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
