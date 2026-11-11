"""
fifine_gui — painel completo do microfone Fifine (Windows).

Aba HARDWARE:        ganho (0–10 dB do aparelho), mute, VU, fone de monitoramento.
Aba MIC VIRTUAL:     ganho digital ALÉM do hardware + supressão de ruído (RNNoise,
                     estilo Discord) + noise gate, roteando para um cabo virtual
                     que os apps usam como microfone.

Execute:  python fifine_gui.py
"""
from __future__ import annotations

import os
import traceback
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import fifine_core as fc
import fifine_config as cfg
import fifine_version as ver

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fifine_error.log")


def log_exception(where, exc=None):
    """Grava um traceback em fifine_error.log (não derruba o app)."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · {where} =====\n")
            fh.write(traceback.format_exc())
    except Exception:
        pass

try:
    import fifine_engine as fe
    _ENGINE_OK = True
    _ENGINE_ERR = None
except Exception as exc:  # pragma: no cover
    _ENGINE_OK = False
    _ENGINE_ERR = str(exc)

REFRESH_MS = 50

BG = "#1e1f26"
CARD = "#262833"
FG = "#e6e6e6"
ACCENT = "#4fd1c5"
MUTED = "#ff5c5c"
GREEN = "#2ec27e"
YELLOW = "#f5c542"
TRACK = "#2c2f3a"


class FifineApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"{ver.APP_NAME} — por {ver.AUTHOR}")
        root.configure(bg=BG)
        root.geometry("480x680")
        root.minsize(460, 640)
        try:
            import os
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fifine.ico")
            if os.path.exists(ico):
                root.iconbitmap(ico)
        except Exception:
            pass

        self.mic = None
        self.mon = None
        self.engine = fe.AudioEngine() if _ENGINE_OK else None
        self._syncing = False
        self._update_info = None
        _c = cfg.load()
        self._auto_check = bool(_c.get("auto_check", True))
        self._auto_update = bool(_c.get("auto_update", False))

        # captura exceções de qualquer callback do Tk (senão morrem em silêncio no pythonw)
        root.report_callback_exception = self._tk_exc

        self._build_style()
        self._build_banner(root)          # barra de atualização (oculta até haver update)
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_hw = ttk.Frame(self.nb)
        self.tab_proc = ttk.Frame(self.nb)
        self.nb.add(self.tab_hw, text="  Hardware  ")
        self.nb.add(self.tab_proc, text="  Mic Virtual (ganho+ / ruído)  ")

        self._build_hw(self.tab_hw)
        self._build_proc(self.tab_proc)

        self.detect()
        self._restore_config()
        self._tick()
        self._start_update_check()        # verificação automática ao abrir
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    _exc_shown = False

    def _tk_exc(self, exc, val, tb):
        log_exception("tk-callback")
        if not self._exc_shown:
            self._exc_shown = True
            try:
                messagebox.showerror(
                    "Fifine Control",
                    f"Ocorreu um erro (registrado em fifine_error.log):\n\n{val}\n\n"
                    "O app continua aberto. Me envie esse arquivo para eu corrigir.")
            except Exception:
                pass

    # ------------------------------------------------------------- estilo
    def _build_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=CARD, foreground=FG,
                     padding=(12, 6), font=("Segoe UI", 9))
        st.map("TNotebook.Tab", background=[("selected", BG)],
               foreground=[("selected", ACCENT)])
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        st.configure("Title.TLabel", font=("Segoe UI Semibold", 12))
        st.configure("Big.TLabel", font=("Segoe UI", 20, "bold"), foreground=ACCENT)
        st.configure("Dim.TLabel", foreground="#8a8f9c", font=("Segoe UI", 9))
        st.configure("TButton", font=("Segoe UI", 10))
        st.configure("TCheckbutton", background=BG, foreground=FG, font=("Segoe UI", 10))
        st.map("TCheckbutton", background=[("active", BG)])
        st.configure("TCombobox", fieldbackground=CARD, background=CARD)

    def _section(self, parent, title):
        f = ttk.Frame(parent, padding=(14, 8))
        f.pack(fill="x", padx=10, pady=(8, 0))
        ttk.Label(f, text=title, style="Title.TLabel").pack(anchor="w")
        return f

    # ========================================================== ABA HARDWARE
    def _build_hw(self, parent):
        header = ttk.Frame(parent, padding=(14, 10, 14, 0))
        header.pack(fill="x")
        self.lbl_device = ttk.Label(header, text="Procurando Fifine…", style="Dim.TLabel")
        self.lbl_device.pack(anchor="w")

        mic_f = self._section(parent, "🎙  Ganho do microfone (hardware)")
        row = ttk.Frame(mic_f); row.pack(fill="x", pady=(4, 0))
        self.lbl_mic_pct = ttk.Label(row, text="--%", style="Big.TLabel")
        self.lbl_mic_pct.pack(side="left")
        self.lbl_mic_db = ttk.Label(row, text="", style="Dim.TLabel")
        self.lbl_mic_db.pack(side="left", padx=(10, 0), pady=(12, 0))

        self.mic_var = tk.DoubleVar(value=0)
        ttk.Scale(mic_f, from_=0, to=100, variable=self.mic_var,
                  command=self._on_mic_slider).pack(fill="x", pady=(2, 4))
        btns = ttk.Frame(mic_f); btns.pack(fill="x")
        self.btn_mic_mute = ttk.Button(btns, text="Mute", width=9, command=self.toggle_mic_mute)
        self.btn_mic_mute.pack(side="left")
        for label, val in (("0", 0), ("50", 50), ("85", 85), ("100", 100)):
            ttk.Button(btns, text=f"{label}%", width=5,
                       command=lambda v=val: self.set_mic_pct(v)).pack(side="left", padx=(6, 0))

        vu_f = self._section(parent, "📶  Nível de entrada (ao vivo)")
        self.vu = tk.Canvas(vu_f, height=24, bg=TRACK, highlightthickness=0)
        self.vu.pack(fill="x", pady=(6, 2))

        mon_f = self._section(parent, "🎧  Fone de monitoramento")
        row2 = ttk.Frame(mon_f); row2.pack(fill="x", pady=(4, 0))
        self.lbl_mon_pct = ttk.Label(row2, text="--%", style="Big.TLabel")
        self.lbl_mon_pct.pack(side="left")
        self.lbl_mon_db = ttk.Label(row2, text="", style="Dim.TLabel")
        self.lbl_mon_db.pack(side="left", padx=(10, 0), pady=(12, 0))
        self.mon_var = tk.DoubleVar(value=0)
        ttk.Scale(mon_f, from_=0, to=100, variable=self.mon_var,
                  command=self._on_mon_slider).pack(fill="x", pady=(2, 4))
        self.btn_mon_mute = ttk.Button(mon_f, text="Mute", width=9, command=self.toggle_mon_mute)
        self.btn_mon_mute.pack(anchor="w")

        foot = ttk.Frame(parent, padding=(14, 12))
        foot.pack(fill="x", side="bottom")
        ttk.Button(foot, text="Definir como mic padrão", command=self.set_default).pack(side="left")
        ttk.Button(foot, text="Redetectar", command=self.detect).pack(side="right")

        bar = ttk.Frame(parent, padding=(14, 0, 14, 8))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, text=f"{ver.APP_NAME}  v{ver.__version__}  ·  por {ver.AUTHOR}",
                  style="Dim.TLabel").pack(side="left")
        ttk.Button(bar, text="Verificar agora",
                   command=self.check_updates).pack(side="right")
        self.autoupd_var = tk.BooleanVar(value=self._auto_update)
        ttk.Checkbutton(bar, text="Atualizar automaticamente", variable=self.autoupd_var,
                        command=self._on_autoupd).pack(side="right", padx=(0, 10))

    # ====================================================== ABA MIC VIRTUAL
    def _build_proc(self, parent):
        if not _ENGINE_OK:
            ttk.Label(parent, text="Motor de áudio indisponível:", style="Title.TLabel").pack(anchor="w", padx=16, pady=(20, 4))
            ttk.Label(parent, text=str(_ENGINE_ERR), style="Dim.TLabel").pack(anchor="w", padx=16)
            ttk.Label(parent, text="Instale:  python -m pip install sounddevice numpy pyrnnoise",
                      style="Dim.TLabel").pack(anchor="w", padx=16, pady=8)
            return

        top = ttk.Frame(parent, padding=(14, 10, 14, 0)); top.pack(fill="x")
        self.btn_engine = ttk.Button(top, text="▶  Ligar microfone virtual", command=self.toggle_engine)
        self.btn_engine.pack(fill="x")
        self.lbl_engine = ttk.Label(top, text="", style="Dim.TLabel")
        self.lbl_engine.pack(anchor="w", pady=(6, 0))

        # presets
        p_f = self._section(parent, "🎚  Presets")
        prow = ttk.Frame(p_f); prow.pack(fill="x", pady=(2, 2))
        for name in fe.PRESETS:
            ttk.Button(prow, text=name, width=11,
                       command=lambda n=name: self.apply_preset(n)).pack(
                           side="left", padx=(0, 4), pady=2)
        self.lbl_preset = ttk.Label(p_f, text="Escolha um preset para começar.",
                                    style="Dim.TLabel", wraplength=430, justify="left")
        self.lbl_preset.pack(anchor="w", pady=(2, 0))

        # saída (cabo virtual)
        out_f = self._section(parent, "🔀  Saída (cabo virtual)")
        self.out_var = tk.StringVar()
        self.cmb_out = ttk.Combobox(out_f, textvariable=self.out_var, state="readonly")
        self.cmb_out.pack(fill="x", pady=(4, 2))
        ttk.Label(out_f, text="Nos apps (Discord/OBS…), escolha “CABLE Output” como microfone.",
                  style="Dim.TLabel").pack(anchor="w")
        self._populate_outputs()

        # ganho digital
        g_f = self._section(parent, "🚀  Ganho digital (além do hardware)")
        rowg = ttk.Frame(g_f); rowg.pack(fill="x")
        self.lbl_gain = ttk.Label(rowg, text="+0 dB", style="Big.TLabel")
        self.lbl_gain.pack(side="left")
        self.gain_var = tk.DoubleVar(value=0)
        ttk.Scale(g_f, from_=0, to=30, variable=self.gain_var,
                  command=self._on_gain).pack(fill="x", pady=(2, 0))
        ttk.Label(g_f, text="0 … +30 dB  ·  limitador suave evita estouro",
                  style="Dim.TLabel").pack(anchor="w")

        # supressão de ruído
        n_f = self._section(parent, "🤫  Supressão de ruído (RNNoise)")
        self.nr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(n_f, text="Ativar RNNoise (estilo Discord)", variable=self.nr_var,
                        command=self._on_nr).pack(anchor="w")
        self.gate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(n_f, text="Noise gate (silêncio entre falas)", variable=self.gate_var,
                        command=self._on_gate).pack(anchor="w")
        rowt = ttk.Frame(n_f); rowt.pack(fill="x", pady=(4, 0))
        ttk.Label(rowt, text="Sensibilidade do gate", style="Dim.TLabel").pack(side="left")
        self.gate_th = tk.DoubleVar(value=45)
        ttk.Scale(n_f, from_=0, to=95, variable=self.gate_th,
                  command=self._on_gate_th).pack(fill="x")
        extra = ttk.Frame(n_f); extra.pack(fill="x", pady=(2, 0))
        self.hpf_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(extra, text="Corte de grave", variable=self.hpf_var,
                        command=self._on_hpf).pack(side="left")
        self.lim_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(extra, text="Limitador", variable=self.lim_var,
                        command=self._on_lim).pack(side="left", padx=(12, 0))

        # medidores do motor
        m_f = self._section(parent, "📊  Medidores")
        ttk.Label(m_f, text="Entrada", style="Dim.TLabel").pack(anchor="w")
        self.vu_in = tk.Canvas(m_f, height=16, bg=TRACK, highlightthickness=0)
        self.vu_in.pack(fill="x", pady=(0, 4))
        ttk.Label(m_f, text="Saída (para os apps)", style="Dim.TLabel").pack(anchor="w")
        self.vu_out = tk.Canvas(m_f, height=16, bg=TRACK, highlightthickness=0)
        self.vu_out.pack(fill="x", pady=(0, 4))
        self.lbl_vad = ttk.Label(m_f, text="voz: --   xruns: 0", style="Dim.TLabel")
        self.lbl_vad.pack(anchor="w")

    def _populate_outputs(self):
        _, outs = fe.list_io_devices()
        seen, names, default = set(), [], None
        for i, name, host, ch in outs:
            label = f"{name}  · {host}"
            if name in seen:
                continue
            seen.add(name)
            names.append(label)
            if default is None and "cable input" in name.lower():
                default = label
        self.cmb_out["values"] = names
        if default:
            self.out_var.set(default)
        elif names:
            self.out_var.set(names[0])

    def _restore_config(self):
        """Carrega config.json e aplica aos controles do motor."""
        if not _ENGINE_OK:
            return
        c = cfg.load()
        try:
            self.gain_var.set(float(c["gain_db"])); self._on_gain(None)
            self.nr_var.set(bool(c["nr_enabled"]))
            self.gate_var.set(bool(c["gate_enabled"]))
            self.gate_th.set(float(c["gate_threshold"]) * 100)
            self.hpf_var.set(bool(c["hpf_enabled"]))
            self.lim_var.set(bool(c["limiter_enabled"]))
            # seleciona a saída salva, se existir no combo
            for label in self.cmb_out["values"]:
                if c["output_name"].lower() in label.lower():
                    self.out_var.set(label); break
            self._push_all_params()
            if self.engine:
                self.engine.nr_amount = float(c["nr_amount"])
            if c.get("preset"):
                self.lbl_preset.config(text=f"● {c['preset']} (restaurado) — "
                                       f"{fe.PRESETS.get(c['preset'],{}).get('desc','')}")
            self._last_preset = c.get("preset")
        except Exception:
            self._last_preset = None

    def _save_config(self):
        if not _ENGINE_OK:
            return
        try:
            sel = self.out_var.get().split("  · ")[0].strip() or "CABLE Input"
            cfg.save({
                "preset": getattr(self, "_last_preset", None),
                "gain_db": self.gain_var.get(),
                "nr_enabled": self.nr_var.get(),
                "nr_amount": self.engine.nr_amount if self.engine else 1.0,
                "gate_enabled": self.gate_var.get(),
                "gate_threshold": self.gate_th.get() / 100.0,
                "hpf_enabled": self.hpf_var.get(),
                "limiter_enabled": self.lim_var.get(),
                "output_name": sel,
                "auto_check": self._auto_check,
                "auto_update": getattr(self, "_auto_update", False),
            })
        except Exception:
            pass

    def apply_preset(self, name):
        try:
            p = fe.PRESETS[name]
            self._last_preset = name
            if self.engine:
                self.engine.apply_preset(name)
            # sincroniza os controles da aba com o preset
            self.gain_var.set(p["gain_db"]); self._on_gain(None)
            self.nr_var.set(p["nr_enabled"])
            self.gate_var.set(p["gate_enabled"])
            self.gate_th.set(p["gate_threshold"] * 100)
            self.hpf_var.set(p["hpf_enabled"])
            self.lim_var.set(p["limiter_enabled"])
            # dica de ganho de hardware (aplica no mic físico, se achado)
            if self.mic:
                try:
                    self.mic.set_percent(p["hw_tip"]); self._sync_from_device()
                except Exception:
                    log_exception("apply_preset-hw")
                    self._maybe_redetect()
            self.lbl_preset.config(text=f"● {name} — {p['desc']}")
            self._save_config()
        except Exception:
            log_exception("apply_preset")
            try:
                self.lbl_preset.config(text=f"● {name} (aplicado)")
            except Exception:
                pass

    def _on_autoupd(self):
        self._auto_update = self.autoupd_var.get()
        try:
            c = cfg.load()
            c["auto_update"] = self._auto_update
            c["auto_check"] = self._auto_check
            cfg.save(c)
        except Exception:
            pass

    # ---------------------------------------------------- barra de atualização
    def _build_banner(self, root):
        """Barra no topo que aparece quando há atualização (oculta por padrão)."""
        self.banner = tk.Frame(root, bg="#223a57")
        self.banner_lbl = tk.Label(self.banner, bg="#223a57", fg="#eaf2ff",
                                   font=("Segoe UI", 10), anchor="w")
        self.banner_lbl.pack(side="left", padx=12, pady=8)
        self.banner_later = tk.Button(self.banner, text="Depois", bd=0, relief="flat",
                                      bg="#223a57", fg="#9fb6d6", cursor="hand2",
                                      activebackground="#2d4a6d", activeforeground="#fff",
                                      command=self._dismiss_banner)
        self.banner_later.pack(side="right", padx=(0, 12))
        self.banner_btn = tk.Button(self.banner, text="Atualizar agora", bd=0, relief="flat",
                                    bg=ACCENT, fg="#06201d", cursor="hand2",
                                    activebackground="#6fe0d4",
                                    font=("Segoe UI Semibold", 10),
                                    command=self._do_update)
        self.banner_btn.pack(side="right", padx=(0, 8), pady=5)
        self.banner_pb = ttk.Progressbar(self.banner, mode="determinate", length=150)
        # a barra de progresso só é empacotada durante o download

    def _show_banner(self):
        self.banner.pack(side="top", fill="x", before=self.nb)

    def _dismiss_banner(self):
        self.banner.pack_forget()

    def _start_update_check(self):
        """Verifica atualizações ao abrir (em thread, se auto_check ligado)."""
        if not getattr(self, "_auto_check", True):
            return
        import threading

        def worker():
            try:
                import fifine_update as up
                info = up.check()
            except Exception:
                return  # silencioso na verificação automática
            if info and info.available:
                self.root.after(0, lambda: self._on_update_found(info))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_found(self, info):
        self._update_info = info
        self.banner_lbl.config(
            text=f"⬆  Nova versão {info.latest} disponível  (você tem {info.current})")
        self.banner_btn.config(state="normal", text="Atualizar agora")
        self.banner_later.config(state="normal")
        self._show_banner()
        if getattr(self, "_auto_update", False):
            self._do_update()   # opcional: baixa e instala sozinho

    def check_updates(self):
        """Botão manual: verifica e, se houver, mostra a barra; senão avisa."""
        import threading

        def worker():
            try:
                import fifine_update as up
                info = up.check()
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Atualização", f"Não foi possível verificar:\n{exc}"))
                return
            if info.available:
                self.root.after(0, lambda: self._on_update_found(info))
            else:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Atualização", f"Você está na versão mais recente ({info.current})."))

        threading.Thread(target=worker, daemon=True).start()

    def _do_update(self):
        """Baixa o instalador mostrando progresso na barra e o executa."""
        info = getattr(self, "_update_info", None)
        if not info:
            return
        import threading
        self.banner_btn.config(state="disabled")
        self.banner_later.config(state="disabled")
        self.banner_lbl.config(text=f"Baixando {info.latest}…")
        self.banner_pb["value"] = 0
        self.banner_pb.pack(side="right", padx=(0, 8), pady=5)

        def prog(frac):
            self.root.after(0, lambda: self.banner_pb.configure(value=frac * 100))

        def worker():
            try:
                import fifine_update as up
                path = up.download(info, progress=prog)
            except Exception as exc:
                self.root.after(0, lambda: self._update_error(exc))
                return
            self.root.after(0, lambda: self._update_ready(path))

        threading.Thread(target=worker, daemon=True).start()

    def _update_error(self, exc):
        self.banner_pb.pack_forget()
        self.banner_lbl.config(text=f"Falha ao baixar: {exc}")
        self.banner_btn.config(state="normal")
        self.banner_later.config(state="normal")

    def _update_ready(self, path):
        self.banner_pb.configure(value=100)
        self.banner_lbl.config(text="Atualização baixada — abrindo o instalador…")
        try:
            if self.engine and self.engine.running:
                self.engine.stop()
        except Exception:
            pass
        import fifine_update as up
        self.root.after(700, lambda: up.run_installer_and_exit(path))

    def _maybe_redetect(self):
        """Se um endpoint ficou inválido (device removido/ocupado), re-resolve."""
        try:
            self.mic = fc.find_mic()
            self.mon = fc.find_monitor()
        except Exception:
            log_exception("redetect")

    # ------------------------------------------------------- engine handlers
    def toggle_engine(self):
        if not self.engine:
            return
        if self.engine.running:
            self.engine.stop()
            self.btn_engine.config(text="▶  Ligar microfone virtual")
        else:
            # aplica a saída escolhida
            sel = self.out_var.get().split("  · ")[0].strip()
            if sel:
                self.engine.output_name = sel
            self._push_all_params()
            try:
                self.engine.start()
            except Exception as exc:
                messagebox.showerror("Motor", f"Não foi possível iniciar:\n{exc}")
                return
            self.btn_engine.config(text="■  Desligar microfone virtual")
            self._save_config()

    def _push_all_params(self):
        e = self.engine
        e.gain_db = self.gain_var.get()
        e.nr_enabled = self.nr_var.get()
        e.gate_enabled = self.gate_var.get()
        e.gate_threshold = self.gate_th.get() / 100.0
        e.hpf_enabled = self.hpf_var.get()
        e.limiter_enabled = self.lim_var.get()

    def _on_gain(self, _v):
        if self.engine:
            self.engine.gain_db = self.gain_var.get()
        self.lbl_gain.config(text=f"+{self.gain_var.get():.0f} dB")

    def _on_nr(self):
        if self.engine: self.engine.nr_enabled = self.nr_var.get()

    def _on_gate(self):
        if self.engine: self.engine.gate_enabled = self.gate_var.get()

    def _on_gate_th(self, _v):
        if self.engine: self.engine.gate_threshold = self.gate_th.get() / 100.0

    def _on_hpf(self):
        if self.engine: self.engine.hpf_enabled = self.hpf_var.get()

    def _on_lim(self):
        if self.engine: self.engine.limiter_enabled = self.lim_var.get()

    # ------------------------------------------------------- hardware logic
    def detect(self):
        try:
            self.mic = fc.find_mic()
            self.mon = fc.find_monitor()
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao acessar o áudio:\n{exc}")
            return
        if not self.mic:
            self.lbl_device.config(text="⚠  Microfone Fifine não encontrado (conectado?)")
            return
        lo, hi, _ = self.mic.db_range()
        self.lbl_device.config(text=f"Conectado · {self.mic.name}  ·  ganho {lo:.0f}…{hi:.0f} dB")
        self._sync_from_device()

    def _sync_from_device(self):
        self._syncing = True
        try:
            if self.mic: self.mic_var.set(self.mic.get_percent())
            if self.mon: self.mon_var.set(self.mon.get_percent())
        finally:
            self._syncing = False
        self._refresh_labels()

    def _refresh_labels(self):
        if self.mic:
            pct = self.mic.get_percent(); muted = self.mic.get_mute()
            self.lbl_mic_pct.config(text=f"{pct:.0f}%", foreground=MUTED if muted else ACCENT)
            self.lbl_mic_db.config(text=f"{self.mic.get_db():+.1f} dB")
            self.btn_mic_mute.config(text="Unmute" if muted else "Mute")
        if self.mon:
            pct = self.mon.get_percent(); muted = self.mon.get_mute()
            self.lbl_mon_pct.config(text=f"{pct:.0f}%", foreground=MUTED if muted else ACCENT)
            self.lbl_mon_db.config(text=f"{self.mon.get_db():+.1f} dB")
            self.btn_mon_mute.config(text="Unmute" if muted else "Mute")

    def _on_mic_slider(self, _v):
        if self._syncing or not self.mic: return
        self.mic.set_percent(self.mic_var.get()); self._refresh_labels()

    def _on_mon_slider(self, _v):
        if self._syncing or not self.mon: return
        self.mon.set_percent(self.mon_var.get()); self._refresh_labels()

    def set_mic_pct(self, pct):
        if self.mic:
            self.mic.set_percent(pct); self._sync_from_device()

    def toggle_mic_mute(self):
        if self.mic:
            self.mic.toggle_mute(); self._refresh_labels()

    def toggle_mon_mute(self):
        if self.mon:
            self.mon.toggle_mute(); self._refresh_labels()

    def set_default(self):
        if not self.mic: return
        ok = fc.set_default_device(self.mic.id, 0) and fc.set_default_device(self.mic.id, 2)
        if ok:
            messagebox.showinfo("Fifine", "Fifine definido como microfone padrão.")
        else:
            messagebox.showwarning("Fifine", "Não foi possível definir o padrão\n(a API interna do Windows recusou).")

    # ------------------------------------------------------- VU / polling
    def _bar(self, canvas, level, vad_mark=None):
        canvas.delete("all")
        w = canvas.winfo_width() or 380
        h = canvas.winfo_height() or 20
        fill_w = int(w * max(0.0, min(1.0, level)))
        x, seg = 0, 3
        while x < fill_w:
            r = x / w
            color = GREEN if r < 0.7 else (YELLOW if r < 0.88 else MUTED)
            canvas.create_rectangle(x, 3, min(x + seg - 1, fill_w), h - 3, fill=color, outline="")
            x += seg
        for mk in (0.7, 0.88):
            mx = int(w * mk)
            canvas.create_line(mx, 0, mx, h, fill="#555")
        if vad_mark is not None:
            vx = int(w * vad_mark)
            canvas.create_line(vx, 0, vx, h, fill=ACCENT, width=2)

    def _tick(self):
        try:
            # VU do hardware
            if self.mic:
                try:
                    self._bar(self.vu, self.mic.peak())
                except Exception:
                    pass
            # medidores do motor
            if self.engine and self.engine.running:
                try:
                    self._bar(self.vu_in, self.engine.in_peak)
                    self._bar(self.vu_out, self.engine.out_peak)
                    gate = "aberto" if self.engine.vad >= self.engine.gate_threshold else "fechado"
                    self.lbl_vad.config(text=f"voz: {self.engine.vad:4.2f} · gate {gate} · xruns: {self.engine.xruns}")
                    self.lbl_engine.config(
                        text=f"● ATIVO → {self.engine.output_name}  ·  RNNoise {'on' if self.engine.has_rnnoise else 'off'}")
                    if self.engine.last_error:
                        self.lbl_engine.config(text=f"⚠ erro no motor: {self.engine.last_error}")
                except Exception:
                    log_exception("_tick-engine")
            elif self.engine:
                self.lbl_engine.config(text="desligado")
        except Exception:
            log_exception("_tick")
        finally:
            self._after_id = self.root.after(REFRESH_MS, self._tick)

    def _on_close(self):
        try:
            if getattr(self, "_after_id", None):
                self.root.after_cancel(self._after_id)
        except Exception:
            pass
        self._save_config()
        try:
            if self.engine and self.engine.running:
                self.engine.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    try:
        root = tk.Tk()
        FifineApp(root)
        root.mainloop()
    except Exception:
        log_exception("main")
        try:
            from tkinter import messagebox as _mb
            _mb.showerror("Fifine Control",
                          f"Falha ao iniciar (ver fifine_error.log):\n{traceback.format_exc()[-500:]}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
