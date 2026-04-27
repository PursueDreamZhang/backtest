from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

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
