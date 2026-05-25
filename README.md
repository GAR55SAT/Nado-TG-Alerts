# Nado TG Alerts

Telegram bot for [Nado](https://nado.xyz) perp DEX alerts: funding rate changes, liquidation feed, and personal account monitoring.

## Features

- **Global funding alerts** — disabled by default; use `/nadofunding` or `/fundingarb` manually
- **Liquidation feed** — optional alerts for accounts at liquidation risk
- **Personal account watch** (`/addwallet`) — for your wallet:
  - appears on liquidation feed
  - actual `liquidate_subaccount` events
  - low maintenance health
  - funding changes on markets where you have open positions

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + all commands explained |
| `/help` | Command reference |
| `/addwallet 0x... [name]` | Save wallet for alerts & positions |
| `/removewallet 0x...` | Remove saved wallet |
| `/wallets` | Your saved wallets |
| `/nadofunding` | Nado funding opportunities (|APR| ≥ 10%) |
| `/funding` | Alias for `/nadofunding` |
| `/fundingarb` | Cross-exchange funding arb vs Nado (spread ≥ 30% APR) |
| `/farb` | Alias for `/fundingarb` |
| `/positions [0x...]` | Positions: value, entry, PnL, est. liq price, funding |
| `/health [0x...]` | Margin health |

## Setup

```bash
cd "Nado TG Alerts"
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
# Edit .env — add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS
python run.py
```

### Get Telegram chat ID

1. Start the bot and send `/start`
2. Copy the chat ID from the reply, or use [@userinfobot](https://t.me/userinfobot)
3. Put it in `TELEGRAM_CHAT_IDS` in `.env`

### VPS (production)

```bash
pip install -r requirements.txt
# systemd unit example:
# ExecStart=/path/to/.venv/bin/python /path/to/run.py
# WorkingDirectory=/path/to/Nado TG Alerts
```

## Environment

See `.env.example` for all options.

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_IDS` | Comma-separated chat IDs for alerts |
| `NADO_WALLET_ADDRESS` | Default wallet to monitor |
| `NADO_SUBACCOUNT_NAME` | Usually `default` |
| `POLL_INTERVAL_SECONDS` | How often to poll Nado API (default 30) |
| `FUNDING_CHANGE_THRESHOLD_BPS` | Min funding move to alert (default 5 bps) |
| `HEALTH_WARNING_USD` | Alert if maintenance health below this USD |
| `FUNDING_OPPORTUNITY_APR_PCT` | `/nadofunding` threshold (default 10% APR) |
| `FUNDING_ARB_MIN_SPREAD_APR_PCT` | `/fundingarb` min spread vs Nado (default 30%) |
| `FUNDING_ARB_MAX_RESULTS` | Max rows in `/fundingarb` (default 8) |
| `GLOBAL_FUNDING_ALERTS` | Market-wide funding alerts |
| `LIQUIDATION_FEED_ALERT` | Personal liquidation feed alerts |

## Data

State is stored in `data/state.json` (last funding values, watches, event cursors). Not committed to git.

## License

MIT
