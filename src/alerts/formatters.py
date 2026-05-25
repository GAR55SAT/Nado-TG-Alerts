from __future__ import annotations

from dataclasses import dataclass

from src.funding.arb import funding_side_label
from src.nado.positions import PositionDetail
from src.nado.subaccount import (
    funding_rate_to_bps,
    parse_subaccount_hex,
    short_address,
)


@dataclass
class AlertMessage:
    text: str
    chat_ids: list[int] | None = None


def format_funding_change(
    symbol: str,
    old_bps: float,
    new_bps: float,
    *,
    personal: bool = False,
    wallet: str | None = None,
) -> str:
    direction = "📈" if new_bps > old_bps else "📉"
    scope = "Your position" if personal else "Market"
    header = f"{direction} <b>Funding update</b> — {symbol}"
    if personal and wallet:
        header += f"\nWallet: <code>{short_address(wallet)}</code>"
    return (
        f"{header}\n"
        f"{scope} 24h funding: <b>{old_bps:+.2f} bps</b> → <b>{new_bps:+.2f} bps</b>\n"
        f"≈ APR: {(new_bps / 10_000 * 365 * 100):+.1f}%"
    )


def format_funding_sign_flip(symbol: str, old_bps: float, new_bps: float) -> str:
    return (
        f"🔄 <b>Funding sign flip</b> — {symbol}\n"
        f"24h funding: {old_bps:+.2f} bps → {new_bps:+.2f} bps\n"
        f"Longs {'pay' if new_bps > 0 else 'receive'} / Shorts {'receive' if new_bps > 0 else 'pay'}"
    )


def format_liquidation_feed_entry(subaccount_hex: str, *, personal: bool = False) -> str:
    owner, name = parse_subaccount_hex(subaccount_hex)
    if personal:
        return (
            f"🚨 <b>LIQUIDATION RISK — your account</b>\n"
            f"Your subaccount <code>{name}</code> ({short_address(owner)}) "
            f"is on Nado's liquidation feed.\n"
            f"Reduce exposure or add collateral immediately."
        )
    return (
        f"⚠️ <b>Liquidation feed</b>\n"
        f"Account {short_address(owner)} / <code>{name}</code> is liquidatable."
    )


def format_liquidation_event(subaccount_hex: str, product_symbol: str) -> str:
    owner, name = parse_subaccount_hex(subaccount_hex)
    return (
        f"💥 <b>Account liquidated</b>\n"
        f"Wallet: <code>{short_address(owner)}</code>\n"
        f"Subaccount: <code>{name}</code>\n"
        f"Product: <b>{product_symbol}</b>\n"
        f"Event: <code>liquidate_subaccount</code>"
    )


def format_health_warning(
    wallet: str,
    subaccount_name: str,
    maintenance_health_usd: float,
    assets_usd: float,
    liabilities_usd: float,
) -> str:
    ratio = (maintenance_health_usd / assets_usd * 100) if assets_usd > 0 else 0
    return (
        f"🟠 <b>Low margin health</b>\n"
        f"Wallet: <code>{short_address(wallet)}</code> / <code>{subaccount_name}</code>\n"
        f"Maintenance health: <b>${maintenance_health_usd:,.2f}</b>\n"
        f"Assets: ${assets_usd:,.2f} | Liabilities: ${liabilities_usd:,.2f}\n"
        f"Health / assets: {ratio:.1f}%\n"
        f"Consider reducing positions or adding collateral."
    )


def format_nado_funding(
    rows: list[tuple[str, float, float]],
    min_apr_pct: float,
) -> str:
    """rows: (symbol, bps, apr%) — only |apr| >= min_apr_pct."""
    lines = [
        f"📊 <b>Nado funding</b> (|APR| ≥ {min_apr_pct:.0f}%)",
        "",
    ]
    if not rows:
        lines.append("No Nado markets above the threshold right now.")
        lines.append("Try again later with /nadofunding")
        return "\n".join(lines)

    for symbol, bps, apr in sorted(rows, key=lambda r: abs(r[2]), reverse=True):
        tag = "Longs pay" if apr > 0 else "Shorts pay"
        lines.append(f"• <b>{symbol}</b>: {bps:+.2f} bps · {apr:+.1f}% APR ({tag})")
    return "\n".join(lines)


def format_funding_arbitrage(
    opportunities: list,
    *,
    min_spread_apr_pct: float,
    venue_errors: dict[str, str],
    hedge_hint_fn,
) -> str:
    lines = [
        f"⚡ <b>Funding arbitrage vs Nado</b> (spread ≥ {min_spread_apr_pct:.0f}% APR)",
        "Positive &amp; negative funding · annual APR · delta-neutral hint.",
        "",
    ]

    if not opportunities:
        lines.append("No fat spreads vs Nado right now.")
        lines.append(f"Threshold: {min_spread_apr_pct:.0f}% APR spread.")
        lines.append("Try again with /fundingarb")
    else:
        for idx, opp in enumerate(opportunities):
            if idx > 0:
                lines.append("")
            lines.append(f"<b>{opp.nado_symbol}</b> — spread <b>{opp.spread_apr:.0f}%</b>")
            lines.append(
                f"Nado: {opp.nado_apr:+.1f}% ({funding_side_label(opp.nado_apr)})"
            )
            lines.append(
                f"{opp.venue}: {opp.venue_apr:+.1f}% ({funding_side_label(opp.venue_apr)})"
            )
            lines.append(f"→ {hedge_hint_fn(opp)}")

    if venue_errors:
        lines.append("")
        lines.append("<i>Partial data:</i>")
        for venue, error in venue_errors.items():
            short = error if len(error) <= 60 else error[:57] + "…"
            lines.append(f"• {venue}: {short}")

    return "\n".join(lines)


def format_funding_opportunities(
    rows: list[tuple[str, float, float]],
    min_apr_pct: float,
) -> str:
    """Backward-compatible alias for Nado-only funding screen."""
    return format_nado_funding(rows, min_apr_pct)


def format_positions_summary(
    wallet: str,
    subaccount_name: str,
    positions: list[PositionDetail],
    maintenance_health_usd: float,
) -> str:
    lines = [
        f"📊 <b>Positions</b>",
        f"<code>{short_address(wallet)}</code> / <code>{subaccount_name}</code>",
        f"Maintenance health: <b>${maintenance_health_usd:,.2f}</b>",
        "",
    ]

    if not positions:
        lines.append("No open perp positions.")
        return "\n".join(lines)

    for idx, pos in enumerate(positions):
        if idx > 0:
            lines.append("")
        lines.extend(_format_single_position(pos))

    return "\n".join(lines)


def _format_single_position(pos: PositionDetail) -> list[str]:
    liq_txt = f"${pos.est_liq_price:,.2f}" if pos.est_liq_price is not None else "—"

    pnl_prefix = "+" if pos.est_pnl_usd >= 0 else ""
    fund_prefix = "+" if pos.funding_paid_usd >= 0 else ""

    return [
        f"<b>{pos.symbol}</b> · {pos.side} {pos.size:.4f}",
        f"Value: <b>${pos.value_usd:,.2f}</b>",
        f"Entry: ${pos.entry_price:,.2f} · Mark: ${pos.mark_price:,.2f}",
        f"Est. PnL: <b>{pnl_prefix}${pos.est_pnl_usd:,.2f}</b>",
        f"Funding paid: {fund_prefix}${pos.funding_paid_usd:,.2f} · Rate: {pos.funding_rate_bps:+.2f} bps",
        f"Est. liq. price: {liq_txt}",
    ]


def format_liquidation_feed_list(entries: list[str], limit: int = 10) -> str:
    lines = [f"⚠️ <b>Liquidation feed</b> ({len(entries)} accounts)", ""]
    for sub in entries[:limit]:
        owner, name = parse_subaccount_hex(sub)
        lines.append(f"• {short_address(owner)} / <code>{name}</code>")
    if len(entries) > limit:
        lines.append(f"\n… and {len(entries) - limit} more")
    return "\n".join(lines)
