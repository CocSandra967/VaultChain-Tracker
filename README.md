# VaultChain-Tracker

Privacy-first, open-source CLI to track crypto and stocks locally. No account, no cloud, no telemetry.

- Real-time prices: BTC, ETH, SOL, DOGE… + AAPL, MSFT, NVDA, SPY, QQQ, etc.
- Local portfolio valuation
- CSV export with timestamp

## Quick start

### Prerequisites
- Python 3.11+ (3.13 tested)

### Install
```bash
python -m pip install -r requirements.txt
```

### Configure API key
- Crypto prices use CoinGecko (no key required)
- Stock prices use Alpha Vantage (free key, ~25 requests/day)
  - Get a key: https://www.alphavantage.co/support/#api-key
  - Put it in a `.env` file at the project root:
    ```
    ALPHA_VANTAGE_API_KEY=YOUR_KEY
    ```
  - Or for the current PowerShell session only:
    ```powershell
    $env:ALPHA_VANTAGE_API_KEY='YOUR_KEY'
    ```

## Run
```bash
python vaultchain/vaultchain_tracker.py
```

You can run in two ways.

### 1) Interactive mode
Type your holdings when prompted.

- Crypto example:
  ```python
  {'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}
  ```
- Stocks (US):
  ```python
  {'AAPL': 1, 'MSFT': 2, 'NVDA': 1}
  ```
- International (with exchange suffix):
  ```python
  {'700.HK': 2, '7203.T': 1, 'RIO.L': 3}
  ```
  Notes:
  - Hong Kong tickers are auto-padded to 4 digits internally (e.g., `700.HK` → `0700.HK`).
  - If Alpha Vantage has no realtime quote, the tool auto-falls back to the latest daily close or Yahoo Finance.
- Mixed:
  ```python
  {'BTC': 0.005, 'AAPL': 1, 'ETH': 0.1}
  ```
- Type `examples` anytime to see sample inputs
- Type `watch` after a run to refresh every 5 minutes

### 2) Non-interactive mode (automation friendly)
- Use a preset portfolio:
  ```bash
  python vaultchain/vaultchain_tracker.py --preset crypto   # BTC/ETH/SOL
  python vaultchain/vaultchain_tracker.py --preset stocks   # AAPL/MSFT/NVDA
  python vaultchain/vaultchain_tracker.py --preset intl     # 700.HK/7203.T/RIO.L (HK padded automatically)
  python vaultchain/vaultchain_tracker.py --preset etf      # SPY/QQQ/VTI
  python vaultchain/vaultchain_tracker.py --preset mix
  ```
- Pass holdings inline:
  ```bash
  python vaultchain/vaultchain_tracker.py --holdings "{'BTC': 0.01, 'ETH': 0.2, 'SOL': 3}"
  ```
- Or from a file:
  ```bash
  # holdings.json -> {"BTC": 0.005, "AAPL": 1}
  python vaultchain/vaultchain_tracker.py --holdings-file holdings.json
  ```
- Watch mode:
  ```bash
  python vaultchain/vaultchain_tracker.py --preset mix --watch 300
  ```

## Supported assets
- Crypto via CoinGecko
  - Built-in symbol mapping: BTC→bitcoin, ETH→ethereum, SOL→solana, DOGE→dogecoin, BNB, XRP, ADA, MATIC, TRX, LTC, DOT
  - You can also use CoinGecko ids directly (e.g., `bitcoin`, `ethereum`, `solana`)
- Stocks via Alpha Vantage with resilient fallbacks
  - US tickers (AAPL, MSFT, NVDA, SPY, QQQ, …)
  - International tickers with exchange suffix: `700.HK` (HK), `7203.T` (TSE), `RIO.L` (LSE)
  - Hong Kong tickers are normalized to 4 digits automatically (e.g., `700.HK` → `0700.HK`)
  - If the realtime quote is missing or throttled, the tool falls back to the latest daily close; if still unavailable, it falls back to Yahoo Finance
  - Note: Mainland China A-shares are not supported in this version

## Output
- Each run prints a table: Asset, Quantity, Price(USD), Value(USD), plus a total row
- CSV export is automatic: `vaultchain_portfolio_YYYYMMDD_HHMMSS.csv`

## Troubleshooting
- Alpha Vantage notice / rate limit
  - The free tier allows ~25 requests/day; wait ~60 seconds and retry, or reduce refresh frequency
- A price shows as 0 or missing
  - The app will try: Realtime → Daily Close → Yahoo Finance; logs like “Using last daily close …” or “Using Yahoo Finance …” are expected
- PowerShell quoting issues
  - Prefer `--holdings-file` or `--preset` to avoid quoting/escaping problems

## Why privacy-first?
- No servers, no cloud sync, no telemetry
- Your keys and CSVs stay on your machine

## Roadmap
- Multi-fiat support (EUR, HKD, JPY), FX conversion
- Custom symbol mappings via config file
- Alerts and simple rules (paid version)
- Optional GUI & cloud sync (paid version)

## License
MIT
