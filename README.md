# Nado TG Alerts

Telegram bot for [Nado](https://nado.xyz) risk monitoring and funding arbitrage discovery.

The bot watches saved Nado wallets for liquidation risk and margin health, and includes a cross-exchange funding screener that compares Nado funding against other venues using annualized APR.

## Features

- **Wallet monitoring** — save wallets and receive liquidation-risk alerts.
- **Margin health alerts** — warns when maintenance health drops below the configured threshold.
- **Liquidation events** — alerts when a saved account is liquidated on Nado.
- **Nado funding screener** — shows Nado markets with high positive or negative annualized funding.
- **Funding arbitrage screener** — compares Nado funding against other venues and highlights large APR spreads.
- **Telegram command menu** — commands appear in Telegram when typing `/`.

## Funding Arbitrage Venues

`/fundingarb` compares Nado against:

- Pacifica
- Hyperliquid
- TradeXYZ
- Variational
- RISEx

Funding rates are normalized to annual APR before comparison.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + all commands explained |
| `/help` | Command reference |
| `/addwallet 0x...` | Save wallet for alerts & positions |
| `/removewallet 0x...` | Remove saved wallet |
| `/wallets` | Your saved wallets |
| `/nadofunding` | Nado funding opportunities (|APR| ≥ 10%) |
| `/fundingarb` | Cross-exchange funding arb vs Nado (spread ≥ 30% APR) |
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

### Telegram setup

Create a bot with [@BotFather](https://t.me/BotFather), copy the API token, and put it in `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

Get your Telegram chat ID:

1. Start the bot and send `/start`
2. Copy the chat ID from the reply, or use [@userinfobot](https://t.me/userinfobot)
3. Put it in `TELEGRAM_CHAT_IDS` in `.env`

### VPS (production)

```bash
git clone https://github.com/YOUR_USERNAME/Nado-TG-Alerts.git
cd Nado-TG-Alerts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env, then run:
python run.py
```

For 24/7 operation, run the bot with `systemd` or another process manager.

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

## Disclaimer

Funding APR is indicative and can change quickly. Always check liquidity, fees, slippage, settlement timing, and position risk before trading.

## License

MIT
