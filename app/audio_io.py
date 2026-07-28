"""Captura de microfone com VAD (Silero) para detectar turnos de fala,
e playback de audio sintetizado. Expoe niveis de amplitude para a UI."""
from __future__ import annotations

import queue
import threading

import numpy as np
import sounddevice as sd
import torch
from silero_vad import load_silero_vad


class AmplitudeMonitor:
    """Objeto thread-safe compartilhado entre audio e UI para animar a waveform."""

    def __init__(self):
        self._lock = threading.Lock()
        self._level = 0.0
        self._state = "idle"  # idle | listening | thinking | speaking

    def set_level(self, level: float) -> None:
        with self._lock:
            self._level = level

    def get_level(self) -> float:
        with self._lock:
            return self._level

    def set_state(self, state: str) -> None:
        with self._lock:
            self._state = state

    def get_state(self) -> str:
        with self._lock:
            return self._state


class AudioIO:
    FRAME_SIZE = 512  # amostras por frame de VAD a 16kHz (~32ms)

    def __init__(
        self,
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        min_silence_ms: int = 700,
        min_speech_ms: int = 250,
        min_utterance_rms: float = 0.008,
        input_device=None,
        output_device=None,
        amplitude_monitor: AmplitudeMonitor | None = None,
    ):
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self.min_silence_frames = max(1, int(min_silence_ms / 1000 * sample_rate / self.FRAME_SIZE))
        self.min_speech_frames = max(1, int(min_speech_ms / 1000 * sample_rate / self.FRAME_SIZE))
        self.min_utterance_rms = min_utterance_rms
        self.input_device = input_device
        self.output_device = output_device
        self.amp = amplitude_monitor or AmplitudeMonitor()
        self.vad_model = load_silero_vad()

    def listen_for_utterance(self, stop_event: threading.Event | None = None) -> np.ndarray:
        """Bloqueia ate detectar um turno de fala completo (fala cercada de silencio)."""
        q: "queue.Queue[np.ndarray]" = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(indata[:, 0].copy())

        speech_frames: list[np.ndarray] = []
        pre_roll: list[np.ndarray] = []
        in_speech = False
        silence_run = 0
        speech_run = 0

        self.amp.set_state("listening")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.FRAME_SIZE,
            device=self.input_device,
            callback=callback,
        ):
            while True:
                if stop_event is not None and stop_event.is_set():
                    return np.zeros(0, dtype=np.float32)
                frame = q.get()
                self.amp.set_level(float(np.sqrt(np.mean(frame**2))))

                prob = self.vad_model(torch.from_numpy(frame), self.sample_rate).item()

                if prob >= self.vad_threshold:
                    speech_run += 1
                    silence_run = 0
                    if not in_speech and speech_run >= self.min_speech_frames:
                        in_speech = True
                        speech_frames.extend(pre_roll)
                    if in_speech:
                        speech_frames.append(frame)
                    else:
                        pre_roll.append(frame)
                        pre_roll = pre_roll[-5:]
                else:
                    speech_run = 0
                    if in_speech:
                        silence_run += 1
                        speech_frames.append(frame)
                        if silence_run >= self.min_silence_frames:
                            break
                    else:
                        pre_roll.append(frame)
                        pre_roll = pre_roll[-5:]

        self.vad_model.reset_states()
        self.amp.set_state("thinking")
        if not speech_frames:
            return np.zeros(0, dtype=np.float32)

        utterance = np.concatenate(speech_frames)
        rms = float(np.sqrt(np.mean(utterance**2)))
        if rms < self.min_utterance_rms:
            # provavelmente ruido de fundo que passou o VAD por engano; descarta para nao
            # alimentar o whisper com audio fraco demais (fonte comum de alucinacao de texto).
            self.amp.set_state("idle")
            return np.zeros(0, dtype=np.float32)
        return utterance

    def play(self, audio: np.ndarray, sample_rate: int) -> None:
        if audio.size == 0:
            return
        self.amp.set_state("speaking")
        chunk = 512
        sd.play(audio, samplerate=sample_rate, device=self.output_device, blocking=False)
        idx = 0
        while idx < len(audio):
            block = audio[idx : idx + chunk]
            self.amp.set_level(float(np.sqrt(np.mean(block**2))) if len(block) else 0.0)
            sd.sleep(int(1000 * chunk / sample_rate))
            idx += chunk
        sd.wait()
        self.amp.set_level(0.0)
        self.amp.set_state("idle")
