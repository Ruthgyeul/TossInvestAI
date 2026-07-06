"""장 마감 후 자기평가. KR 15:40 / US 06:10 (KST) 1회 실행 (docs/BIN.md)."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import structlog

from core.config import settings
from core.db import store as db
from core.events.publisher import publish_event
from core.models import Market, Mode

log = structlog.get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_REFLECTIONS_DIR = Path("logs/reports")

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

_REFLECTION_SYSTEM_PROMPT = (
    "너는 빈(Bin)의 자기평가 보조 AI다. 아래 오늘자 매매 내역과 Safety Gate 거부 이력을 검토해 "
    "한국어 마크다운 목록으로 다음 네 항목을 각각 한두 문장으로 평가하라.\n"
    "1. 오늘 매매가 적절했는가\n"
    "2. 놓친 매수/매도 기회는 무엇인가\n"
    "3. Safety Gate 거부 중 옳았던 것은 무엇인가\n"
    "4. 내일 개선할 점은 무엇인가"
)


def _summarize_trades(trades: list[dict]) -> str:
    if not trades:
        return "체결 없음"
    lines = []
    for t in trades:
        pnl = t.get("pnl_krw")
        pnl_str = f", 손익 {pnl:+,} KRW" if pnl is not None else ""
        lines.append(f"- {t['action']} {t['symbol']} {t['quantity']}주 @ {t['fill_price']:,}{pnl_str}")
    return "\n".join(lines)


def _summarize_rejections(rejections: list[dict]) -> str:
    if not rejections:
        return "거부 없음"
    return "\n".join(f"- {r['symbol']}: {r['reason']}" for r in rejections)


async def _call_claude_reflection(market: Market, trades: list[dict], rejections: list[dict]) -> str:
    """자기평가는 하루 1회뿐이라 Prompt Caching을 적용하지 않는다 (docs/BIN.md)."""
    user_message = (
        f"[{market} 시장 오늘 체결 내역]\n{_summarize_trades(trades)}\n\n"
        f"[{market} 시장 오늘 Safety Gate 거부 내역]\n{_summarize_rejections(rejections)}"
    )
    response = await _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=_REFLECTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    from core.fund.manager import fund_manager

    await fund_manager.record_api_usage(
        model=settings.CLAUDE_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    block = response.content[0]
    if not isinstance(block, anthropic.types.TextBlock):
        raise ValueError(f"Claude 응답이 텍스트 블록이 아님: {type(block).__name__}")
    return block.text


def _reflection_filename(market: Market, now: datetime) -> Path:
    _REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _REFLECTIONS_DIR / f"reflection_{now:%Y-%m-%d}_{market.lower()}.md"


async def run_reflection(market: Market) -> None:
    """오늘 매매 적절성·놓친 기회·Safety Gate 거부 타당성·개선점을 Claude에 질의하고
    reflections 테이블 + logs/reports/reflection_YYYY-MM-DD.md 에 저장한다."""
    mode: Mode = settings.run_mode  # type: ignore[assignment]
    trade_mode: Mode = "LIVE" if mode == "LIVE" else "SIMULATION"

    trades = await db.get_today_trades(trade_mode, market)
    rejections = await db.get_today_rejections(market)

    content_md = await _call_claude_reflection(market, trades, rejections)

    now = datetime.now(_KST)
    full_content = f"# [빈] {market} 자기평가 — {now:%Y-%m-%d} (장 마감 후)\n\n{content_md}"

    await db.insert("reflections", {"market": market, "mode": mode, "content_md": full_content})
    _reflection_filename(market, now).write_text(full_content, encoding="utf-8")

    log.info("reflection_completed", market=market, mode=mode)
    await publish_event(
        "reflection_ready",
        mode=mode,
        market=market,
        payload={"market": market, "contentMd": full_content[:3800]},
    )
