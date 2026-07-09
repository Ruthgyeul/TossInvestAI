# CLAUDE.md — monitor (BIN MONITOR 키오스크)

> 이 폴더는 루트 [`CLAUDE.md`](../CLAUDE.md)가 정의하는 빈(Bin) 프로젝트의
> 하위 앱이다. 여기서 작업하기 전에 루트 `CLAUDE.md`와
> [`docs/MONITOR.md`](../docs/MONITOR.md)를 먼저 읽는다. Next.js 관련
> 세부사항은 `@AGENTS.md`도 함께 참고한다.

@AGENTS.md

## 이 앱의 목적

7인치 모니터에 24/7 띄워두는 **읽기 전용 키오스크 디스플레이**다.
트레이딩 코어(`core/`)·Discord 봇(`discord-bot/`)과는 별도의 Next.js
프로젝트이며, 매매를 실행하거나 core에 쓰기 요청을 보내지 않는다 — 오직
상태를 보여주기만 한다.

## 절대 규칙

1. **상호작용 요소를 추가하지 않는다.** 버튼, 링크, 폼, 클릭/터치 핸들러,
   호버 전용 정보 노출 금지. 사용자가 이 화면을 조작할 일이 없다는 전제로
   설계됐다 — 키보드·마우스·터치 없이도 모든 정보가 항상 보여야 한다.
2. **디자인을 임의로 재해석하지 않는다.** 색상·간격·타이포는
   `claude.ai/design`의 **Bin Monitor.dc.html** 원본 값을 그대로 따른다.
   변경이 필요하면 먼저 디자인 프로젝트를 갱신한 뒤 코드에 반영한다.
3. **`core`의 내부 API 토큰을 브라우저로 내려보내지 않는다.** 실데이터
   연동 시 `CORE_INTERNAL_API_TOKEN`은 Next.js Route Handler(서버 사이드)
   안에서만 사용한다 (`docs/INTERNAL_API.md`의 인증 규칙과 동일한 원칙).
4. **폴링 실패가 화면을 비우면 안 된다.** `/api/snapshot` 호출이 실패하면
   마지막으로 받은 정상 스냅샷을 계속 표시한다 (`MonitorDashboard.tsx`).
5. **1024×600 고정 캔버스를 유지한다.** 실제 화면 크기가 다르면
   `KioskStage`의 스케일링으로 해결한다 — 컴포넌트 내부에서 반응형
   브레이크포인트를 만들지 않는다.

## 스택 메모

- 스타일은 Tailwind가 아니라 순수 CSS Modules (`Dashboard.module.css`)다.
  원본 디자인의 `oklch()` 값·소수점 px 단위를 정확히 옮기려면 유틸리티
  클래스보다 원본 인라인 스타일에 1:1 대응하는 클래스가 더 안전하다.
- 색상 토큰은 `src/app/globals.css`의 CSS 변수로 정의돼 있다. 새 색을
  추가할 때도 원본 디자인의 `oklch()` 값을 그대로 옮긴다.
