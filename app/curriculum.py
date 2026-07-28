"""Curriculo estruturado da Emily: trilha sequencial de aulas A1 -> C2.

Baseado nos "CEFR Can-Do Statements" oficiais do Conselho da Europa (Common
European Framework of Reference for Languages) para Spoken Interaction e
Spoken Production - o padrao internacional mais usado para descrever nivel
de conversacao em lingua estrangeira:
https://www.coe.int/en/web/common-european-framework-reference-languages

Cada aula (Lesson) e a unidade real de progresso do aluno - ver
docs/lesson_progression.md para o desenho completo do sistema. O progresso
NAO e mais contado por sessao/abertura do app: so avanca quando uma aula e
genuinamente concluida (ver app/memory.py e app/tutor.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Descritores oficiais (resumidos) do que o aluno consegue fazer falando em
# cada nivel - usados para calibrar o tom geral da Emily junto ao objetivo
# especifico de cada aula.
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
    "C2": "Can express themselves spontaneously, very fluently and precisely, "
    "differentiating finer shades of meaning. Has a good command of "
    "idiomatic expressions and colloquialisms.",
}

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


@dataclass(frozen=True)
class Lesson:
    id: str
    level: str
    title: str
    can_do_objective: str
    focus_vocab: list[str] = field(default_factory=list)
    min_student_turns: int = 3


LESSONS: list[Lesson] = [
    # --- A1: Breakthrough --------------------------------------------------
    Lesson(
        "A1-01", "A1", "Introducing yourself",
        "Can say their name, where they're from, and one basic fact about "
        "themselves when asked directly.",
        ["my name is", "I'm from", "nice to meet you", "I live in"], 3,
    ),
    Lesson(
        "A1-02", "A1", "Talking about your family",
        "Can name 2-3 family members and say one simple fact about each "
        "(age, job, or where they live).",
        ["mother", "father", "brother", "sister", "years old"], 3,
    ),
    Lesson(
        "A1-03", "A1", "Your home and daily routine",
        "Can describe where they live in simple terms and list 2-3 things "
        "they do every day.",
        ["I live in", "I wake up", "every day", "in the morning"], 3,
    ),
    Lesson(
        "A1-04", "A1", "Food and drinks you like",
        "Can say what food/drinks they like or dislike using simple "
        "sentences.",
        ["I like", "I don't like", "my favorite", "for breakfast"], 3,
    ),
    Lesson(
        "A1-05", "A1", "Numbers, days, and time",
        "Can state the current day, a simple time, and count basic "
        "quantities.",
        ["what time is it", "today is", "o'clock", "how many"], 3,
    ),
    Lesson(
        "A1-06", "A1", "Asking for help with basic needs",
        "Can ask a simple question when they don't understand or need "
        "something.",
        ["can you repeat", "what does ... mean", "I don't understand"], 3,
    ),
    # --- A2: Waystage --------------------------------------------------
    Lesson(
        "A2-01", "A2", "Your hobbies and free time",
        "Can describe 2-3 hobbies and say how often they do them.",
        ["I enjoy", "on weekends", "sometimes", "I usually"], 3,
    ),
    Lesson(
        "A2-02", "A2", "Shopping and prices",
        "Can ask the price of something and respond to simple shopping "
        "questions.",
        ["how much is", "that's expensive", "I'd like to buy"], 3,
    ),
    Lesson(
        "A2-03", "A2", "Describing your city or neighborhood",
        "Can describe 2-3 features of where they live using simple "
        "adjectives.",
        ["there is/are", "near", "far from", "quiet", "busy"], 3,
    ),
    Lesson(
        "A2-04", "A2", "Asking for and giving directions",
        "Can ask how to get somewhere and understand or give a simple "
        "direction.",
        ["turn left/right", "go straight", "next to"], 3,
    ),
    Lesson(
        "A2-05", "A2", "Your job or studies",
        "Can describe what they do for work/study and one daily task "
        "involved.",
        ["I work as", "I study", "my job is"], 3,
    ),
    Lesson(
        "A2-06", "A2", "The weather and seasons",
        "Can describe today's weather and compare two seasons simply.",
        ["it's sunny/rainy/cold", "in summer", "I prefer"], 3,
    ),
    # --- B1: Threshold --------------------------------------------------
    Lesson(
        "B1-01", "B1", "A trip or vacation you remember",
        "Can narrate a past trip in a few connected sentences, including "
        "where, when, and what happened.",
        ["last year", "we went", "it was"], 4,
    ),
    Lesson(
        "B1-02", "B1", "Your plans and ambitions for the future",
        "Can describe a future plan or ambition and briefly explain why.",
        ["I'm going to", "I hope to", "my goal is"], 4,
    ),
    Lesson(
        "B1-03", "B1", "A movie, show, or book you enjoyed",
        "Can summarize a story briefly and describe their reaction to it.",
        ["it's about", "I really liked", "my favorite part"], 4,
    ),
    Lesson(
        "B1-04", "B1", "Comparing life now vs. when you were a kid",
        "Can make 2-3 simple comparisons between past and present.",
        ["used to", "nowadays", "more than", "less than"], 4,
    ),
    Lesson(
        "B1-05", "B1", "Giving an opinion on an everyday topic",
        "Can state an opinion and give one reason to support it.",
        ["I think", "in my opinion", "because"], 4,
    ),
    Lesson(
        "B1-06", "B1", "A challenge you overcame",
        "Can describe a difficulty they faced and how they dealt with it.",
        ["it was difficult", "I managed to", "in the end"], 4,
    ),
    # --- B2: Vantage --------------------------------------------------
    Lesson(
        "B2-01", "B2", "Advantages and disadvantages of remote work",
        "Can present at least one advantage and one disadvantage with "
        "justification.",
        ["on one hand", "on the other hand", "a benefit of"], 4,
    ),
    Lesson(
        "B2-02", "B2", "How technology is changing daily life",
        "Can discuss a specific way technology has changed something, with "
        "an example.",
        ["has changed the way", "for instance", "as a result"], 4,
    ),
    Lesson(
        "B2-03", "B2", "A current event or news topic",
        "Can summarize a topic and share a reasoned opinion on it.",
        ["I read that", "it seems that", "I'm concerned about"], 4,
    ),
    Lesson(
        "B2-04", "B2", "Environmental issues in your city or country",
        "Can describe a specific issue and suggest a possible solution.",
        ["one issue is", "a possible solution", "should"], 4,
    ),
    Lesson(
        "B2-05", "B2", "A decision you're unsure about",
        "Can weigh the pros and cons of a real or hypothetical decision "
        "aloud.",
        ["I'm torn between", "the upside", "the downside"], 4,
    ),
    Lesson(
        "B2-06", "B2", "Cultural differences you've noticed or heard about",
        "Can compare a cultural difference and explain their perspective on "
        "it.",
        ["compared to", "what surprised me", "I find it interesting that"], 4,
    ),
    # --- C1: Effective Operational Proficiency ------------------------
    Lesson(
        "C1-01", "C1", "A nuanced opinion on a controversial topic",
        "Can present a nuanced position while acknowledging a "
        "counterargument.",
        ["that said", "to some extent", "a fair point, but"], 5,
    ),
    Lesson(
        "C1-02", "C1", "Solving a complex problem at work or in society",
        "Can propose a structured solution to a complex problem, "
        "explaining trade-offs.",
        ["the root cause", "a trade-off", "in the long run"], 5,
    ),
    Lesson(
        "C1-03", "C1", "Abstract ideas like happiness, success, or ambition",
        "Can discuss an abstract concept with personal examples and "
        "reflection.",
        ["what it means to", "personally, I feel that"], 5,
    ),
    Lesson(
        "C1-04", "C1", "A hypothetical scenario",
        "Can reason through a hypothetical using appropriate conditional "
        "structures.",
        ["if I were", "I would probably", "it depends on"], 5,
    ),
    Lesson(
        "C1-05", "C1", "Critiquing an idea or argument in detail",
        "Can identify a weakness in an argument and articulate why.",
        ["the flaw in that is", "it assumes that", "however"], 5,
    ),
    Lesson(
        "C1-06", "C1", "Negotiating or persuading in a professional context",
        "Can construct a persuasive case with a claim, reasons, and an "
        "example.",
        ["I'd argue that", "for example", "which is why"], 5,
    ),
    # --- C2: Mastery --------------------------------------------------
    Lesson(
        "C2-01", "C2", "Debating a controversial topic with nuance",
        "Can debate fluently, using idiomatic expressions appropriately.",
        ["at the end of the day", "let's face it", "to play devil's advocate"], 5,
    ),
    Lesson(
        "C2-02", "C2", "Explaining a specialized topic to a non-expert",
        "Can simplify complex information for a lay audience clearly.",
        ["put simply", "in other words", "the key takeaway is"], 5,
    ),
    Lesson(
        "C2-03", "C2", "Telling a richly detailed story",
        "Can narrate with vivid detail and an appropriate stylistic "
        "register.",
        ["as it turned out", "little did I know", "vividly"], 5,
    ),
    Lesson(
        "C2-04", "C2", "Analyzing subtle differences in meaning or tone",
        "Can distinguish and explain nuanced differences between similar "
        "expressions.",
        ["subtly different", "connotes", "as opposed to"], 5,
    ),
    Lesson(
        "C2-05", "C2", "A persuasive argument on an abstract issue",
        "Can build a sophisticated, well-structured argument with a clear "
        "conclusion.",
        ["it follows that", "ultimately", "the crux of the matter"], 5,
    ),
    Lesson(
        "C2-06", "C2", "Reflecting on language, identity, and communication",
        "Can reflect fluently on language/communication topics with "
        "precision and ease.",
        ["what strikes me is", "it's worth noting", "in a sense"], 5,
    ),
]

LESSONS_BY_ID: dict[str, Lesson] = {lesson.id: lesson for lesson in LESSONS}
FIRST_LESSON_ID: str = LESSONS[0].id


def get_lesson(lesson_id: str) -> Lesson:
    return LESSONS_BY_ID.get(lesson_id, LESSONS[0])


def next_lesson_id(lesson_id: str) -> str:
    """Proximo id na trilha. Se ja for a ultima aula (fim do curriculo),
    permanece nela - o aluno continua conversando naquele nivel/topico."""
    ids = [lesson.id for lesson in LESSONS]
    try:
        idx = ids.index(lesson_id)
    except ValueError:
        return FIRST_LESSON_ID
    if idx + 1 < len(ids):
        return ids[idx + 1]
    return lesson_id
