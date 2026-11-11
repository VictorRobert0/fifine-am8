"""
fifine_update — verificação e download de atualizações via GitHub Releases.

Fluxo (estilo commit/patch):
  - O desenvolvedor publica um Release no GitHub com uma tag (v1.0.1) e anexa o
    instalador (FifineAM8-Setup-x.y.z.exe) como asset.
  - Este módulo consulta a API do GitHub, compara a versão da tag mais recente
    com a versão local (fifine_version.__version__) e, se houver uma mais nova,
    baixa o instalador e o executa — o instalador substitui a versão antiga.

Usa só a biblioteca padrão (urllib/json), para empacotar leve e sem dependências.
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

import fifine_version as ver

API_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
_TIMEOUT = 10


class UpdateInfo:
    def __init__(self, available, latest, current, url=None, notes="", asset_name=""):
        self.available = available
        self.latest = latest
        self.current = current
        self.url = url
        self.notes = notes
        self.asset_name = asset_name


def check(repo: str = None) -> UpdateInfo:
    """Consulta o GitHub e diz se há versão mais nova. Lança em erro de rede."""
    repo = repo or ver.GITHUB_REPO
    url = API_LATEST.format(repo=repo)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{ver.APP_ID}/{ver.__version__}",
    })
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # repositório sem nenhum Release publicado ainda → não é erro
            return UpdateInfo(available=False, latest="(nenhum release)",
                              current="v" + ver.__version__)
        raise

    tag = data.get("tag_name", "")
    notes = data.get("body", "") or ""
    # escolhe o asset .exe (instalador)
    asset_url, asset_name = None, ""
    for a in data.get("assets", []):
        name = a.get("name", "")
        if name.lower().endswith(".exe"):
            asset_url = a.get("browser_download_url")
            asset_name = name
            break

    newer = ver.version_tuple(tag) > ver.version_tuple(ver.__version__)
    return UpdateInfo(
        available=bool(newer and asset_url),
        latest=tag or "?",
        current="v" + ver.__version__,
        url=asset_url,
        notes=notes,
        asset_name=asset_name,
    )


def download(info: UpdateInfo, progress=None) -> str:
    """Baixa o instalador para a pasta temporária e devolve o caminho."""
    if not info.url:
        raise RuntimeError("Sem URL de instalador no Release.")
    dest = os.path.join(tempfile.gettempdir(), info.asset_name or "FifineAM8-Setup.exe")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(info.url, headers={"User-Agent": ver.APP_ID})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length", 0))
        read = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            fh.write(chunk)
            read += len(chunk)
            if progress and total:
                progress(read / total)
    return dest


def run_installer_and_exit(path: str) -> bool:
    """Aplica a atualização no estilo launcher e encerra o app.

    Roda o instalador do Inno em modo silencioso e **elevado** (um único UAC).
    O instalador fecha a instância em execução, troca os arquivos e reabre o app
    já na versão nova — por isso o app "volta sozinho". Se o usuário recusar o
    UAC, cai no modo interativo (assistente visível) como alternativa.

    Devolve True se o instalador foi disparado; só retorna em caso de falha ao
    lançar (quando dá certo, encerra o processo).
    """
    # /VERYSILENT: sem assistente · /SUPPRESSMSGBOXES: sem caixas · /NORESTART:
    # nunca reinicia o PC · /NOCANCEL: o usuário não cancela no meio da troca.
    params = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL"
    launched = False
    try:
        import ctypes
        # ShellExecuteW com o verbo "runas" → pede elevação com UM prompt de UAC.
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, params, None, 1)
        launched = int(rc) > 32  # <=32 = erro (ex.: usuário recusou o UAC)
    except Exception:
        launched = False

    if not launched:
        # Alternativa: abre o assistente visível (ainda pede elevação sozinho).
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            launched = True
        except AttributeError:
            try:
                subprocess.Popen([path])
                launched = True
            except Exception:
                launched = False

    if launched:
        # Sai "duro": evita que a thread da bandeja segure o processo e deixe
        # arquivos travados durante a troca feita pelo instalador.
        os._exit(0)
    return False


# --- uso por linha de comando ---
def _main():
    try:
        info = check()
    except Exception as exc:
        print(f"Falha ao verificar atualizações: {exc}")
        return
    print(f"Versão atual: {info.current}   |   mais recente: {info.latest}")
    if not info.available:
        print("Você já está na versão mais recente (ou o Release ainda não tem instalador).")
        return
    print(f"Atualização disponível: {info.latest}")
    if info.notes:
        print("\nNovidades:\n" + info.notes[:800])
    ans = input("\nBaixar e instalar agora? [s/N] ").strip().lower()
    if ans in ("s", "sim", "y", "yes"):
        print("Baixando...")
        path = download(info, progress=lambda f: print(f"\r  {f*100:5.1f}%", end="", flush=True))
        print("\nAbrindo instalador...")
        run_installer_and_exit(path)


if __name__ == "__main__":
    _main()
