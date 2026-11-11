# Rota — apoio à decisão para o aluno dessemestralizado

**Protótipo funcional executável.** Universidade Federal da Bahia · Instituto de
Computação · ADMF01 Sistemas de Apoio à Decisão · 2026.2.

---

## A decisão que este sistema apoia

Um aluno **dessemestralizado** é o que saiu do bloco do seu período: reprovou,
trancou, trabalhou, e hoje cursa matérias de três semestres diferentes ao mesmo
tempo. Na semana da matrícula ele precisa decidir **o que pedir** — e decide no
escuro, porque as três informações que governam a decisão moram em telas
separadas do SIGAA e nenhuma delas conversa com as outras:

1. **Pré-requisito** — o que já está destravado;
2. **Oferta** — se a disciplina costuma abrir no semestre que ele quer;
3. **Fila de vaga** — se, estando destravada e ofertada, ele chega a conseguir
   a vaga. Esta é a que ninguém calcula, e é regida por norma pública.

O Rota junta as três e devolve **caminhos de formatura hierarquizados**: cada
caminho diz a data de conclusão, quantas disciplinas por semestre exige, e como
isso se compara ao ritmo que o aluno de fato tem. A inversão é proposital —
o aluno diz *"quero me formar até X"* e o sistema responde *o que isso custa*,
em vez de sugerir uma grade e pedir que ele confie.

> **Isto não é um sistema de recomendação.** Ele não escolhe a disciplina. Ele
> hierarquiza alternativas, aceita cenários ("e se eu reprovar isto?"), mostra a
> conta por trás de cada número e deixa a escolha com o aluno. Onde o sistema
> não sabe, ele diz que não sabe.

**Classificação da decisão:** nível **operacional/tático**, grau
**semiestruturado**. As restrições (pré-requisito, paridade de oferta, carga,
norma de alocação) são formalizáveis; a função de preferência do aluno —
trabalhar, priorizar o TCC, evitar certa disciplina — não é, e por isso
permanece com ele.

---

## Rodando em dois minutos (modo demonstração)

O modo demonstração **não precisa de conta no SIGAA**. Ele carrega um aluno
**fictício** de Ciência da Computação, dessemestralizado, montado sobre a estrutura
curricular ativa (G20251X), os pré-requisitos e a oferta de 2023.1 a 2026.2 reais do curso.

```bash
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app:app --port 8012
```

Abra <http://127.0.0.1:8012> e clique em **"Entrar no modo demonstração"**.

Testado em Python 3.12 (Linux). São quatro dependências e nenhuma compila.

### Rodando com um aluno real

O Rota não fala com o SIGAA diretamente: ele consome a
[`sigaa-ufba-api`](https://github.com/caioalcarria/sigaa-ufba-api), uma API
pública construída para este trabalho que faz login com a sessão do próprio
aluno. Suba-a primeiro e aponte o Rota para ela:

```bash
export SIGAA_API=http://127.0.0.1:8000     # é o padrão
python -m uvicorn app:app --port 8012
```

**Nada é gravado.** O login vai direto ao SIGAA, nenhuma credencial é salva em
disco ou banco, e o espelho dos dados mora em memória e morre com o processo.

---

## Arquitetura

```
  navegador  ──HTTP──▶  Rota (FastAPI)  ──HTTP──▶  sigaa-ufba-api  ──▶  SIGAA UFBA
  HTML/CSS/JS            app.py                    (projeto à parte)
  sem build              nucleo/*.py
                         espelho em memória
```

Três camadas, e a fronteira entre elas é deliberada:

- **`web/`** — HTML, CSS e JavaScript sem framework e **sem etapa de build**.
  O professor abre o `index.html` e lê o que roda; não existe bundle gerado.
- **`app.py`** — a API HTTP. Orquestra, espelha e devolve. Não decide nada.
- **`nucleo/`** — onde mora a decisão. Cada módulo responde uma pergunta e
  nenhum deles sabe que existe uma tela.

O **espelho em memória** existe por uma razão concreta: a API do SIGAA aceita
no máximo 6 requisições simultâneas por token. Sem o espelho, cada ajuste de
cenário na tela refaria a busca inteira e tomaria 429. Com ele, a conversa com
a origem acontece uma vez e os cenários rodam localmente.

Diagrama completo: [`docs/arquitetura.md`](docs/arquitetura.md).

| rota | o que faz |
|---|---|
| `POST /api/login` | troca usuário e senha por um token de sessão |
| `POST /api/painel` | o retrato: situação, pendências, oferta, fila, mineração |
| `POST /api/caminhos` | os caminhos de formatura possíveis, hierarquizados |
| `POST /api/plano` | a grade semestre a semestre de um caminho escolhido |
| `POST /api/e-se` | cenários: reprovar, pular um semestre, fixar disciplina |
| `GET /api/status` | saúde do Rota e da API de origem |

---

## As funções analíticas

Três estão **em uso no sistema**. Duas foram **testadas e rejeitadas**, e a
evidência da rejeição está no repositório — ela é parte do resultado.

### 1. Sumarização — `nucleo/situacao.py`, `_ritmo()` em `app.py`

| | |
|---|---|
| **Entrada** | histórico completo e quadro de integralização por categoria |
| **Processamento** | agrega carga e componentes por categoria, **limitando ao teto de cada uma** (excedente de complementares não compensa optativa), e calcula o ritmo como média móvel de aprovações nos últimos 5 semestres cursados, descartando semestres de trancamento total e o semestre em curso |
| **Resultado decisório** | "faltam 18 matérias" e "você aprova 3,2 por semestre" — é o par que torna um prazo de formatura verificável em vez de desejado |

### 2. Agrupamento — `nucleo/mineracao.py:agrupar()`

k-médias em Python puro, sobre as pendências.

| | |
|---|---|
| **Entrada** | cada pendência em 4 eixos: quantas matérias ela destrava, em que fração dos semestres ela abriu, quanto está atrasada na matriz, carga horária |
| **Processamento** | padronização z-score (sem ela a carga horária domina e o agrupamento vira "por carga horária"), início **determinístico** por quantis — sem sorteio, para o resultado ser reproduzível —, e o **k não é arbitrado**: testa k=2,3,4 e fica com a maior silhueta média, descartando qualquer k que produza grupo de um só membro |
| **Resultado decisório** | a ordem de ataque. "Destrava o caminho" vem antes de "Encaixe livre" quando há disputa por vaga |

TCC e estágio ficam **fora** do agrupamento: eles nunca abrem turma, então
entrariam com raridade 1,0 e o método os leria como as disciplinas mais raras
do curso.

### 3. Associação — `nucleo/mineracao.py:regras_de_cooferta()`

Apriori (AGRAWAL & SRIKANT, 1994) em Python puro, sobre o histórico de oferta.

| | |
|---|---|
| **Entrada** | 8 semestres de oferta; **um semestre é uma transação**, uma disciplina ofertada é um item |
| **Processamento** | geração por níveis com poda, suporte mínimo de 2 semestres; a confiança de um par é a **menor** das duas direções, não a maior |
| **Resultado decisório** | quais pares podem ser planejados no mesmo semestre. No caso de referência, MATB02 e MATB09 coincidiram em **2 de 8** semestres: planejar as duas juntas é aposta |

A leitura é honesta sobre o que não achou: *lift* em torno de 1 significa
independência, e a tela diz isso em vez de despejar 36 regras vazias.

### Rejeitadas: regressão e classificação

Tentei prever **chance de aprovação por disciplina** e a função não se
sustentou. Foram três tentativas, com variáveis e alvos diferentes, por isso os
três AUC abaixo são medidas distintas e não a mesma repetida.

> **Os scripts estão aqui; o dado de entrada não.** As 42 observações são um
> histórico acadêmico real, anonimizado, e não foram publicadas. Então **a
> validação preditiva não se reproduz a partir deste repositório**, e os números
> abaixo são o registro dela, não uma promessa de reexecução. Os scripts rodam
> contra qualquer histórico no mesmo formato, que é o uso para o qual existem.

- `validacao/backtest.py` — escore aditivo de risco com pesos declarados,
  validação fora da amostra no eixo do tempo (para prever o período P, só
  enxerga até P−1): **AUC 0,5693** (IC 0,39–0,75) em 42 casos. Laudo em
  [`validacao/resultado-backtest.md`](validacao/resultado-backtest.md).
- `validacao/ajuste.py` — regressão logística sobre as **mesmas** 5 variáveis,
  com os pesos estimados em vez de arbitrados, 30 casos fora da amostra:
  **AUC 0,5848** (0,70 dentro da amostra). Estimar os pesos não salvou o modelo.
- Regressão logística sobre o **esforço do semestre** (carga horária, número de
  matérias e tempo de curso), *rolling-origin*, 6 dobras, 25 previsões:
  **AUC 0,6905, com intervalo de confiança de 95% entre 0,49 e 0,88**, que
  inclui o acaso. Esse script é `atividade/funcoes_analise.py`, da entrega de
  *funções de análise de dados* da disciplina: usa *scikit-learn* e **não está
  neste repositório**, cujas dependências são deliberadamente quatro.

O código do modelo rejeitado está em `validacao/modelo_rejeitado/`, **fora do
`nucleo/`**, exatamente para que a separação fique visível: ele não roda no
produto, existe para que a rejeição seja reproduzível.

> Um número de 0 a 100 que o sistema não consegue sustentar é pior do que não
> ter número nenhum, porque o aluno decide confiando nele. Retirar a
> funcionalidade foi o resultado da validação, não uma desistência.

---

## A fila de vaga — Resolução CAE nº 02/2017

A parte do sistema que nenhuma ferramenta de mercado tem. Destravar o
pré-requisito e **conseguir a vaga** são problemas diferentes; na UFBA o segundo
é determinístico e público, e o aluno sente a regra agindo contra ele sem saber
o nome dela.

`nucleo/fila.py` implementa a norma com os artigos citados no próprio código:

- **Art. 2º II** — o Semestre de Avaliação é *"o primeiro semestre da matriz
  curricular do qual ainda não tenha cumprido mais da metade dos componentes"*.
  O cálculo é **exato**, não estimado: a matriz inteira vem de uma rota pública
  da API (`/v1/publico/cursos/{id}/estruturas/{id}`).
- **Art. 4º** — os seis níveis de prioridade, na ordem da norma. A ordem
  importa: provável concluinte (II) vem antes de não semestralizado (III).
- **Art. 6º** — o desempate: IAP, menos reprovações por falta, menos
  trancamentos, maior período de ingresso.

A tela mostra a derivação **nível a nível**, para o aluno conferir de onde saiu
o número que define a posição dele.

---

## Dados, privacidade e procedência

- **Nenhuma credencial é persistida.** Login direto no SIGAA, sessão em
  memória, morre com o processo.
- O snapshot de demonstração (`dados_demo.json`) é de um aluno **fictício**.
  É real e público o que é do curso de Ciência da Computação: a estrutura
  G20251X, os pré-requisitos, a oferta de 2023.1 a 2026.2 (consulta pública de
  turmas do SIGAA) e as turmas de 2026.2. É inventado o que seria de uma pessoa: histórico, notas,
  trancamentos e atividades. Os docentes aparecem como `DOCENTE nn` — o
  repositório é público e nome de terceiro amarrado a turma e horário não tem
  por que estar nele.
- A validação do modelo (`validacao/`) roda sobre um histórico real
  anonimizado (`validacao/dados_reais_anonimizados.json`), com o mesmo
  tratamento dos docentes.
- Toda tela que mostra oferta **assina a procedência e o período** do dado, e
  o relatório impresso avisa, em negrito, que **não é documento oficial**.

## Qualidade de interface

`validador/` é um validador de usabilidade próprio que roda nas seis telas e
checa contraste (WCAG AA), tamanho de alvo (24×24), tamanho de fonte,
comprimento de linha e densidade. A política é **zero erros**; o resultado
atual é 0 erros nas seis telas, e os avisos que sobram estão registrados.

Ele já pegou defeitos reais que eu tinha introduzido — rótulo de gráfico a
10,5 px (ilegível em projetor) e um link com contraste 3,43:1 e alvo de 14,6 px.

---

## Mapa do repositório

```
app.py                      API HTTP: orquestra, espelha, devolve
requirements.txt            4 dependências
nucleo/
  situacao.py               fonte única de "quanto falta" (sumarização)
  plano.py                  monta a grade semestre a semestre
  oferta.py                 padrão de oferta por disciplina
  fila.py                   Resolução CAE 02/2017: posição na fila de vaga
  mineracao.py              k-médias e apriori, em Python puro
  sigaa.py                  cliente da sigaa-ufba-api (com semáforo de 6)
web/                        interface, sem framework e sem build
validacao/
  backtest.py               validação temporal do modelo rejeitado
  dados_reais_anonimizados.json   o histórico real que a validação usa
  resultado-backtest.md     o laudo: AUC 0,5693
  modelo_rejeitado/         o modelo que NÃO roda no produto
validador/                  validador de usabilidade (6 telas, 0 erros)
docs/arquitetura.md         diagrama e fluxo de dados
dados_demo.json             aluno fictício da demonstração
DECLARACAO-IA.md            uso de IA na construção deste trabalho
```

## Referências

- AGRAWAL, R.; SRIKANT, R. *Fast algorithms for mining association rules.*
  VLDB, 1994.
- UFBA. **Resolução CAE nº 02/2017** — critérios de alocação de vagas.
  <https://colmat.ufba.br/sites/colmat.ufba.br/files/resolucao_no_02.2017_-_cae.pdf>
- API de origem: [`sigaa-ufba-api`](https://github.com/caioalcarria/sigaa-ufba-api)
