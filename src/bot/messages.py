WELCOME_TEXT = """\
👋 <b>Welcome to Nado TG Alerts</b>

I watch your wallets on <a href="https://nado.xyz">Nado</a> and send risk alerts here in Telegram.

<b>🔔 Automatic alerts</b>
• Liquidation risk on saved wallets (before it happens)
• Low margin health (only when it keeps getting worse)
• Liquidation on saved wallets (when it actually happens)

<b>📋 Commands</b>

<b>Wallets</b>
/addwallet &lt;0xAddress&gt; — save a wallet for alerts &amp; /positions
/removewallet &lt;0xAddress&gt; — remove a saved wallet
/wallets — list your saved wallets

<b>Markets</b>
/nadofunding — Nado funding only (|APR| ≥ 10%)
/fundingarb — cross-exchange funding arb vs Nado (spread ≥ 30%)

<b>Your account</b>
/positions [0xAddress] — open positions: value, entry, PnL, liq price, funding
/health [0xAddress] — margin health &amp; liquidation risk

<b>Other</b>
/help — command list

<b>Get started</b>
/addwallet 0xYourWalletAddress
"""

HELP_TEXT = """\
<b>Nado TG Alerts — commands</b>

<b>Wallets</b>
/addwallet &lt;0xWallet&gt; — save wallet
/removewallet &lt;0xWallet&gt; — remove wallet
/wallets — your saved wallets

<b>Markets</b>
/nadofunding — Nado funding (|APR| ≥ 10%)
/fundingarb — funding arbitrage vs Nado (spread ≥ 30% APR)

<b>Account</b>
/positions [0xWallet] — positions: value, entry, PnL, est. liq price, funding
/health [0xWallet] — margin health

/help — show this message
"""
