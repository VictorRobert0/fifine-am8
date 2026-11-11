"""
fifine_hid — leitura do hardware do Fifine pela interface HID (MI_03).

O AM8 (e outros Fifine com VID 3142) expõem uma interface HID com:
  - Coleção CONSUMER (page 0x0C): Mute, Volume+/-, Play/Stop, usages vendor
  - Coleção TELEPHONY (page 0x0B): Hook Switch (estado de mute por toque)
  - Um OUTPUT report vendor (page 0x7FF, 16 bytes) — canal proprietário gravável
    cujo protocolo NÃO é documentado (não usado aqui por segurança).

ATENÇÃO: nos testes deste projeto, o botão de mute por toque do AM8 não emitiu
relatórios HID nem alterou o estado de áudio no Core Audio — indício de que o
mute é tratado *internamente* no mic. Rode este monitor e pressione o botão para
confirmar no SEU aparelho: se aparecer alguma linha, o botão fala com o PC e dá
para reagir a ele; se não aparecer nada, o mute é local (apenas firmware).

Uso:  python fifine_hid.py          # monitor ao vivo (Ctrl+C para sair)
"""
from __future__ import annotations

import time

try:
    import pywinusb.hid as hid
    _HAS_HID = True
except Exception:
    _HAS_HID = False

VID, PID = 0x3142, 0x0A80

# Nomes amigáveis de alguns usages da página Consumer (0x0C)
_CONSUMER_NAMES = {
    0xB5: "Próxima faixa", 0xB6: "Faixa anterior", 0xB7: "Stop",
    0xCD: "Play/Pause", 0xE2: "Mute", 0xE9: "Volume +", 0xEA: "Volume -",
}


def find_collections():
    if not _HAS_HID:
        return []
    return hid.HidDeviceFilter(vendor_id=VID, product_id=PID).get_devices()


class HidListener:
    """Ouve as coleções HID do Fifine e chama callbacks com eventos decodificados.

    callback(evento: dict) onde evento tem {'tipo', 'tag', 'raw', ...}.
    """

    def __init__(self, on_event=None):
        self.on_event = on_event
        self._open = []
        self.running = False

    def _handler(self, tag, page):
        def h(data):
            ev = {"tipo": "hid", "tag": tag, "page": page, "raw": list(data),
                  "t": time.time()}
            # decodificação leve
            if page == 0x0C:
                pressed = [n for b, n in _CONSUMER_NAMES.items() if b in data[1:]]
                ev["botoes"] = pressed
            elif page == 0x0B:
                ev["hook_switch"] = bool(data[1] & 0x01) if len(data) > 1 else None
            if self.on_event:
                self.on_event(ev)
        return h

    def start(self):
        if self.running:
            return 0
        self._open = []
        for d in find_collections():
            try:
                d.open()
                page = d.hid_caps.usage_page
                tag = {0x0C: "CONSUMER", 0x0B: "TELEPHONY"}.get(page, hex(page))
                d.set_raw_data_handler(self._handler(tag, page))
                self._open.append(d)
            except Exception:
                pass
        self.running = len(self._open) > 0
        return len(self._open)

    def stop(self):
        for d in self._open:
            try:
                d.close()
            except Exception:
                pass
        self._open = []
        self.running = False


def _monitor():
    if not _HAS_HID:
        print("pywinusb não instalado:  python -m pip install pywinusb")
        return
    cols = find_collections()
    if not cols:
        print("Nenhuma coleção HID do Fifine encontrada (VID 3142). Conectado?")
        return
    count = {"n": 0}

    def show(ev):
        count["n"] += 1
        extra = ""
        if ev.get("botoes"):
            extra = "  botões=" + ",".join(ev["botoes"])
        if ev.get("hook_switch") is not None:
            extra = f"  hook_switch={'MUTE' if ev['hook_switch'] else 'ativo'}"
        print(f"[{time.strftime('%H:%M:%S')}] {ev['tag']:9} raw={ev['raw']}{extra}")

    lis = HidListener(on_event=show)
    n = lis.start()
    print(f"Ouvindo {n} coleção(ões) HID do Fifine.")
    print("Pressione o BOTÃO DE MUTE e gire os knobs do AM8. Ctrl+C para sair.\n")
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        lis.stop()
        print(f"\nfim. relatórios recebidos: {count['n']}")
        if count["n"] == 0:
            print("Nada foi emitido → no seu AM8 esses controles são locais "
                  "(tratados dentro do mic, sem avisar o PC).")


if __name__ == "__main__":
    _monitor()
