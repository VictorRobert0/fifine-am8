"""
fifine_config — salva/recupera as preferências do usuário em config.json.

Lembra o último preset, o ganho digital, estado da supressão/gate e a saída
escolhida, para que o app reabra do jeito que você deixou.
"""
from __future__ import annotations

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

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
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            data.update({k: saved[k] for k in DEFAULTS if k in saved})
    except Exception:
        pass
    return data


def save(data: dict) -> bool:
    try:
        out = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
