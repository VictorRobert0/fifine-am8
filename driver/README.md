# Driver virtual de áudio — caminho validado (POC)

Este diretório documenta e dá o scaffolding para criar um **dispositivo de áudio
virtual** próprio do Fifine AM8 Control — substituindo a dependência do VB-Audio
Virtual Cable. A pesquisa foi feita com o REA inspecionando o driver real do
VB-Cable instalado nesta máquina.

> **Status:** caminho de criação **validado** (toolchain, molde de INF e passos
> comprovados). O driver de kernel em si é construído a partir da amostra oficial
> da Microsoft (SYSVAD) — não é código escrito à mão, porque um miniport de áudio
> WDM funcional tem milhares de linhas e a Microsoft já mantém a referência.

## O que o REA confirmou (fatos)

O VB-Audio Virtual Cable (a referência que funciona) é:

- Um **miniport de áudio WDM/Kernel-Streaming**, classe `MEDIA`
  (`ClassGUID={4d36e96c-e325-11ce-bfc1-08002be10318}`).
- INF (`oem43.inf`) que faz `Include=ks.inf,wdmaudio.inf` e
  `Needs=KS.Registration, WDMAUDIO.Registration`, registra `SubClasses "wave,mixer"`
  e aponta o `wdmaud.drv`. Veja o molde em `FifineVirtualMic.inf`.
- Driver em `.sys` kernel-mode (vbaudio_cable64_win10.sys).

Ou seja: a Rota A (dispositivo virtual) é **comprovadamente viável** — é assim
que o VB-Cable faz. O AM8, por sua vez, usa o driver USB classe padrão da
Microsoft (`wdma_usb.inf`), sem APO próprio.

## Base recomendada: SYSVAD (amostra oficial da Microsoft)

A amostra **SYSVAD** ("Virtual Audio Device Driver") é o ponto de partida correto
para um endpoint de áudio virtual. Ela já implementa o miniport wave/topology.

Repositório: `https://github.com/microsoft/Windows-driver-samples` →
`audio/sysvad`.

Fluxo:

1. Clonar `Windows-driver-samples`.
2. Abrir `audio/sysvad/sysvad.sln` no Visual Studio **com o WDK instalado**.
3. Reduzir o SYSVAD ao mínimo: manter apenas um endpoint de **captura (microfone)**
   virtual (remover speakers/HDMI/etc. dos arrays de topologia).
4. Renomear o produto para "Fifine Virtual Mic" (strings e `FriendlyName`).
5. Compilar para **x64 Release**.

## Pré-requisitos de build (o que falta nesta máquina)

| Ferramenta | Status aqui | Observação |
|---|---|---|
| Visual Studio / Build Tools | ✅ 2019 presente | precisa do workload C++ |
| Windows SDK 10 | ✅ 10.0.19041 presente | signtool/makecert OK |
| **WDK (Windows Driver Kit)** | ❌ **ausente** | **instalar** — é obrigatório |
| signtool.exe (x64) | ✅ presente | usado nos scripts |

Instale o WDK **da mesma versão** do SDK/VS:
`https://learn.microsoft.com/windows-hardware/drivers/download-the-wdk`
(e a extensão "WDK Visual Studio Extension").

## Test-signing (para validar na SUA máquina, sem custo)

Driver não-assinado por uma CA confiável **não carrega**. Para TESTAR localmente:

```powershell
# (admin) liga o modo de teste e reinicia
bcdedit /set testsigning on
# reinicie o Windows
```

Depois use os scripts deste diretório:

- `scripts\testsign.ps1` — cria um certificado de teste e assina o `.sys` + catálogo.
- `scripts\install.ps1` — instala o INF (`pnputil /add-driver ... /install`).

> O modo de teste é **só para desenvolvimento**. Usuários finais **não** devem
> ligá-lo. Para eles, veja "Distribuição" abaixo.

## Distribuição (o obstáculo real: assinatura)

Para usuários instalarem sem modo de teste, o pacote precisa de:

1. **Certificado EV de code-signing** (~US$ 200–400/ano).
2. **Conta no Microsoft Partner Center / Hardware Dev Center**.
3. **Assinatura por atestação** (submeter o `.cab` do driver à Microsoft; ela
   devolve o pacote assinado para o kernel aceitar).

Esse é o custo/burocracia que decide se vale criar o driver próprio ou continuar
redistribuindo o VB-Cable (gratuito) — veja a comparação no README principal.

## Arquivos deste diretório

| Arquivo | O quê |
|---|---|
| `FifineVirtualMic.inf` | Molde de INF do dispositivo virtual (derivado do VB-Cable). |
| `scripts\testsign.ps1` | Cria certificado de teste e assina driver + catálogo. |
| `scripts\install.ps1` | Instala/desinstala o driver via `pnputil`. |

## Alternativa elegante (Rota B — APO)

Em vez de um dispositivo virtual, um **APO** (Audio Processing Object, DLL COM C++)
injeta ganho+ e RNNoise direto no stream de captura do AM8 — sem cabo e sem app
em segundo plano. Base: amostra **SwapAPO**/**MsApo** do Windows-driver-samples
(`audio/sysvad/APO`). Também exige assinatura. Maior esforço, melhor experiência.
