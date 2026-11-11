# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-11-11
### Adicionado
- Controle de hardware do AM8 via Core Audio: ganho (0–10 dB), mute, volume e
  mute do fone de monitoramento, medidor de nível ao vivo.
- Microfone virtual: ganho digital até +30 dB (além do hardware) com limitador.
- Supressão de ruído **RNNoise** (estilo Discord) + **noise gate** por detecção de voz.
- 5 presets com recomendação de uso: Limpo, Gravação, Stream, Reunião, Voz distante.
- Interface gráfica com abas (Hardware / Mic Virtual) e linha de comando.
- Persistência de preferências (`config.json`) e atalho na Área de Trabalho.
- Atualização automática via GitHub Releases.
- Instalador Windows (Inno Setup) com verificação do VB-Audio Virtual Cable.
- Diagnóstico HID dos controles físicos (`fifine_hid.py`).
