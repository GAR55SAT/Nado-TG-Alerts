from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from src.funding.normalize import rate_to_apr_pct, variational_rate_to_apr_pct

logger = logging.getLogger(__name__)

HOUR = 3600
EIGHT_HOURS = 8 * HOUR

PACIFICA_URL = "https://api.pacifica.fi/api/v1/info/prices"
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"
VARIATIONAL_URL = (
    "https://omni-client-api.prod.ap-northeast-1.variational.io/metadata/stats"
)
RISEX_URL = "https://api.rise.trade/v1/markets"


@dataclass
class VenueSnapshot:
    rates: dict[str, float] = field(default_factory=dict)
    error: str | None = None


def _hl_meta_ctxs(data: list) -> tuple[list[dict], list[dict]]:
    meta = data[0]
    ctxs = data[1]
    universe = meta["universe"] if isinstance(meta, dict) else meta
    return universe, ctxs


async def _fetch_pacifica(client: httpx.AsyncClient) -> VenueSnapshot:
    try:
        response = await client.get(PACIFICA_URL)
        response.raise_for_status()
        body = response.json()
        rates: dict[str, float] = {}
        for item in body.get("data", []):
            base = item["symbol"].upper()
            raw = item.get("next_funding") or item.get("funding") or "0"
            rates[base] = rate_to_apr_pct(float(raw), HOUR)
        return VenueSnapshot(rates=rates)
    except Exception as exc:
        logger.warning("Pacifica funding fetch failed: %s", exc)
        return VenueSnapshot(error=str(exc))


async def _fetch_hyperliquid_dex(
    client: httpx.AsyncClient, *, dex: str, interval_seconds: float, prefix: str
) -> VenueSnapshot:
    try:
        payload: dict[str, str] = {"type": "metaAndAssetCtxs"}
        if dex:
            payload["dex"] = dex
        response = await client.post(HYPERLIQUID_URL, json=payload)
        response.raise_for_status()
        universe, ctxs = _hl_meta_ctxs(response.json())
        rates: dict[str, float] = {}
        for asset, ctx in zip(universe, ctxs):
            name = asset["name"]
            if prefix and not name.startswith(prefix):
                continue
            base = name.split(":", 1)[1] if ":" in name else name
            rates[base.upper()] = rate_to_apr_pct(float(ctx["funding"]), interval_seconds)
        return VenueSnapshot(rates=rates)
    except Exception as exc:
        logger.warning("Hyperliquid dex=%s funding fetch failed: %s", dex or "main", exc)
        return VenueSnapshot(error=str(exc))


async def _fetch_variational(client: httpx.AsyncClient) -> VenueSnapshot:
    try:
        response = await client.get(VARIATIONAL_URL)
        response.raise_for_status()
        body = response.json()
        rates: dict[str, float] = {}
        for item in body.get("listings", []):
            ticker = item.get("ticker")
            funding = item.get("funding_rate")
            if not ticker or funding is None:
                continue
            rates[ticker.upper()] = variational_rate_to_apr_pct(float(funding))
        return VenueSnapshot(rates=rates)
    except Exception as exc:
        logger.warning("Variational funding fetch failed: %s", exc)
        return VenueSnapshot(error=str(exc))


async def _fetch_risex(client: httpx.AsyncClient) -> VenueSnapshot:
    try:
        response = await client.get(RISEX_URL)
        response.raise_for_status()
        body = response.json()
        rates: dict[str, float] = {}
        for item in body.get("data", {}).get("markets", []):
            raw_symbol = item.get("base_asset_symbol") or item.get("display_base_asset_symbol") or ""
            base = raw_symbol.split("/")[0].upper()
            if not base:
                continue
            rate = float(item.get("current_funding_rate") or 0)
            interval_ns = int(item.get("funding_interval") or HOUR * 1_000_000_000)
            interval_s = interval_ns / 1_000_000_000
            rates[base] = rate_to_apr_pct(rate, interval_s)
        return VenueSnapshot(rates=rates)
    except Exception as exc:
        logger.warning("RISEx funding fetch failed: %s", exc)
        return VenueSnapshot(error=str(exc))


async def fetch_all_venues() -> dict[str, VenueSnapshot]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        (
            pacifica,
            hyperliquid,
            trade_xyz,
            variational,
            risex,
        ) = await asyncio.gather(
            _fetch_pacifica(client),
            _fetch_hyperliquid_dex(client, dex="", interval_seconds=EIGHT_HOURS, prefix=""),
            _fetch_hyperliquid_dex(
                client, dex="xyz", interval_seconds=HOUR, prefix="xyz:"
            ),
            _fetch_variational(client),
            _fetch_risex(client),
        )
    return {
        "Pacifica": pacifica,
        "Hyperliquid": hyperliquid,
        "TradeXYZ": trade_xyz,
        "Variational": variational,
        "RISEx": risex,
    }
