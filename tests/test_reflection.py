"""자기평가(Reflection) 루프 단위 테스트 (docs/BIN.md "자기평가")."""

from pathlib import Path
from types import SimpleNamespace

import anthropic
import pytest

import core.trading.reflection as reflection_module
from core.config import settings


@pytest.mark.asyncio
async def test_run_reflection_calls_claude_saves_db_and_file_and_publishes_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "DRY_RUN", False)
    monkeypatch.setattr(settings, "SIMULATION", True)  # run_mode == "SIMULATION"
    monkeypatch.setattr(reflection_module, "_REFLECTIONS_DIR", tmp_path)

    async def _get_today_trades(mode: str, market: str) -> list[dict]:
        assert mode == "SIMULATION"
        assert market == "KR"
        return [
            {"action": "BUY", "symbol": "005930", "quantity": 2, "fill_price": 75_000, "pnl_krw": None}
        ]

    async def _get_today_rejections(market: str) -> list[dict]:
        return [{"symbol": "AAPL", "reason": "현금 버퍼 부족"}]

    monkeypatch.setattr(reflection_module.db, "get_today_trades", _get_today_trades)
    monkeypatch.setattr(reflection_module.db, "get_today_rejections", _get_today_rejections)

    fake_usage = SimpleNamespace(input_tokens=500, output_tokens=150)
    fake_response = SimpleNamespace(
        content=[anthropic.types.TextBlock(text="1. 적절했음\n2. 없음\n3. 옳았음\n4. 없음", type="text")],
        usage=fake_usage,
    )

    async def _fake_create(**kwargs):
        return fake_response

    monkeypatch.setattr(reflection_module._client.messages, "create", _fake_create)

    recorded_usage: dict = {}

    async def _fake_record_api_usage(**kwargs):
        recorded_usage.update(kwargs)

    import core.fund.manager as manager_module

    monkeypatch.setattr(manager_module.fund_manager, "record_api_usage", _fake_record_api_usage)

    inserted: dict = {}

    async def _fake_insert(table: str, values: dict) -> dict:
        inserted["table"] = table
        inserted["values"] = values
        return values

    monkeypatch.setattr(reflection_module.db, "insert", _fake_insert)

    published: dict = {}

    async def _fake_publish_event(event_type: str, **kwargs):
        published["event_type"] = event_type
        published.update(kwargs)

    monkeypatch.setattr(reflection_module, "publish_event", _fake_publish_event)

    await reflection_module.run_reflection("KR")

    assert inserted["table"] == "reflections"
    assert inserted["values"]["market"] == "KR"
    assert inserted["values"]["mode"] == "SIMULATION"
    assert "적절했음" in inserted["values"]["content_md"]

    assert recorded_usage == {
        "model": settings.CLAUDE_MODEL,
        "input_tokens": 500,
        "output_tokens": 150,
    }

    assert published["event_type"] == "reflection_ready"
    assert published["market"] == "KR"
    assert "적절했음" in published["payload"]["contentMd"]

    saved_files = list(tmp_path.glob("reflection_*_kr.md"))
    assert len(saved_files) == 1
    assert "적절했음" in saved_files[0].read_text(encoding="utf-8")
