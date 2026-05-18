from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


TRADE_COLUMNS = [
    "symbol",
    "name",
    "direction",
    "setup",
    "signal_date",
    "entry_date",
    "entry_price",
    "stop_loss_at_entry",
    "exit_date",
    "exit_price",
    "exit_reason",
    "holding_days",
    "shares",
    "gross_pnl",
    "net_return",
]

EQUITY_COLUMNS = ["trade_date", "cash", "market_value", "equity", "positions"]

DIARY_COLUMNS = [
    "trade_date",
    "symbol",
    "name",
    "direction",
    "thesis",
    "group",
    "setup",
    "score",
    "latest_price",
    "support",
    "stop_loss",
    "risk_to_stop_pct",
    "trigger_price",
    "trigger_price_rule",
    "action",
]

TRADE_COLUMN_LABELS = {
    "symbol": "代码",
    "name": "名称",
    "direction": "方向",
    "setup": "模型",
    "signal_date": "信号日",
    "entry_date": "买入日",
    "entry_price": "买入价",
    "stop_loss_at_entry": "入场止损价",
    "exit_date": "卖出日",
    "exit_price": "卖出价",
    "exit_reason": "卖出原因",
    "holding_days": "持有天数",
    "shares": "股数",
    "gross_pnl": "盈亏金额",
    "net_return": "收益率",
}

EQUITY_COLUMN_LABELS = {
    "trade_date": "交易日",
    "cash": "现金",
    "market_value": "持仓市值",
    "equity": "总权益",
    "positions": "持仓数量",
}

DIARY_COLUMN_LABELS = {
    "trade_date": "交易日",
    "symbol": "代码",
    "name": "名称",
    "direction": "方向",
    "thesis": "逻辑",
    "group": "分组",
    "setup": "模型",
    "score": "评分",
    "latest_price": "最新价",
    "support": "支撑位",
    "stop_loss": "止损位",
    "risk_to_stop_pct": "距离止损风险(%)",
    "trigger_price": "触发价",
    "trigger_price_rule": "触发价规则",
    "action": "动作",
}

SUMMARY_LABELS = {
    "initial_cash": "初始资金",
    "final_equity": "期末权益",
    "total_return_pct": "总收益率(%)",
    "max_drawdown_pct": "最大回撤(%)",
    "trade_count": "交易笔数",
    "signal_count": "触发信号数",
    "win_rate_pct": "胜率(%)",
    "avg_win_pct": "平均盈利(%)",
    "avg_loss_pct": "平均亏损(%)",
    "avg_holding_days": "平均持有天数",
}

EXIT_REASON_LABELS = {
    "stop_loss": "触发止损",
    "excluded": "转为排除观察",
    "max_hold_days": "达到最大持有天数",
}


def _localize_trade_frame(trades: pd.DataFrame) -> pd.DataFrame:
    localized = trades.copy()
    if "symbol" in localized.columns:
        localized["symbol"] = localized["symbol"].map(
            lambda value: str(value).split(".")[0].zfill(6) if pd.notna(value) else value
        )
    if "exit_reason" in localized.columns:
        localized["exit_reason"] = localized["exit_reason"].map(
            lambda value: EXIT_REASON_LABELS.get(value, value)
        )
    return localized


def _max_drawdown_pct(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty:
        return 0.0
    running_peak = equity_curve["equity"].cummax()
    drawdown = equity_curve["equity"] / running_peak - 1.0
    return abs(float(drawdown.min()) * 100.0)


def build_summary(
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    signal_diary: pd.DataFrame,
    *,
    initial_cash: float,
) -> dict:
    final_equity = float(equity_curve.iloc[-1]["equity"]) if not equity_curve.empty else float(initial_cash)
    total_return_pct = (final_equity / float(initial_cash) - 1.0) * 100.0
    trade_count = int(len(trades))
    win_rate = float((trades["net_return"] > 0).mean() * 100.0) if trade_count else 0.0
    avg_win = float(trades.loc[trades["net_return"] > 0, "net_return"].mean() * 100.0) if trade_count else 0.0
    avg_loss = float(trades.loc[trades["net_return"] <= 0, "net_return"].mean() * 100.0) if trade_count else 0.0
    avg_holding_days = float(trades["holding_days"].mean()) if trade_count else 0.0
    signal_count = int((signal_diary["group"] == "触发买点").sum()) if not signal_diary.empty else 0

    by_setup = []
    if trade_count:
        grouped = trades.groupby("setup")
        for setup, group in grouped:
            by_setup.append(
                {
                    "setup": setup,
                    "trades": int(len(group)),
                    "win_rate_pct": round(float((group["net_return"] > 0).mean() * 100.0), 2),
                    "avg_return_pct": round(float(group["net_return"].mean() * 100.0), 2),
                }
            )

    by_direction = []
    if trade_count:
        grouped = trades.groupby("direction")
        for direction, group in grouped:
            by_direction.append(
                {
                    "direction": direction,
                    "trades": int(len(group)),
                    "win_rate_pct": round(float((group["net_return"] > 0).mean() * 100.0), 2),
                    "avg_return_pct": round(float(group["net_return"].mean() * 100.0), 2),
                }
            )

    return {
        "initial_cash": float(initial_cash),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(_max_drawdown_pct(equity_curve), 2),
        "trade_count": trade_count,
        "signal_count": signal_count,
        "win_rate_pct": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "avg_holding_days": round(avg_holding_days, 2),
        "by_setup": by_setup,
        "by_direction": by_direction,
    }


def _localized_summary(summary: dict) -> dict:
    localized = {SUMMARY_LABELS[key]: value for key, value in summary.items() if key in SUMMARY_LABELS}
    localized["按模型统计"] = [
        {
            "模型": row["setup"],
            "交易数": row["trades"],
            "胜率(%)": row["win_rate_pct"],
            "平均收益(%)": row["avg_return_pct"],
        }
        for row in summary.get("by_setup", [])
    ]
    localized["按方向统计"] = [
        {
            "方向": row["direction"],
            "交易数": row["trades"],
            "胜率(%)": row["win_rate_pct"],
            "平均收益(%)": row["avg_return_pct"],
        }
        for row in summary.get("by_direction", [])
    ]
    return localized


def write_backtest_reports(
    *,
    output_dir: str,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    signal_diary: pd.DataFrame,
    summary: dict,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    trades_path = output / "trades.csv"
    equity_path = output / "equity_curve.csv"
    diary_path = output / "signal_diary.csv"
    summary_path = output / "summary.json"
    html_path = output / "report.html"

    trades = trades.reindex(columns=TRADE_COLUMNS)
    equity_curve = equity_curve.reindex(columns=EQUITY_COLUMNS)
    signal_diary = signal_diary.reindex(columns=DIARY_COLUMNS)
    localized_trades = _localize_trade_frame(trades)

    localized_trades.rename(columns=TRADE_COLUMN_LABELS).to_csv(trades_path, index=False)
    equity_curve.rename(columns=EQUITY_COLUMN_LABELS).to_csv(equity_path, index=False)
    signal_diary.rename(columns=DIARY_COLUMN_LABELS).to_csv(diary_path, index=False)
    summary_path.write_text(
        json.dumps(_localized_summary(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    trade_rows = "".join(
        f"<tr><td>{row['symbol']}</td><td>{row['name']}</td><td>{row['direction']}</td><td>{row['setup']}</td>"
        f"<td>{row['entry_date']}</td><td>{row['exit_date']}</td><td>{row['exit_reason']}</td>"
        f"<td>{row['net_return'] * 100:.2f}%</td></tr>"
        for _, row in localized_trades.head(30).iterrows()
    )
    setup_rows = "".join(
        f"<tr><td>{row['setup']}</td><td>{row['trades']}</td><td>{row['win_rate_pct']:.2f}%</td><td>{row['avg_return_pct']:.2f}%</td></tr>"
        for row in summary["by_setup"]
    )
    direction_rows = "".join(
        f"<tr><td>{row['direction']}</td><td>{row['trades']}</td><td>{row['win_rate_pct']:.2f}%</td><td>{row['avg_return_pct']:.2f}%</td></tr>"
        for row in summary["by_direction"]
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>观察池策略回测</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 24px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; font-size: 13px; }}
    th {{ background: #f9fafb; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .metric {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }}
    .metric .label {{ color: #6b7280; font-size: 12px; }}
    .metric .value {{ font-size: 22px; font-weight: 600; margin-top: 4px; }}
  </style>
</head>
<body>
  <h1>观察池策略回测</h1>
  <div class="grid">
    <div class="metric"><div class="label">总收益</div><div class="value">{summary['total_return_pct']:.2f}%</div></div>
    <div class="metric"><div class="label">最大回撤</div><div class="value">{summary['max_drawdown_pct']:.2f}%</div></div>
    <div class="metric"><div class="label">交易笔数</div><div class="value">{summary['trade_count']}</div></div>
    <div class="metric"><div class="label">胜率</div><div class="value">{summary['win_rate_pct']:.2f}%</div></div>
    <div class="metric"><div class="label">平均持有天数</div><div class="value">{summary['avg_holding_days']:.2f}</div></div>
    <div class="metric"><div class="label">触发信号数</div><div class="value">{summary['signal_count']}</div></div>
  </div>
  <h2>模型统计</h2>
  <table><thead><tr><th>模型</th><th>交易数</th><th>胜率</th><th>平均收益</th></tr></thead><tbody>{setup_rows}</tbody></table>
  <h2>方向统计</h2>
  <table><thead><tr><th>方向</th><th>交易数</th><th>胜率</th><th>平均收益</th></tr></thead><tbody>{direction_rows}</tbody></table>
  <h2>最近交易</h2>
  <table><thead><tr><th>代码</th><th>名称</th><th>方向</th><th>模型</th><th>买入日</th><th>卖出日</th><th>原因</th><th>收益</th></tr></thead><tbody>{trade_rows}</tbody></table>
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")

    return {
        "trades": str(trades_path),
        "equity_curve": str(equity_path),
        "signal_diary": str(diary_path),
        "summary": str(summary_path),
        "html": str(html_path),
    }
