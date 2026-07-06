"""US 모멘텀 전략 — 정규장 추세 돌파 기반 (docs/BIN.md STEP 3 규칙 기반 필터와 연동).

신규 진입(BUY) 신호만 다룬다 — 청산 로직은 다루지 않고 Safety Gate가 최종 리스크를 검증한다.
"""

from core.models import Decision, StateSnapshot
from core.strategy.base import BaseStrategy

_VOLUME_SURGE_RATIO = 2.0  # docs/REPORT.md "거래량 급증 종목" 기준과 동일
_RULE_BASED_BUY_KRW = 50_000


class MomentumStrategy(BaseStrategy):
    version = "v1.0.0"

    async def generate_signal(self, state: StateSnapshot) -> Decision | None:
        held_symbols = {h["symbol"] for h in state.portfolio.get("holdings", [])}

        for symbol, data in state.prices.items():
            if symbol in held_symbols:
                continue

            volume_ratio = data.get("volume_ratio")
            ema_20 = data.get("ema_20")
            ema_60 = data.get("ema_60")
            if volume_ratio is None or ema_20 is None or ema_60 is None:
                continue
            if volume_ratio < _VOLUME_SURGE_RATIO or ema_20 <= ema_60:
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
                reason=(
                    f"거래량 {volume_ratio:.1f}배 급증 + EMA20({ema_20:.0f}) > "
                    f"EMA60({ema_60:.0f}) 추세 돌파 — 소액 매수"
                ),
            )

        return None
