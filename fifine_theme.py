"""
fifine_theme — paletas de cores (temas) da interface.

Cada tema é um dicionário de cores. A interface lê o tema atual e permite trocar
ao vivo.
"""

THEMES = {
    "Violeta Noturno": {
        "win":   "#141019",   # fundo da janela
        "panel": "#1e1826",   # painéis
        "panel2":"#271f33",   # painel destacado / trilhas
        "rail":  "#120e18",   # menu lateral
        "text":  "#f0ecf6",
        "dim":   "#9b8fb0",
        "accent":"#a06bff",   # cor principal
        "accent2":"#ff5cc8",  # secundária (glow)
        "track": "#2c2440",
        "good":  "#4fd08a",
        "warn":  "#ffcc55",
        "bad":   "#ff5c7a",
    },
    "Âmbar": {
        "win":   "#17120b", "panel": "#241b10", "panel2": "#30240f", "rail": "#120d07",
        "text":  "#fbf3e6", "dim": "#b39a76", "accent": "#ffab2e", "accent2": "#ff6a3d",
        "track": "#3a2c14", "good": "#8fd04f", "warn": "#ffcc55", "bad": "#ff6a5c",
    },
    "Ciano Gelo": {
        "win":   "#0e1620", "panel": "#15212e", "panel2": "#1b2b3c", "rail": "#0b121a",
        "text":  "#eaf4fb", "dim": "#7f97ad", "accent": "#35d0e0", "accent2": "#4f8cff",
        "track": "#203345", "good": "#3fd08a", "warn": "#ffcc55", "bad": "#ff5c7a",
    },
    "Rubi": {
        "win":   "#190f12", "panel": "#271519", "panel2": "#331a20", "rail": "#140a0d",
        "text":  "#fdeef0", "dim": "#b38793", "accent": "#ff4d6d", "accent2": "#ff9e57",
        "track": "#3a1f26", "good": "#4fd08a", "warn": "#ffcc55", "bad": "#ff7a5c",
    },
}

DEFAULT_THEME = "Violeta Noturno"


def get(name):
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def names():
    return list(THEMES.keys())
