"""KR 평균회귀 전략 — RSI 과매수/과매도 반등 기반 (docs/BIN.md STEP 3 규칙 기반 필터와 연동)."""

from core.models import Decision, StateSnapshot
from core.strategy.base import BaseStrategy

_RSI_OVERBOUGHT = 75
_RSI_OVERSOLD = 28
# 규칙 기반 매수는 소액만 즉시 진입시킨다 — 최종 한도는 Safety Gate가 검증한다 (docs/SAFETY.md).
_RULE_BASED_BUY_KRW = 50_000


class MeanReversionStrategy(BaseStrategy):
    version = "v1.0.0"

    async def generate_signal(self, state: StateSnapshot) -> Decision | None:
        holdings = {h["symbol"]: h for h in state.portfolio.get("holdings", [])}

        for symbol, data in state.prices.items():
            rsi = data.get("rsi_14")
            if rsi is None:
                continue

            holding = holdings.get(symbol)

            if holding is not None and rsi > _RSI_OVERBOUGHT:
                return self.make_decision(
                    symbol=symbol,
                    action="SELL",
                    quantity=holding["quantity"],
                    price=None,
                    reason=f"RSI {rsi:.1f} > {_RSI_OVERBOUGHT} 과매수 구간 — 보유 물량 매도",
                )

            if holding is None and rsi < _RSI_OVERSOLD:
                if state.market == "KR" and data.get("vi_triggered"):
                    continue

                price = data.get("price")
                quantity = int(_RULE_BASED_BUY_KRW // price) if price else 0
                if quantity <= 0:
                    continue

                return self.make_decision(
                    symbol=symbol,
                    action="BUY",
                    quantity=quantity,
                    price=None,
                    reason=f"RSI {rsi:.1f} < {_RSI_OVERSOLD} 과매도 구간 — 소액 매수",
                )

        return None
