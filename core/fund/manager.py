"""자금 배분·재투자·API 비용 추적 (docs/FUND_MANAGER.md).

INITIAL_SEED_KRW는 손익 계산 기준점이므로 최초 설정 이후 절대 변경하지 않는다.
"""

from dataclasses import dataclass

from core.config import settings
from core.db import store as db
from core.toss import account as toss_account
from core.toss import market as toss_market

_KRW_PER_USD = 1382.0  # 실시간 환율로 교체 가능
_WEEKLY_REINVEST_RATIO = 0.80
_MAX_CASH_BUFFER_RATIO = 0.20


@dataclass
class RebalanceResult:
    api_cost_covered_krw: int
    reinvested_krw: int
    buffer_added_krw: int


class FundManager:
    async def _get_position_value_krw(self, symbol: str) -> float:
        """특정 종목의 현재 평가액 (KRW 환산)."""
        holdings = await toss_account.get_holdings()
        holding = next((h for h in holdings if h["symbol"] == symbol), None)
        if holding is None:
            return 0.0

        price_data = await toss_market.get_price(symbol)
        value = holding["quantity"] * price_data["price"]
        if holding["market"] == "US":
            value *= await toss_market.get_exchange_rate()
        return float(value)

    async def _get_holdings_value_krw(self) -> float:
        """보유 종목 전체 평가액 (KRW 환산)."""
        holdings = await toss_account.get_holdings()
        exchange_rate = await toss_market.get_exchange_rate()

        total = 0.0
        for holding in holdings:
            price_data = await toss_market.get_price(holding["symbol"])
            value = holding["quantity"] * price_data["price"]
            if holding["market"] == "US":
                value *= exchange_rate
            total += value
        return total

    async def get_total_value_krw(self) -> float:
        """총 자산 KRW 환산 (보유 주식 시가 + 현금)."""
        holdings_value = await self._get_holdings_value_krw()
        cash = await toss_account.get_buying_power()
        return holdings_value + cash

    async def get_cash_buffer_krw(self) -> float:
        """현금 버퍼 잔고 = 총 자산의 CASH_BUFFER_RATIO."""
        total_value = await self.get_total_value_krw()
        return total_value * settings.CASH_BUFFER_RATIO

    async def get_operating_funds_krw(self) -> float:
        """운용 자금 = 총 자산 - 현금 버퍼."""
        total_value = await self.get_total_value_krw()
        return total_value * (1 - settings.CASH_BUFFER_RATIO)

    async def get_position_ratio(self, symbol: str) -> float:
        """특정 종목의 운용 자금 대비 비중."""
        operating_funds = await self.get_operating_funds_krw()
        if operating_funds <= 0:
            return 0.0
        position_value = await self._get_position_value_krw(symbol)
        return position_value / operating_funds

    async def can_allocate(self, amount_krw: float, symbol: str) -> tuple[bool, str]:
        """주문 가능 여부 판단 (종목당 상한 MAX_POSITION_RATIO 체크)."""
        operating_funds = await self.get_operating_funds_krw()
        if operating_funds <= 0:
            return False, "운용 자금 부족"

        current_position_krw = await self._get_position_value_krw(symbol)
        projected_ratio = (current_position_krw + amount_krw) / operating_funds
        if projected_ratio > settings.MAX_POSITION_RATIO:
            return False, f"종목당 상한 초과: {projected_ratio:.1%}"

        return True, "허용"

    async def weekly_rebalance(self) -> RebalanceResult:
        """매주 월요일 장 시작 전 자동 실행. 코드 외부에서 임의 변경 불가.

        STEP 1. Claude API 사용료 추정 → 현금 버퍼에서 확보
        STEP 2. 남은 순수익의 80% → 운용 자금 재투자
        STEP 3. 남은 순수익의 20% → 현금 버퍼 적립
        STEP 4. 현금 버퍼가 총 자산의 20% 초과 시 초과분을 운용 자금으로 이동
        """
        api_cost_krw = int(await self.estimated_api_cost_krw())
        net_profit_krw = await db.get_weekly_net_profit_krw()
        remaining = max(net_profit_krw - api_cost_krw, 0)

        reinvested_krw = int(remaining * _WEEKLY_REINVEST_RATIO)
        buffer_added_krw = remaining - reinvested_krw

        total_value = await self.get_total_value_krw()
        cash_buffer = await self.get_cash_buffer_krw() + buffer_added_krw
        max_buffer = total_value * _MAX_CASH_BUFFER_RATIO
        if cash_buffer > max_buffer:
            overflow = cash_buffer - max_buffer
            reinvested_krw += int(overflow)
            buffer_added_krw -= int(overflow)

        return RebalanceResult(
            api_cost_covered_krw=api_cost_krw,
            reinvested_krw=reinvested_krw,
            buffer_added_krw=buffer_added_krw,
        )

    async def record_api_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        """Claude API 호출마다 토큰 수·비용을 api_usage 테이블에 기록한다."""
        p_in = settings.claude_input_price_per_mtok / 1_000_000
        p_out = settings.claude_output_price_per_mtok / 1_000_000

        cost_usd = (
            input_tokens * p_in
            + cache_write_tokens * p_in * 1.25  # 5m write
            + cache_read_tokens * p_in * 0.10  # hit
            + output_tokens * p_out
        )
        await self._insert_api_usage(
            model,
            cost_usd,
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
        )

    async def _insert_api_usage(
        self,
        model: str,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_write_tokens: int,
    ) -> None:
        await db.insert(
            "api_usage",
            {
                "model": model,
                "cost_usd": cost_usd,
                "cost_krw": int(cost_usd * _KRW_PER_USD),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_write_tokens": cache_write_tokens,
            },
        )

    async def estimated_api_cost_krw(self) -> float:
        """이번 달 추정 API 비용 (KRW 환산)."""
        return await db.get_api_usage_month_krw()


fund_manager = FundManager()
