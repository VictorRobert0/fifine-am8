# testsign.ps1 — cria um certificado de teste e assina o driver + catálogo.
# Uso (admin, com WDK instalado e modo de teste ligado):
#   .\testsign.ps1 -SysPath ..\x64\Release\FifineVMic.sys -InfPath ..\FifineVirtualMic.inf
param(
    [Parameter(Mandatory = $true)][string]$SysPath,
    [Parameter(Mandatory = $true)][string]$InfPath,
    [string]$CertName = "DZK Fifine Test Cert"
)

$ErrorActionPreference = "Stop"
$sdkBin = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64"
$signtool = Join-Path $sdkBin "signtool.exe"
$inf2cat  = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x86\inf2cat.exe"  # vem do WDK

# 1) certificado de teste (auto-assinado) no repositório de certificados
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=$CertName" `
        -CertStoreLocation "Cert:\CurrentUser\My" -KeyUsage DigitalSignature `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")
Write-Host "Certificado criado: $($cert.Thumbprint)"

# confia no certificado (dev): copia para Root e TrustedPublisher
$tmp = Join-Path $env:TEMP "dzk_test.cer"
Export-Certificate -Cert $cert -FilePath $tmp | Out-Null
Import-Certificate -FilePath $tmp -CertStoreLocation "Cert:\LocalMachine\Root" | Out-Null
Import-Certificate -FilePath $tmp -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher" | Out-Null

# 2) gera o catálogo (.cat) a partir do INF — requer inf2cat (WDK)
$drvDir = Split-Path $InfPath -Parent
if (Test-Path $inf2cat) {
    & $inf2cat /driver:$drvDir /os:10_X64
} else {
    Write-Warning "inf2cat ausente (instale o WDK). Pulei a geração do .cat."
}

# 3) assina o .sys e o .cat com o certificado de teste
& $signtool sign /fd SHA256 /a /s My /n $CertName /t http://timestamp.digicert.com $SysPath
$cat = Join-Path $drvDir "FifineVirtualMic.cat"
if (Test-Path $cat) { & $signtool sign /fd SHA256 /a /s My /n $CertName $cat }

Write-Host "`nAssinado. Agora rode install.ps1 (admin)." -ForegroundColor Green
