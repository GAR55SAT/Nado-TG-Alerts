from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WatchedAccount:
    wallet: str
    subaccount_name: str = "default"
    chat_id: int | None = None


@dataclass
class BotState:
    funding_rates: dict[str, str] = field(default_factory=dict)
    liquidation_feed: set[str] = field(default_factory=set)
    personal_feed_alerted: set[str] = field(default_factory=set)
    last_liquidation_event_idx: dict[str, str] = field(default_factory=dict)
    last_health_alert_ts: dict[str, float] = field(default_factory=dict)
    last_health_alert_value: dict[str, float] = field(default_factory=dict)
    watched_accounts: list[WatchedAccount] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "funding_rates": self.funding_rates,
            "liquidation_feed": sorted(self.liquidation_feed),
            "personal_feed_alerted": sorted(self.personal_feed_alerted),
            "last_liquidation_event_idx": self.last_liquidation_event_idx,
            "last_health_alert_ts": self.last_health_alert_ts,
            "last_health_alert_value": self.last_health_alert_value,
            "watched_accounts": [
                {
                    "wallet": a.wallet,
                    "subaccount_name": a.subaccount_name,
                    "chat_id": a.chat_id,
                }
                for a in self.watched_accounts
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> BotState:
        watched = [
            WatchedAccount(
                wallet=item["wallet"],
                subaccount_name=item.get("subaccount_name", "default"),
                chat_id=item.get("chat_id"),
            )
            for item in data.get("watched_accounts", [])
        ]
        return cls(
            funding_rates=data.get("funding_rates", {}),
            liquidation_feed=set(data.get("liquidation_feed", [])),
            personal_feed_alerted=set(data.get("personal_feed_alerted", [])),
            last_liquidation_event_idx=data.get("last_liquidation_event_idx", {}),
            last_health_alert_ts={
                k: float(v) for k, v in data.get("last_health_alert_ts", {}).items()
            },
            last_health_alert_value={
                k: float(v) for k, v in data.get("last_health_alert_value", {}).items()
            },
            watched_accounts=watched,
        )


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> BotState:
        if not self.path.exists():
            return BotState()
        with self.path.open("r", encoding="utf-8") as f:
            return BotState.from_dict(json.load(f))

    def save(self, state: BotState) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

    def add_watch(self, state: BotState, wallet: str, subaccount_name: str, chat_id: int) -> bool:
        wallet = wallet.lower()
        for account in state.watched_accounts:
            if (
                account.wallet.lower() == wallet
                and account.subaccount_name == subaccount_name
                and account.chat_id == chat_id
            ):
                return False
        state.watched_accounts.append(
            WatchedAccount(wallet=wallet, subaccount_name=subaccount_name, chat_id=chat_id)
        )
        return True

    def remove_watch(
        self, state: BotState, wallet: str, subaccount_name: str, chat_id: int
    ) -> bool:
        wallet = wallet.lower()
        before = len(state.watched_accounts)
        state.watched_accounts = [
            a
            for a in state.watched_accounts
            if not (
                a.wallet.lower() == wallet
                and a.subaccount_name == subaccount_name
                and a.chat_id == chat_id
            )
        ]
        return len(state.watched_accounts) < before
