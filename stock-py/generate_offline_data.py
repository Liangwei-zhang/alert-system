from __future__ import annotations

import csv
import json
import ssl
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


UA = "StockPy OfflineDataBot/1.0 (contact:dev@stockpy.local)"
OFFLINE_OUTPUT = Path("frontend/app/js/offline-data.js")


def _fetch_text(url: str) -> str:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
        return response.read().decode("utf-8", errors="ignore")


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper().replace(" ", "")


def _clean_us_name(name: str, symbol: str) -> str:
    cleaned = str(name or "").strip()
    suffixes = [
        " Common Stock",
        ", Common Stock",
        " Class A Common Stock",
        ", Class A Common Stock",
        " Class B Common Stock",
        ", Class B Common Stock",
        " Ordinary Shares",
        ", Ordinary Shares",
        " Ordinary Share",
        ", Ordinary Share",
    ]
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned or symbol


def _add_entry(registry: dict[str, dict], entry: dict) -> None:
    symbol = _normalize_symbol(entry.get("symbol", ""))
    if not symbol:
        return
    if symbol in registry:
        return

    aliases = []
    for alias in entry.get("aliases", []):
        normalized = _normalize_symbol(alias)
        if normalized and normalized != symbol and normalized not in aliases:
            aliases.append(normalized)

    item = {
        "symbol": symbol,
        "name": str(entry.get("name", symbol)).strip() or symbol,
        "market": entry.get("market", "US"),
        "exchange": entry.get("exchange", ""),
        "asset_type": entry.get("asset_type", "EQUITY"),
    }
    if aliases:
        item["aliases"] = aliases
    registry[symbol] = item


def _load_us_symbols(registry: dict[str, dict]) -> int:
    before = len(registry)

    nasdaq_raw = _fetch_text("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt")
    for row in csv.DictReader(nasdaq_raw.splitlines(), delimiter="|"):
        symbol = _normalize_symbol(row.get("Symbol"))
        if not symbol or symbol.startswith("FILECREATIONTIME"):
            continue
        if row.get("Test Issue") == "Y":
            continue
        _add_entry(
            registry,
            {
                "symbol": symbol,
                "name": _clean_us_name(row.get("Security Name", ""), symbol),
                "market": "US",
                "exchange": "NASDAQ",
                "asset_type": "EQUITY",
            },
        )

    other_raw = _fetch_text("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt")
    exchange_map = {
        "N": "NYSE",
        "A": "NYSE American",
        "P": "NYSE Arca",
        "Z": "Cboe BZX",
        "V": "IEX",
        "M": "Chicago",
    }
    for row in csv.DictReader(other_raw.splitlines(), delimiter="|"):
        symbol = _normalize_symbol(row.get("ACT Symbol"))
        if not symbol or symbol.startswith("FILECREATIONTIME"):
            continue
        if row.get("Test Issue") == "Y":
            continue
        exchange_code = str(row.get("Exchange", "")).strip().upper()
        _add_entry(
            registry,
            {
                "symbol": symbol,
                "name": _clean_us_name(row.get("Security Name", ""), symbol),
                "market": "US",
                "exchange": exchange_map.get(exchange_code, exchange_code),
                "asset_type": "EQUITY",
            },
        )

    return len(registry) - before


def _load_cad_symbols(registry: dict[str, dict]) -> int:
    before = len(registry)

    tsx_raw = _fetch_text("https://www.tsx.com/json/company-directory/search/tsx/*")
    payload = json.loads(tsx_raw)
    for item in payload.get("results", []):
        raw_symbol = _normalize_symbol(item.get("symbol"))
        if not raw_symbol:
            continue
        symbol = raw_symbol if raw_symbol.endswith(".TO") else f"{raw_symbol}.TO"
        _add_entry(
            registry,
            {
                "symbol": symbol,
                "name": str(item.get("name", symbol)).strip() or symbol,
                "market": "CAD",
                "exchange": "TSX",
                "asset_type": "EQUITY",
                "aliases": [raw_symbol],
            },
        )

    return len(registry) - before


def _load_crypto_symbols(registry: dict[str, dict]) -> int:
    before = len(registry)

    binance_raw = _fetch_text("https://api.binance.com/api/v3/exchangeInfo")
    payload = json.loads(binance_raw)
    for item in payload.get("symbols", []):
        if item.get("status") != "TRADING":
            continue
        quote = _normalize_symbol(item.get("quoteAsset"))
        if quote not in {"USDT", "USDC"}:
            continue

        pair_symbol = _normalize_symbol(item.get("symbol"))
        base = _normalize_symbol(item.get("baseAsset"))
        if not pair_symbol or not base:
            continue

        _add_entry(
            registry,
            {
                "symbol": pair_symbol,
                "name": f"{base} / {quote}",
                "market": "CRYPTO",
                "exchange": "BINANCE",
                "asset_type": "SPOT",
                "aliases": [f"{base}-{quote}", base],
            },
        )

    return len(registry) - before


def _write_output(registry: dict[str, dict]) -> None:
    universe = sorted(
        registry.values(),
        key=lambda item: (item.get("market", ""), item.get("symbol", "")),
    )
    stats = {"US": 0, "CAD": 0, "CRYPTO": 0}
    for item in universe:
        market = item.get("market", "")
        if market in stats:
            stats[market] += 1

    payload = {
        "version": "2026.04.07",
        "generated_at": datetime.now(UTC).isoformat(),
        "stats": stats,
        "universe": universe,
    }

    OFFLINE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OFFLINE_OUTPUT.write_text(
        "window.OFFLINE_MARKET_DATA = "
        + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    registry: dict[str, dict] = {}
    loaded = {"US": 0, "CAD": 0, "CRYPTO": 0}

    try:
        loaded["US"] = _load_us_symbols(registry)
    except Exception as exc:  # pragma: no cover - best effort fetch path
        print(f"WARN: failed to load US universe: {exc}")

    try:
        loaded["CAD"] = _load_cad_symbols(registry)
    except Exception as exc:  # pragma: no cover - best effort fetch path
        print(f"WARN: failed to load CAD universe: {exc}")

    try:
        loaded["CRYPTO"] = _load_crypto_symbols(registry)
    except Exception as exc:  # pragma: no cover - best effort fetch path
        print(f"WARN: failed to load CRYPTO universe: {exc}")

    _write_output(registry)
    print(
        "Offline market data generated:",
        f"US={loaded['US']},",
        f"CAD={loaded['CAD']},",
        f"CRYPTO={loaded['CRYPTO']},",
        f"TOTAL={len(registry)}",
    )


if __name__ == "__main__":
    main()
