<img src="assets/emily_icon.png" alt="Emily" width="96" height="96">

# Emily - English Tutor

Um tutor de inglês pessoal por voz chamado **Emily**, rodando **100%
localmente** no seu PC: sem custo de API, sem depender de internet no dia a
dia. Você conversa por voz, ela corrige seus erros, ensina vocabulário novo
e vai ajustando a dificuldade conforme você evolui - tudo com uma interface
visual própria: um orbe orgânico e quente que "respira" e reage à sua voz,
em vez de um HUD frio de ficção científica (sem avatar/rosto).

## Como funciona

```
Microfone (streaming) -> Silero VAD (detecta quando voce fala)
   -> faster-whisper (STT, local)
   -> Ollama / Llama 3.1 8B (Emily, a "professora", local)
   -> Piper TTS (voz feminina, local)
   -> UI sci-fi HUD anima a waveform
   -> correcoes e vocabulario novo ficam salvos localmente (SQLite)
```

Nada disso chama serviços externos. Depois do setup inicial (que baixa os
modelos), o app roda inteiramente offline.

## Pré-requisitos

Instale estas duas coisas manualmente antes do setup:

1. **Python 3.12** - https://www.python.org/downloads/release/python-3120/
   (no instalador, marque "Add python.exe to PATH")
2. **Ollama** - https://ollama.com/download

**GPU NVIDIA**: não é obrigatória. O setup detecta automaticamente se você
tem uma GPU NVIDIA e quanta VRAM ela tem, e escolhe os modelos certos para
o seu hardware (sem precisar editar nada na mão):

| Hardware detectado | Modelo de linguagem | Whisper | Onde roda |
|---|---|---|---|
| GPU NVIDIA com 8GB+ VRAM | `llama3.1:8b-instruct` | `small.en` | GPU |
| GPU NVIDIA com 4-7GB VRAM | `llama3.2:3b-instruct` | `small.en` | GPU |
| GPU NVIDIA com <4GB VRAM | `llama3.2:3b-instruct` | `base.en` | GPU |
| Sem GPU NVIDIA (CPU) | `llama3.2:3b-instruct` | `base.en` | CPU |

Sem GPU, o app funciona igual, só que as respostas do tutor demoram mais.
Desenvolvido e testado numa RTX 4060 (8GB VRAM).

## Instalação

Depois de clonar o repositório:

```bash
git clone <url-do-seu-repo> emily-english-tutor
cd emily-english-tutor
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

O setup faz tudo sozinho:
- Cria um ambiente virtual Python (`.venv`)
- Instala PyTorch (com CUDA se detectar GPU NVIDIA), faster-whisper,
  PyQt6, etc.
- Baixa o modelo de linguagem via Ollama (`llama3.1:8b-instruct-q4_K_M`,
  ~4.9GB)
- Baixa o binário do Piper TTS + a voz feminina em inglês (`en_US-hfc_female-medium`)
- Baixa o modelo do Whisper (`small.en`)

No total, baixa uns **7-8GB** - só precisa de internet nessa primeira vez.
Depois disso, o app roda 100% offline.

### Se você estiver usando o Claude Code

Basta abrir a pasta do projeto no Claude Code e digitar:

```
install emily
```

Ele confirma os pré-requisitos, avisa sobre o download (~7-8GB) e roda o
setup adaptado ao seu hardware. Depois disso, para abrir o tutor é só
digitar `run emily` (veja abaixo).

## Rodando (depois de instalado)

O `setup.ps1` registra o comando `run emily` no PATH do Windows. Depois
disso, **em qualquer terminal (cmd.exe ou PowerShell), de qualquer pasta**,
basta digitar:

```
run emily
```

> **Importante:** o registro no PATH só é lido por terminais abertos *depois*
> do setup. Se o setup acabou de rodar, feche e abra um terminal novo (ou
> abra um novo terminal no Claude Code) antes de usar `run emily`.

Isso também funciona digitando `run emily` diretamente no chat do Claude
Code. Se preferir rodar sem depender do PATH:

```bash
powershell -ExecutionPolicy Bypass -File scripts\run_emily.ps1
```

Esse script detecta sozinho se é a primeira vez (roda o setup automático se
faltar algo) e depois abre o app. Se preferir rodar direto sem essa checagem:

```bash
.venv\Scripts\python.exe -m app.main
```

Uma janela "Emily - English Tutor" abre e o microfone já fica escutando
continuamente - fale em inglês, o tutor responde por voz e mostra as
correções na tela.

## Configuração

Tudo ajustável em [config.yaml](config.yaml):

| Seção | O que controla |
|---|---|
| `tutor.name` | Nome do tutor (padrão: Emily) |
| `ollama.model` | Qual modelo local usar como professor |
| `stt.device` | `cuda` ou `cpu` - troque para `cpu` se não tiver GPU NVIDIA |
| `vad.min_silence_ms` | Quanto tempo de silêncio até considerar que você parou de falar |
| `vad.min_utterance_rms` | Sensibilidade mínima do microfone (filtra ruído) |
| `tts.voice_path` | Qual voz do Piper usar |

## Estrutura do projeto

```
app/
  main.py       # loop principal: microfone -> STT -> LLM -> TTS -> UI
  audio_io.py   # captura de mic + VAD (deteccao de fala)
  stt.py        # faster-whisper (voz -> texto)
  tts.py        # Piper TTS (texto -> voz)
  tutor.py      # cliente Ollama + persona da Emily
  curriculum.py # niveis CEFR e topicos de conversa por nivel
  memory.py     # progresso do aluno (SQLite)
  theme.py      # identidade visual (paleta + desenho do orbe)
  ui.py         # janela e o orbe organico (PyQt6)
config.yaml     # configuracao central
assets/
  emily_icon.ico / .png  # icone do app (gerado por scripts/generate_icon.py)
scripts/
  setup.ps1       # instalacao (roda uma vez, tambem registra "run emily" no PATH)
  run_emily.ps1   # roda o setup se preciso + abre o app
  run.cmd         # shim que faz "run emily" funcionar em qualquer terminal
  generate_icon.py # regenera o icone a partir de app/theme.py
data/
  tutor.db      # progresso do aluno (nao versionado)
  tutor.log     # logs de execucao (nao versionado)
  voices/       # voz Piper baixada no setup (nao versionado)
bin/
  piper/        # binario do Piper TTS (nao versionado)
```

## Progressão / como ela "aprende com você"

A progressão é baseada nos **CEFR Can-Do Statements** ([Common European
Framework of Reference for Languages](https://www.coe.int/en/web/common-european-framework-reference-languages),
Conselho da Europa) - o padrão internacional de referência para nível de
conversação em língua estrangeira. Ver [app/curriculum.py](app/curriculum.py):

- O número de sessões concluídas estima seu nível CEFR (A1 → C1), que
  calibra a complexidade das perguntas e do vocabulário que a Emily usa.
- Cada nível tem uma lista de tópicos de conversa apropriados (ex: A1 =
  se apresentar e família; B1 = viagens e opiniões; C1 = temas abstratos e
  debate).
- A cada resposta, a Emily extrai (via JSON estruturado) as correções feitas
  e o vocabulário novo introduzido, salvando em `data/tutor.db`. Isso calibra
  o nível e reforça o que você mais erra ao longo do tempo.
- **Ela puxa assunto primeiro**: na primeira vez que você abre o app, ela se
  apresenta; nas vezes seguintes, ela já abre com uma saudação e uma pergunta
  sobre um tópico do seu nível (sem repetir o tópico da vez anterior), em vez
  de ficar esperando calada você começar a falar.
- O histórico recente da conversa também persiste entre execuções, então ela
  lembra do que vocês conversaram da última vez.

## Solução de problemas

- **App abre mas não escuta nada**: confira `data/tutor.log` - a waveform
  fica vermelha ("ERROR") se algo falhar num turno, e o app tenta se
  recuperar sozinho.
- **Sem GPU NVIDIA / erro de CUDA**: o setup já deveria ter configurado
  `stt.device: cpu` automaticamente. Se ainda assim der erro de CUDA, edite
  `config.yaml` manualmente e confirme que `stt.device` está `cpu`.
- **Quer forçar um modelo diferente do que o setup escolheu**: edite
  `config.yaml` (`ollama.model`, `stt.model_size`) depois do setup e rode
  `ollama pull <modelo-novo>` manualmente.
- **Quer trocar a voz**: baixe outra voz feminina em
  https://github.com/rhasspy/piper/blob/master/VOICES.md e aponte
  `tts.voice_path`/`tts.config_path` em `config.yaml` para os novos
  arquivos `.onnx`/`.onnx.json`.
- **Ollama não encontrado**: confirme que o app do Ollama está instalado e
  rodando (ele roda como serviço em segundo plano depois de instalado).

## Limitações conhecidas

- Sem "barge-in": você não interrompe o tutor enquanto ele fala, precisa
  esperar ele terminar.
- Qualidade das correções depende do modelo local de 8B parâmetros - é
  sólida, mas não perfeita.
