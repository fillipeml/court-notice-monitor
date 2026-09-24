"""Local state in SQLite. Idempotency: no duplicate alert, nothing lost between runs."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .notice import Notice

SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    notice_key      TEXT PRIMARY KEY,
    case_number     TEXT,
    type            TEXT,
    status          TEXT,
    category        TEXT NOT NULL,
    sent_at         TEXT,
    acknowledge_by  TEXT,
    court           TEXT,
    urgent          INTEGER NOT NULL DEFAULT 0,
    account         TEXT NOT NULL,
    seen_at         TEXT NOT NULL,
    alerted_at      TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at      TEXT NOT NULL,
    success     INTEGER NOT NULL,
    listed      INTEGER,
    new         INTEGER,
    alert_sent  INTEGER,
    dry_run     INTEGER,
    error       TEXT
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class State:
    def __init__(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.executescript(SCHEMA)

    def record(self, notice: Notice, category: str, account: str) -> bool:
        """Insert the notice if unseen. Returns True when it is new."""
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO notices (notice_key, case_number, type, status, category,"
            " sent_at, acknowledge_by, court, urgent, account, seen_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                notice.key(account),
                notice.case_number,
                notice.type,
                notice.status,
                category,
                notice.sent_at,
                notice.acknowledge_by,
                notice.court,
                int(notice.urgent),
                account,
                _now(),
            ),
        )
        self._conn.commit()
        return cursor.rowcount == 1

    def mark_alerted(self, keys: list[str]) -> None:
        now = _now()
        self._conn.executemany(
            "UPDATE notices SET alerted_at = ? WHERE notice_key = ?",
            [(now, k) for k in keys],
        )
        self._conn.commit()

    def record_run(
        self,
        success: bool,
        listed: int | None = None,
        new: int | None = None,
        alert_sent: bool | None = None,
        dry_run: bool | None = None,
        error: str | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO runs (ran_at, success, listed, new, alert_sent, dry_run, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _now(),
                int(success),
                listed,
                new,
                None if alert_sent is None else int(alert_sent),
                None if dry_run is None else int(dry_run),
                error,
            ),
        )
        self._conn.commit()

    def recent_runs(self, count: int = 5) -> list[dict[str, Any]]:
        columns = ["ran_at", "success", "listed", "new", "alert_sent", "dry_run", "error"]
        rows = self._conn.execute(
            f"SELECT {', '.join(columns)} FROM runs ORDER BY id DESC LIMIT ?", (count,)
        ).fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def summary(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT category, COUNT(*) FROM notices GROUP BY category"
        ).fetchall()
        return {category: total for category, total in rows}

    def alerted_at(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT alerted_at FROM notices WHERE notice_key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def account_of(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT account FROM notices WHERE notice_key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._conn.close()
