"""자동 DB 백업 단위 테스트 (docs/LOGGING.md "자동 DB 백업"). pg_dump/psql 서브프로세스는 mock한다."""

import gzip
import time
from pathlib import Path

import pytest

import core.db.backup as backup_module


class _FakeProcess:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, input: bytes | None = None):  # noqa: A002
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_run_daily_backup_writes_gzip_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(backup_module, "BACKUPS_DIR", tmp_path)

    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(stdout=b"-- fake pg_dump output --")

    monkeypatch.setattr(backup_module.asyncio, "create_subprocess_exec", _fake_exec)

    path = await backup_module.run_daily_backup()

    assert path.exists()
    assert path.parent == tmp_path / "daily"
    assert gzip.decompress(path.read_bytes()) == b"-- fake pg_dump output --"


@pytest.mark.asyncio
async def test_run_daily_backup_prunes_files_older_than_retention(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(backup_module, "BACKUPS_DIR", tmp_path)
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir(parents=True)

    old_file = daily_dir / "2020-01-01_0300.sql.gz"
    old_file.write_bytes(gzip.compress(b"old"))
    old_timestamp = time.time() - (backup_module._DAILY_RETENTION_DAYS + 1) * 86400
    import os

    os.utime(old_file, (old_timestamp, old_timestamp))

    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(stdout=b"fresh dump")

    monkeypatch.setattr(backup_module.asyncio, "create_subprocess_exec", _fake_exec)

    await backup_module.run_daily_backup()

    assert not old_file.exists()


@pytest.mark.asyncio
async def test_backup_failure_publishes_health_alert(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(backup_module, "BACKUPS_DIR", tmp_path)

    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(stdout=b"", stderr=b"pg_dump: error: connection failed", returncode=1)

    monkeypatch.setattr(backup_module.asyncio, "create_subprocess_exec", _fake_exec)

    published: dict = {}

    async def _fake_publish_event(event_type: str, **kwargs):
        published["event_type"] = event_type
        published.update(kwargs)

    monkeypatch.setattr(backup_module, "publish_event", _fake_publish_event)

    with pytest.raises(RuntimeError, match="pg_dump 실패"):
        await backup_module.run_daily_backup()

    assert published["event_type"] == "health_alert"
    assert "백업 실패" in published["payload"]["warnings"][0]
