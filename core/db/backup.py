"""자동 백업·복구 (docs/LOGGING.md).

매일 03:00 전체 덤프(30일 보관) / 매주 일요일 주간 스냅샷(1년) / 매월 1일 월간 스냅샷(무제한).
실패 시 Discord #stock-error 즉시 알림.
"""

import asyncio
import gzip
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog

from core.config import settings
from core.events.publisher import publish_event

log = structlog.get_logger(__name__)

BACKUPS_DIR = Path("backups")
_KST = ZoneInfo("Asia/Seoul")
_DAILY_RETENTION_DAYS = 30
_WEEKLY_RETENTION_DAYS = 365


def _pg_dump_dsn() -> str:
    """asyncpg용 DATABASE_URL(`postgresql+asyncpg://...`)을 pg_dump/psql이 이해하는 형식으로 변환한다."""
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _dump_to_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        "pg_dump",
        _pg_dump_dsn(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"pg_dump 실패 (exit {process.returncode}): {stderr.decode(errors='replace')[:500]}"
        )

    compressed = await asyncio.to_thread(gzip.compress, stdout)
    await asyncio.to_thread(path.write_bytes, compressed)


def _prune_old_backups(directory: Path, retention_days: int) -> None:
    if not directory.exists():
        return
    cutoff = datetime.now(_KST).timestamp() - retention_days * 86400
    for f in directory.glob("*.sql.gz"):
        if f.stat().st_mtime < cutoff:
            f.unlink()


async def _run_backup(directory: Path, filename: str, retention_days: int | None) -> Path:
    path = directory / filename
    try:
        await _dump_to_file(path)
    except Exception as e:  # noqa: BLE001 — 백업 실패는 그대로 #stock-error 알림으로 전달돼야 한다
        log.error("db_backup_failed", target=str(path), error=str(e))
        await publish_event(
            "health_alert",
            mode=settings.run_mode,
            market=None,
            payload={"warnings": [f"DB 백업 실패 ({path.name}): {e}"]},
        )
        raise

    if retention_days is not None:
        await asyncio.to_thread(_prune_old_backups, directory, retention_days)
    return path


async def run_daily_backup() -> Path:
    """매일 03:00 KST — 전체 덤프, 30일 보관 (backups/daily/)."""
    now = datetime.now(_KST)
    filename = f"{now:%Y-%m-%d_%H%M}.sql.gz"
    return await _run_backup(BACKUPS_DIR / "daily", filename, _DAILY_RETENTION_DAYS)


async def run_weekly_backup() -> Path:
    """매주 일요일 — 주간 스냅샷, 1년 보관 (backups/weekly/)."""
    now = datetime.now(_KST)
    iso_year, iso_week, _ = now.isocalendar()
    filename = f"{iso_year}-W{iso_week:02d}.sql.gz"
    return await _run_backup(BACKUPS_DIR / "weekly", filename, _WEEKLY_RETENTION_DAYS)


async def run_monthly_backup() -> Path:
    """매월 1일 — 월간 스냅샷, 무제한 보관 (backups/monthly/)."""
    now = datetime.now(_KST)
    filename = f"{now:%Y-%m}.sql.gz"
    return await _run_backup(BACKUPS_DIR / "monthly", filename, None)


async def restore(backup_path: Path) -> None:
    """백업 파일로부터 복구한다.

    실행 전 대상 DATABASE_URL이 실전 DB가 아닌지 반드시 확인할 것
    (CLAUDE.md 규칙 11 — 실전 DB와 시뮬레이션 DB 절대 혼용 금지). 이 함수는 안전 확인 없이
    DATABASE_URL이 가리키는 DB에 그대로 복구를 실행한다.
    """
    compressed = await asyncio.to_thread(backup_path.read_bytes)
    sql = await asyncio.to_thread(gzip.decompress, compressed)

    process = await asyncio.create_subprocess_exec(
        "psql",
        _pg_dump_dsn(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate(input=sql)
    if process.returncode != 0:
        raise RuntimeError(
            f"psql 복구 실패 (exit {process.returncode}): {stderr.decode(errors='replace')[:500]}"
        )
