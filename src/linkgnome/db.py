"""SQLite database layer for LinkGnome."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from linkgnome.fetchers.base import Platform, Post

DB_DIR = Path.home() / ".local" / "share" / "linkgnome"
DB_PATH = DB_DIR / "linkgnome.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    author TEXT NOT NULL,
    author_display_name TEXT,
    content TEXT,
    created_at TEXT NOT NULL,
    is_boost INTEGER DEFAULT 0,
    original_post_id TEXT,
    boosted_by TEXT,
    boost_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    raw_data TEXT
);

CREATE TABLE IF NOT EXISTS post_urls (
    post_id TEXT NOT NULL,
    url TEXT NOT NULL,
    PRIMARY KEY (post_id, url),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS url_metadata (
    url TEXT PRIMARY KEY,
    title TEXT,
    status_code INTEGER,
    fetched_at TEXT,
    final_url TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT,
    bio TEXT,
    avatar_url TEXT,
    last_updated TEXT,
    PRIMARY KEY (platform, handle)
);

CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
CREATE INDEX IF NOT EXISTS idx_post_urls_post ON post_urls(post_id);
CREATE INDEX IF NOT EXISTS idx_post_urls_url ON post_urls(url);
"""


class LinkgnomeDB:
    """SQLite-backed storage for posts, URLs, metadata, and profiles."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        return self._conn

    def save_posts(self, posts: list[Post]) -> int:
        """Batch insert posts. Returns count of new posts added."""
        conn = self.conn
        rows_added = 0
        for post in posts:
            existing = conn.execute(
                "SELECT id FROM posts WHERE id = ?", (post.id,)
            ).fetchone()
            if existing:
                continue

            conn.execute(
                """INSERT INTO posts
                   (id, platform, author, author_display_name, content,
                    created_at, is_boost, original_post_id, boosted_by,
                    boost_count, like_count, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    post.id,
                    post.platform.value,
                    post.author,
                    post.author_display_name,
                    post.content,
                    post.created_at.isoformat(),
                    int(post.is_boost),
                    post.original_post_id,
                    post.boosted_by,
                    post.boost_count,
                    post.like_count,
                    json.dumps(post.raw_data) if post.raw_data else None,
                ),
            )

            for url in post.urls:
                conn.execute(
                    "INSERT OR IGNORE INTO post_urls (post_id, url) VALUES (?, ?)",
                    (post.id, url),
                )

            rows_added += 1

        conn.commit()
        return rows_added

    def load_posts(
        self,
        platform: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Post]:
        """Load posts with their URLs."""
        query = """
            SELECT p.*, GROUP_CONCAT(DISTINCT pu.url) as urls
            FROM posts p
            LEFT JOIN post_urls pu ON p.id = pu.post_id
        """
        params: list[Any] = []
        where_clauses = []

        if platform:
            where_clauses.append("p.platform = ?")
            params.append(platform)
        if since:
            where_clauses.append("p.created_at >= ?")
            params.append(since.isoformat())

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " GROUP BY p.id"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        posts = []
        for row in rows:
            urls_str = row["urls"]
            urls = urls_str.split(",") if urls_str else []
            posts.append(
                Post(
                    id=row["id"],
                    platform=Platform(row["platform"]),
                    author=row["author"],
                    author_display_name=row["author_display_name"] or "",
                    content=row["content"] or "",
                    urls=urls,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    is_boost=bool(row["is_boost"]),
                    original_post_id=row["original_post_id"],
                    boosted_by=row["boosted_by"],
                    boost_count=row["boost_count"],
                    like_count=row["like_count"],
                    raw_data=json.loads(row["raw_data"]) if row["raw_data"] else None,
                )
            )
        return posts

    def count_posts(self, since: datetime | None = None) -> int:
        """Count posts matching criteria."""
        query = "SELECT COUNT(*) as cnt FROM posts"
        params: list[Any] = []
        if since:
            query += " WHERE created_at >= ?"
            params.append(since.isoformat())
        row = self.conn.execute(query, params).fetchone()
        return row["cnt"] if row else 0

    def clear_old_posts(self, keep_hours: int = 24) -> int:
        """Remove posts older than the specified window. Returns count deleted."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=keep_hours)
        ).isoformat()
        cursor = self.conn.execute(
            "DELETE FROM posts WHERE created_at < ?", (cutoff,)
        )
        self.conn.execute(
            "DELETE FROM post_urls WHERE post_id NOT IN (SELECT id FROM posts)"
        )
        self.conn.commit()
        return cursor.rowcount

    def save_url_metadata(
        self,
        url: str,
        title: str | None,
        status_code: int,
        final_url: str | None = None,
    ) -> None:
        """Cache fetched metadata for a URL."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO url_metadata
               (url, title, status_code, fetched_at, final_url)
               VALUES (?, ?, ?, ?, ?)""",
            (url, title, status_code, now, final_url),
        )
        self.conn.commit()

    def get_url_metadata(self, url: str) -> dict[str, Any] | None:
        """Get cached metadata for a URL."""
        row = self.conn.execute(
            "SELECT * FROM url_metadata WHERE url = ?", (url,)
        ).fetchone()
        if row is None:
            return None
        return {
            "title": row["title"],
            "status_code": row["status_code"],
            "fetched_at": row["fetched_at"],
            "final_url": row["final_url"],
        }

    def save_profile(
        self,
        platform: str,
        handle: str,
        display_name: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """Save or update a profile."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO profiles
               (platform, handle, display_name, bio, avatar_url, last_updated)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (platform, handle, display_name, bio, avatar_url, now),
        )
        self.conn.commit()

    def get_profile(self, platform: str, handle: str) -> dict[str, Any] | None:
        """Get profile data."""
        row = self.conn.execute(
            "SELECT * FROM profiles WHERE platform = ? AND handle = ?",
            (platform, handle),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
