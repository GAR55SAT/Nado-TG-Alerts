from __future__ import annotations

import logging
import re

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from src.alerts.formatters import (
    format_funding_arbitrage,
    format_nado_funding,
    format_positions_summary,
)
from src.bot.messages import HELP_TEXT, WELCOME_TEXT
from src.config import Settings
from src.funding.arb import hedge_hint_for, scan_funding_arbitrage
from src.nado.client import NadoClient
from src.nado.positions import build_position_details
from src.nado.subaccount import (
    build_subaccount_hex,
    format_usd,
    funding_rate_to_apr_percent,
    funding_rate_to_bps,
    from_x18,
    is_valid_wallet,
    short_address,
)
from src.storage.state import StateStore

logger = logging.getLogger(__name__)

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

BOT_COMMANDS = [
    BotCommand("start", "Welcome and quick setup"),
    BotCommand("help", "Show command list"),
    BotCommand("addwallet", "Save a wallet for alerts"),
    BotCommand("removewallet", "Remove a saved wallet"),
    BotCommand("wallets", "List saved wallets"),
    BotCommand("nadofunding", "Nado funding opportunities"),
    BotCommand("fundingarb", "Funding arbitrage vs Nado"),
    BotCommand("positions", "Open positions and PnL"),
    BotCommand("health", "Margin health and liquidation risk"),
]


class TelegramBotApp:
    def __init__(
        self,
        settings: Settings,
        client: NadoClient,
        store: StateStore,
    ) -> None:
        self.settings = settings
        self.client = client
        self.store = store
        self.state = store.load()
        self.application = (
            Application.builder().token(settings.telegram_bot_token).build()
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        handlers = [
            ("start", self.cmd_start),
            ("help", self.cmd_help),
            ("nadofunding", self.cmd_nado_funding),
            ("funding", self.cmd_nado_funding),
            ("fundingarb", self.cmd_funding_arb),
            ("farb", self.cmd_funding_arb),
            ("addwallet", self.cmd_addwallet),
            ("removewallet", self.cmd_removewallet),
            ("wallets", self.cmd_wallets),
            ("watch", self.cmd_addwallet),
            ("unwatch", self.cmd_removewallet),
            ("watches", self.cmd_wallets),
            ("positions", self.cmd_positions),
            ("health", self.cmd_health),
        ]
        for name, callback in handlers:
            self.application.add_handler(CommandHandler(name, callback))

    async def set_command_menu(self) -> None:
        await self.application.bot.set_my_commands(BOT_COMMANDS)

    async def send_alert(self, text: str, chat_ids: list[int] | None = None) -> None:
        targets = chat_ids or self.settings.default_chat_ids
        for chat_id in targets:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception as exc:
                logger.error("Failed to send alert to %s: %s", chat_id, exc)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            WELCOME_TEXT,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            HELP_TEXT,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    async def cmd_nado_funding(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_chat_action("typing")
        try:
            perps = self.client.get_perp_products()
            ids = [p["product_id"] for p in perps]
            rates = self.client.get_funding_rates(ids)
            min_apr = self.settings.funding_opportunity_apr_pct
            rows = []
            for p in perps:
                pid = str(p["product_id"])
                data = rates.get(pid)
                if not data:
                    continue
                bps = funding_rate_to_bps(data["funding_rate_x18"])
                apr = funding_rate_to_apr_percent(data["funding_rate_x18"])
                if abs(apr) >= min_apr:
                    rows.append((p["symbol"], bps, apr))
            await update.message.reply_text(
                format_nado_funding(rows, min_apr),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.exception("nadofunding command failed")
            await update.message.reply_text(f"Error: {exc}")

    async def cmd_funding_arb(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_chat_action("typing")
        try:
            opportunities, venue_snapshots = await scan_funding_arbitrage(
                self.client,
                min_spread_apr_pct=self.settings.funding_arb_min_spread_apr_pct,
                max_results=self.settings.funding_arb_max_results,
            )
            venue_errors = {
                name: snap.error
                for name, snap in venue_snapshots.items()
                if snap.error
            }
            await update.message.reply_text(
                format_funding_arbitrage(
                    opportunities,
                    min_spread_apr_pct=self.settings.funding_arb_min_spread_apr_pct,
                    venue_errors=venue_errors,
                    hedge_hint_fn=hedge_hint_for,
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.exception("fundingarb command failed")
            await update.message.reply_text(f"Error: {exc}")

    async def cmd_addwallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        args = context.args or []
        wallet = args[0] if args else self.settings.nado_wallet_address
        subaccount = args[1] if len(args) > 1 else self.settings.nado_subaccount_name

        if not wallet or not WALLET_RE.match(wallet):
            await update.message.reply_text(
                "<b>Add wallet</b>\n\n"
                "Usage: /addwallet 0xYourWalletAddress\n\n"
                "Example:\n"
                "<code>/addwallet 0xabc...def</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        added = self.store.add_watch(
            self.state, wallet, subaccount, update.effective_chat.id
        )
        self.store.save(self.state)

        if added:
            await update.message.reply_text(
                f"✅ Wallet added\n"
                f"<code>{short_address(wallet)}</code>\n\n"
                "You will receive alerts for:\n"
                "• liquidation risk on your wallet\n"
                "• low margin health\n"
                "• actual liquidations\n\n"
                "Try /positions to see details.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text("This wallet is already saved.")

    async def cmd_removewallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        args = context.args or []
        if not args or not WALLET_RE.match(args[0]):
            await update.message.reply_text("Usage: /removewallet 0xYourWalletAddress")
            return

        wallet = args[0]
        subaccount = args[1] if len(args) > 1 else "default"
        removed = self.store.remove_watch(
            self.state, wallet, subaccount, update.effective_chat.id
        )
        self.store.save(self.state)
        await update.message.reply_text(
            "Wallet removed." if removed else "Wallet not found in your list."
        )

    async def cmd_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat:
            return
        chat_id = update.effective_chat.id
        mine = [a for a in self.state.watched_accounts if a.chat_id == chat_id]
        if not mine:
            await update.message.reply_text(
                "No wallets saved yet.\nUse /addwallet 0xYourWalletAddress"
            )
            return
        lines = ["<b>Your wallets</b>", ""]
        for a in mine:
            lines.append(f"• <code>{short_address(a.wallet)}</code>")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    def _resolve_account(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> tuple[str, str] | None:
        args = context.args or []
        if args and WALLET_RE.match(args[0]):
            wallet = args[0]
            subaccount = args[1] if len(args) > 1 else self.settings.nado_subaccount_name
            return wallet, subaccount

        if update.effective_chat:
            chat_id = update.effective_chat.id
            mine = [a for a in self.state.watched_accounts if a.chat_id == chat_id]
            if mine:
                return mine[0].wallet, mine[0].subaccount_name

        if is_valid_wallet(self.settings.nado_wallet_address):
            return self.settings.nado_wallet_address, self.settings.nado_subaccount_name

        return None

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        resolved = self._resolve_account(update, context)
        if not resolved:
            await update.message.reply_text(
                "No wallet configured.\n\n"
                "Add one: /addwallet 0xYourWalletAddress\n"
                "Or query directly: /positions 0xYourWalletAddress"
            )
            return

        wallet, subaccount = resolved
        await update.message.reply_chat_action("typing")
        try:
            sub_hex = build_subaccount_hex(wallet, subaccount)
            info = self.client.get_subaccount_info(sub_hex)
            if not info.get("exists"):
                await update.message.reply_text("Subaccount not found on Nado.")
                return

            product_ids = [
                b["product_id"]
                for b in info.get("perp_balances", [])
                if int(b["balance"]["amount"]) != 0
            ]

            symbols = {p["product_id"]: p["symbol"] for p in self.client.get_perp_products()}
            rates = self.client.get_funding_rates(product_ids) if product_ids else {}
            market_prices = self.client.get_market_prices(product_ids)

            maintenance = (
                from_x18(info["healths"][1]["health"]) if info.get("healths") else 0.0
            )
            positions = build_position_details(
                info,
                symbol_map=symbols,
                funding_rates=rates,
                market_prices=market_prices,
                maintenance_health=maintenance,
            )

            await update.message.reply_text(
                format_positions_summary(wallet, subaccount, positions, maintenance),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.exception("positions command failed")
            await update.message.reply_text(f"Error: {exc}")

    async def cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        resolved = self._resolve_account(update, context)
        if not resolved:
            await update.message.reply_text(
                "Usage: /health 0xWallet or /addwallet 0xWallet first"
            )
            return

        wallet, subaccount = resolved
        await update.message.reply_chat_action("typing")
        try:
            sub_hex = build_subaccount_hex(wallet, subaccount)
            info = self.client.get_subaccount_info(sub_hex)
            if not info.get("exists"):
                await update.message.reply_text("Subaccount not found.")
                return
            h = info["healths"]
            text = (
                f"🩺 <b>Margin health</b>\n"
                f"<code>{short_address(wallet)}</code> / <code>{subaccount}</code>\n\n"
                f"Initial: {format_usd(h[0]['health'])}\n"
                f"Maintenance: {format_usd(h[1]['health'])}\n"
                f"Unweighted: {format_usd(h[2]['health'])}\n\n"
                f"Assets (maint.): {format_usd(h[1]['assets'])}\n"
                f"Liabilities: {format_usd(h[1]['liabilities'])}"
            )
            on_feed = any(
                e["subaccount"].lower() == sub_hex.lower()
                for e in self.client.get_liquidation_feed()
            )
            if on_feed:
                text += "\n\n🚨 <b>On liquidation feed!</b>"
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        except Exception as exc:
            logger.exception("health command failed")
            await update.message.reply_text(f"Error: {exc}")

    def persist_state(self) -> None:
        self.store.save(self.state)
