from __future__ import annotations

from pathlib import Path

import pytest

from notice_monitor.config import Config
from notice_monitor.demo import FixtureNoticeClient

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "notices.json"


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        dry_run=True,
        demo_mode=True,
        db_path=tmp_path / "state.sqlite",
        fixtures_path=FIXTURES,
        outbox_dir=tmp_path / "outbox",
        window_days=7,
    )


@pytest.fixture
def fixture_client(config) -> FixtureNoticeClient:
    return FixtureNoticeClient(config)
