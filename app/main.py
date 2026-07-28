"""Tutor de ingles local (Emily): liga microfone -> VAD -> STT -> LLM (Ollama) -> TTS -> UI sci-fi HUD."""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from pathlib import Path

import yaml

from app import curriculum
from app.audio_io import AudioIO, AmplitudeMonitor
from app.memory import Memory
from app.stt import SpeechToText
from app.tts import TextToSpeech
from app.tutor import Tutor
from app.ui import TutorBridge, run_ui

ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "data" / "tutor.log", encoding="utf-8")],
)
log = logging.getLogger("tutor")


def load_config() -> dict:
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _process_turn(
    cfg: dict,
    memory: Memory,
    stt: SpeechToText,
    tts: TextToSpeech,
    tutor: Tutor,
    audio_io: AudioIO,
    bridge: TutorBridge,
    stop_event: threading.Event,
    session_id: int,
    history: list[dict],
) -> None:
    window_turns = cfg["memory"]["history_window_turns"]

    audio = audio_io.listen_for_utterance(stop_event)
    if stop_event.is_set() or audio.size == 0:
        return

    user_text = stt.transcribe(audio)
    if not user_text:
        return

    bridge.error_changed.emit("")
    bridge.user_text_changed.emit(user_text)

    profile = memory.build_profile()
    turn = tutor.respond(profile.as_prompt_block(), history, user_text)

    bridge.reply_text_changed.emit(turn.reply)
    if turn.corrections:
        lines = [
            f"{c.get('wrong', '')} -> {c.get('right', '')}: {c.get('explanation', '')}"
            for c in turn.corrections
        ]
        bridge.correction_added.emit(" | ".join(lines))
    else:
        bridge.correction_added.emit("")

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": turn.reply})
    history[:] = history[-window_turns * 2 :]

    memory.record_turn(session_id, user_text, turn.reply)
    memory.record_corrections(session_id, turn.corrections)
    memory.record_vocabulary(session_id, turn.new_vocab)

    audio_out = tts.synthesize(turn.reply)
    audio_io.play(audio_out, tts.sample_rate)


def _open_session(
    cfg: dict,
    memory: Memory,
    tts: TextToSpeech,
    tutor: Tutor,
    audio_io: AudioIO,
    bridge: TutorBridge,
    session_id: int,
    history: list[dict],
    is_first_session: bool,
) -> None:
    """Emily fala primeiro: se apresenta (1a vez) ou puxa assunto (demais vezes),
    em vez de ficar esperando calada o usuario iniciar a conversa."""
    window_turns = cfg["memory"]["history_window_turns"]
    profile = memory.build_profile()
    last_topic = memory.get_setting("last_topic")
    topic = curriculum.pick_topic(profile.cefr_level, avoid=last_topic)

    turn = tutor.open_session(
        profile.as_prompt_block(), history, is_first_session, level=profile.cefr_level, topic=topic
    )

    bridge.reply_text_changed.emit(turn.reply)
    bridge.correction_added.emit("")

    history.append({"role": "assistant", "content": turn.reply})
    history[:] = history[-window_turns * 2 :]

    memory.record_turn(session_id, "", turn.reply)
    memory.record_vocabulary(session_id, turn.new_vocab)
    if not is_first_session:
        memory.set_setting("last_topic", topic)

    audio_out = tts.synthesize(turn.reply)
    audio_io.play(audio_out, tts.sample_rate)


def conversation_loop(
    cfg: dict,
    memory: Memory,
    stt: SpeechToText,
    tts: TextToSpeech,
    tutor: Tutor,
    audio_io: AudioIO,
    bridge: TutorBridge,
    stop_event: threading.Event,
) -> None:
    """Loop principal com auto-recuperacao: um erro num turno nao mata a sessao inteira."""
    session_id = memory.start_session()
    history = memory.load_recent_history(cfg["memory"]["history_window_turns"])
    is_first_session = memory.build_profile().sessions_count <= 1

    try:
        try:
            _open_session(cfg, memory, tts, tutor, audio_io, bridge, session_id, history, is_first_session)
        except Exception:
            log.exception("Greeting failed, continuing straight to listening")
            audio_io.amp.set_state("idle")

        while not stop_event.is_set():
            try:
                _process_turn(cfg, memory, stt, tts, tutor, audio_io, bridge, stop_event, session_id, history)
            except Exception:
                log.exception("Turn failed, recovering")
                bridge.error_changed.emit("Something went wrong on that turn - try speaking again.")
                audio_io.amp.set_state("error")
                time.sleep(1.5)
                audio_io.amp.set_state("idle")
    finally:
        memory.end_session(session_id)


def supervised_conversation_loop(
    cfg: dict,
    memory: Memory,
    stt: SpeechToText,
    tts: TextToSpeech,
    tutor: Tutor,
    audio_io: AudioIO,
    bridge: TutorBridge,
    stop_event: threading.Event,
) -> None:
    """Se o loop inteiro cair por algum motivo inesperado, reinicia em vez de deixar a UI muda."""
    while not stop_event.is_set():
        try:
            conversation_loop(cfg, memory, stt, tts, tutor, audio_io, bridge, stop_event)
        except Exception:
            log.exception("conversation_loop crashed, restarting in 2s")
            bridge.error_changed.emit("Tutor restarted after an internal error.")
            audio_io.amp.set_state("error")
            time.sleep(2)


def _fix_windows_taskbar_icon() -> None:
    """Sem isso, o Windows agrupa a janela sob o icone do python.exe na barra
    de tarefas em vez do icone da Emily."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("emily.english.tutor")
    except Exception:
        pass


def main() -> None:
    _fix_windows_taskbar_icon()
    cfg = load_config()

    amp_monitor = AmplitudeMonitor()
    audio_io = AudioIO(
        sample_rate=cfg["vad"]["sample_rate"],
        vad_threshold=cfg["vad"]["threshold"],
        min_silence_ms=cfg["vad"]["min_silence_ms"],
        min_speech_ms=cfg["vad"]["min_speech_ms"],
        min_utterance_rms=cfg["vad"]["min_utterance_rms"],
        input_device=cfg["audio"]["input_device"],
        output_device=cfg["audio"]["output_device"],
        amplitude_monitor=amp_monitor,
    )
    stt = SpeechToText(
        model_size=cfg["stt"]["model_size"],
        device=cfg["stt"]["device"],
        compute_type=cfg["stt"]["compute_type"],
    )
    tts = TextToSpeech(
        piper_exe=str(ROOT / cfg["tts"]["piper_exe"]),
        model_path=str(ROOT / cfg["tts"]["voice_path"]),
        config_path=str(ROOT / cfg["tts"]["config_path"]),
    )
    tutor = Tutor(
        host=cfg["ollama"]["host"],
        model=cfg["ollama"]["model"],
        tutor_name=cfg["tutor"]["name"],
        temperature=cfg["ollama"]["temperature"],
    )
    memory = Memory(ROOT / cfg["memory"]["db_path"])
    bridge = TutorBridge()

    stop_event = threading.Event()
    worker = threading.Thread(
        target=supervised_conversation_loop,
        args=(cfg, memory, stt, tts, tutor, audio_io, bridge, stop_event),
        daemon=True,
    )
    worker.start()

    try:
        run_ui(amp_monitor, bridge, cfg["ui"]["window_title"])
    finally:
        stop_event.set()
        worker.join(timeout=5)
        tts.close()
        memory.close()


if __name__ == "__main__":
    main()
