"""FundManager 자금 배분·API 비용 기록 단위 테스트 (docs/FUND_MANAGER.md)."""

import pytest

from core.config import settings
from core.fund.manager import FundManager


@pytest.fixture
def fund_manager() -> FundManager:
    return FundManager()


@pytest.mark.asyncio
async def test_can_allocate_rejects_over_position_ratio(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _operating_funds() -> float:
        return 425_000.0

    async def _position_value(symbol: str) -> float:
        return 150_000.0  # 이미 운용 자금의 약 35% 보유 중

    monkeypatch.setattr(fund_manager, "get_operating_funds_krw", _operating_funds)
    monkeypatch.setattr(fund_manager, "_get_position_value_krw", _position_value)

    # 150,000 + 100,000 = 250,000 / 425,000 ≈ 58.8% > MAX_POSITION_RATIO(50%)
    allowed, reason = await fund_manager.can_allocate(100_000, "005930")

    assert allowed is False
    assert "종목당 상한" in reason


@pytest.mark.asyncio
async def test_can_allocate_allows_order_within_ratio(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _operating_funds() -> float:
        return 425_000.0

    async def _position_value(symbol: str) -> float:
        return 0.0

    monkeypatch.setattr(fund_manager, "get_operating_funds_krw", _operating_funds)
    monkeypatch.setattr(fund_manager, "_get_position_value_krw", _position_value)

    allowed, reason = await fund_manager.can_allocate(100_000, "005930")

    assert allowed is True


@pytest.mark.asyncio
async def test_can_allocate_rejects_when_no_operating_funds(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _operating_funds() -> float:
        return 0.0

    monkeypatch.setattr(fund_manager, "get_operating_funds_krw", _operating_funds)

    allowed, reason = await fund_manager.can_allocate(10_000, "005930")

    assert allowed is False
    assert "운용 자금 부족" in reason


@pytest.mark.asyncio
async def test_get_position_ratio(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _operating_funds() -> float:
        return 425_000.0

    async def _position_value(symbol: str) -> float:
        return 85_000.0

    monkeypatch.setattr(fund_manager, "get_operating_funds_krw", _operating_funds)
    monkeypatch.setattr(fund_manager, "_get_position_value_krw", _position_value)

    ratio = await fund_manager.get_position_ratio("005930")

    assert ratio == pytest.approx(85_000 / 425_000)


@pytest.mark.asyncio
async def test_record_api_usage_applies_cache_pricing(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: dict = {}

    async def _insert_api_usage(
        model: str,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_write_tokens: int,
    ) -> None:
        recorded.update(
            model=model,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    monkeypatch.setattr(fund_manager, "_insert_api_usage", _insert_api_usage)

    await fund_manager.record_api_usage(
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=500,
        cache_write_tokens=300,
    )

    p_in = settings.claude_input_price_per_mtok / 1_000_000
    p_out = settings.claude_output_price_per_mtok / 1_000_000
    expected_cost_usd = (
        1000 * p_in + 300 * p_in * 1.25 + 500 * p_in * 0.10 + 200 * p_out
    )

    assert recorded["model"] == "claude-sonnet-4-6"
    assert recorded["cost_usd"] == pytest.approx(expected_cost_usd)
    assert recorded["input_tokens"] == 1000
    assert recorded["output_tokens"] == 200
    assert recorded["cache_read_tokens"] == 500
    assert recorded["cache_write_tokens"] == 300


@pytest.mark.asyncio
async def test_weekly_rebalance_splits_net_profit_80_20(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _estimated_api_cost_krw() -> float:
        return 8_000.0

    async def _weekly_net_profit_krw() -> int:
        return 40_000

    async def _total_value_krw() -> float:
        return 550_000.0

    async def _cash_buffer_krw() -> float:
        return 75_000.0

    monkeypatch.setattr(fund_manager, "estimated_api_cost_krw", _estimated_api_cost_krw)
    monkeypatch.setattr(fund_manager, "get_total_value_krw", _total_value_krw)
    monkeypatch.setattr(fund_manager, "get_cash_buffer_krw", _cash_buffer_krw)

    import core.fund.manager as manager_module

    monkeypatch.setattr(
        manager_module.db, "get_weekly_net_profit_krw", _weekly_net_profit_krw
    )

    result = await fund_manager.weekly_rebalance()

    # remaining = 40,000 - 8,000 = 32,000 → 80% 재투자(25,600) / 20% 버퍼(6,400)
    assert result.api_cost_covered_krw == 8_000
    assert result.reinvested_krw == 25_600
    assert result.buffer_added_krw == 6_400


@pytest.mark.asyncio
async def test_weekly_rebalance_moves_buffer_overflow_to_operating_funds(
    fund_manager: FundManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _estimated_api_cost_krw() -> float:
        return 0.0

    async def _weekly_net_profit_krw() -> int:
        return 100_000

    async def _total_value_krw() -> float:
        return 500_000.0  # 버퍼 상한 = 100,000

    async def _cash_buffer_krw() -> float:
        return 95_000.0  # 이미 상한에 근접

    monkeypatch.setattr(fund_manager, "estimated_api_cost_krw", _estimated_api_cost_krw)
    monkeypatch.setattr(fund_manager, "get_total_value_krw", _total_value_krw)
    monkeypatch.setattr(fund_manager, "get_cash_buffer_krw", _cash_buffer_krw)

    import core.fund.manager as manager_module

    monkeypatch.setattr(
        manager_module.db, "get_weekly_net_profit_krw", _weekly_net_profit_krw
    )

    result = await fund_manager.weekly_rebalance()

    # remaining=100,000 → 재투자 80,000 / 버퍼 20,000 → 버퍼 합계 115,000 > 상한 100,000
    # 초과분 15,000은 운용 자금으로 이동
    assert result.buffer_added_krw == 5_000
    assert result.reinvested_krw == 95_000
