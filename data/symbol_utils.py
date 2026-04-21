"""Helpers for inferring exchange and instrument type from CN symbols."""

from __future__ import annotations


def infer_cn_exchange(symbol: str) -> str:
    normalized = str(symbol).strip()
    if normalized.startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def is_probable_etf(symbol: str) -> bool:
    normalized = str(symbol).strip()
    return normalized.startswith(("1", "5"))
