"""
fifine_version — identidade e versão do produto (fonte única da verdade).

Ao lançar uma nova versão:
  1. Incremente __version__ (padrão SemVer: MAIOR.MENOR.CORRECAO).
  2. Descreva as mudanças no CHANGELOG.md.
  3. Faça commit e crie a tag:  git tag v1.0.1  &&  git push --tags
  4. Gere o instalador (build.py) e publique no GitHub Releases.
O app dos usuários detecta a nova tag e se oferece para atualizar.
"""

__version__ = "1.0.7"

APP_NAME = "Fifine AM8 Control"
APP_ID = "FifineAM8Control"              # usado em caminhos/registro
AUTHOR = "DZK"                           # desenvolvido por
PUBLISHER = "DZK"                        # editor (instalador/registro)

# Repositório no GitHub onde os Releases (instaladores) são publicados.
# Formato "usuario/repositorio". Troque pelo seu antes de distribuir.
GITHUB_REPO = "VictorRobert0/fifine-am8"


def version_tuple(v: str):
    """'v1.2.3' ou '1.2.3' -> (1, 2, 3). Ignora sufixos (-beta etc.)."""
    v = v.strip().lstrip("vV").split("-")[0].split("+")[0]
    parts = []
    for p in v.split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])
