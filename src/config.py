from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str
    telegram_chat_ids: str = ""

    nado_network: str = "mainnet"
    nado_wallet_address: str = ""
    nado_subaccount_name: str = "default"

    poll_interval_seconds: int = 30
    funding_opportunity_apr_pct: float = 10.0
    funding_arb_min_spread_apr_pct: float = 30.0
    funding_arb_max_results: int = 8
    funding_change_threshold_bps: float = 5.0
    health_warning_usd: float = 50.0
    health_alert_cooldown_seconds: int = 900

    liquidation_feed_alert: bool = True
    global_funding_alerts: bool = False
    personal_funding_alerts: bool = False
    global_liquidation_alerts: bool = False

    state_file: str = "data/state.json"

    @property
    def default_chat_ids(self) -> list[int]:
        if not self.telegram_chat_ids.strip():
            return []
        return [int(x.strip()) for x in self.telegram_chat_ids.split(",") if x.strip()]

    @property
    def archive_url(self) -> str:
        if self.nado_network == "testnet":
            return "https://archive.test.nado.xyz/v1"
        return "https://archive.prod.nado.xyz/v1"

    @property
    def gateway_url(self) -> str:
        if self.nado_network == "testnet":
            return "https://gateway.test.nado.xyz"
        return "https://gateway.prod.nado.xyz"


def get_settings() -> Settings:
    return Settings()
