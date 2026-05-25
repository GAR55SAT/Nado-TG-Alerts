from __future__ import annotations

from dataclasses import dataclass

from src.funding.symbols import index_venue_rates, lookup_keys, nado_base_symbol
from src.funding.venues import VenueSnapshot, fetch_all_venues
from src.nado.client import NadoClient
from src.nado.subaccount import funding_rate_to_apr_percent


@dataclass
class FundingArbOpportunity:
    nado_symbol: str
    base: str
    nado_apr: float
    venue: str
    venue_apr: float
    spread_apr: float


def funding_side_label(apr: float) -> str:
    if apr > 0:
        return "longs pay"
    if apr < 0:
        return "longs receive"
    return "neutral"


def _hedge_hint(nado_apr: float, venue_apr: float, venue: str) -> str:
    if nado_apr >= venue_apr:
        return f"Short Nado · Long {venue}"
    return f"Long Nado · Short {venue}"


def _involves_negative_funding(opp: FundingArbOpportunity) -> bool:
    return (
        opp.nado_apr < 0
        or opp.venue_apr < 0
        or (opp.nado_apr * opp.venue_apr < 0)
    )


def _select_opportunities(
    opportunities: list[FundingArbOpportunity],
    max_results: int,
) -> list[FundingArbOpportunity]:
    """Keep top spreads but reserve slots for negative / opposite-sign funding arbs."""
    if not opportunities:
        return []

    negative_pool = sorted(
        [o for o in opportunities if _involves_negative_funding(o)],
        key=lambda item: item.spread_apr,
        reverse=True,
    )
    all_sorted = sorted(opportunities, key=lambda item: item.spread_apr, reverse=True)

    reserved = min(max(2, max_results // 3), len(negative_pool)) if negative_pool else 0
    selected: list[FundingArbOpportunity] = []
    seen: set[str] = set()

    for opp in negative_pool:
        if len(selected) >= reserved:
            break
        if opp.nado_symbol in seen:
            continue
        selected.append(opp)
        seen.add(opp.nado_symbol)

    for opp in all_sorted:
        if len(selected) >= max_results:
            break
        if opp.nado_symbol in seen:
            continue
        selected.append(opp)
        seen.add(opp.nado_symbol)

    selected.sort(key=lambda item: item.spread_apr, reverse=True)
    return selected[:max_results]


def _find_rate(indexed: dict[str, float], base: str) -> float | None:
    for key in lookup_keys(base):
        if key in indexed:
            return indexed[key]
    return None


async def scan_funding_arbitrage(
    nado_client: NadoClient,
    *,
    min_spread_apr_pct: float,
    max_results: int,
) -> tuple[list[FundingArbOpportunity], dict[str, VenueSnapshot]]:
    perps = nado_client.get_perp_products()
    product_ids = [p["product_id"] for p in perps]
    nado_rates = nado_client.get_funding_rates(product_ids)

    venue_snapshots = await fetch_all_venues()
    indexed_venues = {
        name: index_venue_rates(snapshot.rates)
        for name, snapshot in venue_snapshots.items()
    }

    opportunities: list[FundingArbOpportunity] = []

    for product in perps:
        pid = str(product["product_id"])
        rate_data = nado_rates.get(pid)
        if not rate_data:
            continue

        nado_symbol = product["symbol"]
        base = nado_base_symbol(nado_symbol)
        nado_apr = funding_rate_to_apr_percent(rate_data["funding_rate_x18"])

        best: FundingArbOpportunity | None = None
        for venue_name, indexed in indexed_venues.items():
            venue_apr = _find_rate(indexed, base)
            if venue_apr is None:
                continue
            spread = abs(nado_apr - venue_apr)
            if spread < min_spread_apr_pct:
                continue
            candidate = FundingArbOpportunity(
                nado_symbol=nado_symbol,
                base=base,
                nado_apr=nado_apr,
                venue=venue_name,
                venue_apr=venue_apr,
                spread_apr=spread,
            )
            if best is None or candidate.spread_apr > best.spread_apr:
                best = candidate

        if best:
            opportunities.append(best)

    return _select_opportunities(opportunities, max_results), venue_snapshots


def hedge_hint_for(opportunity: FundingArbOpportunity) -> str:
    return _hedge_hint(opportunity.nado_apr, opportunity.venue_apr, opportunity.venue)
