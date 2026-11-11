"""
install_shortcut — cria (ou recria) o atalho "Fifine Control" na Área de Trabalho,
apontando para a GUI via pythonw (sem janela de console) com o ícone do app.

Uso:  python install_shortcut.py
"""
from __future__ import annotations

import os
import subprocess
import sys

PROJ = os.path.dirname(os.path.abspath(__file__))


def main():
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # fallback (mostra console)
    target_script = os.path.join(PROJ, "fifine_ui.py")
    icon = os.path.join(PROJ, "fifine.ico")

    ps = f'''
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop 'Fifine Control.lnk'
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = {ps_quote(pythonw)}
$sc.Arguments = {ps_quote('"' + target_script + '"')}
$sc.WorkingDirectory = {ps_quote(PROJ)}
$sc.IconLocation = {ps_quote(icon)}
$sc.Description = 'Controle do microfone Fifine - ganho, supressao de ruido, mic virtual'
$sc.WindowStyle = 1
$sc.Save()
Write-Output $lnk
'''
    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        print("Atalho criado:", res.stdout.strip())
    else:
        print("Falha ao criar atalho:\n", res.stderr.strip())
        sys.exit(1)


def ps_quote(s: str) -> str:
    """Aspas simples seguras para PowerShell."""
    return "'" + s.replace("'", "''") + "'"


if __name__ == "__main__":
    main()
