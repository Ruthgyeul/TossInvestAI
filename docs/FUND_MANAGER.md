# FUND_MANAGER.md — 자금 관리

---

## 초기 시드 및 운용 원칙

| 항목 | 값 |
|------|----|
| 초기 시드 | **500,000 KRW** |
| 운용 자금 | 시드의 85% → 425,000 KRW |
| 현금 버퍼 | 시드의 15% → 75,000 KRW |
| 외부 추가 입금 | **없음** — 수익금이 유일한 재투자 재원 |

`INITIAL_SEED_KRW=500000` 은 손익 계산 기준점이므로 절대 변경하지 않는다.

---

## 자금 배분 구조

```
총 운용 자금: 500,000 KRW (+ 누적 수익금)
│
├── 운용 자금 (KR + US 자유 배분) : 85%  → 425,000 KRW
│   ├── KR / US 비중    봇이 시장 상황에 따라 자율 결정
│   ├── 최대 보유 종목  제한 없음 (봇 자율)
│   └── 종목당 상한     운용 자금의 50% 이하 (하드 상한)
│
└── 현금 버퍼           : 15%  → 75,000 KRW
    └── 급등 기회 대응, 수수료 준비금, Claude API 비용 확보
```

---

## 수익금 재배분 규칙

매주 월요일 장 시작 전 자동 실행된다. 코드 외부에서 임의 변경 불가.

```
STEP 1. Claude API 사용료 추정 (전주 실제 사용량 기반)
        → 현금 버퍼에서 확보

STEP 2. 남은 순수익의 80% → 운용 자금 재투자

STEP 3. 남은 순수익의 20% → 현금 버퍼 적립

STEP 4. 현금 버퍼가 총 자산의 20% 초과 시
        → 초과분 전액 운용 자금으로 이동
```

---

## Claude API 비용 관리

| 호출 유형 | 주기 | 모델 |
|-----------|------|------|
| 전략 판단 (결정 루프) | 장중 매 15분 (필요 시만) | claude-sonnet-4-6 |
| 심층 분석 | 장 시작 전 1회 / 장 마감 후 1회 | claude-sonnet-4-6 |
| 자기평가 (Reflection) | 장 마감 후 1회 | claude-sonnet-4-6 |
| 즉시 리포트 | Discord 명령 시 | claude-sonnet-4-6 |

규칙 기반으로 명확한 신호(RSI > 75 → 매도 등)는 Claude 호출 없이 처리.

---

## FundManager 클래스 명세

```python
class FundManager:

    def get_total_value_krw(self) -> float:
        """총 자산 KRW 환산 (보유 주식 시가 + 현금)"""

    def get_operating_funds_krw(self) -> float:
        """운용 자금 = 총 자산 - 현금 버퍼"""

    def get_cash_buffer_krw(self) -> float:
        """현금 버퍼 잔고"""

    def can_allocate(self, amount_krw: float, symbol: str) -> tuple[bool, str]:
        """주문 가능 여부 판단 (종목당 상한 50% 체크)"""

    async def weekly_rebalance(self) -> RebalanceResult:
        """주간 수익 정산 및 재배분 실행"""

    def record_api_usage(self, input_tokens: int, output_tokens: int, model: str) -> None:
        """Claude API 호출마다 토큰 수 기록"""

    def estimated_api_cost_krw(self) -> float:
        """이번 달 추정 API 비용 (KRW 환산)"""

    def get_position_ratio(self, symbol: str) -> float:
        """특정 종목의 운용 자금 대비 비중"""
```

---

## 성과 지표 계산

`FundManager`는 아래 지표를 항상 최신 상태로 유지한다.

| 지표 | 계산 방식 |
|------|-----------|
| 총 수익률 | (현재 총 자산 - INITIAL_SEED_KRW) / INITIAL_SEED_KRW |
| MDD | 고점 대비 현재 낙폭 최대값 |
| 일일 손익 | 당일 실현 손익 + 평가 손익 변화 |
| 누적 API 비용 | 월별 토큰 사용량 × 단가 (KRW 환산) |

---

## 미국 주식 금액 처리

- 모든 내부 계산은 **KRW 기준**으로 통일
- US 포지션 가치 = USD 평가액 × 현재 환율 (KRW/USD)
- 매수 시점 환율을 PostgreSQL `positions` 테이블에 함께 저장
- 실현 손익 계산 시 매수·매도 시점 환율 모두 반영

```python
realized_pnl_krw = (sell_price_usd * sell_rate) - (buy_price_usd * buy_rate) * quantity - commission_krw
```

---

## 시뮬레이션 모드 자금 관리

`SIMULATION=true` 일 때 FundManager는 **가상 포트폴리오**를 별도로 유지한다.
실제 토스 계좌 잔고가 아닌 `simulation_positions` + `simulation_daily_pnl` 테이블 기반.

### 가상 포트폴리오 초기 상태

```python
# 시뮬레이션 시작 시 실제 시드와 동일한 가상 자금으로 초기화
SIM_INITIAL_CASH_KRW = INITIAL_SEED_KRW  # 500,000 KRW
SIM_OPERATING_FUNDS_KRW = SIM_INITIAL_CASH_KRW * 0.85  # 425,000 KRW
SIM_CASH_BUFFER_KRW = SIM_INITIAL_CASH_KRW * 0.15       # 75,000 KRW
```

### 핵심 지표 (봇이 직접 계산)

| 지표 | 계산 방식 |
|------|-----------|
| 가상 총 자산 | 가상 현금 + 보유 종목 현재가 기준 평가액 |
| 가상 수익률 | (가상 총 자산 - INITIAL_SEED_KRW) / INITIAL_SEED_KRW |
| 가상 MDD | 시뮬레이션 시작 이후 고점 대비 최대 낙폭 |
| 가상 승률 | 수익 거래 수 / simulation_trades 전체 수 |
| 가상 샤프 지수 | 일별 수익률 평균 / 표준편차 × √252 |

### /simstatus Discord 명령 출력 예시

```
[빈] 🟡 시뮬레이션 성과 리포트
──────────────────────────────────────────
📅 시뮬레이션 기간   2026-07-01 ~ 2026-07-14 (14일)
💰 가상 시드         500,000 KRW
💎 가상 총 자산      538,400 KRW

📈 수익 지표
  누적 수익률   +7.68%  (+38,400 KRW)
  일평균 수익률 +0.55%
  MDD          -3.2%
  샤프 지수     1.84

🎯 거래 지표
  총 거래      28회 (매수 15 / 매도 13)
  승률         71.4%
  평균 보유    2.3일
  Safety Gate 거부  3회

💡 Claude API 비용 (시뮬레이션 기간)
  총 호출      312회
  총 비용      8,240 KRW
  일평균       589 KRW

→ 실전 전환 준비 상태: 🟢 양호
```
