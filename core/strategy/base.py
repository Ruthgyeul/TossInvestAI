"""전략 확장 지점. 새 전략은 BaseStrategy를 상속한다 (CODING_RULES.md 확장성 원칙)."""

import uuid
from abc import ABC, abstractmethod
from typing import Literal

from core.models import Decision, StateSnapshot


class BaseStrategy(ABC):
    version: str

    @abstractmethod
    async def generate_signal(self, state: StateSnapshot) -> Decision | None:
        """규칙 기반으로 판단 가능하면 Decision을, 모호하면 None을 반환한다."""
        ...

    @staticmethod
    def make_decision(
        *,
        symbol: str,
        action: Literal["BUY", "SELL"],
        quantity: int,
        price: float | None,
        reason: str,
        confidence: float = 1.0,
        risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW",
    ) -> Decision:
        """규칙 기반 전략이 공통으로 사용하는 Decision 생성 헬퍼 (order_type은 항상 시장가)."""
        return Decision(
            decision_id=str(uuid.uuid4()),
            action=action,
            symbol=symbol,
            quantity=quantity,
            order_type="MARKET",
            price=price,
            confidence=confidence,
            reason=reason,
            risk_level=risk_level,
        )
