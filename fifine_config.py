"""
fifine_config — salva/recupera as preferências do usuário em config.json.

Lembra o último preset, o ganho digital, estado da supressão/gate e a saída
escolhida, para que o app reabra do jeito que você deixou.

As preferências ficam em %APPDATA%\\Fifine AM8 Control\\config.json — uma pasta
gravável pelo usuário. (Versões antigas tentavam salvar junto do executável, em
Program Files, onde não há permissão de escrita; por isso nada era lembrado.)
"""
from __future__ import annotations

import json
import os

import fifine_version as ver


def data_dir() -> str:
    """Pasta gravável de dados do app (%APPDATA%\\Fifine AM8 Control)."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, ver.APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.dirname(os.path.abspath(__file__))
    return d


CONFIG_PATH = os.path.join(data_dir(), "config.json")
# Caminho antigo (ao lado do módulo) — migrado uma vez, se existir.
_LEGACY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "preset": None,
    "gain_db": 0.0,
    "nr_enabled": True,
    "nr_amount": 1.0,
    "gate_enabled": True,
    "gate_threshold": 0.45,
    "hpf_enabled": True,
    "limiter_enabled": True,
    "output_name": "CABLE Input",
    "auto_check": True,     # verificar atualizações ao abrir
    "auto_update": False,   # baixar e instalar automaticamente quando houver
    "theme": "Violeta Noturno",   # paleta de cores do skin
    "minimize_to_tray": True,     # fechar/minimizar envia para a bandeja
}


def _read(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        return saved if isinstance(saved, dict) else None
    except Exception:
        return None


def load() -> dict:
    data = dict(DEFAULTS)
    saved = _read(CONFIG_PATH)
    if saved is None and CONFIG_PATH != _LEGACY_PATH:
        # migra preferências de uma instalação antiga, se houver
        saved = _read(_LEGACY_PATH)
    if saved:
        data.update({k: saved[k] for k in DEFAULTS if k in saved})
    return data


def save(data: dict) -> bool:
    try:
        out = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
