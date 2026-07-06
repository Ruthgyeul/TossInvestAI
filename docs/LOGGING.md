# LOGGING.md — 거래 로그 및 시스템 로그

---

## 원칙

- 모든 거래 내역은 PostgreSQL과 **별도로 사람이 읽을 수 있는 파일**에도 기록한다
- 로그는 **append 방식**으로 유지하며 **절대 삭제하지 않는다**
- 로그 파일은 날짜별로 자동 분리된다
- **모든 로그 항목에 운영 모드(`LIVE` / `SIMULATION` / `DRY_RUN`)를 반드시 포함한다**

---

## 로그 디렉토리 구조

```
logs/
├── trading/
│   ├── 2026-07-06.log           # 날짜별 거래 로그 (LIVE + SIMULATION 혼재 가능)
│   └── ...
├── reports/
│   ├── report_kr_2026-07-06_0850.md
│   ├── reflection_2026-07-06.md
│   └── charts/
│       └── 2026-07-06_portfolio.png
└── errors/
    ├── 2026-07-06.log           # Safety Gate 거부 + API 에러
    └── ...
```

---

## 거래 로그 형식 (logs/trading/YYYY-MM-DD.log)

### 실전 거래 (LIVE)

```
================================================================================
[LIVE][거래] 2026-07-06 10:31:42 KST
--------------------------------------------------------------------------------
종목명          삼성전자
심볼            005930
시장            KR
매수/매도       매수 (BUY)
수량            2주
주문 가격       74,500원 (지정가)
체결 평균단가   74,800원
수수료          224원
실현 손익       해당 없음 (신규 매수)
주문 사유       RSI 62.3 반등 확인, 거래량 전일 대비 +38%,
               MACD 골든크로스 임박, 단기 상승 기대
Claude Decision ID  a3f2b1c4-9d1e-4f2a-b3c5-d6e7f8a9b0c1
Toss Order ID       TOSS-20260706-KR-001
전략 버전       v1.2.0
프롬프트 버전   system_kr_v3
================================================================================
```

### 시뮬레이션 거래 (SIMULATION)

```
================================================================================
[SIM][거래] 2026-07-06 10:31:42 KST
--------------------------------------------------------------------------------
종목명          삼성전자
심볼            005930
시장            KR
매수/매도       매수 (BUY) [가상 체결]
수량            2주
주문 가격       74,500원 (지정가)
가상 체결단가   74,800원  ← 요청 시점 실제 현재가 기준
수수료          224원     ← 실제 수수료율 동일 적용
실현 손익       해당 없음 (신규 매수)
가상 잔고 변화  -149,824원 (체결금액 + 수수료)
주문 사유       RSI 62.3 반등 확인, 거래량 전일 대비 +38%,
               MACD 골든크로스 임박, 단기 상승 기대
Claude Decision ID  a3f2b1c4-9d1e-4f2a-b3c5-d6e7f8a9b0c1
Toss Order ID       SIM-20260706-KR-001   ← SIM 접두사로 실전과 구분
전략 버전       v1.2.0
프롬프트 버전   system_kr_v3
================================================================================
```

---

## 에러 로그 형식 (logs/errors/YYYY-MM-DD.log)

```
================================================================================
[LIVE][에러] 2026-07-06 09:03:11 KST  SAFETY_GATE_REJECTION
--------------------------------------------------------------------------------
종목           005930 삼성전자
시도 행위      매수 3주 (225,000 KRW)
거부 사유      단일 종목 비중 상한 초과
              현재 비중: 48.2% → 주문 후 예상: 61.5% (상한: 50%)
조치           주문 취소, Discord #stock-error 알림 발송
================================================================================

================================================================================
[SIM][에러] 2026-07-06 11:45:02 KST  SAFETY_GATE_REJECTION
--------------------------------------------------------------------------------
종목           005930 삼성전자
시도 행위      매수 3주 (225,000 KRW) [가상]
거부 사유      일일 손실 한도 초과 (가상 손익 기준)
              오늘 손실: 52,000 KRW / 한도: 50,000 KRW
조치           가상 주문 취소, Discord #stock-error 알림 발송 [시뮬레이션]
================================================================================
```

---

## 시뮬레이션 전용 DB 테이블

실전 테이블과 완전 분리한다. 절대 혼용 금지.

| 테이블 | 용도 |
|--------|------|
| `simulation_trades` | 가상 체결 내역 |
| `simulation_positions` | 가상 보유 포지션 |
| `simulation_daily_pnl` | 가상 일별 손익 |
| `simulation_portfolio_snapshots` | 가상 포트폴리오 시간대별 스냅샷 |

`mode` 컬럼은 모든 공용 테이블(`decisions`, `safety_rejections`, `api_usage`, `reflections`)에 포함된다.

```sql
-- 예시: decisions 테이블 mode 컬럼
ALTER TABLE decisions ADD COLUMN mode VARCHAR(10)
  CHECK (mode IN ('LIVE', 'SIMULATION', 'DRY_RUN'))
  NOT NULL DEFAULT 'SIMULATION';
```

---

## 시뮬레이션 수익률 자체 계산

봇이 직접 가상 포지션·잔고·수익률을 계산한다. 토스증권 API 의존 없음.

```python
# core/simulation/portfolio.py

class SimulationPortfolio:
    """가상 포트폴리오 상태를 메모리 + DB에서 관리한다."""

    async def apply_buy(self, symbol: str, qty: int, fill_price: float,
                        commission: float, market: str) -> None:
        """가상 매수 체결 처리."""
        cost = fill_price * qty + commission
        self.cash -= cost
        if symbol in self.positions:
            # 평균 단가 재계산
            old = self.positions[symbol]
            total_qty = old.qty + qty
            avg_price = (old.qty * old.avg_price + qty * fill_price) / total_qty
            self.positions[symbol] = Position(qty=total_qty, avg_price=avg_price)
        else:
            self.positions[symbol] = Position(qty=qty, avg_price=fill_price)
        await db.upsert("simulation_positions", self.positions[symbol])

    async def apply_sell(self, symbol: str, qty: int, fill_price: float,
                         commission: float) -> float:
        """가상 매도 체결 처리. 실현 손익 반환."""
        pos = self.positions[symbol]
        realized_pnl = (fill_price - pos.avg_price) * qty - commission
        self.cash += fill_price * qty - commission
        if pos.qty == qty:
            del self.positions[symbol]
        else:
            self.positions[symbol].qty -= qty
        await db.insert("simulation_trades", {
            "pnl_krw": realized_pnl, "mode": "SIMULATION"
        })
        return realized_pnl

    def get_total_value(self, current_prices: dict[str, float]) -> float:
        """총 자산 = 현금 + 보유 종목 평가액."""
        holdings_value = sum(
            pos.qty * current_prices.get(sym, pos.avg_price)
            for sym, pos in self.positions.items()
        )
        return self.cash + holdings_value

    def get_return_rate(self, current_prices: dict[str, float]) -> float:
        """시드 대비 수익률."""
        return (self.get_total_value(current_prices) - INITIAL_SEED_KRW) / INITIAL_SEED_KRW
```

---

## Discord 알림 구분

| 항목 | 실전 | 시뮬레이션 |
|------|------|-----------|
| Embed 상단 뱃지 | (없음) | `🟡 [시뮬레이션]` |
| Embed 색상 | 매수: 초록 / 매도: 빨강 | 매수: 노란초록 / 매도: 노란빨강 (채도 낮춤) |
| 채널 | #stock-buy / #stock-sell | 동일 채널 (뱃지로 구분) |
| #status 업데이트 | 실전 포트폴리오 | 시뮬레이션 포트폴리오 (별도 섹션) |

`#status` 채널에는 실전과 시뮬레이션 포트폴리오가 **동시에** 표시된다
(실전 데이터가 없는 초기엔 시뮬레이션 섹션만 표시).

```
[빈] 포트폴리오 현황
──────────────────────────────────────
🟢 실전 포트폴리오
  현재 없음 (SIMULATION 모드 운용 중)

🟡 시뮬레이션 포트폴리오
  💰 가상 총 자산   512,300 KRW
  📈 오늘 가상 손익 +3,200 KRW (+0.63%)
  📊 누적 가상 수익 +12,300 KRW (+2.46%)
  ─────────────────────────
  삼성전자(005930)  2주  74,800원  +1.2%  [SIM]
  NVDA              0.5주  $128.40  +2.1%  [SIM]
  ─────────────────────────
  💵 가상 현금 버퍼  76,800 KRW
  🕐 시뮬레이션 시작  2026-07-01 (D+5)
  🔄 업데이트  2026-07-06 10:45 KST
```

---

## 자동 DB 백업

| 주기 | 대상 | 보관 기간 |
|------|------|-----------|
| 매일 새벽 3시 | PostgreSQL 전체 덤프 | 30일 |
| 매주 일요일 | 주간 스냅샷 | 1년 |
| 매월 1일 | 월간 스냅샷 | 무제한 |

```
backups/
├── daily/   2026-07-06_0300.sql.gz
├── weekly/  2026-W28.sql.gz
└── monthly/ 2026-07.sql.gz
```

장애 발생 시 Discord `#stock-error` 즉시 알림.

---

## 구조적 로깅 (structlog)

```python
import structlog
log = structlog.get_logger()

# 모든 로그에 mode 필드 포함
log.warning("order_executed",
    mode="SIMULATION",       # "LIVE" | "SIMULATION" | "DRY_RUN"
    agent="Bin",
    symbol="005930",
    action="BUY",
    quantity=2,
    price=74800,
    virtual=True,
    decision_id="a3f2b1c4-..."
)
```

---

## 헬스 모니터링 (Raspberry Pi)

`core/monitoring/health.py`가 매 5분마다 수집.

| 항목 | 임계값 | 알림 |
|------|--------|------|
| CPU 사용률 | > 85% (5분 평균) | #stock-error |
| 메모리 사용률 | > 80% | #stock-error |
| 디스크 사용량 | > 90% | #stock-error |
| CPU 온도 | > 75°C | #stock-error |
| 네트워크 | 토스 API 응답 없음 > 30s | #stock-error |
| 봇 프로세스 | 비정상 종료 | #stock-error + systemd 자동 재시작 |
