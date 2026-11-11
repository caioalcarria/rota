# Declaração de uso de inteligência artificial

> **Este texto precisa ser lido e ajustado pelo autor antes da entrega.** Só ele
> pode atestar o que de fato revisou. O rascunho abaixo descreve o uso como ele
> ocorreu; corrija qualquer linha que não corresponda.

ADMF01 — Sistemas de Apoio à Decisão · 2026.2 · UFBA/IC

---

## O que foi usado

Assistentes de IA baseados em modelos de linguagem foram usados **ao longo de
toda a construção** deste trabalho: na escrita de código, na redação de
documentos, na leitura de normas e na revisão crítica das próprias decisões de
projeto.

Não houve uso pontual ou acessório. Declarar o contrário seria falso.

## Em que exatamente

| frente | uso |
|---|---|
| **Código** | escrita e refatoração dos módulos do `nucleo/`, da API em `app.py` e da interface em `web/` |
| **Normas** | leitura da Resolução CAE nº 02/2017 e tradução dos artigos 2º, 4º e 6º em código, com os trechos citados nos próprios docstrings |
| **Análise** | implementação de k-médias e apriori em Python puro, e execução das validações que levaram à rejeição da classificação |
| **Documentação** | redação do README, deste arquivo, do documento de arquitetura e do relatório final |
| **Crítica** | revisão adversarial do próprio sistema: um validador de usabilidade automatizado e simulações de uso por um usuário leigo |
| **Vídeo** | roteiro redigido com IA e revisado por mim; a **narração é a minha voz clonada** (modelo de síntese de fala treinado com gravações minhas), lendo texto que eu escrevi e aprovei; a trilha instrumental também é gerada por IA. Nenhuma frase do vídeo é dita por mim ao vivo, e é por isso que isto está declarado aqui e numa cartela no próprio vídeo |

## O que permaneceu com o autor

- **A escolha do problema.** O recorte do aluno dessemestralizado veio da
  experiência própria de quem passou por ela, não de uma sugestão.
- **A decisão de produto que define o trabalho:** que o sistema **hierarquiza
  alternativas e não recomenda**. Essa restrição foi imposta por mim ao
  trabalho, e foi ela que levou à remoção de funcionalidades que já estavam
  prontas.
- **As rejeições.** Retirar o escore de 0 a 100 e a "chance de passar" foi
  decisão minha diante dos resultados da validação.
- **A verificação do que entrou.** Os números apresentados foram conferidos
  contra o SIGAA real.

## Onde a IA errou, e como isso foi tratado

Registro isto porque omitir seria dar uma impressão falsa de que o uso foi
livre de problemas. Erros que apareceram no caminho e precisaram ser corrigidos:

- um plano de edição automática destruiu dois endpoints de `app.py`, que
  tiveram de ser reconstruídos;
- uma contagem de rotas da API foi reportada errada (161 em vez de 166) e
  chegou a sair num e-mail;
- um limite de concorrência da API foi dado como inexistente a partir de um
  teste mal construído, e a conclusão teve de ser retratada depois da medição
  correta;
- defeitos de acessibilidade foram **introduzidos** no código e só apareceram
  porque o validador os pegou (contraste 3,43:1 e alvo de 14,6 px);
- o documento final e o README afirmavam que as validações da função rejeitada
  eram "ambas reproduzíveis no repositório". **Era falso**: uma das três usa
  *scikit-learn* e vive fora do repositório do protótipo. Uma conferência em
  10/11/2026 pegou isso, e os dois textos foram corrigidos para nomear os três
  modelos, com script, variáveis e alvo. Uma afirmação de reprodutibilidade que
  não se sustenta é o pior tipo de erro num trabalho avaliado por embasamento,
  e por isso ela está registrada aqui em vez de apagada;
- um AUC de 0,6429 foi anotado no diário do projeto sem sair de nenhum script, e
  não foi reproduzível quando alguém tentou. Ficou marcado como não utilizável.

Nenhum desses erros teria sido pego sem conferência. É a razão pela qual este
repositório tem um validador automatizado e um laudo de validação com os
números ruins publicados junto.

## Integridade

O trabalho descrito neste repositório é meu. A ferramenta acelerou a execução;
ela não substituiu a escolha do problema, as decisões de projeto, nem a
responsabilidade pelo que está entregue — inclusive pelos erros.

---

Caio Alcarria Martins dos Santos
Sistemas de Informação · Instituto de Computação · UFBA
