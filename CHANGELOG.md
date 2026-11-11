# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.4] - 2026-11-11
### Adicionado
- Nova interface moderna: janela sem borda, título customizado, menu lateral,
  knob circular de ganho e interruptores.
- 4 temas de cores selecionáveis (Violeta Noturno, Âmbar, Ciano Gelo, Rubi).
- Ícone na bandeja do sistema; fechar/minimizar envia para a bandeja.
- Opção "Iniciar com o Windows (na bandeja)" — no app e no instalador.
### Corrigido
- Crash de COM (0xC0000005 em `_ctypes`): os endpoints de áudio passam a usar
  `QueryInterface` em vez de `cast()`, eliminando o double-release de ponteiros
  COM que o coletor de lixo disparava em qualquer thread. App agora estável.
- Auto-recuperação de COM: os controles re-resolvem o endpoint se ele for
  invalidado (ex.: reconectar o dispositivo).

## [1.0.3] - 2026-11-11
### Adicionado
- Verificação automática de atualização ao abrir o app.
- Barra de atualização no topo da janela: mostra a nova versão e baixa com
  barra de progresso visível, abrindo o instalador ao final. Opcional — dá para
  adiar ("Depois") ou ativar "Atualizar automaticamente" (baixa sem clique).

## [1.0.2] - 2026-11-11
### Corrigido
- Pipeline de release (CI): `build.py` quebrava no runner do GitHub por causa de
  caractere não-ASCII na saída (cp1252). Agora força UTF-8. O instalador v1.0.1
  chegou a ser compilado no CI, mas o release não foi publicado por esse erro.

## [1.0.1] - 2026-11-11
### Adicionado
- Crédito "Desenvolvido por DZK" no app (janela, rodapé e linha de comando).
- Licença MIT (`LICENSE`) — projeto oficialmente open source.
- README destacando o propósito open source e de gestão do uso do AM8.
### Observação
- Primeira atualização publicada para validar o fluxo de auto-update.

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
