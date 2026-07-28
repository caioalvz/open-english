"""Speech-to-text local via faster-whisper (CUDA)."""
from __future__ import annotations

import os

# Evita que o huggingface_hub tente checar atualizacoes do modelo pela rede a cada
# inicializacao - depois do download feito no setup, o app deve ficar 100% offline.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
from faster_whisper import WhisperModel


class SpeechToText:
    def __init__(self, model_size: str = "small.en", device: str = "cuda", compute_type: str = "int8_float16"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        """audio: mono float32 numpy array at 16kHz, range [-1, 1]."""
        if audio.size == 0:
            return ""
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
