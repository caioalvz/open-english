"""Base curricular para a progressao da Emily.

Baseado nos "CEFR Can-Do Statements" oficiais do Conselho da Europa (Common
European Framework of Reference for Languages) para Spoken Interaction e
Spoken Production - o padrao internacional mais usado para descrever nivel
de conversacao em lingua estrangeira:
https://www.coe.int/en/web/common-european-framework-reference-languages

Os topicos por nivel seguem a progressao tipica de material didatico de
conversacao alinhado ao CEFR (ex: British Council, Cambridge English): comecam
em informacoes pessoais concretas (A1) e avancam ate discussao abstrata e
argumentativa (C1+).
"""
from __future__ import annotations

import random

# Descritores oficiais (traduzidos/resumidos) do que o aluno consegue fazer
# falando em cada nivel - usados para calibrar a complexidade da Emily.
CEFR_SPEAKING_DESCRIPTORS: dict[str, str] = {
    "A1": "Can interact in a simple way if the other person speaks slowly and "
    "helps formulate ideas. Can ask/answer simple questions on very familiar "
    "topics (self, family, immediate needs).",
    "A2": "Can handle simple, direct exchanges on familiar topics and routine "
    "tasks. Can manage very short social exchanges.",
    "B1": "Can enter unprepared into conversation on familiar topics of "
    "personal interest (family, hobbies, work, travel, current events). Can "
    "describe experiences, dreams, hopes, and briefly justify opinions.",
    "B2": "Can interact with fluency and spontaneity, making regular "
    "interaction with native speakers possible. Can take an active part in "
    "discussion, accounting for and sustaining views.",
    "C1": "Can express ideas fluently and spontaneously without much obvious "
    "searching for expressions. Can use language flexibly for social and "
    "professional purposes, formulating precise opinions.",
}

# Topicos de conversa tipicos por nivel (progressao didatica alinhada ao CEFR).
TOPICS_BY_LEVEL: dict[str, list[str]] = {
    "A1": [
        "introducing yourself (name, where you're from, what you do)",
        "your family",
        "your home and daily routine",
        "food and drinks you like",
        "numbers, days, and telling time",
    ],
    "A2": [
        "your hobbies and free time",
        "shopping and prices",
        "describing your city or neighborhood",
        "asking for and giving simple directions",
        "your job or studies",
        "the weather and seasons",
    ],
    "B1": [
        "a trip or vacation you remember",
        "your plans and ambitions for the future",
        "a movie, show, or book you enjoyed",
        "comparing life now vs. when you were a kid",
        "your opinion on a everyday topic (social media, work-life balance)",
        "a challenge you overcame",
    ],
    "B2": [
        "advantages and disadvantages of remote work",
        "how technology is changing daily life",
        "a current event or news topic",
        "environmental issues in your city or country",
        "a decision you're unsure about and why",
        "cultural differences you've noticed or heard about",
    ],
    "C1": [
        "a nuanced opinion on a controversial topic",
        "how you'd solve a complex problem at work or in society",
        "abstract ideas like happiness, success, or ambition",
        "a hypothetical scenario (\"what would you do if...\")",
        "critiquing an idea or argument in detail",
    ],
}

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1"]


def level_from_session_count(sessions_count: int) -> str:
    """Progressao simples: mais sessoes concluidas -> nivel mais avancado.

    Heuristica deliberadamente conservadora (poucas sessoes por nivel no
    inicio, mais depois) - o importante nao e cravar o nivel exato do aluno,
    e sim dar a Emily uma nocao razoavel de que tipo de topico/complexidade
    oferecer em seguida.
    """
    thresholds = [0, 3, 8, 16, 28]  # sessoes acumuladas para cada nivel
    level = LEVEL_ORDER[0]
    for lvl, minimum in zip(LEVEL_ORDER, thresholds):
        if sessions_count >= minimum:
            level = lvl
    return level


def pick_topic(level: str, avoid: str | None = None) -> str:
    """Escolhe um topico de conversa para o nivel, evitando repetir o ultimo."""
    topics = TOPICS_BY_LEVEL.get(level, TOPICS_BY_LEVEL["A1"])
    candidates = [t for t in topics if t != avoid] or topics
    return random.choice(candidates)
