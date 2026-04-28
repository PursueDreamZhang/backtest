from __future__ import annotations

import csv
from dataclasses import asdict
from html import escape
import json
from pathlib import Path
from typing import Any, Iterable

from .signals import SignalResult


GROUP_PRIORITY = {
    "盘中失效": 0,
    "排除观察": 0,
    "盘中触发": 1,
    "触发买点": 1,
    "盘中预警": 2,
    "重点观察": 2,
    "盘中等待": 3,
    "等待回调": 3,
    "数据不足": 4,
}

OVERVIEW_GROUP_PRIORITY = {
    "盘中触发": 0,
    "触发买点": 0,
    "盘中预警": 1,
    "重点观察": 1,
    "盘中等待": 2,
    "等待回调": 2,
    "盘中失效": 3,
    "排除观察": 3,
    "数据不足": 4,
}


def _sort_results(results: Iterable[SignalResult]) -> list[SignalResult]:
    return sorted(
        results,
        key=lambda item: (GROUP_PRIORITY.get(item.group, 99), -item.score, item.symbol),
    )


def _summary(results: list[SignalResult], mode: str) -> dict[str, int]:
    if mode == "intraday":
        return {
            "intraday_triggered": sum(item.group == "盘中触发" for item in results),
            "intraday_alert": sum(item.group == "盘中预警" for item in results),
            "intraday_wait": sum(item.group == "盘中等待" for item in results),
            "intraday_invalid": sum(item.group == "盘中失效" for item in results),
            "insufficient_data": sum(item.group == "数据不足" for item in results),
        }
    return {
        "triggered": sum(item.group == "触发买点" for item in results),
        "focus": sum(item.group == "重点观察" for item in results),
        "wait": sum(item.group == "等待回调" for item in results),
        "excluded": sum(item.group == "排除观察" for item in results),
        "insufficient_data": sum(item.group == "数据不足" for item in results),
    }


def _write_csv(path: Path, results: list[SignalResult]) -> None:
    fields = [
        "symbol",
        "name",
        "instrument_type",
        "mode",
        "group",
        "signal_timing",
        "confidence",
        "score",
        "setup",
        "latest_price",
        "support",
        "stop_loss",
        "risk_to_stop_pct",
        "action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            writer.writerow({field: row.get(field) for field in fields})


def _summary_fields(mode: str) -> list[str]:
    if mode == "intraday":
        return [
            "intraday_triggered",
            "intraday_alert",
            "intraday_wait",
            "intraday_invalid",
            "insufficient_data",
        ]
    return ["triggered", "focus", "wait", "excluded", "insufficient_data"]


def _merge_overview_items(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for report in reports:
        direction = report["direction"]
        for item in report["items"]:
            row = asdict(item) if isinstance(item, SignalResult) else dict(item)
            symbol = row["symbol"]
            current = merged.get(symbol)
            if current is None:
                current = row
                current["directions"] = [direction]
                current["direction_count"] = 1
                merged[symbol] = current
                continue

            if direction not in current["directions"]:
                current["directions"].append(direction)
                current["direction_count"] = len(current["directions"])
            current_priority = OVERVIEW_GROUP_PRIORITY.get(current["group"], 99)
            row_priority = OVERVIEW_GROUP_PRIORITY.get(row["group"], 99)
            if (row_priority, -row["score"]) < (current_priority, -current["score"]):
                directions = current["directions"]
                direction_count = current["direction_count"]
                current.clear()
                current.update(row)
                current["directions"] = directions
                current["direction_count"] = direction_count

    return sorted(
        merged.values(),
        key=lambda row: (
            OVERVIEW_GROUP_PRIORITY.get(row["group"], 99),
            -row.get("score", 0),
            -row.get("direction_count", 1),
            row["symbol"],
        ),
    )


def _write_overview_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fields = [
        "symbol",
        "name",
        "directions",
        "group",
        "score",
        "setup",
        "latest_price",
        "support",
        "stop_loss",
        "risk_to_stop_pct",
        "action",
        "invalid_if",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in items:
            row = dict(item)
            row["directions"] = " / ".join(row["directions"])
            writer.writerow({field: row.get(field) for field in fields})


def _write_overview_markdown(
    path: Path,
    *,
    mode: str,
    run_date: str,
    summary: dict[str, int],
    theme_rows: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> None:
    lines = [
        "# 观察标的总览",
        "",
        f"- 日期: {run_date}",
        f"- 模式: {mode}",
        f"- 汇总: {json.dumps(summary, ensure_ascii=False)}",
        "",
        "## 今日优先级清单",
        "",
        "| symbol | name | directions | group | score | setup | latest_price | action |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for item in items:
        if item["group"] in {"等待回调", "盘中等待", "排除观察", "盘中失效", "数据不足"}:
            continue
        lines.append(
            f"| {item['symbol']} | {item['name']} | {' / '.join(item['directions'])} | "
            f"{item['group']} | {item['score']} | {item['setup']} | "
            f"{item['latest_price']:.3f} | {item['action']} |"
        )

    lines.extend(
        [
            "",
            "## 题材热度排行",
            "",
            "| direction | triggered | focus | wait | excluded | insufficient_data |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in theme_rows:
        lines.append(
            f"| {row['direction']} | {row.get('triggered', row.get('intraday_triggered', 0))} | "
            f"{row.get('focus', row.get('intraday_alert', 0))} | "
            f"{row.get('wait', row.get('intraday_wait', 0))} | "
            f"{row.get('excluded', row.get('intraday_invalid', 0))} | "
            f"{row.get('insufficient_data', 0)} |"
        )

    lines.extend(["", "## 全量清单", ""])
    lines.extend(
        [
            "| symbol | name | directions | group | score | setup | latest_price | action |",
            "| --- | --- | --- | --- | ---: | --- | ---: | --- |",
        ]
    )
    for item in items:
        lines.append(
            f"| {item['symbol']} | {item['name']} | {' / '.join(item['directions'])} | "
            f"{item['group']} | {item['score']} | {item['setup']} | "
            f"{item['latest_price']:.3f} | {item['action']} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def _group_class(group: str) -> str:
    if group in {"盘中触发", "触发买点"}:
        return "tag trigger"
    if group in {"盘中预警", "重点观察"}:
        return "tag focus"
    if group in {"盘中失效", "排除观察"}:
        return "tag invalid"
    return "tag wait"


def _summary_label(key: str) -> str:
    labels = {
        "triggered": "触发买点",
        "focus": "重点观察",
        "wait": "等待回调",
        "excluded": "排除观察",
        "intraday_triggered": "盘中触发",
        "intraday_alert": "盘中预警",
        "intraday_wait": "盘中等待",
        "intraday_invalid": "盘中失效",
        "insufficient_data": "数据不足",
    }
    return labels.get(key, key)


def _render_priority_rows(items: list[dict[str, Any]], *, include_all: bool) -> str:
    rows = []
    hidden_groups = {"等待回调", "盘中等待", "排除观察", "盘中失效", "数据不足"}
    for item in items:
        if not include_all and item["group"] in hidden_groups:
            continue
        directions = " / ".join(item["directions"])
        rows.append(
            "<tr>"
            f"<td class=\"mono\">{escape(item['symbol'])}</td>"
            f"<td class=\"name\">{escape(item['name'])}</td>"
            f"<td>{escape(directions)}</td>"
            f"<td><span class=\"{_group_class(item['group'])}\">{escape(item['group'])}</span></td>"
            f"<td class=\"num\">{item['score']}</td>"
            f"<td>{escape(item['setup'])}</td>"
            f"<td class=\"num\">{_fmt_number(item['latest_price'])}</td>"
            f"<td>{escape(item['action'])}</td>"
            "</tr>"
        )
    if not rows:
        return "<tr><td colspan=\"8\" class=\"empty\">暂无匹配标的</td></tr>"
    return "\n".join(rows)


def _render_theme_rows(theme_rows: list[dict[str, Any]]) -> str:
    rows = []
    for row in theme_rows:
        triggered = row.get("triggered", row.get("intraday_triggered", 0))
        focus = row.get("focus", row.get("intraday_alert", 0))
        wait = row.get("wait", row.get("intraday_wait", 0))
        excluded = row.get("excluded", row.get("intraday_invalid", 0))
        rows.append(
            "<tr>"
            f"<td class=\"name\">{escape(row['direction'])}</td>"
            f"<td class=\"num hot\">{triggered}</td>"
            f"<td class=\"num warm\">{focus}</td>"
            f"<td class=\"num\">{wait}</td>"
            f"<td class=\"num muted\">{excluded}</td>"
            f"<td class=\"num muted\">{row.get('insufficient_data', 0)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _write_overview_html(
    path: Path,
    *,
    mode: str,
    run_date: str,
    summary: dict[str, int],
    theme_rows: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> None:
    cards = "\n".join(
        f"<section class=\"metric\"><div>{escape(_summary_label(key))}</div><strong>{value}</strong></section>"
        for key, value in summary.items()
    )
    priority_rows = _render_priority_rows(items, include_all=False)
    all_rows = _render_priority_rows(items, include_all=True)
    theme_html = _render_theme_rows(theme_rows)
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>观察标的总览</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #667085;
      --line: #d8dde6;
      --trigger: #c2410c;
      --trigger-bg: #fff1e8;
      --focus: #0f766e;
      --focus-bg: #e6f7f4;
      --wait: #475467;
      --wait-bg: #eef1f5;
      --invalid: #9f1239;
      --invalid-bg: #ffe8ef;
      --accent: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}
    header {{
      padding: 24px 28px 16px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 6px; font-size: 26px; font-weight: 750; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .meta {{ color: var(--muted); display: flex; gap: 16px; flex-wrap: wrap; }}
    main {{ padding: 20px 28px 36px; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
    }}
    .metric div {{ color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 24px; }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 18px;
      overflow: hidden;
    }}
    .section-header {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }}
    .hint {{ color: var(--muted); font-size: 13px; }}
    .table-wrap {{ overflow: auto; max-height: 72vh; }}
    table {{ width: 100%; border-collapse: separate; border-spacing: 0; min-width: 920px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f9fafb;
      color: #344054;
      font-size: 12px;
      text-align: left;
      font-weight: 700;
    }}
    tr:hover td {{ background: #f8fbff; }}
    .num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: nowrap; }}
    .name {{ font-weight: 650; white-space: nowrap; }}
    .tag {{
      display: inline-flex;
      min-width: 72px;
      justify-content: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .trigger {{ color: var(--trigger); background: var(--trigger-bg); }}
    .focus {{ color: var(--focus); background: var(--focus-bg); }}
    .wait {{ color: var(--wait); background: var(--wait-bg); }}
    .invalid {{ color: var(--invalid); background: var(--invalid-bg); }}
    .hot {{ color: var(--trigger); font-weight: 800; }}
    .warm {{ color: var(--focus); font-weight: 800; }}
    .muted {{ color: var(--muted); }}
    .empty {{ text-align: center; color: var(--muted); padding: 28px; }}
    @media (max-width: 760px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      h1 {{ font-size: 22px; }}
      .section-header {{ align-items: flex-start; flex-direction: column; }}
      table {{ min-width: 840px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>观察标的总览</h1>
    <div class="meta"><span>日期：{escape(run_date)}</span><span>模式：{escape(mode)}</span></div>
  </header>
  <main>
    <div class="metrics">{cards}</div>
    <section class="section">
      <div class="section-header">
        <h2>今日优先级清单</h2>
        <span class="hint">合并重复标的，按触发、观察、评分排序</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>代码</th><th>名称</th><th>题材</th><th>状态</th><th>评分</th><th>形态</th><th>价格</th><th>动作</th></tr></thead>
          <tbody>{priority_rows}</tbody>
        </table>
      </div>
    </section>
    <section class="section">
      <div class="section-header">
        <h2>题材热度排行</h2>
        <span class="hint">按触发数、重点观察数排序</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>题材</th><th>触发</th><th>重点</th><th>等待</th><th>排除</th><th>数据不足</th></tr></thead>
          <tbody>{theme_html}</tbody>
        </table>
      </div>
    </section>
    <section class="section">
      <div class="section-header">
        <h2>全量清单</h2>
        <span class="hint">包含等待和排除，便于复盘</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>代码</th><th>名称</th><th>题材</th><th>状态</th><th>评分</th><th>形态</th><th>价格</th><th>动作</th></tr></thead>
          <tbody>{all_rows}</tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _write_markdown(
    path: Path,
    *,
    direction: str,
    thesis: str,
    mode: str,
    run_date: str,
    summary: dict[str, int],
    results: list[SignalResult],
) -> None:
    lines = [
        f"# 观察标的执行策略报告",
        "",
        f"- 日期: {run_date}",
        f"- 模式: {mode}",
        f"- 方向: {direction}",
        f"- 逻辑: {thesis}",
        f"- 汇总: {json.dumps(summary, ensure_ascii=False)}",
        "",
        "| symbol | name | group | score | setup | latest_price | action |",
        "| --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item.symbol} | {item.name} | {item.group} | {item.score} | "
            f"{item.setup} | {item.latest_price:.3f} | {item.action} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(
    *,
    output_dir: str,
    direction: str,
    thesis: str,
    mode: str,
    results: list[SignalResult],
    run_date: str,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    sorted_results = _sort_results(results)
    summary = _summary(sorted_results, mode)

    json_path = output / "watchlist_report.json"
    csv_path = output / "watchlist_report.csv"
    markdown_path = output / "watchlist_report.md"

    payload = {
        "run_date": run_date,
        "mode": mode,
        "direction": direction,
        "thesis": thesis,
        "summary": summary,
        "items": [asdict(result) for result in sorted_results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, sorted_results)
    _write_markdown(
        markdown_path,
        direction=direction,
        thesis=thesis,
        mode=mode,
        run_date=run_date,
        summary=summary,
        results=sorted_results,
    )

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(markdown_path),
    }


def write_overview_reports(
    *,
    output_dir: str,
    reports: list[dict[str, Any]],
    mode: str,
    run_date: str,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    items = _merge_overview_items(reports)
    if mode == "intraday":
        summary = {
            "intraday_triggered": sum(item["group"] == "盘中触发" for item in items),
            "intraday_alert": sum(item["group"] == "盘中预警" for item in items),
            "intraday_wait": sum(item["group"] == "盘中等待" for item in items),
            "intraday_invalid": sum(item["group"] == "盘中失效" for item in items),
            "insufficient_data": sum(item["group"] == "数据不足" for item in items),
        }
    else:
        summary = {
            "triggered": sum(item["group"] == "触发买点" for item in items),
            "focus": sum(item["group"] == "重点观察" for item in items),
            "wait": sum(item["group"] == "等待回调" for item in items),
            "excluded": sum(item["group"] == "排除观察" for item in items),
            "insufficient_data": sum(item["group"] == "数据不足" for item in items),
        }
    theme_rows = []
    for report in reports:
        row = {"direction": report["direction"], **report["summary"]}
        theme_rows.append(row)

    theme_rows.sort(
        key=lambda row: (
            -row.get("triggered", row.get("intraday_triggered", 0)),
            -row.get("focus", row.get("intraday_alert", 0)),
            row["direction"],
        )
    )

    json_path = output / "overview.json"
    csv_path = output / "overview.csv"
    markdown_path = output / "overview.md"
    html_path = output / "overview.html"
    payload = {
        "run_date": run_date,
        "mode": mode,
        "summary": summary,
        "themes": theme_rows,
        "items": items,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_overview_csv(csv_path, items)
    _write_overview_markdown(
        markdown_path,
        mode=mode,
        run_date=run_date,
        summary=summary,
        theme_rows=theme_rows,
        items=items,
    )
    _write_overview_html(
        html_path,
        mode=mode,
        run_date=run_date,
        summary=summary,
        theme_rows=theme_rows,
        items=items,
    )

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
    }
