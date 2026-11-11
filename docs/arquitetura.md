# Arquitetura e fluxo de dados

Três diagramas: **onde as coisas moram**, **por onde o dado passa** e **como a
decisão se forma**. Cada um existe porque responde uma pergunta diferente que
alguém faz ao abrir este repositório.

---

## 1. Arquitetura — onde as coisas moram

```mermaid
flowchart LR
  subgraph NAV["Navegador do aluno"]
    UI["web/<br/>HTML · CSS · JS<br/><i>sem framework, sem build</i>"]
  end

  subgraph ROTA["Rota · FastAPI · porta 8012"]
    API["app.py<br/><i>orquestra, espelha, devolve</i>"]
    ESP[("espelho em memória<br/>por token")]
    subgraph NUC["nucleo/ — onde mora a decisão"]
      SIT["situacao.py<br/>quanto falta"]
      PLA["plano.py<br/>grade por semestre"]
      OFE["oferta.py<br/>padrão de oferta"]
      FIL["fila.py<br/>CAE 02/2017"]
      MIN["mineracao.py<br/>k-médias · apriori"]
    end
  end

  SIG["sigaa-ufba-api<br/><i>projeto à parte · porta 8000</i>"]
  UFBA[("SIGAA UFBA")]

  UI -- "HTTP · token de sessão" --> API
  API --> ESP
  API --> SIT & PLA & OFE & FIL & MIN
  API -- "máx. 6 simultâneas<br/>por token" --> SIG
  SIG --> UFBA
```

**A fronteira entre as camadas é deliberada.**

| camada | regra que ela obedece |
|---|---|
| `web/` | não calcula nada que decida. Se um número aparece na tela, ele veio pronto da API — assim o que o aluno lê e o que o relatório imprime não podem divergir. |
| `app.py` | orquestra e espelha. **Não decide.** Quando precisa de uma regra, chama o `nucleo/`. |
| `nucleo/` | cada módulo responde **uma** pergunta e nenhum sabe que existe uma tela. É o que permite testar a regra sem abrir o navegador. |

**Por que existe o espelho em memória.** A API de origem aceita no máximo **6
requisições simultâneas por token** — medido: 10 rotas frias distintas devolvem
6 × `200` e 4 × `429` em 0,0 s. Sem o espelho, cada ajuste de cenário na tela
refaria a busca inteira e tomaria 429 na cara do aluno. Com ele, a conversa com
a origem acontece **uma vez** e todos os cenários rodam locais. O espelho vive
no processo, por token, e morre com ele — não há banco, não há disco.

---

## 2. Fluxo de dados — do SIGAA à tela

```mermaid
flowchart TD
  L["POST /api/login<br/>usuário + senha"] --> T{"token de sessão<br/><i>só em memória</i>"}
  T --> P["POST /api/painel"]

  P --> F1["/v1/me · /v1/integralizacao<br/>/v1/indices · /v1/historico<br/>/v1/grade-horaria"]
  P --> F2["/v1/planejamento/oferta"]
  P --> F3["/v1/planejamento/previsao-oferta"]
  P --> F4["/v1/publico/cursos/.../estruturas<br/><i>matriz curricular · sem token</i>"]

  F1 & F2 & F3 & F4 --> E[("espelho")]

  E --> S["situacao.resumo()<br/><b>sumarização</b>"]
  E --> O["Oferta()<br/>padrão por paridade"]
  E --> FI["fila.posicao()<br/><b>CAE 02/2017</b>"]
  E --> MI["mineracao.agrupar()<br/>mineracao.regras_de_cooferta()<br/><b>agrupamento · associação</b>"]

  S & O & FI & MI --> R["painel<br/><i>um JSON, uma verdade</i>"]
  R --> TELA["as 6 telas"]

  E --> C["POST /api/caminhos<br/>plano.menor_carga_para()"]
  C --> TELA
  E --> ES["POST /api/e-se<br/>cenários"]
  ES --> TELA
```

**Três cuidados que o fluxo esconde e que mudaram o resultado:**

1. **A matriz curricular vem de rota pública, sem token** — matriz é documento
   do curso, não dado pessoal. É o que torna o Semestre de Avaliação **exato**
   em vez de estimado por carga horária (o que teria errado o número que
   governa toda a fila).
2. **`faltando` é uma UNIÃO, não uma lista "E".** O SIGAA devolve a união dos
   códigos de todas as alternativas não satisfeitas. Mostrá-la crua fazia a
   tela dizer que Inteligência Artificial exigia 4 disciplinas quando bastava
   uma. `plano.falta_mesmo()` lê a estrutura OU/E e devolve o caminho mais
   curto.
3. **Chance de oferta 0 não quer dizer "não abre".** TCC e estágio nunca abrem
   turma, e tratar o 0 como "não abre" prendia o TCC fora de qualquer plano —
   ou seja, o aluno nunca se formava, silenciosamente.

---

## 3. Fluxo da decisão — como a resposta se forma

```mermaid
flowchart TD
  A["O aluno diz até quando<br/>quer se formar"] --> B["Quais disciplinas<br/>ainda faltam?"]
  B --> C{"Pré-requisito<br/>destravado?"}
  C -- não --> C1["o que falta mesmo<br/><i>caminho mais curto da expressão OU/E</i>"]
  C -- sim --> D{"Costuma abrir<br/>neste semestre?"}
  D -- não --> D1["empurra para a próxima<br/>janela de paridade"]
  D -- sim --> E{"Cabe na carga<br/>que ele aguenta?"}
  E -- não --> E1["entra no semestre seguinte"]
  E -- sim --> F["entra na grade"]

  F --> G["<b>Caminhos hierarquizados</b><br/>data · carga por semestre · folga"]
  C1 & D1 & E1 --> G

  G --> H["confronta com o<br/><b>ritmo real</b> do aluno"]
  H --> I["<b>Fila da vaga</b><br/>nível na CAE 02/2017"]
  I --> J["<b>Por onde começar</b><br/>agrupamento"]
  J --> K["<b>O que abre junto</b><br/>associação"]
  K --> L(["O ALUNO decide"])

  style L stroke-width:3px
```

O sistema para em `L` de propósito. Ele hierarquiza, mostra a conta e aceita
cenário; não escolhe. A última caixa não é retórica: não existe no código
nenhuma função que devolva "pegue esta disciplina".

---

## O que é projeto à parte

A **`sigaa-ufba-api`** não faz parte deste repositório. Ela é uma API REST
pública e somente leitura para o SIGAA da UFBA, construída para este trabalho,
que faz login com a sessão do próprio aluno e devolve histórico, índices,
integralização, oferta e consultas públicas em JSON.

Repositório: <https://github.com/caioalcarria/sigaa-ufba-api>

A separação importa para a avaliação: o Rota é o **sistema de apoio à decisão**;
a API é a **fonte de dados** que o viabiliza. Misturar os dois num repositório
só esconderia que o SAD depende de uma camada de integração que precisou ser
construída antes — que é, aliás, o ponto de partida do trabalho.
