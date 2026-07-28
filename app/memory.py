"""Persistencia local (SQLite) do progresso do aluno: sessoes, erros e vocabulario."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.curriculum import CEFR_SPEAKING_DESCRIPTORS, level_from_session_count

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    created_at TEXT NOT NULL,
    user_text TEXT NOT NULL,
    reply_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    created_at TEXT NOT NULL,
    wrong TEXT NOT NULL,
    right TEXT NOT NULL,
    explanation TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    created_at TEXT NOT NULL,
    word TEXT NOT NULL,
    UNIQUE(word)
);
"""


@dataclass
class LearnerProfile:
    sessions_count: int = 0
    top_mistake_patterns: list[str] = field(default_factory=list)
    known_vocab_count: int = 0
    cefr_level: str = "A1"

    def as_prompt_block(self) -> str:
        descriptor = CEFR_SPEAKING_DESCRIPTORS.get(self.cefr_level, "")
        if self.sessions_count == 0:
            return (
                "This is the student's first session ever. Assume CEFR level A1 "
                f"(beginner) until proven otherwise. What A1 speakers can do: {descriptor}"
            )
        lines = [
            f"Sessions so far: {self.sessions_count}",
            f"Estimated CEFR level: {self.cefr_level} - {descriptor}",
            f"Vocabulary already introduced: {self.known_vocab_count} words",
        ]
        if self.top_mistake_patterns:
            lines.append("Recurring mistakes to watch for and gently drill: " + "; ".join(self.top_mistake_patterns))
        return "\n".join(lines)


class Memory:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def start_session(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute("INSERT INTO sessions (started_at) VALUES (?)", (now,))
        self._conn.commit()
        return cur.lastrowid

    def end_session(self, session_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (now, session_id))
        self._conn.commit()

    def load_recent_history(self, max_turns: int) -> list[dict]:
        """Carrega os ultimos turnos (de qualquer sessao) para dar continuidade a conversa."""
        rows = self._conn.execute(
            "SELECT user_text, reply_text FROM turns ORDER BY id DESC LIMIT ?", (max_turns,)
        ).fetchall()
        rows.reverse()
        history: list[dict] = []
        for user_text, reply_text in rows:
            # turnos de abertura (saudacao proativa) nao tem fala do usuario
            if user_text:
                history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply_text})
        return history

    def record_turn(self, session_id: int, user_text: str, reply_text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO turns (session_id, created_at, user_text, reply_text) VALUES (?, ?, ?, ?)",
            (session_id, now, user_text, reply_text),
        )
        self._conn.commit()

    def record_corrections(self, session_id: int, corrections: list[dict]) -> None:
        if not corrections:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                session_id,
                now,
                c.get("wrong", ""),
                c.get("right", ""),
                c.get("explanation", ""),
                c.get("category", "grammar"),
            )
            for c in corrections
        ]
        self._conn.executemany(
            "INSERT INTO mistakes (session_id, created_at, wrong, right, explanation, category) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def record_vocabulary(self, session_id: int, words: list[str]) -> None:
        if not words:
            return
        now = datetime.now(timezone.utc).isoformat()
        for word in words:
            self._conn.execute(
                "INSERT OR IGNORE INTO vocabulary (session_id, created_at, word) VALUES (?, ?, ?)",
                (session_id, now, word.lower().strip()),
            )
        self._conn.commit()

    def build_profile(self) -> LearnerProfile:
        sessions_count = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        known_vocab_count = self._conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]

        categories = self._conn.execute("SELECT category FROM mistakes").fetchall()
        counts = Counter(c[0] for c in categories if c[0])
        top_patterns = [f"{cat} ({n}x)" for cat, n in counts.most_common(5)]

        return LearnerProfile(
            sessions_count=sessions_count,
            top_mistake_patterns=top_patterns,
            known_vocab_count=known_vocab_count,
            cefr_level=level_from_session_count(sessions_count),
        )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
