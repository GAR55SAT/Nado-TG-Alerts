from __future__ import annotations

from dataclasses import dataclass

from src.nado.subaccount import from_x18


@dataclass
class PositionDetail:
    symbol: str
    product_id: int
    side: str
    size: float
    mark_price: float
    entry_price: float
    value_usd: float
    est_pnl_usd: float
    funding_paid_usd: float
    funding_rate_bps: float
    est_liq_price: float | None


def _mid_price(market: dict | None, product: dict | None) -> float:
    if market:
        bid = from_x18(market["bid_x18"])
        ask = from_x18(market["ask_x18"])
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
    if product:
        return from_x18(product["oracle_price_x18"])
    return 0.0


def _entry_price(amount: float, v_quote: float) -> float | None:
    if amount == 0:
        return None
    return abs(v_quote / amount)


def _unrealized_pnl(amount: float, mark: float, v_quote: float) -> float:
    return amount * mark + v_quote


def _funding_paid_usd(amount: float, last_cum: int, product_state: dict) -> float:
    if amount == 0:
        return 0.0
    if amount > 0:
        current = int(product_state["cumulative_funding_long_x18"])
    else:
        current = int(product_state["cumulative_funding_short_x18"])
    index_delta = current - int(last_cum)
    return from_x18(amount) * from_x18(index_delta)


def _estimate_liq_price(
    *,
    side: str,
    mark: float,
    size: float,
    maintenance_health: float,
) -> float | None:
    if size == 0 or maintenance_health <= 0:
        return None
    abs_size = abs(size)
    if side == "LONG":
        return mark - (maintenance_health / abs_size)
    return mark + (maintenance_health / abs_size)


def build_position_details(
    info: dict,
    *,
    symbol_map: dict[int, str],
    funding_rates: dict[str, dict],
    market_prices: dict[int, dict],
    maintenance_health: float,
) -> list[PositionDetail]:
    perp_products = {p["product_id"]: p for p in info.get("perp_products", [])}
    details: list[PositionDetail] = []

    for bal in info.get("perp_balances", []):
        product_id = bal["product_id"]
        amount = from_x18(bal["balance"]["amount"])
        if amount == 0:
            continue

        product = perp_products.get(product_id, {})
        mark = _mid_price(market_prices.get(product_id), product)
        v_quote = from_x18(bal["balance"]["v_quote_balance"])
        entry = _entry_price(amount, v_quote)
        side = "LONG" if amount > 0 else "SHORT"
        pnl = _unrealized_pnl(amount, mark, v_quote)
        value = abs(amount) * mark

        product_state = product.get("state", {})
        funding_paid = _funding_paid_usd(
            amount,
            int(bal["balance"]["last_cumulative_funding_x18"]),
            product_state,
        )

        pid = str(product_id)
        funding_bps = 0.0
        if pid in funding_rates:
            from src.nado.subaccount import funding_rate_to_bps

            funding_bps = funding_rate_to_bps(funding_rates[pid]["funding_rate_x18"])

        liq = _estimate_liq_price(
            side=side,
            mark=mark,
            size=amount,
            maintenance_health=maintenance_health,
        )

        details.append(
            PositionDetail(
                symbol=symbol_map.get(product_id, f"PRODUCT-{product_id}"),
                product_id=product_id,
                side=side,
                size=abs(amount),
                mark_price=mark,
                entry_price=entry or 0.0,
                value_usd=value,
                est_pnl_usd=pnl,
                funding_paid_usd=funding_paid,
                funding_rate_bps=funding_bps,
                est_liq_price=liq,
            )
        )

    return details
