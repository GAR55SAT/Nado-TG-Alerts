from __future__ import annotations

import httpx


class NadoApiError(Exception):
    pass


class NadoClient:
    def __init__(self, archive_url: str, gateway_url: str, timeout: float = 30.0) -> None:
        self.archive_url = archive_url.rstrip("/")
        self.gateway_url = gateway_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip, br, deflate",
            },
        )

    def close(self) -> None:
        self._client.close()

    def _archive_post(self, payload: dict) -> dict | list:
        response = self._client.post(self.archive_url, json=payload)
        response.raise_for_status()
        return response.json()

    def _gateway_query(self, payload: dict) -> dict:
        response = self._client.post(f"{self.gateway_url}/query", json=payload)
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise NadoApiError(body.get("error", "Gateway query failed"))
        return body["data"]

    def get_symbols(self) -> list[dict]:
        response = self._client.get(f"{self.gateway_url}/symbols")
        response.raise_for_status()
        return response.json()

    def get_perp_products(self) -> list[dict]:
        return [s for s in self.get_symbols() if s.get("type") == "perp"]

    def get_funding_rates(self, product_ids: list[int]) -> dict[str, dict]:
        if not product_ids:
            return {}
        return self._archive_post({"funding_rates": {"product_ids": product_ids}})

    def get_liquidation_feed(self) -> list[dict]:
        return self._archive_post({"liquidation_feed": {}})

    def get_subaccount_orders(self, subaccount_hex: str, product_ids: list[int]) -> dict[int, list[dict]]:
        if not product_ids:
            return {}
        data = self._gateway_query(
            {
                "type": "orders",
                "sender": subaccount_hex,
                "product_ids": product_ids,
            }
        )
        result: dict[int, list[dict]] = {}
        for item in data.get("product_orders", []):
            result[item["product_id"]] = item.get("orders", [])
        return result

    def get_market_prices(self, product_ids: list[int]) -> dict[int, dict]:
        if not product_ids:
            return {}
        data = self._gateway_query(
            {"type": "market_prices", "product_ids": product_ids}
        )
        return {p["product_id"]: p for p in data.get("market_prices", [])}

    def get_events(
        self,
        *,
        subaccounts: list[str] | None = None,
        event_types: list[str] | None = None,
        limit: int = 20,
        idx: str | None = None,
    ) -> dict:
        events_payload: dict = {"limit": {"raw": limit}}
        if subaccounts:
            events_payload["subaccounts"] = subaccounts[:5]
        if event_types:
            events_payload["event_types"] = event_types
        if idx is not None:
            events_payload["idx"] = idx
        return self._archive_post({"events": events_payload})

    def get_subaccount_info(self, subaccount_hex: str) -> dict:
        return self._gateway_query(
            {"type": "subaccount_info", "subaccount": subaccount_hex}
        )
