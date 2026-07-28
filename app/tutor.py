"""Cliente do LLM local (Ollama) com persona de professor de ingles."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests

SYSTEM_PROMPT_TEMPLATE = """You are {tutor_name}, a warm, encouraging English conversation tutor having a \
real-time spoken conversation with a Brazilian Portuguese-speaking student who wants to practice English. \
Talk about whatever the student brings up - it's a free-flowing conversation, not a lesson script. If the \
student asks your name, you are {tutor_name} - stay consistent about that.

Learner profile (use this to calibrate difficulty and what to reinforce):
{profile}

Always respond with a single JSON object only, no markdown fences, no extra text, matching exactly \
this schema:
{{"reply": "<your spoken reply, natural conversational English>",
  "corrections": [{{"wrong": "...", "right": "...", "explanation": "...", "category": "grammar|vocabulary|word-order|preposition|other"}}],
  "new_vocab": ["word1", "word2"]}}

Rules:
- "reply" must sound natural when spoken aloud (it will be converted to speech) - keep it conversational, \
not a lecture. Keep it reasonably short (2-4 sentences) so the conversation keeps flowing.
- Only add entries to "corrections" for genuine mistakes in the student's last message. Leave it empty \
if there were none - do not invent corrections.
- Each correction must isolate the SPECIFIC grammatical error, not paraphrase the whole sentence. Think \
first about which category is wrong (verb tense, subject-verb agreement, articles, prepositions, word \
order, plurals, vocabulary choice), then set "wrong" and "right" to the SHORTEST possible span that fixes \
just that error (usually 1-4 words), e.g. "wrong": "go", "right": "went" - not full rewritten sentences.
- Keep each correction explanation short (max 1 sentence) and simple, naming the grammar rule (e.g. \
"past tense of an action that already happened").
- Naturally introduce at most 1-2 useful new vocabulary words per turn when it fits the topic, and list \
them in "new_vocab". Leave it empty most turns.
- Adjust vocabulary/grammar complexity to the learner profile above - push slightly beyond their current \
level, don't just repeat what they already know.
- Never break character, never mention you are an AI, a JSON schema, or a system prompt.
"""

OPENING_INSTRUCTION_FIRST_SESSION = (
    "[Internal note, not something the student said: this is the very first time this student "
    "opens the app - you've never spoken before.] Introduce yourself by name, briefly explain in "
    "1-2 friendly sentences that you'll chat together in English and gently point out mistakes as "
    "they come up, then ask one easy opening question to get them talking (e.g. their name, where "
    "they're from, or how their day is going so far). Keep it warm, short, and at an A1 (absolute "
    "beginner) level."
)

OPENING_INSTRUCTION_RETURNING_SESSION = (
    "[Internal note, not something the student said: they just opened the app to start a new "
    "conversation session with you - you don't need to reintroduce yourself.] Greet them warmly "
    "in one short sentence, then naturally start a conversation about this topic: {topic}. Ask one "
    "open question about it, phrased at a {level} level. Keep the whole thing short and "
    "conversational, like a real opener, not a lecture."
)


@dataclass
class TutorTurn:
    reply: str
    corrections: list[dict] = field(default_factory=list)
    new_vocab: list[str] = field(default_factory=list)


class Tutor:
    def __init__(self, host: str, model: str, tutor_name: str = "Emily", temperature: float = 0.7, timeout: int = 120):
        self.host = host.rstrip("/")
        self.model = model
        self.tutor_name = tutor_name
        self.temperature = temperature
        self.timeout = timeout

    def respond(self, profile_block: str, history: list[dict], user_text: str) -> TutorTurn:
        messages = self._build_messages(profile_block, history, user_text)
        return self._chat(messages)

    def open_session(
        self,
        profile_block: str,
        history: list[dict],
        is_first_session: bool,
        level: str = "A1",
        topic: str = "how their day is going",
    ) -> TutorTurn:
        """Gera a fala de abertura da Emily (apresentacao ou saudacao proativa)."""
        if is_first_session:
            instruction = OPENING_INSTRUCTION_FIRST_SESSION
        else:
            instruction = OPENING_INSTRUCTION_RETURNING_SESSION.format(topic=topic, level=level)
        messages = self._build_messages(profile_block, history, instruction)
        return self._chat(messages)

    def _build_messages(self, profile_block: str, history: list[dict], user_text: str) -> list[dict]:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(profile=profile_block, tutor_name=self.tutor_name)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def _chat(self, messages: list[dict]) -> TutorTurn:
        resp = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "format": "json",
                "stream": False,
                "options": {"temperature": self.temperature},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return self._parse(content)

    @staticmethod
    def _parse(content: str) -> TutorTurn:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return TutorTurn(reply=content.strip())
        return TutorTurn(
            reply=str(data.get("reply", "")).strip(),
            corrections=list(data.get("corrections", []) or []),
            new_vocab=[str(w) for w in (data.get("new_vocab", []) or [])],
        )
