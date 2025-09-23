import os
import time
import ast
from datetime import datetime
from typing import Dict, Optional, Tuple, Any

import requests
import pandas as pd
from dotenv import load_dotenv
import yfinance as yf

load_dotenv()

COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
ALPHA_VANTAGE_GLOBAL_QUOTE_URL = "https://www.alphavantage.co/query"
DEFAULT_FIAT = "usd"

SYMBOL_TO_COIN_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "MATIC": "polygon-pos",
    "TRX": "tron",
    "LTC": "litecoin",
    "DOT": "polkadot",
}


def resolve_crypto_identifier(asset: str) -> Optional[str]:
    key = asset.strip()
    if not key:
        return None
    upper = key.upper()
    lower = key.lower()
    if upper in SYMBOL_TO_COIN_ID:
        return SYMBOL_TO_COIN_ID[upper]
    # Accept direct CoinGecko ids like 'bitcoin', 'ethereum'
    return lower


def fetch_crypto_price(asset: str, vs_currency: str = DEFAULT_FIAT, timeout_seconds: int = 15) -> Optional[float]:
    coin_id = resolve_crypto_identifier(asset)
    if not coin_id:
        print(f"Invalid crypto asset: {asset}")
        return None

    params = {
        "ids": coin_id,
        "vs_currencies": vs_currency,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "VaultChain-Tracker/0.1 (+https://github.com/yourusername/vaultchain-tracker)",
    }
    try:
        response = requests.get(COINGECKO_SIMPLE_PRICE_URL, params=params, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
        price = data.get(coin_id, {}).get(vs_currency)
        if price is None:
            print(f"CoinGecko price not found for {asset}")
            return None
        return float(price)
    except Exception as error:
        print(f"Error fetching crypto price for {asset}: {error}")
        return None


def get_alpha_vantage_api_key() -> Optional[str]:
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if key:
        return key.strip()
    try:
        entered = input("Enter Alpha Vantage API key (or press Enter to skip stocks): ").strip()
        return entered or None
    except Exception:
        return None


def normalize_stock_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    # Auto-pad Hong Kong tickers like 700.HK -> 0700.HK
    if s.endswith(".HK"):
        base = s[:-3]
        if base.isdigit():
            if len(base) < 4:
                base = base.zfill(4)
            s = f"{base}.HK"
    return s


def alpha_vantage_symbol_search(keywords: str, api_key: str, timeout_seconds: int = 15) -> Optional[str]:
    params = {
        "function": "SYMBOL_SEARCH",
        "keywords": keywords,
        "apikey": api_key,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "VaultChain-Tracker/0.1 (+https://github.com/yourusername/vaultchain-tracker)",
    }
    try:
        response = requests.get(ALPHA_VANTAGE_GLOBAL_QUOTE_URL, params=params, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
        matches = data.get("bestMatches", [])
        if not matches:
            return None
        # Try to pick the most relevant by region hint from suffix in keywords
        region_hint = None
        k = keywords.upper()
        if k.endswith(".HK"):
            region_hint = "Hong Kong"
        elif k.endswith(".T"):
            region_hint = "Japan"
        elif k.endswith(".L"):
            region_hint = "United Kingdom"
        # First pass: exact region match
        if region_hint:
            for m in matches:
                if m.get("4. region", "").strip() == region_hint:
                    sym = m.get("1. symbol")
                    if sym:
                        return sym.strip().upper()
        # Fallback: first match
        sym = matches[0].get("1. symbol")
        return sym.strip().upper() if sym else None
    except Exception:
        return None


def fetch_alpha_daily_close(symbol: str, api_key: str, timeout_seconds: int = 20) -> Optional[Tuple[float, str]]:
    def _daily(sym: str) -> Optional[Tuple[float, str]]:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": sym,
            "outputsize": "compact",
            "apikey": api_key,
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "VaultChain-Tracker/0.1 (+https://github.com/yourusername/vaultchain-tracker)",
        }
        try:
            response = requests.get(ALPHA_VANTAGE_GLOBAL_QUOTE_URL, params=params, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()
            ts = data.get("Time Series (Daily)")
            if not isinstance(ts, dict) or not ts:
                return None
            latest_date = sorted(ts.keys())[-1]
            close_str = ts[latest_date].get("4. close")
            if close_str:
                return (float(close_str), latest_date)
            return None
        except Exception:
            return None

    # Try daily first; if not, try adjusted as a backup
    result = _daily(symbol)
    if result:
        return result
    try:
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": api_key,
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "VaultChain-Tracker/0.1 (+https://github.com/yourusername/vaultchain-tracker)",
        }
        response = requests.get(ALPHA_VANTAGE_GLOBAL_QUOTE_URL, params=params, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
        ts = data.get("Time Series (Daily)") or data.get("Time Series (Daily) ")
        if not isinstance(ts, dict) or not ts:
            return None
        latest_date = sorted(ts.keys())[-1]
        close_str = ts[latest_date].get("4. close") or ts[latest_date].get("5. adjusted close")
        if close_str:
            return (float(close_str), latest_date)
        return None
    except Exception:
        return None


def fetch_stock_price(symbol: str, api_key: Optional[str], timeout_seconds: int = 20) -> Optional[float]:
    if not api_key:
        print(f"Skipping stock fetch for {symbol}: missing Alpha Vantage API key.")
        return None

    normalized_symbol = normalize_stock_symbol(symbol)

    def _do_fetch(sym: str) -> Tuple[Optional[float], Dict[str, Any]]:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": sym.upper(),
            "apikey": api_key,
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "VaultChain-Tracker/0.1 (+https://github.com/yourusername/vaultchain-tracker)",
        }
        response = requests.get(ALPHA_VANTAGE_GLOBAL_QUOTE_URL, params=params, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        payload: Dict[str, Any] = response.json()
        raw_price = None
        note = None
        if isinstance(payload, dict):
            note = payload.get("Note") or payload.get("Information")
            quote = payload.get("Global Quote", {})
            raw_price = quote.get("05. price") or quote.get("05. Price")
        return (float(raw_price) if raw_price else None, payload if isinstance(payload, dict) else {})

    try:
        price, payload = _do_fetch(normalized_symbol)
        if payload.get("Note") or payload.get("Information"):
            note = payload.get("Note") or payload.get("Information")
            print(f"Alpha Vantage notice for {symbol}: {note}")
            return None
        if price is not None:
            return price

        # If not found, try SYMBOL_SEARCH then retry once
        suggested = alpha_vantage_symbol_search(normalized_symbol, api_key)
        if suggested and suggested != normalized_symbol:
            retry_price, retry_payload = _do_fetch(suggested)
            if retry_payload.get("Note") or retry_payload.get("Information"):
                note = retry_payload.get("Note") or retry_payload.get("Information")
                print(f"Alpha Vantage notice for {suggested}: {note}")
                return None
            if retry_price is not None:
                print(f"Resolved symbol {symbol} -> {suggested}")
                return retry_price

        # Fallback: use last daily close if available
        daily = fetch_alpha_daily_close(normalized_symbol, api_key, timeout_seconds)
        if not daily and suggested:
            daily = fetch_alpha_daily_close(suggested, api_key, timeout_seconds)
        if daily:
            close_price, date_str = daily
            print(f"Using last daily close for {symbol} ({date_str})")
            return close_price

        # Final fallback: Yahoo Finance
        yahoo_price = fetch_stock_price_yahoo(normalized_symbol)
        if yahoo_price is not None:
            return yahoo_price
        if suggested and suggested != normalized_symbol:
            yahoo_price = fetch_stock_price_yahoo(suggested)
            if yahoo_price is not None:
                print(f"Resolved symbol {symbol} -> {suggested} via Yahoo Finance")
                return yahoo_price

        print(f"Alpha Vantage price not found for {symbol}")
        return None
    except Exception as error:
        print(f"Error fetching stock price for {symbol}: {error}")
        return None


def fetch_stock_price_yahoo(symbol: str) -> Optional[float]:
    try:
        ticker = yf.Ticker(symbol)
        # Try fast_info first
        price = None
        try:
            fi = getattr(ticker, "fast_info", None)
            if fi and getattr(fi, "last_price", None):
                price = float(fi.last_price)
        except Exception:
            price = None
        if price is not None and price > 0:
            print(f"Using Yahoo Finance price for {symbol}")
            return price
        # Fallback: last close
        hist = ticker.history(period="1d")
        if not hist.empty:
            last_close = hist["Close"].iloc[-1]
            if pd.notna(last_close):
                print(f"Using Yahoo Finance daily close for {symbol}")
                return float(last_close)
    except Exception:
        pass
    return None


def classify_asset(asset: str) -> str:
    token = asset.strip()
    if not token:
        return "crypto"

    # Explicit crypto by known symbols
    if token.upper() in SYMBOL_TO_COIN_ID:
        return "crypto"

    # International tickers (with dots) or tickers containing digits → treat as stocks
    if "." in token or any(ch.isdigit() for ch in token):
        return "stock"

    # Known CoinGecko ids
    lower = token.lower()
    known_crypto_ids = set(SYMBOL_TO_COIN_ID.values())
    if lower in known_crypto_ids:
        return "crypto"

    # All-uppercase alphabetic but not mapped → likely stock (e.g., AAPL)
    if token.isupper() and token.isalpha():
        return "stock"

    # Default to crypto (allows direct ids like 'bitcoin', 'solana')
    return "crypto"


def get_price_for_asset(asset: str, alpha_key: Optional[str]) -> Optional[float]:
    asset_type = classify_asset(asset)
    if asset_type == "crypto":
        return fetch_crypto_price(asset)
    return fetch_stock_price(asset, alpha_key)


def calculate_portfolio(holdings: Dict[str, float]) -> pd.DataFrame:
    alpha_key = get_alpha_vantage_api_key()
    rows = []
    for asset, quantity in holdings.items():
        try:
            quantity_float = float(quantity)
        except Exception:
            print(f"Invalid quantity for {asset}: {quantity}. Skipping.")
            continue
        price = get_price_for_asset(asset, alpha_key)
        if price is None:
            continue
        value = price * quantity_float
        rows.append({
            "Asset": asset,
            "Quantity": quantity_float,
            "Price(USD)": round(price, 6),
            "Value(USD)": round(value, 2),
        })
    df = pd.DataFrame(rows, columns=["Asset", "Quantity", "Price(USD)", "Value(USD)"])
    if not df.empty:
        df.loc["Total"] = ["-", "-", "-", round(df["Value(USD)"].sum(), 2)]
    return df


def export_portfolio_to_csv(df: pd.DataFrame, directory: str = ".") -> Optional[str]:
    if df is None or df.empty:
        print("Nothing to export: portfolio is empty.")
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vaultchain_portfolio_{stamp}.csv"
    path = os.path.join(directory, filename)
    try:
        df.to_csv(path, index=False)
        print(f"Exported to {filename}")
        return path
    except Exception as error:
        print(f"Failed to export CSV: {error}")
        return None


def pretty_print_dataframe(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        print("No data to display.")
        return
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(df.to_string(index=False))


def watch_portfolio(holdings: Dict[str, float], refresh_seconds: int = 300) -> None:
    print(f"Watching portfolio every {refresh_seconds} seconds. Press Ctrl+C to stop.\n")
    try:
        while True:
            df = calculate_portfolio(holdings)
            pretty_print_dataframe(df)
            export_portfolio_to_csv(df)
            time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        print("\nStopped watching.")


BANNER = "VaultChain-Tracker v0.1 - Privacy-first Crypto/Stock Tracker"


def parse_holdings_input(raw: str) -> Dict[str, float]:
    raw = raw.strip()
    if not raw:
        return {}
    # Try Python-literal first (allows single quotes)
    try:
        data = ast.literal_eval(raw)
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except Exception:
        pass
    # Fallback: try JSON
    try:
        import json
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except Exception:
        pass
    raise ValueError("Invalid holdings format. Example: {'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}")


COMMON_STOCK_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "SPY", "QQQ"
]

PRESET_HOLDINGS: Dict[str, Dict[str, float]] = {
    "stocks": {"AAPL": 1, "MSFT": 1, "NVDA": 1},
    "crypto": {"BTC": 0.01, "ETH": 0.2, "SOL": 3},
    "mix": {"BTC": 0.005, "AAPL": 1, "ETH": 0.1},
    "intl": {"700.HK": 2, "7203.T": 1, "RIO.L": 3},
    "etf": {"SPY": 1, "QQQ": 1, "VTI": 1},
}


def print_examples() -> None:
    print("Examples (copy/paste one line):")
    print("- Crypto: {'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}")
    print("- Stocks (US): {'AAPL': 1, 'MSFT': 2, 'NVDA': 1}")
    print("- ETF: {'SPY': 1, 'QQQ': 1, 'VTI': 1}")
    print("- International: {'700.HK': 2, '7203.T': 1, 'RIO.L': 3}")
    print("- Mixed: {'BTC': 0.005, 'AAPL': 1}")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="VaultChain-Tracker CLI")
    parser.add_argument(
        "--holdings",
        type=str,
        help="Holdings as a Python dict or JSON string, e.g. {'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}",
    )
    parser.add_argument(
        "--holdings-file",
        type=str,
        help="Path to a file containing holdings as JSON or Python dict.",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=["stocks", "crypto", "mix", "intl", "etf"],
        help="Use a predefined sample holdings: stocks | crypto | mix | intl | etf",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Print example inputs and exit.",
    )
    parser.add_argument(
        "--watch",
        type=int,
        nargs="?",
        const=300,
        help="Watch mode refresh interval in seconds (default 300). If provided without value, defaults to 300.",
    )
    args = parser.parse_args()

    print(BANNER)
    print("- Real-time prices (BTC, ETH, AAPL)")
    print("- Local portfolio tracking")
    print("- CSV export\n")

    if args.examples:
        print_examples()
        raise SystemExit(0)

    # Non-interactive path for CI/automation and shells that do not support piping into input()
    if args.holdings or args.holdings_file or args.preset:
        try:
            raw_text = None
            if args.holdings_file:
                with open(args.holdings_file, "r", encoding="utf-8") as fp:
                    raw_text = fp.read()
            elif args.holdings:
                raw_text = args.holdings

            if raw_text is not None:
                holdings = parse_holdings_input(raw_text)
            elif args.preset:
                holdings = PRESET_HOLDINGS.get(args.preset, {})
            else:
                holdings = {}

            if not holdings:
                print("No holdings provided.")
                raise SystemExit(1)
            df = calculate_portfolio(holdings)
            pretty_print_dataframe(df)
            export_portfolio_to_csv(df)
            if args.watch:
                watch_portfolio(holdings, refresh_seconds=int(args.watch))
        except Exception as error:
            example = "{'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}"
            print(f"Error: {error}. Use format {example}")
            raise SystemExit(1)
        raise SystemExit(0)

    # Interactive fallback
    while True:
        try:
            holdings_input = input("Enter holdings (e.g., {'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}) or 'quit' (or type 'examples'): ")
        except EOFError:
            break
        if not holdings_input:
            continue
        lower = holdings_input.strip().lower()
        if lower == "quit":
            break
        if lower == "examples":
            print_examples()
            continue
        try:
            holdings = parse_holdings_input(holdings_input)
            if not holdings:
                print("No holdings provided.")
                continue
            df = calculate_portfolio(holdings)
            pretty_print_dataframe(df)
            export_portfolio_to_csv(df)

            follow_up = input("Type 'watch' to refresh every 5 minutes, or press Enter to continue: ").strip().lower()
            if follow_up == "watch":
                watch_portfolio(holdings, refresh_seconds=300)
        except Exception as error:
            example = "{'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}"
            print(f"Error: {error}. Use format {example}")

    print("Goodbye!") 