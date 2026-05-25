from __future__ import annotations

X18 = 10**18


def is_valid_wallet(address: str) -> bool:
    if not address:
        return False
    clean = address.lower().removeprefix("0x")
    if len(clean) != 40:
        return False
    try:
        int(clean, 16)
    except ValueError:
        return False
    return True


def build_subaccount_hex(owner: str, subaccount_name: str = "default") -> str:
    owner_clean = owner.lower().removeprefix("0x")
    if not is_valid_wallet(owner):
        raise ValueError(f"Invalid wallet address: {owner}")
    name_bytes = subaccount_name.encode("utf-8")[:12].ljust(12, b"\x00")
    return "0x" + owner_clean + name_bytes.hex()


def parse_subaccount_hex(subaccount_hex: str) -> tuple[str, str]:
    raw = subaccount_hex.lower().removeprefix("0x")
    if len(raw) != 64:
        raise ValueError(f"Invalid subaccount hex: {subaccount_hex}")
    owner = "0x" + raw[:40]
    name_bytes = bytes.fromhex(raw[40:])
    name = name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace") or "default"
    return owner, name


def from_x18(value: str | int | float) -> float:
    return int(value) / X18


def funding_rate_to_bps(rate_x18: str | int) -> float:
    """Convert 24h funding rate (x18) to basis points."""
    return from_x18(rate_x18) * 10_000


def funding_rate_to_apr_percent(rate_x18: str | int) -> float:
    """Approximate APR from 24h funding rate."""
    daily = from_x18(rate_x18)
    return daily * 365 * 100


def format_usd(value_x18: str | int, decimals: int = 2) -> str:
    return f"${from_x18(value_x18):,.{decimals}f}"


def short_address(address: str) -> str:
    if len(address) < 10:
        return address
    return f"{address[:6]}…{address[-4:]}"
