"""US 오버나이트 전략 — 정규장 마감 보유 포지션의 익일 갭 대응.

미구현 상태다. "갭 대응"이 구체적으로 무엇을 뜻하는지(포지션 축소·헤지·홀드 등)
docs/BIN.md에 정의되어 있지 않아 임의로 구현하지 않는다 — 개발자 결정이 필요하다.
core/trading/decision.py의 전략 디스패치에도 등록하지 않는다 (raise NotImplementedError
상태로 호출되면 매 루프마다 예외가 발생하므로).
"""

from core.models import Decision, StateSnapshot
from core.strategy.base import BaseStrategy


class OvernightStrategy(BaseStrategy):
    version = "v1.0.0"

    async def generate_signal(self, state: StateSnapshot) -> Decision | None:
        raise NotImplementedError
