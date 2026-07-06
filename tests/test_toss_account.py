"""계좌·보유주식·매수가능금액 조회 단위 테스트 (docs/CODING_RULES.md Phase 2-6)."""

import pytest
from aioresponses import aioresponses

from core.toss import account

_BASE_URL = "https://openapi.tossinvest.com"


@pytest.fixture(autouse=True)
def _stub_token(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_token() -> str:
        return "test-token"

    monkeypatch.setattr(account.client, "get_access_token", _fake_token)


@pytest.mark.asyncio
async def test_get_accounts(fake_redis) -> None:
    with aioresponses() as mocked:
        mocked.get(
            f"{_BASE_URL}/api/v1/accounts",
            payload={"accounts": [{"accountSeq": "test-account-seq"}]},
        )
        accounts = await account.get_accounts()

    assert accounts == [{"accountSeq": "test-account-seq"}]


@pytest.mark.asyncio
async def test_get_holdings_kr_and_us(fake_redis) -> None:
    holdings = [
        {"symbol": "005930", "market": "KR", "quantity": 2, "avgPrice": 74800},
        {"symbol": "AAPL", "market": "US", "quantity": 1, "avgPrice": 210.5},
    ]
    with aioresponses() as mocked:
        mocked.get(f"{_BASE_URL}/api/v1/holdings", payload={"holdings": holdings})
        result = await account.get_holdings()

    assert result == holdings


@pytest.mark.asyncio
async def test_get_buying_power(fake_redis) -> None:
    with aioresponses() as mocked:
        mocked.get(
            f"{_BASE_URL}/api/v1/buying-power", payload={"buyingPower": 123456.0}
        )
        result = await account.get_buying_power()

    assert result == 123456.0


@pytest.mark.asyncio
async def test_get_sellable_quantity(fake_redis) -> None:
    with aioresponses() as mocked:
        mocked.get(
            f"{_BASE_URL}/api/v1/sellable-quantity?symbol=005930",
            payload={"sellableQuantity": 2},
        )
        result = await account.get_sellable_quantity("005930")

    assert result == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("market_code", ["KR", "US"])
async def test_get_commissions(fake_redis, market_code: str) -> None:
    with aioresponses() as mocked:
        mocked.get(
            f"{_BASE_URL}/api/v1/commissions?market={market_code}",
            payload={"market": market_code, "rate": 0.00015},
        )
        result = await account.get_commissions(market_code)

    assert result == {"market": market_code, "rate": 0.00015}
