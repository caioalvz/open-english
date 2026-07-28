# Emily English Tutor - instruções para o Claude Code

Este é um tutor de inglês por voz (nome: **Emily**) que roda 100% localmente
(STT, LLM e TTS locais, sem custo, sem internet no dia a dia). A interface é
visual sci-fi HUD (waveform), e a persona/IA se chama Emily. Veja
[README.md](README.md) para a arquitetura completa.

## Comando "install emily"

Quando o usuário disser algo como **"install emily"**, "instala a Emily",
"faz o setup do tutor" ou equivalente - normalmente a primeira vez que ele
abre este projeto numa máquina nova - faça o seguinte:

1. Antes de rodar qualquer coisa, avise o usuário que o setup vai baixar uns
   **7-8GB** (PyTorch, modelo Ollama de ~4.9GB, voz Piper, modelo Whisper) e
   confirme que ele quer prosseguir - é uma ação de download que exige
   permissão explícita.
2. Confirme os pré-requisitos abaixo (o script também valida e avisa se
   faltar algo, mas é bom já checar antes):
   - Python 3.12 (https://www.python.org/downloads/release/python-3120/,
     marcando "Add python.exe to PATH")
   - Ollama (https://ollama.com/download)
   - GPU NVIDIA é opcional. O `setup.ps1` detecta automaticamente se há GPU
     NVIDIA e quanta VRAM tem, e escolhe sozinho o tamanho certo do modelo
     de linguagem e do Whisper (modelo menor em GPUs fracas ou sem GPU,
     ajustando `config.yaml` sem precisar de intervenção manual).
3. Rode `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` a
   partir da raiz do projeto.
4. Esse setup também registra o comando `run emily` no PATH do usuário
   (variável de ambiente), para funcionar em qualquer terminal, de qualquer
   pasta - não só dentro deste projeto ou dentro do Claude Code.
5. Quando terminar, avise o usuário que a instalação está pronta, que para
   rodar a Emily depois é só digitar **"run emily"**, e que isso funciona
   tanto aqui no Claude Code quanto em qualquer terminal (cmd.exe ou
   PowerShell) - mas só em terminais abertos **depois** do setup, já que o
   PATH só é recarregado em processos novos.

## Comando "run emily"

Quando o usuário disser algo como **"run emily"**, "roda a Emily", "inicia o
tutor" ou equivalente, faça o seguinte:

1. Rode `run emily` diretamente (o setup já registrou isso no PATH). Se der
   "comando não encontrado" (ex: PATH ainda não recarregado nesta sessão do
   Claude Code), use o caminho completo como fallback:
   `powershell -ExecutionPolicy Bypass -File scripts\run_emily.ps1`
2. Esse script detecta sozinho se é a primeira execução nesta máquina
   (verifica se `.venv`, `bin\piper\piper.exe` e a voz Piper já existem). Se
   não existirem, ele roda `scripts\setup.ps1` automaticamente antes de abrir
   o app - ou seja, "run emily" também funciona como primeira instalação, só
   que sem o aviso prévio do passo 1 do "install emily". Se o usuário ainda
   não instalou nada, prefira usar o fluxo de "install emily" acima para
   avisar sobre o download antes.
3. Se o setup automático for disparado aqui, avise sobre os ~7-8GB de
   download e confirme antes de deixar o script continuar.
4. Depois que o app abrir (janela "Emily - English Tutor"), ele fica rodando
   escutando o microfone continuamente - não precisa fazer mais nada, só
   avisar o usuário que está pronto para conversar em inglês.

## Coisas a saber sobre este projeto

- Todo código está em `app/`. `config.yaml` controla o nome do tutor
  (`tutor.name`), modelos, voz e sensibilidade do microfone (VAD).
- A progressão segue os CEFR Can-Do Statements (Conselho da Europa) - ver
  `app/curriculum.py`. A Emily fala primeiro em toda sessão: se apresenta na
  primeira vez, ou puxa assunto com um tópico do nível estimado do aluno nas
  vezes seguintes, em vez de esperar em silêncio.
- O progresso do aluno (erros recorrentes, vocabulário, nível estimado) fica
  em `data/tutor.db` (SQLite) - não versionar isso no git, é dado local do
  usuário.
- Logs de execução vão para `data/tutor.log`.
- `scripts/run.cmd` é o "shim" que faz `run emily` funcionar como comando de
  terminal de verdade (ele existe na pasta que o setup adiciona ao PATH).
- `bin/`, `.venv/`, `data/voices/*.onnx*`, `data/*.db`, `data/*.log` não
  devem ir para o repositório (são baixados/gerados pelo setup) - confira o
  `.gitignore`.
