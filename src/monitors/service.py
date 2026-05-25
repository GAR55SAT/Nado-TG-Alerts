from __future__ import annotations

import logging
import time
from typing import Callable, Awaitable

from src.alerts.formatters import (
    AlertMessage,
    format_funding_change,
    format_funding_sign_flip,
    format_health_warning,
    format_liquidation_event,
    format_liquidation_feed_entry,
)
from src.config import Settings
from src.nado.client import NadoClient
from src.nado.subaccount import (
    build_subaccount_hex,
    funding_rate_to_bps,
    from_x18,
    is_valid_wallet,
)
from src.storage.state import BotState, WatchedAccount

logger = logging.getLogger(__name__)

AlertCallback = Callable[[AlertMessage], Awaitable[None]]


class MonitorService:
    def __init__(
        self,
        client: NadoClient,
        settings: Settings,
        state: BotState,
        on_alert: AlertCallback,
    ) -> None:
        self.client = client
        self.settings = settings
        self.state = state
        self.on_alert = on_alert
        self._symbol_map: dict[int, str] = {}

    def refresh_symbols(self) -> None:
        products = self.client.get_perp_products()
        self._symbol_map = {p["product_id"]: p["symbol"] for p in products}

    def _symbol(self, product_id: int) -> str:
        return self._symbol_map.get(product_id, f"PRODUCT-{product_id}")

    async def run_cycle(self) -> None:
        self.refresh_symbols()
        perp_ids = list(self._symbol_map.keys())

        if self.settings.global_funding_alerts:
            await self._check_global_funding(perp_ids)

        if self.settings.global_liquidation_alerts:
            await self._check_global_liquidation_feed()

        accounts = self._collect_watched_accounts()
        for account in accounts:
            await self._check_account(account, perp_ids)

    def _collect_watched_accounts(self) -> list[WatchedAccount]:
        seen: set[tuple[str, str, int | None]] = set()
        accounts: list[WatchedAccount] = []

        if is_valid_wallet(self.settings.nado_wallet_address):
            for chat_id in self.settings.default_chat_ids:
                key = (
                    self.settings.nado_wallet_address.lower(),
                    self.settings.nado_subaccount_name,
                    chat_id,
                )
                if key not in seen:
                    seen.add(key)
                    accounts.append(
                        WatchedAccount(
                            wallet=self.settings.nado_wallet_address,
                            subaccount_name=self.settings.nado_subaccount_name,
                            chat_id=chat_id,
                        )
                    )

        for account in self.state.watched_accounts:
            key = (account.wallet.lower(), account.subaccount_name, account.chat_id)
            if key not in seen:
                seen.add(key)
                accounts.append(account)

        return accounts

    async def _check_global_funding(self, perp_ids: list[int]) -> None:
        rates = self.client.get_funding_rates(perp_ids)
        for product_id_str, data in rates.items():
            symbol = self._symbol(int(product_id_str))
            rate_x18 = data["funding_rate_x18"]
            new_bps = funding_rate_to_bps(rate_x18)
            old_raw = self.state.funding_rates.get(product_id_str)
            self.state.funding_rates[product_id_str] = rate_x18

            if old_raw is None:
                continue

            old_bps = funding_rate_to_bps(old_raw)
            delta = abs(new_bps - old_bps)
            sign_flip = (old_bps >= 0 > new_bps) or (old_bps < 0 <= new_bps)

            if sign_flip:
                await self.on_alert(
                    AlertMessage(text=format_funding_sign_flip(symbol, old_bps, new_bps))
                )
            elif delta >= self.settings.funding_change_threshold_bps:
                await self.on_alert(
                    AlertMessage(
                        text=format_funding_change(symbol, old_bps, new_bps)
                    )
                )

    async def _check_global_liquidation_feed(self) -> None:
        feed = self.client.get_liquidation_feed()
        current = {entry["subaccount"] for entry in feed}
        new_entries = current - self.state.liquidation_feed
        self.state.liquidation_feed = current

        for subaccount in new_entries:
            await self.on_alert(
                AlertMessage(text=format_liquidation_feed_entry(subaccount, personal=False))
            )

    async def _check_account(self, account: WatchedAccount, perp_ids: list[int]) -> None:
        subaccount_hex = build_subaccount_hex(account.wallet, account.subaccount_name)
        chat_ids = [account.chat_id] if account.chat_id else None

        if self.settings.liquidation_feed_alert:
            await self._check_personal_liquidation_feed(subaccount_hex, chat_ids)

        await self._check_liquidation_events(subaccount_hex, chat_ids)
        await self._check_health(subaccount_hex, account, chat_ids)
        if self.settings.personal_funding_alerts:
            await self._check_position_funding(subaccount_hex, account, chat_ids)

    async def _check_personal_liquidation_feed(
        self,
        subaccount_hex: str,
        chat_ids: list[int] | None,
    ) -> None:
        feed = self.client.get_liquidation_feed()
        key = subaccount_hex.lower()
        on_feed = any(entry["subaccount"].lower() == key for entry in feed)

        if on_feed and key not in self.state.personal_feed_alerted:
            self.state.personal_feed_alerted.add(key)
            await self.on_alert(
                AlertMessage(
                    text=format_liquidation_feed_entry(subaccount_hex, personal=True),
                    chat_ids=chat_ids,
                )
            )

        if not on_feed and key in self.state.personal_feed_alerted:
            self.state.personal_feed_alerted.discard(key)

    async def _check_liquidation_events(
        self,
        subaccount_hex: str,
        chat_ids: list[int] | None,
    ) -> None:
        key = subaccount_hex.lower()
        last_idx = self.state.last_liquidation_event_idx.get(key)

        payload = self.client.get_events(
            subaccounts=[subaccount_hex],
            event_types=["liquidate_subaccount"],
            limit=5,
        )
        events = payload.get("events", [])
        if not events:
            return

        newest_idx = events[0]["submission_idx"]
        if last_idx is None:
            self.state.last_liquidation_event_idx[key] = newest_idx
            return

        if int(newest_idx) <= int(last_idx):
            return

        new_events = [
            e for e in events if int(e["submission_idx"]) > int(last_idx)
        ]
        self.state.last_liquidation_event_idx[key] = newest_idx

        for event in reversed(new_events):
            symbol = self._symbol(event.get("product_id", -1))
            await self.on_alert(
                AlertMessage(
                    text=format_liquidation_event(subaccount_hex, symbol),
                    chat_ids=chat_ids,
                )
            )

    async def _check_health(
        self,
        subaccount_hex: str,
        account: WatchedAccount,
        chat_ids: list[int] | None,
    ) -> None:
        try:
            info = self.client.get_subaccount_info(subaccount_hex)
        except Exception as exc:
            logger.warning("subaccount_info failed for %s: %s", subaccount_hex, exc)
            return

        if not info.get("exists"):
            return

        healths = info.get("healths", [])
        if len(healths) < 2:
            return

        maintenance = from_x18(healths[1]["health"])
        assets = from_x18(healths[1]["assets"])
        liabilities = from_x18(healths[1]["liabilities"])

        alert_key = subaccount_hex.lower()
        threshold = self.settings.health_warning_usd

        if maintenance > threshold:
            self.state.last_health_alert_value.pop(alert_key, None)
            return

        now = time.time()
        last_alert_ts = self.state.last_health_alert_ts.get(alert_key, 0)
        last_alert_health = self.state.last_health_alert_value.get(alert_key)

        cooldown = self.settings.health_alert_cooldown_seconds
        if now - last_alert_ts < cooldown:
            return

        if last_alert_health is not None and maintenance >= last_alert_health:
            return

        self.state.last_health_alert_ts[alert_key] = now
        self.state.last_health_alert_value[alert_key] = maintenance
        await self.on_alert(
            AlertMessage(
                text=format_health_warning(
                    account.wallet,
                    account.subaccount_name,
                    maintenance,
                    assets,
                    liabilities,
                ),
                chat_ids=chat_ids,
            )
        )

    async def _check_position_funding(
        self,
        subaccount_hex: str,
        account: WatchedAccount,
        chat_ids: list[int] | None,
    ) -> None:
        try:
            info = self.client.get_subaccount_info(subaccount_hex)
        except Exception as exc:
            logger.warning("subaccount_info failed for %s: %s", subaccount_hex, exc)
            return

        if not info.get("exists"):
            return

        perp_balances = info.get("perp_balances", [])
        active_products = [
            b["product_id"]
            for b in perp_balances
            if int(b["balance"]["amount"]) != 0
        ]
        if not active_products:
            return

        rates = self.client.get_funding_rates(active_products)
        for product_id in active_products:
            pid = str(product_id)
            data = rates.get(pid)
            if not data:
                continue

            symbol = self._symbol(product_id)
            rate_x18 = data["funding_rate_x18"]
            new_bps = funding_rate_to_bps(rate_x18)
            state_key = f"personal:{subaccount_hex.lower()}:{pid}"
            old_raw = self.state.funding_rates.get(state_key)
            self.state.funding_rates[state_key] = rate_x18

            if old_raw is None:
                continue

            old_bps = funding_rate_to_bps(old_raw)
            delta = abs(new_bps - old_bps)
            sign_flip = (old_bps >= 0 > new_bps) or (old_bps < 0 <= new_bps)

            if sign_flip or delta >= self.settings.funding_change_threshold_bps:
                await self.on_alert(
                    AlertMessage(
                        text=format_funding_change(
                            symbol,
                            old_bps,
                            new_bps,
                            personal=True,
                            wallet=account.wallet,
                        ),
                        chat_ids=chat_ids,
                    )
                )
