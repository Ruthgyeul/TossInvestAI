"""계좌·보유주식·매수가능금액 조회 (docs/TOSS_API.md)."""

from core.toss import client


async def get_accounts() -> list[dict]:
    """GET /api/v1/accounts."""
    data = await client.request(
        "GET", "/api/v1/accounts", "ACCOUNT", account_required=True
    )
    return data["accounts"]  # type: ignore[no-any-return]


async def get_holdings() -> list[dict]:
    """GET /api/v1/holdings — KR·US 통합 보유 주식."""
    data = await client.request(
        "GET", "/api/v1/holdings", "ASSET", account_required=True
    )
    return data["holdings"]  # type: ignore[no-any-return]


async def get_buying_power() -> float:
    """GET /api/v1/buying-power."""
    data = await client.request(
        "GET", "/api/v1/buying-power", "ORDER_INFO", account_required=True
    )
    return float(data["buyingPower"])


async def get_sellable_quantity(symbol: str) -> int:
    """GET /api/v1/sellable-quantity."""
    data = await client.request(
        "GET",
        "/api/v1/sellable-quantity",
        "ORDER_INFO",
        params={"symbol": symbol},
        account_required=True,
    )
    return int(data["sellableQuantity"])


async def get_commissions(market: str) -> dict:
    """GET /api/v1/commissions — KR·US 요율이 다르다."""
    return await client.request(
        "GET",
        "/api/v1/commissions",
        "ORDER_INFO",
        params={"market": market},
        account_required=True,
    )
