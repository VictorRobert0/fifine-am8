"""
fifine_cli — controle do microfone Fifine pela linha de comando.

Exemplos:
  python fifine_cli.py status                 # mostra ganho, dB, mute dos dois endpoints
  python fifine_cli.py gain 70                # define o ganho do mic em 70%
  python fifine_cli.py gain +10               # aumenta 10 pontos
  python fifine_cli.py gain -10               # diminui 10 pontos
  python fifine_cli.py db 6.5                 # define o ganho em 6,5 dB
  python fifine_cli.py mute on|off|toggle     # mute do microfone
  python fifine_cli.py monitor 40             # volume do fone em 40%
  python fifine_cli.py monitor-mute toggle    # mute do fone
  python fifine_cli.py meter                  # VU meter contínuo (Ctrl+C para sair)
  python fifine_cli.py presets                # lista os presets e as recomendações
  python fifine_cli.py process --preset Stream  # mic virtual com um preset pronto
  python fifine_cli.py default                # define o Fifine como mic padrão
  python fifine_cli.py list                   # lista todos os endpoints de áudio
"""
from __future__ import annotations

import sys
import time

try:  # acentos corretos no console do Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import fifine_core as fc


def _need_mic():
    mic = fc.find_mic()
    if not mic:
        sys.exit("Microfone Fifine não encontrado (está conectado?).")
    return mic


def _need_mon():
    mon = fc.find_monitor()
    if not mon:
        sys.exit("Saída de fone do Fifine não encontrada.")
    return mon


def _apply_relative(ep, token):
    """Aceita '70', '+10', '-10'."""
    cur = ep.get_percent()
    if token.startswith(("+", "-")):
        ep.set_percent(cur + float(token))
    else:
        ep.set_percent(float(token))


def cmd_status():
    mic = fc.find_mic()
    mon = fc.find_monitor()
    if mic:
        s = mic.snapshot()
        print(f"MIC  {s['name']}")
        print(f"     ganho : {s['percent']:.0f}%  ({s['db']:+.2f} dB "
              f"de {s['db_min']:.0f}…{s['db_max']:.0f} dB)")
        print(f"     mute  : {'SIM' if s['mute'] else 'não'}   canais: {s['channels']}")
    else:
        print("MIC  (não encontrado)")
    if mon:
        s = mon.snapshot()
        print(f"FONE {s['name']}")
        print(f"     volume: {s['percent']:.0f}%  ({s['db']:+.2f} dB)")
        print(f"     mute  : {'SIM' if s['mute'] else 'não'}")


def cmd_gain(token):
    mic = _need_mic()
    _apply_relative(mic, token)
    print(f"Ganho = {mic.get_percent():.0f}%  ({mic.get_db():+.2f} dB)")


def cmd_db(value):
    mic = _need_mic()
    mic.set_db(float(value))
    print(f"Ganho = {mic.get_db():+.2f} dB  ({mic.get_percent():.0f}%)")


def _mute_arg(ep, token):
    token = token.lower()
    if token in ("on", "1", "true", "sim"):
        ep.set_mute(True)
    elif token in ("off", "0", "false", "nao", "não"):
        ep.set_mute(False)
    elif token == "toggle":
        ep.toggle_mute()
    else:
        sys.exit("Use: on | off | toggle")
    return ep.get_mute()


def cmd_mute(token):
    mic = _need_mic()
    print("Mic mute:", "SIM" if _mute_arg(mic, token) else "não")


def cmd_monitor(token):
    mon = _need_mon()
    _apply_relative(mon, token)
    print(f"Fone = {mon.get_percent():.0f}%  ({mon.get_db():+.2f} dB)")


def cmd_monitor_mute(token):
    mon = _need_mon()
    print("Fone mute:", "SIM" if _mute_arg(mon, token) else "não")


def cmd_meter():
    mic = _need_mic()
    print("VU meter — Ctrl+C para sair")
    try:
        while True:
            p = mic.peak()
            bar = "#" * int(p * 50)
            print(f"\r{p*100:5.1f}% |{bar:<50}|", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def cmd_default():
    mic = _need_mic()
    ok = fc.set_default_device(mic.id, 0) and fc.set_default_device(mic.id, 2)
    print("Definido como mic padrão." if ok else "Falha ao definir padrão.")


def cmd_process(*args):
    """Liga o microfone virtual: Fifine -> [ganho+ / RNNoise] -> cabo virtual.
    Opções: --gain N(dB)  --nr on|off  --gate on|off  --out "CABLE Input"  --in fifine
    """
    import time as _t
    try:
        import fifine_engine as fe
    except Exception as exc:
        sys.exit(f"Motor indisponível ({exc}). Instale: pip install sounddevice numpy pyrnnoise")
    opts = {"--gain": None, "--nr": None, "--gate": None,
            "--out": "CABLE Input", "--in": "fifine", "--preset": None}
    it = iter(args)
    for a in it:
        if a in opts:
            opts[a] = next(it, opts[a])
    eng = fe.AudioEngine(input_name=opts["--in"], output_name=opts["--out"])
    if opts["--preset"]:
        match = next((n for n in fe.PRESETS if n.lower() == opts["--preset"].lower()), None)
        if not match:
            sys.exit(f"Preset '{opts['--preset']}' inválido. Use: {', '.join(fe.PRESETS)}")
        p = eng.apply_preset(match)
        print(f"Preset: {match} — {p['desc']}")
    # argumentos explícitos sobrescrevem o preset
    if opts["--gain"] is not None:
        eng.gain_db = float(opts["--gain"])
    if opts["--nr"] is not None:
        eng.nr_enabled = opts["--nr"].lower() in ("on", "1", "true", "sim")
    if opts["--gate"] is not None:
        eng.gate_enabled = opts["--gate"].lower() in ("on", "1", "true", "sim")
    try:
        eng.start()
    except Exception as exc:
        sys.exit(f"Falha ao iniciar: {exc}")
    print(f"Mic virtual ATIVO: {opts['--in']} -> {opts['--out']}  |  "
          f"ganho +{eng.gain_db:.0f} dB  nr={eng.nr_enabled}  gate={eng.gate_enabled}  "
          f"RNNoise={eng.has_rnnoise}")
    print("Nos apps escolha 'CABLE Output' como microfone. Ctrl+C para parar.")
    try:
        while True:
            _t.sleep(0.3)
            print(f"\rin {eng.in_peak:4.2f} | out {eng.out_peak:4.2f} | voz {eng.vad:4.2f} | xruns {eng.xruns}   ",
                  end="", flush=True)
    except KeyboardInterrupt:
        eng.stop(); print("\nparado.")


def cmd_update(*args):
    """Verifica atualizações no GitHub (--check só verifica; sem flag, baixa e instala)."""
    import fifine_update as up
    import fifine_version as ver
    print(f"{ver.APP_NAME} v{ver.__version__}")
    try:
        info = up.check()
    except Exception as exc:
        sys.exit(f"Falha ao verificar: {exc}")
    print(f"Mais recente no GitHub: {info.latest}")
    if not info.available:
        print("Já está atualizado.")
        return
    print(f"Nova versão disponível: {info.latest}")
    if "--check" in args:
        return
    print("Baixando instalador...")
    path = up.download(info, progress=lambda f: print(f"\r  {f*100:5.1f}%", end="", flush=True))
    print("\nAbrindo instalador (o app vai fechar)...")
    up.run_installer_and_exit(path)


def cmd_version():
    import fifine_version as ver
    print(f"{ver.APP_NAME} v{ver.__version__}")


def cmd_presets():
    import fifine_engine as fe
    print("Presets disponíveis (use: process --preset <nome>):\n")
    for name, p in fe.PRESETS.items():
        nr = "RNNoise on" if p["nr_enabled"] else "sem RNNoise"
        gate = f"gate {int(p['gate_threshold']*100)}%" if p["gate_enabled"] else "sem gate"
        print(f"  {name:13} +{p['gain_db']:>2} dB · {nr} · {gate} · hw {p['hw_tip']}%")
        print(f"                {p['desc']}\n")


def cmd_list():
    data = fc.list_all()
    for flow in ("capture", "render"):
        print(f"\n== {'CAPTURA (mics)' if flow=='capture' else 'RENDER (saídas)'} ==")
        for ep in data[flow]:
            lo, hi, _ = ep.db_range()
            print(f"  {ep.get_percent():3.0f}%  {ep.name}  [{lo:.0f}…{hi:.0f} dB]")


COMMANDS = {
    "status": (cmd_status, 0),
    "gain": (cmd_gain, 1),
    "db": (cmd_db, 1),
    "mute": (cmd_mute, 1),
    "monitor": (cmd_monitor, 1),
    "monitor-mute": (cmd_monitor_mute, 1),
    "meter": (cmd_meter, 0),
    "process": (cmd_process, -1),
    "presets": (cmd_presets, 0),
    "update": (cmd_update, -1),
    "version": (cmd_version, 0),
    "default": (cmd_default, 0),
    "list": (cmd_list, 0),
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = argv[0]
    if cmd not in COMMANDS:
        sys.exit(f"Comando desconhecido: {cmd}\nUse --help.")
    func, nargs = COMMANDS[cmd]
    args = argv[1:]
    if nargs == -1:          # repassa todos os argumentos (ex.: process)
        func(*args)
    elif nargs == 0:
        func()
    else:
        if len(args) < nargs:
            sys.exit(f"'{cmd}' precisa de {nargs} argumento(s).")
        func(*args[:nargs])


if __name__ == "__main__":
    main(sys.argv[1:])
