# Sistema de progressão por aulas (A1 → C2)

## Objetivo

Substituir o modelo atual de progresso ("quantas vezes o app foi aberto") por
um modelo real de currículo: **uma trilha sequencial de aulas, do A1 ao C2**,
onde o aluno só avança quando genuinamente completa cada aula. Fechar o app
sem interagir, ou interromper no meio, nunca deve fazer o progresso avançar -
a mesma aula deve ser oferecida de novo na próxima abertura.

Este documento descreve a arquitetura para implementar isso. Não implementa
código ainda - é a referência para quando formos construir.

## Conceitos: Sessão vs. Aula

Hoje esses dois conceitos estão fundidos em `Memory.start_session()`. Precisam
ser separados:

- **Sessão** = uma execução do app, do momento que abre até que fecha.
  Continua existindo como está hoje (tabela `sessions`), serve só para
  agrupar logs/telemetria.
- **Aula (lesson)** = uma unidade de currículo especifica (nivel + topico +
  objetivo). E a unidade real de progresso.

Uma sessão pode conter **zero, uma ou várias tentativas de aula**. Se o aluno
continua conversando depois de concluir uma aula, a Emily naturalmente
introduz a próxima, tudo dentro da mesma sessão/janela aberta.

## Estrutura do currículo

Cada nível CEFR (A1, A2, B1, B2, C1, C2) tem uma **lista ordenada e fixa de
aulas**. Cada aula tem:

```python
@dataclass
class Lesson:
    id: str                 # ex: "A1-03"
    level: str               # "A1".."C2"
    title: str                # "Talking about your daily routine"
    can_do_objective: str     # objetivo no estilo CEFR can-do, o que da
                               # pra considerar "concluido"
    focus_vocab: list[str]    # 4-8 palavras/expressoes alvo da aula
    min_student_turns: int    # piso minimo de falas reais do aluno (default 3-4)
```

Os objetivos (`can_do_objective`) devem ser derivados dos **CEFR Can-Do
Statements** oficiais (mesma fonte já usada em `app/curriculum.py`), só que
agora aplicados por aula individual em vez de um descritor genérico por
nível inteiro. Exemplo:

```
A1-01: "Introducing yourself"
  can_do_objective: "Can say their name, where they're from, and one basic
                      fact about themselves when asked directly."
  focus_vocab: ["my name is", "I'm from", "nice to meet you", "I live in"]
  min_student_turns: 3

A1-02: "Talking about family"
  can_do_objective: "Can name 2-3 family members and say one simple fact
                      about each (age, job, or where they live)."
  ...
```

Isso substitui `TOPICS_BY_LEVEL` (lista solta de strings) por uma lista
estruturada e sequencial. O nivel C2 precisa ser adicionado (hoje o
currículo só vai até C1).

## Modelo de dados (SQLite)

### Tabela `lesson_progress` (ponteiro único, 1 linha)

```sql
CREATE TABLE lesson_progress (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton, so uma linha
    current_lesson_id TEXT NOT NULL DEFAULT 'A1-01',
    updated_at TEXT NOT NULL
);
```

Esse é o ponteiro de "onde o aluno está" na trilha. Só é atualizado quando
uma aula é **confirmada como concluída**.

### Tabela `lesson_attempts` (histórico de tentativas)

```sql
CREATE TABLE lesson_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    lesson_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    student_turn_count INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,   -- 0/1, SEMPRE comeca em 0
    completion_reason TEXT                   -- log do porque foi (ou nao) concluida
);
```

Toda tentativa começa com `completed = 0`. **Só uma confirmação positiva e
explícita muda isso para 1** - nunca um valor padrão, nunca algo assumido em
caso de fechamento abrupto/crash. Isso garante que a regra "fechar sem
interagir = não conta" funciona até em cenários de crash/queda de energia,
de graça, sem precisar de nenhum tratamento especial de erro.

## Fluxo de execução

```
1. App abre -> cria sessao (como hoje).
2. Le lesson_progress.current_lesson_id -> essa e a aula desta tentativa.
3. Cria uma linha em lesson_attempts (completed=0).
4. Emily inicia a conversa (saudacao proativa) JA CONTEXTUALIZADA na aula
   atual: sabe o topico, o objetivo, o vocabulario alvo.
5. A cada turno do aluno:
   a. student_turn_count += 1
   b. A resposta da Emily (JSON estruturado) inclui um novo campo:
      "lesson_complete": true/false
      "lesson_complete" so pode virar true se:
        - student_turn_count >= lesson.min_student_turns E
        - a Emily julga (semanticamente) que o objetivo foi coberto
6. Se lesson_complete=true num turno:
   - marca lesson_attempts.completed = 1, completion_reason = "..."
   - avanca lesson_progress.current_lesson_id pra proxima aula da trilha
   - Emily comemora brevemente e PODE emendar na proxima aula na mesma
     conversa, se o aluno continuar falando
7. Se a sessao/app fecha (de qualquer jeito) sem lesson_complete=true:
   - nao faz nada (o default completed=0 ja resolve)
   - proxima abertura: current_lesson_id nao mudou, entao a MESMA aula
     e oferecida de novo
```

## Critério de conclusão (anti-fraude)

Dois portões, ambos obrigatórios:

1. **Piso mecânico**: `student_turn_count >= lesson.min_student_turns`
   (conta só turnos com transcrição não-vazia - já temos isso no pipeline).
2. **Julgamento semântico da Emily**: o modelo, no mesmo JSON que já retorna
   `reply`/`corrections`/`new_vocab`, agora também retorna `lesson_complete`
   e um `lesson_notes` curto explicando o porquê. O prompt (ver
   `emily_lesson_system_prompt.md`) instrui explicitamente a não marcar como
   concluída por complacência - só quando o objetivo foi genuinamente
   abordado na conversa.

Isso evita os dois extremos: um aluno "gamificando" com respostas vazias
(bloqueado pelo piso mecânico), e o modelo sendo bonzinho demais e liberando
cedo demais (bloqueado por exigir julgamento genuíno, reforçado no prompt).

## Aula difícil demais / travamento

Se `lesson_attempts` mostrar 3+ tentativas seguidas incompletas para o
mesmo `lesson_id`, a Emily deve reconhecer isso no início da próxima
tentativa (ex: "Vamos tentar de um jeito mais simples dessa vez") e adaptar
a complexidade da mesma aula, sem pular ela e sem repetir literalmente o
mesmo roteiro. Isso pode ser implementado como uma flag simples passada pro
prompt: `struggling: true` quando essa condição é detectada.

## Como o ensino acontece dentro de cada aula (o "arco pedagógico")

Ter um objetivo e vocabulário-alvo não é suficiente sozinho - a Emily
precisa de alguma estrutura de ensino, não só evitar fugir do tópico. Cada
aula segue duas fases (calculadas a partir de `student_turns` vs. metade de
`min_student_turns`, sem precisar de estado novo no banco):

1. **Prática guiada** (primeira metade da aula): a Emily modela o uso
   correto do vocabulário-alvo com um exemplo natural antes de pedir que o
   aluno produza, e faz perguntas diretas (não totalmente abertas) que
   praticamente exigem o uso da estrutura-alvo.
2. **Produção livre** (segunda metade em diante): menos modelagem, mais
   conversa genuína - o aluno já teve a chance de praticar o padrão.
3. **Recapitulação no fechamento**: quando a Emily marca `lesson_complete`,
   a própria resposta precisa incluir um resumo caloroso do que o aluno
   demonstrou, em vez de simplesmente cortar para a próxima coisa - reforça
   retenção.

Além disso, no aquecimento de cada aula (só na saudação de abertura), a
Emily pode puxar casualmente uma palavra aprendida numa aula anterior
(repetição espaçada simples, via `Memory.get_review_word`) - usa o
vocabulário que já coletamos em vez de deixá-lo parado no banco.

Ver `docs/emily_lesson_system_prompt.md` para o texto exato injetado no
prompt em cada fase.

## Sem conhecimento prévio (acessibilidade)

Só na **primeiríssima aula que o aluno já teve na vida** (ou seja,
`current_lesson_id == "A1-01"` e nenhuma tentativa anterior concluída em
nenhuma aula), a Emily tem permissão de usar uma ponte bilíngue breve para
garantir que ninguém fica travado sem entender nada:

> "Hi! I'm Emily. Vamos praticar inglês juntos - pode responder em
> português se travar, tá bem? Let's start simple: what's your name?"

Depois disso, ela nunca mais volta a usar português (mantém a imersão em
inglês, calibrada ao nível), a menos que o aluno explicitamente peça ajuda
em português no meio de uma frase.

## O que muda nos arquivos existentes (visão geral, não é a implementação)

- `app/curriculum.py`: `TOPICS_BY_LEVEL` (strings soltas) vira uma lista
  estruturada de `Lesson` por nível, cobrindo A1-C2. `level_from_session_count`
  é removido - o nível passa a ser derivado de `current_lesson_id`
  diretamente (o prefixo antes do traço, ex: "B1-04" -> nível "B1").
- `app/memory.py`: adiciona as tabelas `lesson_progress` e `lesson_attempts`,
  e métodos `get_current_lesson()`, `start_lesson_attempt()`,
  `mark_lesson_complete()`, `count_recent_incomplete_attempts(lesson_id)`.
- `app/tutor.py`: o schema JSON de resposta ganha `lesson_complete` e
  `lesson_notes`; o system prompt passa a receber o contexto da aula atual
  (ver `emily_lesson_system_prompt.md`).
- `app/main.py`: o loop de conversa passa a checar `lesson_complete` a cada
  turno e chamar `mark_lesson_complete()`/avançar o ponteiro quando for o
  caso, em vez de só gravar turnos/correções como hoje.

## Limitações conhecidas (deliberadas, para v1)

- Trilha linear única por currículo, não adaptativa por habilidade
  individual (ex: forte em vocabulário, fraco em gramática) - fica como
  possível v2, usando os dados de `mistakes` que já coletamos.
- Não há "meia-conclusão" - uma aula interrompida não retoma exatamente de
  onde parou dentro da própria conversa, ela é reiniciada do zero na
  próxima tentativa (mas com o mesmo objetivo/tópico). Retomar literalmente
  a frase truncada é mais complexo e não parece necessário para o objetivo
  descrito.
