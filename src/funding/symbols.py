from __future__ import annotations

# Canonical base -> alternate symbols seen on other venues
SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "XAUT": ("XAU", "PAXG", "XAUT"),
    "kPEPE": ("kPEPE", "PEPE", "1000PEPE"),
    "kBONK": ("kBONK", "BONK", "1000BONK"),
}


def nado_base_symbol(nado_symbol: str) -> str:
    base = nado_symbol.upper()
    if base.endswith("-PERP"):
        base = base[: -len("-PERP")]
    return base


def lookup_keys(base: str) -> set[str]:
    base = base.upper()
    keys = {base}
    for canonical, aliases in SYMBOL_ALIASES.items():
        if base == canonical or base in aliases:
            keys.add(canonical)
            keys.update(aliases)
    return keys


def index_venue_rates(rates: dict[str, float]) -> dict[str, float]:
    """Map venue-native symbols to canonical lookup keys."""
    indexed: dict[str, float] = {}
    for symbol, apr in rates.items():
        sym = symbol.upper()
        if sym.endswith("USDT"):
            sym = sym[: -len("USDT")]
        elif sym.endswith("USDC"):
            sym = sym[: -len("USDC")]
        if "/" in sym:
            sym = sym.split("/", 1)[0]
        if sym.startswith("XYZ:"):
            sym = sym.split(":", 1)[1]
        indexed[sym] = apr
        for key in lookup_keys(sym):
            indexed[key] = apr
    return indexed
