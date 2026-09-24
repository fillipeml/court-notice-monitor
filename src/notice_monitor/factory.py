"""The only place that reads `demo_mode` and picks real or local implementations."""

from __future__ import annotations

from .api_client import NoticeApiClient
from .config import Config
from .demo import FixtureNoticeClient
from .mail import GraphMailer, Mailer, OutboxMailer
from .sweep import NoticeSource


def build_client(config: Config) -> NoticeSource:
    if config.demo_mode:
        return FixtureNoticeClient(config)
    return NoticeApiClient(config)


def build_mailer(config: Config) -> Mailer:
    if config.demo_mode:
        return OutboxMailer(config.outbox_dir)
    return GraphMailer(config)
