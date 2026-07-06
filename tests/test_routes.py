"""내부 API 핸들러 단위 테스트 — `/status`·`/fund`·`/health` (docs/CODING_RULES.md Phase 4 검증 대상).

DB·토스 API·FundManager 등 실제 협력 객체는 monkeypatch로 격리하고 aiohttp 핸들러 함수를
`make_mocked_request`로 직접 호출해 응답 바디만 검증한다.
"""

import asyncio
import json as json_lib
from unittest import mock

import pytest
from aiohttp import streams
from aiohttp.test_utils import make_mocked_request

from core.api import routes
from core.config import settings
from core.fund.manager import fund_manager
from core.monitoring.health import HEALTH_REDIS_KEY


def _mocked_post_request(path: str, body: dict) -> object:
    """JSON 바디를 읽을 수 있는 POST 목 요청 — make_mocked_request의 payload는
    StreamReader 프로토콜(`at_eof`/`read`)을 요구해 bytes를 직접 넘길 수 없다."""
    protocol = mock.Mock()
    protocol._reading_paused = False
    reader = streams.StreamReader(protocol, 2**16, loop=asyncio.get_event_loop())
    reader.feed_data(json_lib.dumps(body).encode())
    reader.feed_eof()
    return make_mocked_request("POST", path, payload=reader)


@pytest.mark.asyncio
async def test_get_health_returns_defaults_when_no_snapshot_cached(
    fake_redis,  # noqa: ANN001 — tests/conftest.py fixture
) -> None:
    request = make_mocked_request("GET", "/api/v1/health")

    response = await routes.get_health(request)
    body = json_lib.loads(response.body)

    assert body["mode"] == settings.run_mode
    assert body["cpuPct"] == 0.0
    assert body["tossApiReachable"] is False


@pytest.mark.asyncio
async def test_get_health_returns_cached_snapshot(fake_redis) -> None:  # noqa: ANN001
    await fake_redis.set(
        HEALTH_REDIS_KEY,
        json_lib.dumps(
            {
                "cpu_pct": 42.5,
                "memory_pct": 55.0,
                "disk_pct": 60.0,
                "temp_c": 65.0,
                "toss_api_reachable": True,
            }
        ),
    )

    request = make_mocked_request("GET", "/api/v1/health")
    response = await routes.get_health(request)
    body = json_lib.loads(response.body)

    assert body["cpuPct"] == 42.5
    assert body["tossApiReachable"] is True


@pytest.mark.asyncio
async def test_get_status_returns_live_null_in_simulation_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SIMULATION", True)
    monkeypatch.setattr(settings, "DRY_RUN", False)

    async def _get_portfolio_status(mode, market=None):  # noqa: ANN001
        assert mode == "SIMULATION"
        return {"totalValueKrw": 512_000, "holdings": []}

    monkeypatch.setattr(fund_manager, "get_portfolio_status", _get_portfolio_status)

    request = make_mocked_request("GET", "/api/v1/status")
    response = await routes.get_status(request)
    body = json_lib.loads(response.body)

    assert body["live"] is None
    assert body["simulation"]["totalValueKrw"] == 512_000


@pytest.mark.asyncio
async def test_get_fund_computes_position_ratios(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _get_portfolio_status(mode, market=None):  # noqa: ANN001
        return {
            "holdings": [{"symbol": "005930", "quantity": 2, "currentPrice": 75_000}],
            "cashBufferKrw": 75_000,
            "cumulativePnlPct": 0.05,
        }

    async def _get_operating_funds_krw(mode=None):  # noqa: ANN001
        return 425_000.0

    monkeypatch.setattr(fund_manager, "get_portfolio_status", _get_portfolio_status)
    monkeypatch.setattr(fund_manager, "get_operating_funds_krw", _get_operating_funds_krw)

    request = make_mocked_request("GET", "/api/v1/fund")
    response = await routes.get_fund(request)
    body = json_lib.loads(response.body)

    assert body["operatingFundsKrw"] == 425_000
    assert body["cashBufferKrw"] == 75_000
    assert body["positionRatios"] == [
        {"symbol": "005930", "ratio": pytest.approx(150_000 / 425_000)}
    ]


@pytest.mark.asyncio
async def test_post_stop_persists_flags_to_db_and_redis(
    fake_redis,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "EMERGENCY_STOP", False)
    monkeypatch.setattr(settings, "KR_STOP", False)
    monkeypatch.setattr(settings, "US_STOP", False)

    persisted: dict = {}

    async def _set_control_flags(*, emergency_stop: bool, kr_stop: bool, us_stop: bool) -> None:
        persisted.update(
            emergency_stop=emergency_stop, kr_stop=kr_stop, us_stop=us_stop
        )

    monkeypatch.setattr(routes.db, "set_control_flags", _set_control_flags)

    request = _mocked_post_request("/api/v1/control/stop", {})
    response = await routes.post_stop(request)
    body = json_lib.loads(response.body)

    assert body["emergencyStop"] is True
    assert settings.EMERGENCY_STOP is True
    assert persisted == {"emergency_stop": True, "kr_stop": False, "us_stop": False}

    cached = json_lib.loads(await fake_redis.get(routes._CONTROL_FLAGS_REDIS_KEY))
    assert cached["emergencyStop"] is True


@pytest.mark.asyncio
async def test_post_stop_cancels_open_orders_in_live_mode(
    fake_redis,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "EMERGENCY_STOP", False)
    monkeypatch.setattr(settings, "DRY_RUN", False)
    monkeypatch.setattr(settings, "SIMULATION", False)  # run_mode == "LIVE"

    async def _set_control_flags(**_: object) -> None:
        return None

    monkeypatch.setattr(routes.db, "set_control_flags", _set_control_flags)

    async def _get_orders(status: str | None = None) -> list[dict]:
        return [
            {"orderId": "o-1", "symbol": "005930", "market": "KR"},
            {"orderId": "o-2", "symbol": "AAPL", "market": "US"},
        ]

    cancelled_ids: list[str] = []

    async def _cancel(order_id: str) -> dict:
        cancelled_ids.append(order_id)
        return {"orderId": order_id}

    monkeypatch.setattr(routes.toss_order, "get_orders", _get_orders)
    monkeypatch.setattr(routes.toss_order, "cancel", _cancel)

    request = _mocked_post_request("/api/v1/control/stop", {"market": "KR"})
    response = await routes.post_stop(request)
    body = json_lib.loads(response.body)

    assert cancelled_ids == ["o-1"]
    assert body["cancelledOrders"] == [{"orderId": "o-1", "symbol": "005930"}]


@pytest.mark.asyncio
async def test_post_resume_clears_and_persists_flags(
    fake_redis,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "EMERGENCY_STOP", True)
    monkeypatch.setattr(settings, "KR_STOP", True)
    monkeypatch.setattr(settings, "US_STOP", True)

    persisted: dict = {}

    async def _set_control_flags(*, emergency_stop: bool, kr_stop: bool, us_stop: bool) -> None:
        persisted.update(
            emergency_stop=emergency_stop, kr_stop=kr_stop, us_stop=us_stop
        )

    monkeypatch.setattr(routes.db, "set_control_flags", _set_control_flags)

    request = make_mocked_request("POST", "/api/v1/control/resume")
    response = await routes.post_resume(request)
    body = json_lib.loads(response.body)

    assert body["success"] is True
    assert settings.EMERGENCY_STOP is False
    assert persisted == {"emergency_stop": False, "kr_stop": False, "us_stop": False}
