"""
fifine_ui — interface moderna do Fifine AM8 Control.

Janela sem borda com título customizado, menu lateral, knob circular de ganho,
interruptores (toggles), medidores, bandeja do sistema e temas de cores.
Reaproveita todo o backend: fifine_core, fifine_engine, fifine_config,
fifine_update, fifine_version.

Flags:
  --tray   inicia oculto, só na bandeja do sistema
  --shot <arquivo.png>  renderiza e salva um screenshot (uso interno/testes)
"""
from __future__ import annotations

import sys
import math
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import fifine_core as fc
import fifine_config as cfg
import fifine_version as ver
import fifine_theme as theme

try:
    import fifine_engine as fe
    _ENGINE_OK = True
except Exception as exc:
    _ENGINE_OK = False
    _ENGINE_ERR = str(exc)

HERE = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(HERE, "fifine.ico")


# ----------------------------------------------------------------- utilidades
def round_rect(cv, x1, y1, x2, y2, r, **kw):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class Pill(tk.Canvas):
    """Interruptor on/off arredondado."""
    def __init__(self, master, colors, value=False, command=None, **kw):
        super().__init__(master, width=52, height=28, highlightthickness=0,
                         bg=colors["panel"], **kw)
        self.c = colors
        self.value = value
        self.command = command
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        on = self.value
        track = self.c["accent"] if on else self.c["track"]
        round_rect(self, 2, 4, 50, 24, 10, fill=track, outline="")
        kx = 39 if on else 13
        self.create_oval(kx - 9, 5, kx + 9, 23, fill=self.c["text"], outline="")

    def _click(self, _e):
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)

    def set(self, v):
        self.value = bool(v)
        self._draw()


class Gauge(tk.Canvas):
    """Knob circular (arco) para ajustar um valor 0..1. Arraste para mudar."""
    def __init__(self, master, colors, size=190, command=None, fmt=None, sub=""):
        super().__init__(master, width=size, height=size, highlightthickness=0,
                         bg=colors["panel"])
        self.c = colors
        self.size = size
        self.command = command
        self.fmt = fmt or (lambda v: f"{int(v*100)}%")
        self.sub = sub
        self.value = 0.0
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Button-1>", self._drag)
        self._draw()

    START = 135   # graus
    SWEEP = 270

    def _drag(self, e):
        cx = cy = self.size / 2
        ang = math.degrees(math.atan2(e.y - cy, e.x - cx))
        a = (ang - self.START) % 360
        if a > self.SWEEP:
            a = 0 if a - self.SWEEP > (360 - self.SWEEP) / 2 else self.SWEEP
        v = max(0.0, min(1.0, a / self.SWEEP))
        self.set(v, notify=True)

    def set(self, v, notify=False):
        self.value = max(0.0, min(1.0, v))
        self._draw()
        if notify and self.command:
            self.command(self.value)

    def set_sub(self, text):
        self.sub = text
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size
        pad = 16
        x1, y1, x2, y2 = pad, pad, s - pad, s - pad
        # trilho
        self.create_arc(x1, y1, x2, y2, start=-(self.START), extent=-self.SWEEP,
                        style="arc", outline=self.c["track"], width=12)
        # valor
        self.create_arc(x1, y1, x2, y2, start=-(self.START),
                        extent=-self.SWEEP * self.value, style="arc",
                        outline=self.c["accent"], width=12)
        # textos centrais
        self.create_text(s / 2, s / 2 - 8, text=self.fmt(self.value),
                         fill=self.c["text"], font=("Segoe UI", 26, "bold"))
        if self.sub:
            self.create_text(s / 2, s / 2 + 22, text=self.sub,
                             fill=self.c["dim"], font=("Segoe UI", 10))


class VU(tk.Canvas):
    def __init__(self, master, colors, h=14):
        super().__init__(master, height=h, highlightthickness=0, bg=colors["track"])
        self.c = colors
        self.h = h

    def set_level(self, lvl):
        self.delete("all")
        w = self.winfo_width() or 300
        fw = int(w * max(0.0, min(1.0, lvl)))
        x = 0
        while x < fw:
            r = x / w
            col = self.c["good"] if r < 0.7 else (self.c["warn"] if r < 0.88 else self.c["bad"])
            self.create_rectangle(x, 2, min(x + 3, fw), self.h - 2, fill=col, outline="")
            x += 4


# ------------------------------------------------------------------- aplicação
class SkinApp:
    def __init__(self, root, start_tray=False):
        self.root = root
        self.conf = cfg.load()
        self.theme_name = self.conf.get("theme", theme.DEFAULT_THEME)
        self.c = theme.get(self.theme_name)

        self.mic = None
        self.mon = None
        self.engine = fe.AudioEngine() if _ENGINE_OK else None
        self.section = "Microfone"
        self._drag = (0, 0)
        self._update_info = None
        self._tray = None
        self._after_id = None
        self._recheck_id = None

        root.overrideredirect(True)
        root.geometry("880x560")
        self._center()
        try:
            root.iconbitmap(ICO)
        except Exception:
            pass
        root.configure(bg=self.c["accent"])
        root.report_callback_exception = self._log_exc

        self.detect()
        self.build()
        self._tick()
        self._start_tray()
        self._auto_update_check()
        self._schedule_periodic_check()
        if start_tray:
            root.after(100, self.hide_to_tray)

    def _log_exc(self, *a):
        try:
            import traceback, datetime
            with open(os.path.join(cfg.data_dir(), "fifine_error.log"), "a", encoding="utf-8") as fh:
                fh.write(f"\n== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ==\n")
                fh.write(traceback.format_exc())
        except Exception:
            pass

    # --------------------------------------------------------------- janela
    def _center(self):
        self.root.update_idletasks()
        w, h = 880, 560
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//3}")

    def detect(self):
        try:
            self.mic = fc.find_mic()
            self.mon = fc.find_monitor()
        except Exception:
            self.mic = self.mon = None

    # --------------------------------------------------------------- build
    def _style_ttk(self):
        c = self.c
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TScale", background=c["panel"])
        st.configure("Horizontal.TScale", background=c["win"], troughcolor=c["track"])
        st.map("Horizontal.TScale", background=[("active", c["accent"]), ("!active", c["accent"])])
        st.configure("TCombobox", fieldbackground=c["panel2"], background=c["panel2"],
                     foreground=c["text"], arrowcolor=c["accent"], bordercolor=c["panel2"],
                     lightcolor=c["panel2"], darkcolor=c["panel2"], selectbackground=c["panel2"],
                     selectforeground=c["text"])
        st.map("TCombobox", fieldbackground=[("readonly", c["panel2"])],
               foreground=[("readonly", c["text"])])
        st.configure("TProgressbar", troughcolor=c["track"], background=c["accent"],
                     bordercolor=c["track"], lightcolor=c["accent"], darkcolor=c["accent"])

    def build(self):
        self._style_ttk()
        for w in self.root.winfo_children():
            w.destroy()
        c = self.c
        outer = tk.Frame(self.root, bg=c["accent"])      # borda fina de acento
        outer.pack(fill="both", expand=True, padx=1, pady=1)
        body = tk.Frame(outer, bg=c["win"])
        body.pack(fill="both", expand=True)

        self._build_titlebar(body)
        mid = tk.Frame(body, bg=c["win"])
        mid.pack(fill="both", expand=True)
        self._build_rail(mid)
        self.content = tk.Frame(mid, bg=c["win"])
        self.content.pack(side="left", fill="both", expand=True)
        self._build_content()

    def _build_titlebar(self, parent):
        c = self.c
        tb = tk.Frame(parent, bg=c["rail"], height=46)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        # logo + título
        logo = tk.Canvas(tb, width=30, height=30, bg=c["rail"], highlightthickness=0)
        logo.place(x=14, y=8)
        logo.create_oval(4, 4, 26, 26, outline=c["accent"], width=2)
        logo.create_rectangle(13, 9, 17, 18, fill=c["accent"], outline="")
        logo.create_arc(9, 7, 21, 22, start=200, extent=140, style="arc",
                        outline=c["accent"], width=2)
        tk.Label(tb, text="FIFINE AM8 CONTROL", bg=c["rail"], fg=c["text"],
                 font=("Segoe UI Semibold", 11)).place(x=52, y=13)
        # botões direita
        self._winbtn(tb, "✕", 848, self._close, hover=c["bad"])
        self._winbtn(tb, "—", 818, self.hide_to_tray)
        tk.Label(tb, text=f"v{ver.__version__} · por {ver.AUTHOR}", bg=c["rail"],
                 fg=c["dim"], font=("Segoe UI", 8)).place(x=640, y=17)
        # arraste
        for wdg in (tb,):
            wdg.bind("<Button-1>", self._drag_start)
            wdg.bind("<B1-Motion>", self._drag_move)

    def _winbtn(self, parent, text, x, cmd, hover=None):
        c = self.c
        b = tk.Label(parent, text=text, bg=c["rail"], fg=c["dim"],
                     font=("Segoe UI", 12), cursor="hand2", width=2)
        b.place(x=x, y=12)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(fg=hover or c["text"]))
        b.bind("<Leave>", lambda e: b.config(fg=c["dim"]))

    def _build_rail(self, parent):
        c = self.c
        rail = tk.Frame(parent, bg=c["rail"], width=176)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        items = [("Microfone", "🎙"), ("Mic Virtual", "🚀"),
                 ("Presets", "🎚"), ("Ajustes", "⚙")]
        self._navbtns = {}
        for name, icon in items:
            sel = name == self.section
            f = tk.Frame(rail, bg=c["panel"] if sel else c["rail"],
                         height=48, cursor="hand2")
            f.pack(fill="x", padx=10, pady=4)
            f.pack_propagate(False)
            bar = tk.Frame(f, bg=c["accent"] if sel else c["rail"], width=3)
            bar.pack(side="left", fill="y")
            tk.Label(f, text=f"  {icon}  {name}", bg=f["bg"],
                     fg=c["text"] if sel else c["dim"],
                     font=("Segoe UI", 10, "bold" if sel else "normal"),
                     anchor="w").pack(side="left", fill="both", expand=True)
            for wdg in (f, f.winfo_children()[1]):
                wdg.bind("<Button-1>", lambda e, n=name: self._go(n))
            self._navbtns[name] = f

    def _go(self, name):
        self.section = name
        self.build()

    def _section_title(self, text):
        tk.Label(self.content, text=text, bg=self.c["win"], fg=self.c["text"],
                 font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=24, pady=(18, 2))

    def _card(self, parent=None, **kw):
        parent = parent or self.content
        f = tk.Frame(parent, bg=self.c["panel"], **kw)
        return f

    # --------------------------------------------------------- conteúdo
    def _build_content(self):
        self._update_banner_host()
        if self.section == "Microfone":
            self._content_mic()
        elif self.section == "Mic Virtual":
            self._content_virtual()
        elif self.section == "Presets":
            self._content_presets()
        else:
            self._content_settings()

    def _update_banner_host(self):
        self._banner = tk.Frame(self.content, bg="#223a57")
        if self._update_info:
            self._show_banner(self._update_info)

    # ---- Microfone ----
    def _content_mic(self):
        c = self.c
        self._section_title("Microfone")
        if not self.mic:
            tk.Label(self.content, text="Fifine não encontrado. Conecte o AM8 e clique em Redetectar.",
                     bg=c["win"], fg=c["dim"], font=("Segoe UI", 10)).pack(anchor="w", padx=24, pady=10)
            tk.Button(self.content, text="Redetectar", command=self._redetect,
                      **self._btn()).pack(anchor="w", padx=24)
            return
        wrap = tk.Frame(self.content, bg=c["win"]); wrap.pack(fill="both", expand=True, padx=24, pady=10)
        # knob de ganho
        left = tk.Frame(wrap, bg=c["win"]); left.pack(side="left", padx=(0, 30))
        tk.Label(left, text="GANHO", bg=c["win"], fg=c["dim"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="center")
        self.g_mic = Gauge(left, c, command=self._set_mic_pct,
                           fmt=lambda v: f"{int(v*100)}%")
        self.g_mic.pack()
        self.g_mic.set(self.mic.get_percent() / 100.0)
        self.g_mic.set_sub(f"{self.mic.get_db():+.1f} dB")
        # coluna direita
        right = tk.Frame(wrap, bg=c["win"]); right.pack(side="left", fill="both", expand=True)
        self._toggle_row(right, "Mudo (microfone)", self.mic.get_mute(), self._toggle_mic_mute)
        tk.Label(right, text="Fone de monitoramento", bg=c["win"], fg=c["dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 2))
        self.s_mon = self._scale(right, 0, 100,
                                 self.mon.get_percent() if self.mon else 0, self._set_mon)
        if self.mon:
            self._toggle_row(right, "Mudo (fone)", self.mon.get_mute(), self._toggle_mon_mute)
        tk.Label(right, text="Nível de entrada", bg=c["win"], fg=c["dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 2))
        self.vu_mic = VU(right, c); self.vu_mic.pack(fill="x")
        tk.Button(right, text="Definir como mic padrão", command=self._set_default,
                  **self._btn()).pack(anchor="w", pady=(16, 0))

    # ---- Mic Virtual ----
    def _content_virtual(self):
        c = self.c
        self._section_title("Microfone virtual — ganho+ e supressão")
        if not _ENGINE_OK:
            tk.Label(self.content, text=f"Motor indisponível: {_ENGINE_ERR}",
                     bg=c["win"], fg=c["bad"]).pack(anchor="w", padx=24)
            return
        wrap = tk.Frame(self.content, bg=c["win"]); wrap.pack(fill="both", expand=True, padx=24, pady=6)
        left = tk.Frame(wrap, bg=c["win"]); left.pack(side="left", padx=(0, 26))
        tk.Label(left, text="GANHO DIGITAL", bg=c["win"], fg=c["dim"],
                 font=("Segoe UI", 9, "bold")).pack()
        self.g_dig = Gauge(left, c, command=self._set_dig_gain,
                           fmt=lambda v: f"+{int(v*30)}", sub="dB")
        self.g_dig.pack()
        self.g_dig.set(self.engine.gain_db / 30.0)
        self.btn_engine = tk.Button(left, text="▶  Ligar", command=self._toggle_engine,
                                    **self._btn(accent=True))
        self.btn_engine.pack(fill="x", pady=(10, 0))

        right = tk.Frame(wrap, bg=c["win"]); right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Saída (cabo virtual)", bg=c["win"], fg=c["dim"],
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.cmb_out = ttk.Combobox(right, state="readonly")
        self.cmb_out.pack(fill="x", pady=(2, 2))
        self._populate_outputs()
        tk.Label(right, text='Nos apps escolha "CABLE Output" como microfone.',
                 bg=c["win"], fg=c["dim"], font=("Segoe UI", 8)).pack(anchor="w")
        self._toggle_row(right, "Supressão de ruído (RNNoise)", self.engine.nr_enabled, self._set_nr)
        self._toggle_row(right, "Noise gate", self.engine.gate_enabled, self._set_gate)
        self._toggle_row(right, "Corte de grave", self.engine.hpf_enabled, self._set_hpf)
        self._toggle_row(right, "Limitador", self.engine.limiter_enabled, self._set_lim)
        mrow = tk.Frame(right, bg=c["win"]); mrow.pack(fill="x", pady=(10, 0))
        tk.Label(mrow, text="Entrada", bg=c["win"], fg=c["dim"], font=("Segoe UI", 8)).pack(anchor="w")
        self.vu_in = VU(right, c); self.vu_in.pack(fill="x")
        tk.Label(right, text="Saída (apps)", bg=c["win"], fg=c["dim"], font=("Segoe UI", 8)).pack(anchor="w")
        self.vu_out = VU(right, c); self.vu_out.pack(fill="x")
        self.lbl_voz = tk.Label(right, text="voz: -- · xruns: 0", bg=c["win"], fg=c["dim"],
                                font=("Segoe UI", 8)); self.lbl_voz.pack(anchor="w")

    # ---- Presets ----
    def _content_presets(self):
        c = self.c
        self._section_title("Presets")
        if not _ENGINE_OK:
            return
        for name, p in fe.PRESETS.items():
            card = self._card(height=74); card.pack(fill="x", padx=24, pady=5)
            card.pack_propagate(False)
            tk.Label(card, text=name, bg=c["panel"], fg=c["accent"],
                     font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(8, 0))
            tk.Label(card, text=p["desc"], bg=c["panel"], fg=c["dim"],
                     font=("Segoe UI", 8), wraplength=520, justify="left").pack(anchor="w", padx=14)
            btn = tk.Button(card, text="Aplicar", command=lambda n=name: self._apply_preset(n),
                            **self._btn(accent=True))
            btn.place(relx=1.0, x=-100, y=22)

    # ---- Ajustes ----
    def _content_settings(self):
        c = self.c
        self._section_title("Ajustes")
        wrap = tk.Frame(self.content, bg=c["win"]); wrap.pack(fill="both", expand=True, padx=24, pady=6)
        tk.Label(wrap, text="Tema de cores", bg=c["win"], fg=c["dim"],
                 font=("Segoe UI", 9)).pack(anchor="w")
        trow = tk.Frame(wrap, bg=c["win"]); trow.pack(anchor="w", pady=(4, 12))
        for name in theme.names():
            tc = theme.get(name)
            sel = name == self.theme_name
            sw = tk.Frame(trow, bg=tc["accent"], width=26, height=26,
                          highlightthickness=2,
                          highlightbackground=c["text"] if sel else c["panel"])
            sw.pack_propagate(False); sw.pack(side="left", padx=4)
            sw.bind("<Button-1>", lambda e, n=name: self._set_theme(n))
            tk.Label(trow, text=name, bg=c["win"], fg=c["text"] if sel else c["dim"],
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 10))

        self._toggle_row(wrap, "Iniciar com o Windows (na bandeja)",
                         self._autostart_enabled(), self._set_autostart)
        self._toggle_row(wrap, "Atualizar automaticamente",
                         self.conf.get("auto_update", False), self._set_autoupd)
        tk.Button(wrap, text="Verificar atualizações agora", command=self._check_updates_manual,
                  **self._btn()).pack(anchor="w", pady=(8, 2))
        tk.Button(wrap, text="Redetectar microfone", command=self._redetect,
                  **self._btn()).pack(anchor="w", pady=2)
        tk.Label(wrap, text=f"{ver.APP_NAME} v{ver.__version__} — Desenvolvido por {ver.AUTHOR}\n"
                            "Open source (MIT) · github.com/VictorRobert0/fifine-am8",
                 bg=c["win"], fg=c["dim"], font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(16, 0))

    # ----------------------------------------------------- helpers de widget
    def _btn(self, accent=False):
        c = self.c
        if accent:
            return dict(bg=c["accent"], fg="#10121a", activebackground=c["accent2"],
                        relief="flat", bd=0, font=("Segoe UI Semibold", 9),
                        cursor="hand2", padx=14, pady=6)
        return dict(bg=c["panel2"], fg=c["text"], activebackground=c["track"],
                    relief="flat", bd=0, font=("Segoe UI", 9), cursor="hand2", padx=12, pady=6)

    def _toggle_row(self, parent, label, value, cmd):
        c = self.c
        row = tk.Frame(parent, bg=c["win"]); row.pack(fill="x", pady=5)
        tk.Label(row, text=label, bg=c["win"], fg=c["text"],
                 font=("Segoe UI", 10)).pack(side="left")
        p = Pill(row, c, value=value, command=cmd)
        p.pack(side="right")
        return p

    def _scale(self, parent, lo, hi, val, cmd):
        var = tk.DoubleVar(value=val)
        s = ttk.Scale(parent, from_=lo, to=hi, variable=var,
                      command=lambda v: cmd(float(v)))
        s.pack(fill="x")
        return var

    # ----------------------------------------------------- ações de hardware
    def _set_mic_pct(self, v):
        if self.mic:
            self.mic.set_percent(v * 100)
            self.g_mic.set_sub(f"{self.mic.get_db():+.1f} dB")

    def _set_mon(self, v):
        if self.mon:
            self.mon.set_percent(v)

    def _toggle_mic_mute(self, v):
        if self.mic:
            self.mic.set_mute(v)

    def _toggle_mon_mute(self, v):
        if self.mon:
            self.mon.set_mute(v)

    def _set_default(self):
        if self.mic and fc.set_default_device(self.mic.id, 0):
            fc.set_default_device(self.mic.id, 2)
            messagebox.showinfo("Fifine", "Definido como microfone padrão.")

    def _redetect(self):
        self.detect()
        self.build()

    # ----------------------------------------------------- ações do motor
    def _set_dig_gain(self, v):
        if self.engine:
            self.engine.gain_db = v * 30.0

    def _set_nr(self, v): self.engine.nr_enabled = v
    def _set_gate(self, v): self.engine.gate_enabled = v
    def _set_hpf(self, v): self.engine.hpf_enabled = v
    def _set_lim(self, v): self.engine.limiter_enabled = v

    def _toggle_engine(self):
        if not self.engine:
            return
        if self.engine.running:
            self.engine.stop()
            self.btn_engine.config(text="▶  Ligar")
        else:
            sel = self.cmb_out.get().split("  · ")[0].strip()
            if sel:
                self.engine.output_name = sel
            try:
                self.engine.start()
                self.btn_engine.config(text="■  Desligar")
            except Exception as exc:
                messagebox.showerror("Motor", str(exc))

    def _populate_outputs(self):
        _, outs = fe.list_io_devices()
        seen, names, default = set(), [], None
        for i, name, host, ch in outs:
            if name in seen:
                continue
            seen.add(name)
            label = f"{name}  · {host}"
            names.append(label)
            if default is None and "cable input" in name.lower():
                default = label
        self.cmb_out["values"] = names
        saved = self.conf.get("output_name", "CABLE Input")
        pick = next((n for n in names if saved.lower() in n.lower()), default or (names[0] if names else ""))
        if pick:
            self.cmb_out.set(pick)

    def _apply_preset(self, name):
        if not self.engine:
            return
        p = self.engine.apply_preset(name)
        if self.mic:
            try:
                self.mic.set_percent(p["hw_tip"])
            except Exception:
                pass
        self.section = "Mic Virtual"
        self.build()

    # ----------------------------------------------------- tema / config
    def _set_theme(self, name):
        self.theme_name = name
        self.c = theme.get(name)
        self.conf["theme"] = name
        cfg.save(self.conf)
        self.root.configure(bg=self.c["accent"])
        self.build()

    def _set_autoupd(self, v):
        self.conf["auto_update"] = v
        cfg.save(self.conf)

    def _save_engine_conf(self):
        if not self.engine:
            return
        self.conf.update({
            "gain_db": self.engine.gain_db, "nr_enabled": self.engine.nr_enabled,
            "gate_enabled": self.engine.gate_enabled,
            "hpf_enabled": self.engine.hpf_enabled,
            "limiter_enabled": self.engine.limiter_enabled,
        })
        try:
            self.conf["output_name"] = self.cmb_out.get().split("  · ")[0].strip() or "CABLE Input"
        except Exception:
            pass
        cfg.save(self.conf)

    # ----------------------------------------------------- autostart (Run key)
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    RUN_NAME = "FifineAM8Control"

    def _autostart_enabled(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as k:
                winreg.QueryValueEx(k, self.RUN_NAME)
                return True
        except Exception:
            return False

    def _set_autostart(self, v):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
                if v:
                    exe = sys.executable
                    # no app empacotado, sys.executable é o próprio .exe
                    cmd = f'"{exe}" --tray' if exe.lower().endswith("fifineam8control.exe") \
                        else f'"{exe}" "{os.path.join(HERE, "fifine_ui.py")}" --tray'
                    winreg.SetValueEx(k, self.RUN_NAME, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(k, self.RUN_NAME)
                    except FileNotFoundError:
                        pass
        except Exception as exc:
            messagebox.showwarning("Autostart", f"Não foi possível alterar: {exc}")

    # ----------------------------------------------------- atualização
    #
    # Experiência estilo "launcher": ao abrir, o app avisa que está procurando
    # atualizações; depois mostra que já está em dia ou oferece a nova versão.
    def _banner_clear(self):
        b = getattr(self, "_banner", None)
        if not b:
            return
        for w in b.winfo_children():
            w.destroy()
        b.pack_forget()

    def _banner_show(self):
        b = self._banner
        # fica no topo do conteúdo: ancora ANTES do primeiro filho que não seja
        # o próprio banner. Usar before=b (o banner ainda não empacotado) lançava
        # "window isn't packed" e derrubava a inicialização / escondia o aviso.
        kids = [k for k in self.content.winfo_children() if k is not b]
        if kids:
            b.pack(fill="x", before=kids[0])
        else:
            b.pack(fill="x")

    # intervalo da reverificação automática em segundo plano (3 horas)
    RECHECK_MS = 3 * 60 * 60 * 1000

    def _auto_update_check(self):
        if not self.conf.get("auto_check", True):
            return
        self._run_check(manual=False)

    def _schedule_periodic_check(self):
        """Reverifica atualizações de tempos em tempos, sem reabrir o app.

        Diferente da checagem de abertura, roda em silêncio: não mostra a barra
        "Procurando…" nem o aviso "você está em dia" — só exibe o banner quando
        realmente há uma versão nova. Assim o app percebe um release publicado
        enquanto está aberto.
        """
        self._recheck_id = self.root.after(self.RECHECK_MS, self._periodic_check)

    def _periodic_check(self):
        if self.conf.get("auto_check", True):
            def worker():
                try:
                    import fifine_update as up
                    info = up.check()
                except Exception:
                    info = None
                if info and info.available:
                    self.root.after(0, lambda: self._show_banner(info))
            threading.Thread(target=worker, daemon=True).start()
        # reagenda sempre (mesmo com auto_check off, para respeitar se religar)
        self._recheck_id = self.root.after(self.RECHECK_MS, self._periodic_check)

    def _check_updates_manual(self):
        self._run_check(manual=True)

    def _run_check(self, manual=False):
        self._show_checking()
        def worker():
            try:
                import fifine_update as up
                info = up.check()
            except Exception as exc:
                self.root.after(0, lambda: self._show_check_error(exc, manual))
                return
            if info and info.available:
                self.root.after(0, lambda: self._show_banner(info))
            else:
                self.root.after(0, lambda: self._show_uptodate(info))
        threading.Thread(target=worker, daemon=True).start()

    def _show_checking(self):
        self._banner_clear()
        b = self._banner
        b.configure(bg="#223a57")
        self._banner_show()
        tk.Label(b, text="🔄  Procurando atualizações…", bg="#223a57",
                 fg="#eaf2ff", font=("Segoe UI", 10)).pack(side="left", padx=12, pady=7)
        pb = ttk.Progressbar(b, length=120, mode="indeterminate")
        pb.pack(side="right", padx=12)
        try:
            pb.start(12)
        except Exception:
            pass

    def _show_uptodate(self, info):
        self._banner_clear()
        b = self._banner
        b.configure(bg="#1f3b2e")
        self._banner_show()
        cur = (info.current if info else "v" + ver.__version__)
        tk.Label(b, text=f"✓  Você está na versão mais recente ({cur})", bg="#1f3b2e",
                 fg="#d7f5e3", font=("Segoe UI", 10)).pack(side="left", padx=12, pady=7)
        # some sozinho depois de alguns segundos (feel de launcher)
        self.root.after(4000, self._banner_clear)

    def _show_check_error(self, exc, manual):
        self._banner_clear()
        if manual:
            messagebox.showwarning("Atualização",
                                   f"Não foi possível verificar agora.\n{exc}")

    def _show_banner(self, info):
        self._update_info = info
        self._banner_clear()
        b = self._banner
        b.configure(bg="#223a57")
        self._banner_show()
        tk.Label(b, text=f"⬆  Nova versão {info.latest} disponível", bg="#223a57",
                 fg="#eaf2ff", font=("Segoe UI", 10)).pack(side="left", padx=12, pady=7)
        tk.Button(b, text="Depois", command=self._banner_clear, bg="#223a57", fg="#9fb6d6",
                  relief="flat", bd=0, cursor="hand2").pack(side="right", padx=10)
        self._pbar = ttk.Progressbar(b, length=140, mode="determinate")
        self._pstat = tk.Label(b, text="", bg="#223a57", fg="#9fb6d6",
                               font=("Segoe UI", 9))
        tk.Button(b, text="Atualizar agora", command=self._do_update, **self._btn(accent=True)
                  ).pack(side="right", padx=6)
        if self.conf.get("auto_update", False):
            self._do_update()

    def _do_update(self):
        info = self._update_info
        if not info:
            return
        self._pstat.configure(text="Baixando…")
        self._pstat.pack(side="right", padx=(8, 2))
        self._pbar.pack(side="right", padx=8)

        def prog(f):
            self.root.after(0, lambda: self._pbar.configure(value=f * 100))

        def worker():
            try:
                import fifine_update as up
                path = up.download(info, progress=prog)
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Atualização", str(exc)))
                return
            self.root.after(0, lambda: self._finish_update(path))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_update(self, path):
        try:
            self._pbar.configure(value=100)
            self._pstat.configure(text="Instalando e reiniciando…")
        except Exception:
            pass
        try:
            if self.engine and self.engine.running:
                self.engine.stop()
        except Exception:
            pass
        import fifine_update as up
        # Dá um instante para a UI pintar "Instalando…" e então dispara o
        # instalador (silencioso + elevado). Em caso de sucesso, encerra aqui.
        def go():
            ok = up.run_installer_and_exit(path)
            if ok is False:
                messagebox.showerror(
                    "Atualização",
                    "Não foi possível iniciar a instalação da atualização.\n"
                    "Abra o instalador manualmente:\n" + path)
        self.root.after(150, go)

    # ----------------------------------------------------- bandeja
    def _start_tray(self):
        try:
            import pystray
            from PIL import Image
            img = Image.open(ICO)
            menu = pystray.Menu(
                pystray.MenuItem("Abrir", lambda: self.root.after(0, self.show_window), default=True),
                pystray.MenuItem("Sair", lambda: self.root.after(0, self._quit)),
            )
            self._tray = pystray.Icon("fifine", img, "Fifine AM8 Control", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception:
            self._tray = None

    def hide_to_tray(self):
        if self._tray:
            self.root.withdraw()
        else:
            self._close()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))

    def _close(self):
        if self.conf.get("minimize_to_tray", True) and self._tray:
            self.hide_to_tray()
        else:
            self._quit()

    def _quit(self):
        try:
            self._save_engine_conf()
            if self.engine and self.engine.running:
                self.engine.stop()
            if self._tray:
                self._tray.stop()
        except Exception:
            pass
        self.root.destroy()

    # ----------------------------------------------------- arrastar janela
    def _drag_start(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    # ----------------------------------------------------- loop de medidores
    def _tick(self):
        try:
            if self.section == "Microfone" and self.mic and hasattr(self, "vu_mic"):
                self.vu_mic.set_level(self.mic.peak())
            if self.section == "Mic Virtual" and self.engine and self.engine.running:
                if hasattr(self, "vu_in"):
                    self.vu_in.set_level(self.engine.in_peak)
                    self.vu_out.set_level(self.engine.out_peak)
                    gate = "aberto" if self.engine.vad >= self.engine.gate_threshold else "fechado"
                    self.lbl_voz.config(text=f"voz: {self.engine.vad:.2f} · gate {gate} · xruns: {self.engine.xruns}")
        except Exception:
            pass
        self._after_id = self.root.after(60, self._tick)


def _arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    start_tray = "--tray" in sys.argv or "/h" in sys.argv
    root = tk.Tk()
    app = SkinApp(root, start_tray=start_tray)
    # screenshot opcional para testes
    if "--shot" in sys.argv:
        path = sys.argv[sys.argv.index("--shot") + 1]
        sec = _arg("--section")
        thm = _arg("--theme")
        if thm:
            app.theme_name = thm
            app.c = theme.get(thm)
            root.configure(bg=app.c["accent"])
        if sec:
            app.section = sec
        if sec or thm:
            app.build()
        def shot():
            try:
                from PIL import ImageGrab
                root.update(); root.update_idletasks()
                x, y = root.winfo_rootx(), root.winfo_rooty()
                w, h = root.winfo_width(), root.winfo_height()
                ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
            finally:
                root.destroy()
        root.after(500, shot)
    root.mainloop()


if __name__ == "__main__":
    main()
