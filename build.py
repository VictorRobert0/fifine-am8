"""
build.py — pipeline de release do Fifine AM8 Control.

Lê a versão de fifine_version.py, empacota com PyInstaller e gera o instalador
com o Inno Setup. Saída final: Output\FifineAM8-Setup-<versão>.exe

Uso:
  python build.py              # build completo (PyInstaller + instalador)
  python build.py --no-exe     # só o instalador (reaproveita dist\ existente)
"""
from __future__ import annotations

import os
import subprocess
import sys

# saída UTF-8 (runners de CI usam cp1252 e quebram com acentos/símbolos)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import fifine_version as ver  # noqa: E402

ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def find_iscc():
    for p in ISCC_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def run(cmd, **kw):
    print(">", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, **kw)
    if r.returncode != 0:
        sys.exit(f"Falhou (código {r.returncode}): {' '.join(cmd)}")


def main():
    no_exe = "--no-exe" in sys.argv
    print(f"== Build {ver.APP_NAME} v{ver.__version__} ==")

    if not no_exe:
        run([sys.executable, "-m", "PyInstaller", "fifine.spec",
             "--noconfirm", "--distpath", "dist", "--workpath", "build"])

    iscc = find_iscc()
    if not iscc:
        sys.exit("Inno Setup (ISCC.exe) não encontrado. Instale em "
                 "https://jrsoftware.org/isdl.php")
    run([iscc, f"/DMyAppVersion={ver.__version__}", "installer.iss"])

    out = os.path.join(ROOT, "Output", f"FifineAM8-Setup-{ver.__version__}.exe")
    if os.path.exists(out):
        size = os.path.getsize(out) / (1024 * 1024)
        print(f"\nOK -> {out}  ({size:.1f} MB)")
        print("Publique este arquivo como asset do Release no GitHub.")
    else:
        sys.exit("Instalador não foi gerado.")


if __name__ == "__main__":
    main()
