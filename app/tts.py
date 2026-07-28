"""Text-to-speech local via o binario standalone do Piper (voz feminina en_US).

Mantem um processo piper.exe vivo (modo --json-input) em vez de spawnar um processo
novo por frase - evita pagar o custo de carregar o modelo ONNX a cada resposta,
o que reduzia bastante a latencia entre a resposta do tutor e o audio tocado.

Usa o binario standalone (nao o pacote pip piper-tts) porque a dependencia
piper-phonemize nao publica wheel para Windows/Python 3.12+.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np


class TextToSpeech:
    def __init__(self, piper_exe: str, model_path: str, config_path: str | None = None, timeout_s: float = 20.0):
        self.piper_exe = piper_exe
        self.model_path = model_path
        self.config_path = config_path or f"{model_path}.json"
        self.timeout_s = timeout_s

        with open(self.config_path, "r", encoding="utf-8") as f:
            voice_config = json.load(f)
        self.sample_rate = voice_config["audio"]["sample_rate"]

        self._out_dir = tempfile.mkdtemp(prefix="piper_out_")
        self._lock = threading.Lock()
        self._counter = 0
        self._proc = self._spawn()

    def _spawn(self) -> subprocess.Popen:
        return subprocess.Popen(
            [
                self.piper_exe,
                "-m", self.model_path,
                "-c", self.config_path,
                "--json-input",
                "-q",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def synthesize(self, text: str) -> np.ndarray:
        """Retorna audio mono float32 em [-1, 1] na sample_rate da voz."""
        if not text.strip():
            return np.zeros(0, dtype=np.float32)

        with self._lock:
            if self._proc.poll() is not None:
                # processo morreu (ex: crash) - reinicia antes de tentar de novo
                self._proc = self._spawn()

            self._counter += 1
            out_path = os.path.join(self._out_dir, f"utt_{self._counter}.wav")
            # usar caminho absoluto aqui: o piper grava "output_file" relativo ao cwd do
            # processo, ignorando o "-d" quando o JSON ja traz um output_file.
            request = json.dumps({"text": text, "output_file": out_path}) + "\n"

            self._proc.stdin.write(request.encode("utf-8"))
            self._proc.stdin.flush()

            deadline = time.time() + self.timeout_s
            while not os.path.exists(out_path) and time.time() < deadline:
                time.sleep(0.02)
            if not os.path.exists(out_path):
                raise RuntimeError("Piper TTS timed out waiting for synthesized audio")

            # espera o tamanho do arquivo estabilizar (piper ainda pode estar escrevendo)
            last_size = -1
            for _ in range(50):
                size = os.path.getsize(out_path)
                if size == last_size and size > 0:
                    break
                last_size = size
                time.sleep(0.02)

            with wave.open(out_path, "rb") as wf:
                pcm_bytes = wf.readframes(wf.getnframes())
            os.remove(out_path)

        return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    def close(self) -> None:
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            pass
