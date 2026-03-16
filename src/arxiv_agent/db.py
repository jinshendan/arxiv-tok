from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .models import Paper


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    paper_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    authors TEXT NOT NULL,
                    categories TEXT NOT NULL,
                    published TEXT NOT NULL,
                    updated TEXT NOT NULL,
                    url TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    paper_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    summary_cn TEXT NOT NULL,
                    highlights TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, paper_id, profile_name)
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    UNIQUE(paper_id, profile_name, channel)
                );
                """
            )

    def start_run(self, run_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, started_at, status) VALUES (?, ?, ?)",
                (run_id, datetime.utcnow().isoformat(), "running"),
            )

    def finish_run(self, run_id: str, status: str, error: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET finished_at=?, status=?, error=? WHERE run_id=?",
                (datetime.utcnow().isoformat(), status, error, run_id),
            )

    def upsert_papers(self, papers: list[Paper]) -> None:
        if not papers:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO papers (
                    paper_id, title, summary, authors, categories, published, updated, url, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    authors=excluded.authors,
                    categories=excluded.categories,
                    published=excluded.published,
                    updated=excluded.updated,
                    url=excluded.url,
                    fetched_at=excluded.fetched_at
                """,
                [
                    (
                        p.paper_id,
                        p.title,
                        p.summary,
                        ", ".join(p.authors),
                        ", ".join(p.categories),
                        p.published.isoformat(),
                        p.updated.isoformat(),
                        p.url,
                        datetime.utcnow().isoformat(),
                    )
                    for p in papers
                ],
            )

    def already_notified(self, paper_id: str, profile_name: str, channel: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications WHERE paper_id=? AND profile_name=? AND channel=?",
                (paper_id, profile_name, channel),
            ).fetchone()
            return row is not None

    def record_match(
        self,
        run_id: str,
        paper_id: str,
        profile_name: str,
        score: int,
        summary_cn: str,
        highlights: list[str],
        recommendation: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO matches (
                    run_id, paper_id, profile_name, score, summary_cn, highlights, recommendation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    paper_id,
                    profile_name,
                    score,
                    summary_cn,
                    "\n".join(highlights),
                    recommendation,
                    datetime.utcnow().isoformat(),
                ),
            )

    def record_notification(self, paper_id: str, profile_name: str, channel: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notifications (paper_id, profile_name, channel, sent_at) VALUES (?, ?, ?, ?)",
                (paper_id, profile_name, channel, datetime.utcnow().isoformat()),
            )
