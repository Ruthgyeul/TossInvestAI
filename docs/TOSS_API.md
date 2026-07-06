# TOSS_API.md — 토스증권 Open API 스펙

---

## 기본 정보

- **Base URL**: `https://openapi.tossinvest.com`
- **인증**: OAuth 2.0 Client Credentials Grant
- **문서**: https://developers.tossinvest.com/docs

---

## 인증

```
POST /oauth2/token
Content-Type: application/x-www-form-urlencoded
Body: grant_type=client_credentials&client_id={id}&client_secret={secret}
```

- 모든 요청에 `Authorization: Bearer {access_token}` 헤더 필수
- 계좌·주문 API는 추가로 `X-Tossinvest-Account: {accountSeq}` 헤더 필수
- 시세·종목 API는 토큰만으로 호출 가능 (계좌 헤더 불필요)
- 토큰 만료 전 갱신: Redis에 `token:toss` 키로 캐시, 만료 5분 전 자동 갱신

---

## 전체 엔드포인트

| 카테고리 | 메서드 | 경로 | 설명 |
|----------|--------|------|------|
| 시세 | GET | `/api/v1/prices` | 현재가 조회 (KR·US 공통) |
| 시세 | GET | `/api/v1/candles` | 캔들 OHLCV (1분봉·일봉) |
| 시세 | GET | `/api/v1/orderbook` | 호가창 조회 |
| 시세 | GET | `/api/v1/price-limits` | 상·하한가 조회 (KR) |
| 체결 | GET | `/api/v1/trades` | 최근 체결 내역 |
| 종목 | GET | `/api/v1/stocks` | 종목 기본 정보 |
| 종목 | GET | `/api/v1/stocks/{symbol}/warnings` | 매수 유의사항 (VI·투자경고 등) |
| 환율 | GET | `/api/v1/exchange-rate` | KRW↔USD 환율 |
| 캘린더 | GET | `/api/v1/market-calendar/KR` | 국내 장 운영 시간 |
| 캘린더 | GET | `/api/v1/market-calendar/US` | 미국 장 운영 시간 (서머타임 반영) |
| 계좌 | GET | `/api/v1/accounts` | 계좌 목록 |
| 자산 | GET | `/api/v1/holdings` | 보유 주식 조회 (KR·US 통합) |
| 주문 | POST | `/api/v1/orders` | 주문 생성 |
| 주문 | POST | `/api/v1/orders/{orderId}/modify` | 주문 정정 |
| 주문 | POST | `/api/v1/orders/{orderId}/cancel` | 주문 취소 |
| 주문 조회 | GET | `/api/v1/orders` | 주문 목록 (대기중/종료) |
| 주문 조회 | GET | `/api/v1/orders/{orderId}` | 주문 상세 |
| 주문 정보 | GET | `/api/v1/buying-power` | 매수 가능 금액 |
| 주문 정보 | GET | `/api/v1/sellable-quantity` | 판매 가능 수량 |
| 주문 정보 | GET | `/api/v1/commissions` | 매매 수수료 (KR·US 다름) |

---

## Rate Limit

응답 헤더: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

| 그룹 | 한도 | 피크 (09:00~09:10 KST) |
|------|------|------------------------|
| AUTH | 5 req/s | — |
| ACCOUNT | 1 req/s | — |
| ASSET | 5 req/s | — |
| STOCK | 5 req/s | — |
| MARKET_INFO | 3 req/s | — |
| MARKET_DATA | 10 req/s | — |
| MARKET_DATA_CHART | 5 req/s | — |
| ORDER | 6 req/s | **3 req/s** |
| ORDER_HISTORY | 5 req/s | — |
| ORDER_INFO | 6 req/s | **3 req/s** |

**429 처리**: `Retry-After` 헤더 대기 → 지수 백오프 (1s → 2s → 4s) + jitter
**피크 시간 주문**: 최소 400ms 간격 유지 (`asyncio.sleep(0.4)`)

Redis `ratelimit:{group}` 카운터로 선제적 제어.

---

## 에러 코드 전체 목록

| HTTP | 코드 | 의미 | 처리 |
|------|------|------|------|
| 400 | `invalid-request` | 파라미터 오류 | 로그 후 중단 |
| 400 | `confirm-high-value-required` | 1억원 이상 → `confirmHighValueOrder=true` | Safety Gate에서 차단 |
| 400 | `account-header-required` | 계좌 헤더 누락 | 코드 수정 필요 |
| 401 | `invalid-token` | 토큰 형식 오류 | 재발급 후 재시도 |
| 401 | `expired-token` | 토큰 만료 | 재발급 후 재시도 |
| 401 | `edge-blocked` | Authorization 헤더 누락 | 코드 수정 필요 |
| 401 | `login-user-not-found` | 토큰 매핑 실패 | 재발급 후 재시도 |
| 403 | `forbidden` | 권한 부족 | 개발자 확인 필요 |
| 404 | `stock-not-found` | 종목 없음 | Watchlist에서 제거 |
| 404 | `order-not-found` | 주문 없음 | 무시 |
| 404 | `account-not-found` | 계좌 없음 | 개발자 확인 필요 |
| 404 | `exchange-rate-not-found` | 환율 정보 없음 | 캐시된 환율 사용 |
| 409 | `request-in-progress` | 동일 clientOrderId 처리 중 | 새 UUID 생성 후 재시도 |
| 409 | `already-filled` | 이미 체결됨 | 무시 |
| 409 | `already-canceled` | 이미 취소됨 | 무시 |
| 409 | `already-modified` | 이미 정정됨 | 무시 |
| 409 | `already-rejected` | 이미 거부됨 | 로그 후 중단 |
| 409 | `already-processing` | 정정/취소 처리 중 | 1s 대기 후 재시도 |
| 422 | `insufficient-buying-power` | 잔고 부족 | Safety Gate에서 사전 차단 |
| 422 | `order-hours-closed` | 장 마감 시간대 | Safety Gate에서 사전 차단 |
| 422 | `stock-restricted` | 거래 제한 종목 | Watchlist에서 제거 |
| 422 | `price-out-of-range` | 상·하한가 초과 | 가격 재조정 후 재시도 |
| 422 | `opposite-pending-order-exists` | 반대 방향 미체결 존재 | 미체결 취소 후 재시도 |
| 422 | `order-type-not-allowed` | 허용되지 않는 호가 유형 | 주문 유형 변경 |
| 422 | `prerequisite-required` | 약관 동의 미완료 | 개발자 확인 필요 |
| 422 | `market-not-supported-for-stock` | 해당 시장에서 거래 불가 | Watchlist에서 제거 |
| 422 | `investor-exchange-not-integrated` | 거래소 통합(SOR) 미설정 | 개발자 확인 필요 |
| 422 | `amount-order-outside-regular-hours` | 금액 주문은 정규장만 | Safety Gate에서 사전 차단 |
| 422 | `modify-restricted` | 정정 제한 주문 | 취소 후 신규 주문 |
| 422 | `cancel-restricted` | 취소 제한 주문 | 체결 대기 |
| 429 | `rate-limit-exceeded` | Rate limit 초과 | Retry-After 대기 후 재시도 |
| 500 | `internal-error` | 서버 일시 장애 | 30s 대기 후 재시도 |
| 500 | `maintenance` | 시스템 점검 중 | Discord 알림 후 대기 |

---

## 시장별 운영 시간

> **하드코딩 금지. 항상 market-calendar API 기준으로 판단한다.**

### 한국장 (KRX) — 참고용

| 세션 | 시간 (KST) | 봇 동작 |
|------|-----------|---------|
| 프리마켓 | 08:00~09:00 | 분석만 |
| 정규장 | 09:00~15:30 | 전략 루프 실행 |
| 피크타임 | 09:00~09:10 | 주문 간격 최소 400ms |
| 시간외 | 15:40~18:00 | 미체결 정리만 |

### 미국장 (US) — 참고용 (서머타임 미반영)

| 세션 | 시간 (KST) | 봇 동작 |
|------|-----------|---------|
| 정규장 | 23:30~06:00 | 전략 루프 실행 |
| 애프터마켓 | 06:00~07:00 | 미체결 정리만 |

---

## clientOrderId 생성 규칙

```python
import uuid
client_order_id = f"BIN-{market}-{uuid.uuid4().hex[:12].upper()}"
# 예시: BIN-KR-A3F2B1C4D5E6
```
