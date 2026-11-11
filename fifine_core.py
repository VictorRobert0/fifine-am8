"""
fifine_core — camada de controle do microfone Fifine via Windows Core Audio.

Como funciona (verificado por engenharia reversa do dispositivo):
  O Fifine (USB VID_3142 / PID_0A80) é um dispositivo USB composto que usa o
  driver genérico `usbaudio` do Windows (classe USB Audio). Ele NÃO tem protocolo
  proprietário nem app próprio. O "ganho" é um *Feature Unit* da especificação
  USB Audio Class, que o Windows expõe como o volume do endpoint de captura
  (IAudioEndpointVolume). O aparelho também expõe uma saída de fone para
  monitoramento (endpoint de renderização) e uma interface HID (MI_03) para os
  botões/knob físicos — esses botões *enviam* eventos ao PC e não são ajustáveis
  por software, por isso este módulo controla os dois endpoints de áudio.

Faixas reais medidas neste aparelho:
  - Microfone (ganho):   0,0 .. 10,0 dB  (passo ~0,06 dB)
  - Fone (monitor):    -20,0 .. -3,0 dB

Requer: Windows, pycaw, comtypes.
"""
from __future__ import annotations

import sys as _sys
# COM em modo MTA (multithreaded) antes de importar comtypes: chamadas COM mais
# estáveis entre threads (bandeja/medidores). Config mais estável observada.
_sys.coinit_flags = 0

import comtypes
from comtypes import CLSCTX_ALL, cast, POINTER, GUID, COMError
from pycaw.pycaw import IAudioEndpointVolume, IAudioMeterInformation
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY
from pycaw.constants import CLSID_MMDeviceEnumerator

# Direção do fluxo de dados (EDataFlow)
RENDER = 0    # saídas (fone / alto-falantes)
CAPTURE = 1   # entradas (microfones)
STATE_ACTIVE = 0x1

# PKEY_Device_FriendlyName — nome amigável do endpoint
_PKEY_FRIENDLY_NAME = PROPERTYKEY()
_PKEY_FRIENDLY_NAME.fmtid = GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}")
_PKEY_FRIENDLY_NAME.pid = 14


def _enumerator():
    return comtypes.CoCreateInstance(
        CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL
    )


class Endpoint:
    """Um endpoint de áudio controlável (microfone ou fone)."""

    def __init__(self, mmdevice):
        self._dev = mmdevice
        self.id = mmdevice.GetId()
        store = mmdevice.OpenPropertyStore(0)  # STGM_READ
        try:
            self.name = store.GetValue(comtypes.pointer(_PKEY_FRIENDLY_NAME)).GetValue()
        except Exception:
            self.name = "(desconhecido)"
        # QueryInterface (não cast): cast() compartilha o ponteiro COM e causa
        # double-release no GC (crash 0xC0000005 em comtypes __del__).
        self._vol = mmdevice.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        ).QueryInterface(IAudioEndpointVolume)
        self._meter = None  # ativado sob demanda

    # ---- auto-recuperação de COM ----
    # Alguns componentes (ex.: ícone de bandeja, reconexão do dispositivo) podem
    # invalidar os ponteiros COM. Se uma chamada falhar, re-resolvemos o endpoint
    # pelo ID e tentamos novamente uma vez.
    def _reactivate(self):
        enum = _enumerator()
        self._dev = enum.GetDevice(self.id)
        self._vol = self._dev.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        ).QueryInterface(IAudioEndpointVolume)
        self._meter = None

    def _guard(self, fn):
        try:
            return fn()
        except (OSError, COMError):
            self._reactivate()
            return fn()

    # ---- nível em porcentagem (0..100), igual ao slider do Windows ----
    def get_percent(self) -> float:
        return self._guard(lambda: self._vol.GetMasterVolumeLevelScalar() * 100.0)

    def set_percent(self, pct: float) -> None:
        p = max(0.0, min(100.0, float(pct)))
        self._guard(lambda: self._vol.SetMasterVolumeLevelScalar(p / 100.0, None))

    # ---- nível em dB (valor real de hardware) ----
    def get_db(self) -> float:
        return self._guard(lambda: self._vol.GetMasterVolumeLevel())

    def set_db(self, db: float) -> None:
        lo, hi, _ = self.db_range()
        d = max(lo, min(hi, float(db)))
        self._guard(lambda: self._vol.SetMasterVolumeLevel(d, None))

    def db_range(self):
        """(min_dB, max_dB, passo_dB)."""
        return self._guard(lambda: self._vol.GetVolumeRange())

    # ---- mute ----
    def get_mute(self) -> bool:
        return bool(self._guard(lambda: self._vol.GetMute()))

    def set_mute(self, muted: bool) -> None:
        self._guard(lambda: self._vol.SetMute(bool(muted), None))

    def toggle_mute(self) -> bool:
        new = not self.get_mute()
        self.set_mute(new)
        return new

    def channels(self) -> int:
        return self._guard(lambda: self._vol.GetChannelCount())

    # ---- medidor de pico em tempo real (0.0..1.0) para VU meter ----
    def peak(self) -> float:
        def _p():
            if self._meter is None:
                self._meter = self._dev.Activate(
                    IAudioMeterInformation._iid_, CLSCTX_ALL, None
                ).QueryInterface(IAudioMeterInformation)
            return self._meter.GetPeakValue()
        return self._guard(_p)

    def snapshot(self) -> dict:
        lo, hi, step = self.db_range()
        return {
            "name": self.name,
            "id": self.id,
            "percent": round(self.get_percent(), 1),
            "db": round(self.get_db(), 2),
            "db_min": round(lo, 2),
            "db_max": round(hi, 2),
            "db_step": round(step, 3),
            "mute": self.get_mute(),
            "channels": self.channels(),
        }


def _collect(flow, needle):
    enum = _enumerator()
    col = enum.EnumAudioEndpoints(flow, STATE_ACTIVE)
    found = []
    for i in range(col.GetCount()):
        ep = Endpoint(col.Item(i))
        if needle is None or (ep.name and needle.lower() in ep.name.lower()):
            found.append(ep)
    return found


def find_mic(needle: str = "fifine"):
    """Primeiro endpoint de CAPTURA cujo nome contém `needle`."""
    eps = _collect(CAPTURE, needle)
    return eps[0] if eps else None


def find_monitor(needle: str = "fifine"):
    """Primeiro endpoint de RENDER (fone) cujo nome contém `needle`."""
    eps = _collect(RENDER, needle)
    return eps[0] if eps else None


def list_all():
    """Todos os endpoints ativos, separados por fluxo."""
    return {"capture": _collect(CAPTURE, None), "render": _collect(RENDER, None)}


# ---- definir dispositivo padrão (best-effort via IPolicyConfig, não-documentado) ----
def set_default_device(endpoint_id: str, role: int = 0) -> bool:
    """Define o endpoint como padrão. role: 0=console, 1=multimedia, 2=communications.
    Retorna True se bem-sucedido. Usa a interface interna IPolicyConfig."""
    try:
        import ctypes
        from ctypes import HRESULT, c_int
        from ctypes.wintypes import LPCWSTR
        from comtypes import COMMETHOD, IUnknown

        CLSID_PolicyConfigClient = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")
        IID_IPolicyConfig = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")

        class IPolicyConfig(IUnknown):
            _iid_ = IID_IPolicyConfig
            _methods_ = [
                COMMETHOD([], HRESULT, "GetMixFormat"),
                COMMETHOD([], HRESULT, "GetDeviceFormat"),
                COMMETHOD([], HRESULT, "ResetDeviceFormat"),
                COMMETHOD([], HRESULT, "SetDeviceFormat"),
                COMMETHOD([], HRESULT, "GetProcessingPeriod"),
                COMMETHOD([], HRESULT, "SetProcessingPeriod"),
                COMMETHOD([], HRESULT, "GetShareMode"),
                COMMETHOD([], HRESULT, "SetShareMode"),
                COMMETHOD([], HRESULT, "GetPropertyValue"),
                COMMETHOD([], HRESULT, "SetPropertyValue"),
                COMMETHOD([], HRESULT, "SetDefaultEndpoint",
                          (["in"], LPCWSTR, "wszDeviceId"),
                          (["in"], c_int, "role")),
                COMMETHOD([], HRESULT, "SetEndpointVisibility"),
            ]

        pc = comtypes.CoCreateInstance(
            CLSID_PolicyConfigClient, IPolicyConfig, CLSCTX_ALL
        )
        pc.SetDefaultEndpoint(endpoint_id, role)
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[set_default_device] falhou: {exc}")
        return False
