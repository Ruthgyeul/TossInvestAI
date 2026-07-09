# MONITOR.md — BIN MONITOR 키오스크 디스플레이

> `monitor/`(Next.js) 앱의 설계 근거와 운영 방식을 설명한다. 코드 수준의
> 세부 규칙은 `monitor/CLAUDE.md`, 실행·데이터 연동 절차는 `monitor/README.md`
> 참고 — 여기서 중복 설명하지 않는다.

---

## 목적

7인치 모니터(1024×600)에 24/7 띄워두는 **읽기 전용 대시보드**. 총자산,
KR·US 포지션, AI 매매 판단, 시스템 헬스, Safety Gate 거부 이력, 뉴스,
시장 이벤트 캘린더를 한 화면에서 실시간으로 보여준다. Discord가 알림·명령
채널이라면, 이 화면은 **눈으로 훑는 상시 상태판**이다 (docs/DISCORD.md와
용도가 다르다 — 명령을 받지 않는다).

디자인 원본은 `claude.ai/design`의 **Bin Monitor.dc.html**(1024×600 고정
캔버스)이며, `monitor/`는 이 디자인을 값 그대로(색상 `oklch()`, 간격 px)
옮긴 구현체다.

---

## 왜 별도 Next.js 프로젝트인가

- `core`(Python)와 `discord-bot`(Node)은 트레이딩 로직·알림을 담당하고,
  `monitor`는 순수 프레젠테이션 계층이다 — 매매를 실행하거나 core에 쓰기
  요청을 보내지 않는다. 별도 저장소로 분리하지 않고 같은 모노레포의
  `/monitor` 폴더에 둔 이유는 같은 라즈베리파이에서 함께 배포·운영되기
  때문이다 (docs/ARCHITECTURE.md 하드웨어 구성과 동일 기기).
- Next.js(App Router)를 선택한 이유: 정적으로 내려줄 화면이지만 실데이터
  연동 시 서버 사이드 Route Handler로 `core`의 내부 API 토큰을 브라우저에
  노출하지 않고 프록시할 수 있어야 한다 (docs/INTERNAL_API.md의 `Bearer`
  토큰·`127.0.0.1` 바인딩 규칙과 동일한 이유). 순수 정적 HTML로는 이 프록시
  계층을 깔끔하게 넣기 어렵다.

---

## 상호작용 없음 — 하드 제약

이 화면에는 버튼, 링크, 폼, 클릭/터치/호버 핸들러가 없다. 조작이 필요한
동작(주문 승인/거부, `/stop`, `/resume` 등)은 전부 Discord(docs/DISCORD.md)의
몫이다. 모니터에 상호작용 요소를 추가하는 PR은 이 문서의 설계 의도에
어긋난다.

---

## 데이터 흐름

```
core (Python, 127.0.0.1:내부포트)
   │  GET /api/v1/status, /fund, /health, ... (docs/INTERNAL_API.md)
   │  Authorization: Bearer {CORE_INTERNAL_API_TOKEN}
   ▼
monitor/src/app/api/snapshot/route.ts   (Next.js Route Handler, 서버 사이드)
   │  토큰은 여기서만 사용 — 브라우저로 절대 내려가지 않는다
   ▼
GET /api/snapshot  (같은 오리진, 인증 불필요 — 로컬 키오스크 전용)
   │
   ▼
MonitorDashboard.tsx  (클라이언트, 30초 간격 폴링)
   │  LiveClock은 별도로 매초 KST 틱
   ▼
7인치 모니터
```

현재 `route.ts`는 `src/lib/mock-snapshot.ts`의 목업을 반환한다. 실데이터
연동 절차는 `monitor/README.md`의 "데이터 연동" 참고.

---

## 화면 구성 (원본 디자인 섹션)

| 영역 | 내용 |
|------|------|
| 헤더 | 로고, LIVE 뱃지, 전략/프롬프트 버전, USD/KRW, KR·US 장 상태, 실시간 시계 |
| 서브 스트립 | 최근 정기 리포트 요약, 자기개선 승인대기, 토스 인기 종목 겹침, 공포탐욕지수 |
| 총 자산 카드 | 총자산·금일 손익, 현금/KR/US 배분 바, 실현·평가손익, 누적수익률, 운용일수, API 사용량·비용 |
| 일별 손익 차트 | 상승/하락 바 차트, 평균 수익률·승률, 상승/하락 합계 |
| 시스템 헬스 | 서비스별 업타임, 최근 로그, Safety Gate 거부 이력, 자기평가 요약 |
| KR·US 포지션 | 종목별 시장 구분·수량·수익률 |
| AI 매매 판단 | 최근 매매 판단 시각·액션(BUY/SELL/HOLD)·신뢰도 |
| 뉴스 헤드라인 | 감성 태그(호재/주의/악재) + 헤드라인 |
| 시장 이벤트 캘린더 | 예정 이벤트 + 위험도(고위험/일반) |

---

## 화면 크기 대응

원본 디자인은 1024×600 고정 캔버스다. `monitor/src/components/KioskStage.tsx`가
실제 브라우저 뷰포트 크기에 맞춰 이 캔버스를 균등 스케일링(레터박스)한다 —
실제 하드웨어 해상도가 정확히 1024×600이 아니어도 비율이 깨지지 않는다.
컴포넌트 내부에 반응형 브레이크포인트를 추가하지 않는다 (`monitor/CLAUDE.md`
절대 규칙 5).

---

## 키오스크 배포

라즈베리파이에서 Chromium을 `--kiosk` 모드로 자동 기동한다. 구체적인 명령과
systemd 예시는 `monitor/README.md`의 "키오스크 배포" 참고. 전체 시스템
배포·백업·롤백 절차는 `docs/DEPLOYMENT.md`를 따른다 — `monitor`도 같은
git pull → 재빌드 → 서비스 재시작 흐름에 포함시킨다.
