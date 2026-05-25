"""Quick local check for funding arb scanner (run: python scripts/test_funding_arb.py)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.funding.arb import hedge_hint_for, scan_funding_arbitrage
from src.nado.client import NadoClient


async def main() -> None:
    settings = get_settings()
    client = NadoClient(settings.archive_url, settings.gateway_url)
    try:
        opps, venues = await scan_funding_arbitrage(
            client,
            min_spread_apr_pct=settings.funding_arb_min_spread_apr_pct,
            max_results=settings.funding_arb_max_results,
        )
        print(f"Venues loaded: {len(venues)}")
        for name, snap in venues.items():
            status = f"{len(snap.rates)} markets" if not snap.error else f"ERR: {snap.error[:80]}"
            print(f"  {name}: {status}")
        print(f"\nOpportunities (spread >= {settings.funding_arb_min_spread_apr_pct}%): {len(opps)}")
        for opp in opps:
            print(
                f"  {opp.nado_symbol}: Nado {opp.nado_apr:+.1f}% vs "
                f"{opp.venue} {opp.venue_apr:+.1f}% = {opp.spread_apr:.0f}% | {hedge_hint_for(opp)}"
            )
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
