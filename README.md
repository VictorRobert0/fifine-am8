# Fifine AM8 Control

Software local para o microfone **Fifine AM8** (e outros Fifine com `VID 3142`) no
Windows: controle de **ganho**, **mute**, **fone de monitoramento**, **ganho digital
além do hardware**, **supressão de ruído estilo Discord (RNNoise)** e **noise gate**,
com **presets** prontos e **atualização automática**.

**Desenvolvido por DZK.**

> **Open Source:** este projeto é livre (licença MIT) e foi criado para **ajudar a
> gerenciar melhor a utilização do microfone Fifine AM8** — dando aos usuários o
> controle de ganho e a supressão de ruído que o aparelho sozinho não oferece.
> Contribuições, issues e melhorias são bem-vindas.

> **Baixar:** pegue o instalador mais recente em
> [**Releases**](https://github.com/VictorRobert0/fifine-am8/releases).

---

## Recursos

- **Ganho do microfone** (0–10 dB de hardware) — ler e ajustar
- **Mute** do mic e **volume/mute do fone** de monitoramento
- **Ganho digital até +30 dB** — vai *além* do limite do hardware
- **Supressão de ruído RNNoise** — a mesma técnica usada pelo Discord
- **Noise gate** por detecção de voz — silêncio total entre as falas
- **5 presets**: Limpo · Gravação · Stream · Reunião · Voz distante
- **Medidores ao vivo** (entrada, saída, voz)
- **Lembra suas configurações** e **se atualiza** pelo GitHub

## Como o AM8 funciona (resumo técnico)

O AM8 é um **dispositivo USB composto, classe USB Audio padrão** — sem driver nem
protocolo proprietário. O ganho é um *Feature Unit* exposto pelo **Core Audio** do
Windows, com faixa de hardware de **0–10 dB**. Para ir além, o app abre um
**microfone virtual**: captura o AM8, aplica ganho digital + RNNoise + gate e reenvia
para um **cabo de áudio virtual** (VB-Audio Cable) que os programas usam como mic.

```
AM8 → mono → corte de grave → RNNoise → mix → noise gate → GANHO DIGITAL → limitador → CABLE Input
                                                                         nos apps: escolher "CABLE Output"
```

> Os **knobs** de ganho/fone são analógicos (atuam antes do conversor A/D), então o
> PC não enxerga a posição deles — é por isso que o Windows só mostra 0–10 dB. O
> **botão de mute** por toque é tratado internamente no mic e não sinaliza o PC.

## Instalação (usuário final)

1. Baixe `FifineAM8-Setup-x.y.z.exe` em [Releases](https://github.com/VictorRobert0/fifine-am8/releases).
2. Execute e siga o instalador.
3. Para o microfone virtual (ganho++ e supressão), é preciso o
   **[VB-Audio Virtual Cable](https://vb-audio.com/Cable/)** (gratuito) — o instalador
   avisa e abre a página se ele não estiver presente.
4. Abra pelo atalho **Fifine AM8 Control**.

## Uso

**Aba Hardware:** ganho (0–10 dB), mute, VU meter, fone de monitoramento.

**Aba Mic Virtual:** escolha um **preset** → **Ligar microfone virtual** → nos apps
(Discord, OBS, Meet…) selecione **“CABLE Output”** como microfone.

### Presets (recomendação de uso)

| Preset | Ganho dig. | Ruído | Gate | Quando usar |
|---|---|---|---|---|
| **Limpo** | +0 dB | — | — | Sala silenciosa, gravação séria. Qualidade acima de tudo. |
| **Gravação** | +3 dB | leve | — | Podcast/narração. Tira ruído leve sem cortar nuance. |
| **Stream** | +10 dB | forte | sim | Lives e jogos. Mata teclado, mouse e ventilador. |
| **Reunião** | +12 dB | forte | sim | Discord/Meet/Teams. Voz clara, silêncio total no fundo. |
| **Voz distante** | +24 dB | forte | sim | Mic longe/voz baixa. Empurra o volume bem além do hardware. |

## Atualizações

Ao abrir, o app **verifica sozinho** se há uma versão nova e, se houver, mostra uma
**barra no topo** com a opção de atualizar — baixa com barra de progresso e abre o
instalador. É opcional: dá para **adiar** ("Depois") ou marcar **"Atualizar
automaticamente"** (baixa e instala sem clique). Também há o botão **Verificar
agora** e a linha de comando:

```powershell
FifineAM8Control.exe   # ou, em dev:  python fifine_cli.py update
```

---

## Para desenvolvedores

### Rodar do código-fonte

```powershell
python -m pip install --user pycaw comtypes sounddevice numpy pyrnnoise pywinusb
python fifine_gui.py          # interface
python fifine_cli.py --help   # linha de comando
```

### Gerar o instalador

Requer [PyInstaller](https://pyinstaller.org) e [Inno Setup 6](https://jrsoftware.org/isdl.php).

```powershell
python -m pip install --user pyinstaller
python build.py               # PyInstaller + Inno -> Output\FifineAM8-Setup-<versão>.exe
```

### Fluxo de release (estilo commit → patch)

1. Faça suas mudanças e **commit**.
2. Suba a versão em `fifine_version.py` e descreva em `CHANGELOG.md`.
3. Crie a tag e envie:
   ```powershell
   git tag v1.0.1
   git push origin main --tags
   ```
4. `python build.py` gera o instalador.
5. Crie um **Release** no GitHub com a tag e anexe o `.exe` do `Output\`.
   (Ou deixe o GitHub Actions fazer isso — veja `.github/workflows/release.yml`.)
6. Os usuários recebem o aviso de atualização automaticamente.

### Estrutura

| Arquivo | Função |
|---|---|
| `fifine_core.py` | Core Audio: ganho/dB/mute/monitor/pico (hardware). |
| `fifine_engine.py` | Motor em tempo real: ganho digital + RNNoise + gate + presets. |
| `fifine_gui.py` | Interface (Tkinter), abas Hardware e Mic Virtual. |
| `fifine_cli.py` | Linha de comando. |
| `fifine_hid.py` | Leitura HID (diagnóstico dos botões físicos). |
| `fifine_config.py` | Salva/restaura preferências. |
| `fifine_update.py` | Auto-update via GitHub Releases. |
| `fifine_version.py` | Versão e identidade do produto. |
| `fifine.spec` / `build.py` | Empacotamento (PyInstaller). |
| `installer.iss` | Instalador (Inno Setup). |

## Licença

Projeto **open source** sob a licença **MIT** (veja [`LICENSE`](LICENSE)) —
Desenvolvido por **DZK**. O RNNoise e o VB-Audio Cable têm licenças próprias;
o VB-Cable **não** é redistribuído por este projeto.
