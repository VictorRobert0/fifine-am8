# install.ps1 — instala ou remove o driver do microfone virtual.
# Uso (admin):
#   .\install.ps1 -InfPath ..\FifineVirtualMic.inf          # instala
#   .\install.ps1 -Remove                                   # desinstala
param(
    [string]$InfPath = "..\FifineVirtualMic.inf",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Rode este script como Administrador."
    }
}
Assert-Admin

if ($Remove) {
    # encontra o oemNN.inf publicado por este driver e remove
    $pub = pnputil /enum-drivers | Select-String -Pattern "FifineVirtualMic.inf" -Context 1,0
    Write-Host "Removendo driver(s) do Fifine Virtual Mic..."
    pnputil /enum-drivers | ForEach-Object {} | Out-Null
    # remoção explícita por INF original:
    pnputil /delete-driver (Split-Path $InfPath -Leaf) /uninstall /force 2>$null
    Write-Host "Se persistir, use: pnputil /enum-drivers  e  pnputil /delete-driver oemNN.inf /uninstall /force"
    return
}

# instala
Write-Host "Instalando $InfPath ..."
pnputil /add-driver $InfPath /install
Write-Host "`nVerifique em: Painel de Som > Gravação > 'Fifine Virtual Mic (Captura)'" -ForegroundColor Green
Write-Host "Se não aparecer e o modo de teste estiver OFF, o driver não carregou por falta de assinatura confiável."
