"""Persistencia local (SQLite) do progresso do aluno: sessoes, erros e vocabulario."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.curriculum import CEFR_SPEAKING_DESCRIPTORS, FIRST_LESSON_ID, get_lesson

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

CREATE TABLE IF NOT EXISTS lesson_progress (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_lesson_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lesson_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    lesson_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    student_turn_count INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    completion_reason TEXT
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
        """Contexto geral do aluno (erros/vocabulario) - o nivel/aula atual
        entram separadamente no prompt via app/tutor.py (ver
        docs/emily_lesson_system_prompt.md), essa funcao nao decide mais
        isso sozinha."""
        descriptor = CEFR_SPEAKING_DESCRIPTORS.get(self.cefr_level, "")
        lines = [
            f"Sessions so far: {self.sessions_count}",
            f"Estimated CEFR level (based on curriculum progress): {self.cefr_level} - {descriptor}",
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

        lesson = get_lesson(self.get_current_lesson_id())

        return LearnerProfile(
            sessions_count=sessions_count,
            top_mistake_patterns=top_patterns,
            known_vocab_count=known_vocab_count,
            cefr_level=lesson.level,
        )

    # --- progresso por aula (ver docs/lesson_progression.md) ----------------

    def get_current_lesson_id(self) -> str:
        row = self._conn.execute("SELECT current_lesson_id FROM lesson_progress WHERE id = 1").fetchone()
        if row:
            return row[0]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO lesson_progress (id, current_lesson_id, updated_at) VALUES (1, ?, ?)",
            (FIRST_LESSON_ID, now),
        )
        self._conn.commit()
        return FIRST_LESSON_ID

    def is_first_ever_lesson(self) -> bool:
        """True somente se o aluno nunca concluiu nenhuma aula - usado para
        decidir se a Emily precisa da ponte bilingue de acolhimento."""
        if self.get_current_lesson_id() != FIRST_LESSON_ID:
            return False
        completed = self._conn.execute(
            "SELECT COUNT(*) FROM lesson_attempts WHERE completed = 1"
        ).fetchone()[0]
        return completed == 0

    def count_recent_incomplete_attempts(self, lesson_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM lesson_attempts WHERE lesson_id = ? AND completed = 0",
            (lesson_id,),
        ).fetchone()[0]

    def start_lesson_attempt(self, session_id: int, lesson_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO lesson_attempts (session_id, lesson_id, started_at, completed) "
            "VALUES (?, ?, ?, 0)",
            (session_id, lesson_id, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def finalize_attempt(self, attempt_id: int, student_turn_count: int) -> None:
        """Fecha o registro da tentativa (sessao/turno terminou), SEM mexer
        em `completed` - se nao foi marcada como concluida explicitamente
        antes disso, permanece 0 para sempre. E assim que fechar o app sem
        interagir, ou um crash, nunca vira progresso por engano."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE lesson_attempts SET ended_at = ?, student_turn_count = ? WHERE id = ?",
            (now, student_turn_count, attempt_id),
        )
        self._conn.commit()

    def mark_lesson_complete(self, attempt_id: int, lesson_id: str, next_lesson_id: str, reason: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE lesson_attempts SET completed = 1, completion_reason = ?, ended_at = ? WHERE id = ?",
            (reason, now, attempt_id),
        )
        self._conn.execute(
            "UPDATE lesson_progress SET current_lesson_id = ?, updated_at = ? WHERE id = 1",
            (next_lesson_id, now),
        )
        self._conn.commit()

    def get_completed_lesson_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT DISTINCT lesson_id FROM lesson_attempts WHERE completed = 1").fetchall()
        return {r[0] for r in rows}

    def get_streak_days(self) -> int:
        """Dias seguidos com pelo menos uma aula concluida (permite que hoje
        ainda nao tenha nenhuma, senao a sequencia "zeraria" toda manha antes
        do aluno ter chance de praticar)."""
        rows = self._conn.execute(
            "SELECT DISTINCT substr(ended_at, 1, 10) AS d FROM lesson_attempts "
            "WHERE completed = 1 AND ended_at IS NOT NULL ORDER BY d DESC"
        ).fetchall()
        practiced_days = {r[0] for r in rows if r[0]}
        if not practiced_days:
            return 0

        from datetime import timedelta

        today = datetime.now(timezone.utc).date()
        cursor = today
        if cursor.isoformat() not in practiced_days:
            cursor -= timedelta(days=1)
            if cursor.isoformat() not in practiced_days:
                return 0

        streak = 0
        while cursor.isoformat() in practiced_days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

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
