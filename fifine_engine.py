"""
fifine_engine — motor de processamento de áudio em tempo real para o Fifine.

Cadeia de sinal (microfone virtual):

    Fifine (captura)                                           App (Discord/OBS/…)
        │                                                            ▲
        ▼                                                            │
   [downmix mono] → [high-pass] → [RNNoise] → [mix seco/limpo] →     │
        → [noise gate por VAD] → [GANHO DIGITAL] → [limitador] → CABLE Input
                                                                     │
                                            apps escutam "CABLE Output" ──┘

Por que isto existe:
  O ganho de *hardware* do Fifine satura em +10 dB. Para ir ALÉM, o áudio é
  capturado, multiplicado digitalmente (com limitador para não estourar) e
  reenviado a um dispositivo virtual (VB-Audio Cable), que os programas usam
  como microfone. A supressão de ruído usa **RNNoise** — a mesma técnica do
  Discord — complementada por um *noise gate* guiado pela probabilidade de voz
  (VAD) que o próprio RNNoise calcula.

Requer: sounddevice, numpy, pyrnnoise (RNNoise). Um cabo de áudio virtual
(VB-Audio Virtual Cable / Voicemeeter) para o roteamento.
"""
from __future__ import annotations

import threading
from collections import deque

import numpy as np
import sounddevice as sd

try:
    from pyrnnoise import RNNoise
    _HAS_RNNOISE = True
except Exception:  # pragma: no cover
    _HAS_RNNOISE = False

SR = 48000            # RNNoise exige 48 kHz
FRAME = 480           # 10 ms por frame (tamanho nativo do RNNoise)
MAX_BUFFER = 12       # frames máximos no buffer de saída (~120 ms) antes de descartar
PREFILL = 3           # frames acumulados antes de começar a tocar (jitter buffer)


# Presets prontos: parâmetros do motor + recomendação de uso.
# Campos: gain_db, nr_enabled, nr_amount, gate_enabled, gate_threshold,
#         hpf_enabled, limiter_enabled, hw_tip (dica de ganho de hardware), desc.
PRESETS = {
    "Limpo": dict(
        gain_db=0, nr_enabled=False, nr_amount=1.0,
        gate_enabled=False, gate_threshold=0.45,
        hpf_enabled=False, limiter_enabled=True, hw_tip=85,
        desc="Passagem natural, sem artefatos. Use em sala silenciosa e quando "
             "qualidade de áudio importa mais que silenciar o fundo."),
    "Gravacao": dict(
        gain_db=3, nr_enabled=True, nr_amount=0.5,
        gate_enabled=False, gate_threshold=0.45,
        hpf_enabled=True, limiter_enabled=True, hw_tip=85,
        desc="Podcast / narração em casa. Reduz ruído leve sem cortar respiração "
             "e nuances; sem gate para não engolir o fim das palavras."),
    "Stream": dict(
        gain_db=10, nr_enabled=True, nr_amount=1.0,
        gate_enabled=True, gate_threshold=0.40,
        hpf_enabled=True, limiter_enabled=True, hw_tip=85,
        desc="Lives e jogos. Mata teclado, mouse e ventilador; volume firme e "
             "limitado para não estourar nos picos de empolgação."),
    "Reuniao": dict(
        gain_db=12, nr_enabled=True, nr_amount=1.0,
        gate_enabled=True, gate_threshold=0.60,
        hpf_enabled=True, limiter_enabled=True, hw_tip=90,
        desc="Chamadas de voz/vídeo (Discord, Meet, Teams). Voz clara e silêncio "
             "total no fundo; gate mais fechado corta qualquer ruído entre falas."),
    "Voz distante": dict(
        gain_db=24, nr_enabled=True, nr_amount=1.0,
        gate_enabled=True, gate_threshold=0.35,
        hpf_enabled=True, limiter_enabled=True, hw_tip=100,
        desc="Mic longe da boca ou voz baixa. Empurra o volume bem acima do "
             "hardware; o limitador segura os picos e o gate evita amplificar o "
             "ruído da sala quando você está calado."),
}


def list_io_devices():
    """Lista (index, nome, host) de entradas e saídas, separadas."""
    ins, outs = [], []
    for i, d in enumerate(sd.query_devices()):
        host = sd.query_hostapis(d["hostapi"])["name"]
        if d["max_input_channels"] > 0:
            ins.append((i, d["name"], host, d["max_input_channels"]))
        if d["max_output_channels"] > 0:
            outs.append((i, d["name"], host, d["max_output_channels"]))
    return ins, outs


def find_device(name_part, kind="input", host_prefer=("MME", "Windows WASAPI", "Windows DirectSound")):
    """Primeiro device cujo nome contém `name_part`, preferindo certas host APIs."""
    cands = []
    for i, d in enumerate(sd.query_devices()):
        host = sd.query_hostapis(d["hostapi"])["name"]
        ch = d["max_input_channels"] if kind == "input" else d["max_output_channels"]
        if ch > 0 and name_part.lower() in d["name"].lower():
            cands.append((i, host))
    for pref in host_prefer:
        for i, host in cands:
            if host == pref:
                return i
    return cands[0][0] if cands else None


def _one_pole_highpass(x, state, cutoff=90.0, sr=SR):
    """High-pass de 1 polo para cortar rumble/DC. Retorna (y, novo_state)."""
    rc = 1.0 / (2 * np.pi * cutoff)
    alpha = rc / (rc + 1.0 / sr)
    y = np.empty_like(x)
    prev_x, prev_y = state
    for n in range(len(x)):
        y[n] = alpha * (prev_y + x[n] - prev_x)
        prev_x = x[n]
        prev_y = y[n]
    return y, (prev_x, prev_y)


class AudioEngine:
    """Motor de processamento em thread de áudio. Parâmetros são ajustáveis ao vivo."""

    def __init__(self, input_name="fifine", output_name="CABLE Input"):
        self.input_name = input_name
        self.output_name = output_name

        # --- parâmetros ao vivo (thread-safe por serem atribuições atômicas) ---
        self.gain_db = 0.0            # ganho DIGITAL extra, pode passar de +10 dB
        self.nr_enabled = True        # supressão de ruído RNNoise
        self.nr_amount = 1.0          # mistura limpo/seco (0..1)
        self.gate_enabled = True      # noise gate por VAD (silêncio entre falas)
        self.gate_threshold = 0.45    # prob. de voz mínima p/ abrir o gate
        self.gate_floor_db = -30.0    # atenuação quando fechado
        self.hpf_enabled = True       # high-pass anti-rumble
        self.limiter_enabled = True   # limitador soft (anti-clip)

        # --- medidores (lidos pela GUI) ---
        self.in_peak = 0.0
        self.out_peak = 0.0
        self.vad = 0.0
        self.xruns = 0
        self.running = False
        self.last_error = None

        # --- estado interno ---
        self._denoiser = RNNoise(SR) if _HAS_RNNOISE else None
        self._outbuf = deque()
        self._lock = threading.Lock()
        self._prefilled = False
        self._gate_env = 1.0
        self._hpf_state = (0.0, 0.0)
        self._in_stream = None
        self._out_stream = None
        self._in_dev = None
        self._out_dev = None

    # ------------------------------------------------------------------ params
    @property
    def gain(self):
        return 10.0 ** (self.gain_db / 20.0)

    @property
    def has_rnnoise(self):
        return _HAS_RNNOISE

    def apply_preset(self, name):
        """Aplica um preset de PRESETS aos parâmetros do motor (ao vivo)."""
        p = PRESETS.get(name)
        if not p:
            raise KeyError(f"Preset desconhecido: {name}")
        self.gain_db = p["gain_db"]
        self.nr_enabled = p["nr_enabled"]
        self.nr_amount = p["nr_amount"]
        self.gate_enabled = p["gate_enabled"]
        self.gate_threshold = p["gate_threshold"]
        self.hpf_enabled = p["hpf_enabled"]
        self.limiter_enabled = p["limiter_enabled"]
        return p

    # ------------------------------------------------------------------ áudio
    def _process_frame(self, mono_f32):
        """Processa um frame mono float32 (-1..1) de 480 amostras e devolve mono float32."""
        x = mono_f32
        self.in_peak = float(np.max(np.abs(x))) if x.size else 0.0

        if self.hpf_enabled:
            x, self._hpf_state = _one_pole_highpass(x, self._hpf_state)

        vad = self.vad
        if (self.nr_enabled or self.gate_enabled) and self._denoiser is not None:
            i16 = np.clip(x * 32767.0, -32768, 32767).astype(np.int16)
            try:
                prob, frame = next(self._denoiser.denoise_chunk(i16))
                vad = float(np.asarray(prob).ravel()[0])
                wet = np.asarray(frame).ravel().astype(np.float32) / 32767.0
                if self.nr_enabled:
                    a = float(self.nr_amount)
                    x = a * wet + (1.0 - a) * x
            except Exception:
                pass
        self.vad = vad

        # noise gate suavizado (attack rápido, release lento) guiado pelo VAD
        if self.gate_enabled:
            open_gate = vad >= self.gate_threshold
            target = 1.0 if open_gate else 10.0 ** (self.gate_floor_db / 20.0)
            coeff = 0.6 if target > self._gate_env else 0.05  # abre rápido, fecha devagar
            self._gate_env += (target - self._gate_env) * coeff
            x = x * self._gate_env

        # GANHO DIGITAL (além do hardware)
        x = x * self.gain

        # limitador soft (tanh) para evitar clipping duro quando o ganho é alto
        if self.limiter_enabled:
            x = np.tanh(x)
        else:
            x = np.clip(x, -1.0, 1.0)

        self.out_peak = float(np.max(np.abs(x))) if x.size else 0.0
        return x.astype(np.float32)

    def _in_callback(self, indata, frames, time_info, status):
        if status:
            self.xruns += 1
        mono = indata.mean(axis=1).astype(np.float32) if indata.ndim > 1 else indata.astype(np.float32)
        out = self._process_frame(mono)
        with self._lock:
            self._outbuf.append(out)
            while len(self._outbuf) > MAX_BUFFER:
                self._outbuf.popleft()  # descarta p/ não acumular latência (drift)

    def _out_callback(self, outdata, frames, time_info, status):
        if status:
            self.xruns += 1
        with self._lock:
            n = len(self._outbuf)
            if not self._prefilled:
                if n < PREFILL:
                    outdata.fill(0)
                    return
                self._prefilled = True
            frame = self._outbuf.popleft() if self._outbuf else None
        if frame is None:
            outdata.fill(0)  # underflow: silêncio
            return
        ch = outdata.shape[1]
        outdata[:] = np.repeat(frame.reshape(-1, 1), ch, axis=1)

    # ------------------------------------------------------------------ ciclo
    def start(self):
        if self.running:
            return
        self._in_dev = find_device(self.input_name, "input")
        self._out_dev = find_device(self.output_name, "output")
        if self._in_dev is None:
            raise RuntimeError(f"Entrada '{self.input_name}' não encontrada")
        if self._out_dev is None:
            raise RuntimeError(f"Saída '{self.output_name}' não encontrada")
        self._outbuf.clear()
        self._prefilled = False
        self._gate_env = 1.0
        self.xruns = 0
        self.last_error = None
        in_ch = min(2, sd.query_devices(self._in_dev)["max_input_channels"])
        out_ch = min(2, sd.query_devices(self._out_dev)["max_output_channels"])
        self._out_stream = sd.OutputStream(
            device=self._out_dev, samplerate=SR, blocksize=FRAME,
            channels=out_ch, dtype="float32", callback=self._out_callback,
            latency="low",
        )
        self._in_stream = sd.InputStream(
            device=self._in_dev, samplerate=SR, blocksize=FRAME,
            channels=in_ch, dtype="float32", callback=self._in_callback,
            latency="low",
        )
        self._out_stream.start()
        self._in_stream.start()
        self.running = True

    def stop(self):
        self.running = False
        for s in (self._in_stream, self._out_stream):
            try:
                if s:
                    s.stop(); s.close()
            except Exception:
                pass
        self._in_stream = self._out_stream = None
        self.in_peak = self.out_peak = self.vad = 0.0

    def status(self):
        return {
            "running": self.running, "rnnoise": _HAS_RNNOISE,
            "in_dev": self._in_dev, "out_dev": self._out_dev,
            "gain_db": self.gain_db, "nr": self.nr_enabled,
            "gate": self.gate_enabled, "xruns": self.xruns,
            "in_peak": self.in_peak, "out_peak": self.out_peak, "vad": self.vad,
        }
