# monitor — BIN MONITOR 키오스크 디스플레이

7인치 모니터(1024×600)에 24/7 띄워두는 **읽기 전용 키오스크 대시보드**.
빈(Bin) 트레이딩 봇의 총자산·포지션·AI 매매 판단·시스템 헬스·뉴스를 한 화면에 보여준다.

> **상호작용 요소 없음.** 버튼·링크·클릭 핸들러를 추가하지 않는다 — 이 화면은
> 오직 실시간 정보 확인용이다. 루트 [`CLAUDE.md`](../CLAUDE.md)와
> [`docs/MONITOR.md`](../docs/MONITOR.md)를 먼저 읽는다.

디자인 원본: `claude.ai/design`의 **Bin Monitor.dc.html** (1024×600 고정 캔버스).

## 기술 스택

| 항목 | 선택 |
|------|------|
| 프레임워크 | Next.js (App Router) + TypeScript |
| 스타일 | CSS Modules — 원본 디자인의 정확한 `oklch()` 값·px 단위를 그대로 옮기기 위해 Tailwind 대신 순수 CSS 사용 |
| 폰트 | `next/font/google` — Noto Sans KR, JetBrains Mono (빌드 시 자체 호스팅, 런타임에 외부 요청 없음) |
| 데이터 | `GET /api/snapshot` — 현재는 목업(`src/lib/mock-snapshot.ts`), 실데이터 연동은 아래 "데이터 연동" 참고 |

## 디렉토리 구조

```
monitor/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # 폰트, 뷰포트(줌 비활성화), 메타데이터
│   │   ├── page.tsx           # KioskStage + MonitorDashboard 조립
│   │   ├── globals.css        # 디자인 토큰(oklch 색상 변수) + 키오스크 리셋
│   │   └── api/snapshot/route.ts  # 스냅샷 JSON 엔드포인트 (현재 목업)
│   ├── components/
│   │   ├── KioskStage.tsx     # 1024x600 캔버스를 실제 화면 크기에 맞춰 스케일링
│   │   ├── MonitorDashboard.tsx  # 30초 간격 폴링 + 전체 조립
│   │   ├── Dashboard.module.css  # 전체 대시보드 스타일 (섹션별 클래스)
│   │   ├── LiveClock.tsx      # 1초마다 틱 (KST 고정)
│   │   └── Header.tsx / SubStrip.tsx / TotalAssetsCard.tsx / PnlChart.tsx /
│   │       SystemHealthPanel.tsx / PositionsPanel.tsx / AiDecisionsPanel.tsx /
│   │       NewsPanel.tsx / EventCalendarPanel.tsx
│   └── lib/
│       ├── types.ts           # MonitorSnapshot 및 하위 타입
│       ├── mock-snapshot.ts   # 목업 데이터 (디자인 원본 값과 동일)
│       └── format.ts          # KRW/퍼센트 포맷터, 부호 기반 색상 클래스 선택
```

## 실행

```bash
npm install
npm run dev      # http://localhost:3000
npm run build && npm start   # 프로덕션 빌드
npm run lint
```

## 데이터 연동

지금은 `src/lib/mock-snapshot.ts`가 정적 목업을 반환하고, `MonitorDashboard`가
`/api/snapshot`을 30초마다 폴링해 화면을 갱신한다 (초 단위 시계는 `LiveClock`이
별도로 매초 틱). 실데이터로 전환하려면:

1. `core`의 내부 API(`docs/INTERNAL_API.md`)에 이 대시보드 전용 읽기 스냅샷
   엔드포인트를 추가하거나, `/api/v1/status`·`/fund`·`/health` 등 기존
   엔드포인트를 조합한다.
2. `core`의 HTTP 서버는 `127.0.0.1`에만 바인딩하고 `Bearer` 토큰이 필요하다
   (`CORE_INTERNAL_API_TOKEN`). 이 토큰은 **절대 브라우저로 내려보내지 않는다** —
   `src/app/api/snapshot/route.ts`(Next.js Route Handler, 서버 사이드)에서만
   `core`를 호출하고, 브라우저는 이 프록시 엔드포인트만 본다.
3. `route.ts`의 `getMockSnapshot()` 호출을 실제 `fetch()` 호출로 교체하고,
   `MonitorSnapshot` 타입에 맞게 응답을 매핑한다.
4. 모니터는 트레이딩 코어와 같은 라즈베리파이에서 로컬로 실행되므로
   (`docs/DEPLOYMENT.md`), 외부 네트워크 노출은 필요 없다.

## 키오스크 배포 (7인치 모니터)

라즈베리파이에서 Chromium을 kiosk 모드로 띄운다. 예시:

```bash
chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  http://localhost:3000
```

화면이 정확히 1024×600이 아니어도 `KioskStage`가 원본 비율을 유지한 채
레터박스로 맞춰 그리므로 레이아웃이 찌그러지지 않는다. systemd로 등록해
부팅 시 자동 실행하는 방법은 [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) 참고.

## 디자인 충실도

- 색상은 디자인 원본의 `oklch()` 값을 그대로 CSS 변수로 옮겼다
  (`src/app/globals.css`) — 임의로 팔레트를 재해석하지 않았다.
- 레이아웃은 4열 그리드(`1.1fr 1fr 1fr 1.3fr` × `1.2fr 0.8fr`)와 하단
  2열 스트립까지 원본 인라인 스타일의 px 값을 그대로 옮겼다.
- 원본 디자인에는 있던 "차트 기간(14일/30일/전체) 선택" 같은 편집 가능한
  prop은 키오스크에 상호작용 요소가 없어야 하므로 구현하지 않았고, 기본값
  "전체"로 고정했다.
