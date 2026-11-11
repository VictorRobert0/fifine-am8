# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.6] - 2026-11-11
### Corrigido
- **Crash na inicialização / interface "sumindo"** (regressão do 1.0.5): a barra de
  atualização era ancorada com `pack(before=...)` apontando para **ela mesma** (o
  banner é o primeiro filho, ainda não empacotado, do contêiner de conteúdo).
  Isso lançava `TclError: window isn't packed`. No 1.0.5 a verificação de
  atualização roda de forma síncrona no `__init__`, então a exceção **derrubava a
  abertura do app**; no 1.0.4 ela rodava dentro de um `after()` e era engolida
  pelo tratador global — por isso o **aviso/botão de atualização nunca aparecia**.
  Agora o banner ancora antes do primeiro filho que **não seja** o próprio banner.
- Com isso, voltam a funcionar: abrir o app, navegar entre Microfone/Mic
  Virtual/Presets/Ajustes e o aviso "Procurando atualizações… / Você está na
  versão mais recente / Nova versão disponível".

## [1.0.5] - 2026-11-11
### Corrigido
- Atualização "estilo launcher": antes o app fechava ao atualizar e **não
  voltava** (o instalador era disparado sem elevação limpa e sem reabrir o app).
  Agora o updater roda o instalador em modo silencioso e elevado (um único UAC),
  fecha a instância em execução, troca os arquivos e **reabre o app sozinho** já
  na versão nova.
- Preferências não eram lembradas: o `config.json` era salvo dentro de
  `Program Files` (sem permissão de escrita). Agora fica em
  `%APPDATA%\Fifine AM8 Control\` — e migra as preferências antigas uma vez. O
  log de erros também passou para essa pasta gravável.
### Adicionado
- Aviso de verificação ao abrir: "🔄 Procurando atualizações…" e, em seguida,
  "✓ Você está na versão mais recente" ou a oferta da nova versão com barra de
  progresso ("Baixando…" → "Instalando e reiniciando…").
- Instalador fecha o app em execução antes de trocar os arquivos
  (`CloseApplications`), evitando falhas por arquivo travado.
### Removido
- Interface antiga (`fifine_gui.py`): descontinuada em favor do design novo
  (`fifine_ui.py`). Removido o atalho que ainda apontava para ela.

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
