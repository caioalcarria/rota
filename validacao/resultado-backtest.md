# Backtesting do modelo de risco — Rota

Validação fora da amostra no eixo do tempo: para prever o período P,
o modelo só enxerga o histórico até P-1.

- Períodos avaliados: **9**
- Casos previstos: **42** (22 deram errado, 20 deram certo)
- Risco médio atribuído a quem **reprovou ou trancou**: **0.328**
- Risco médio atribuído a quem **foi aprovado**: **0.298**
- Separação (diferença entre as médias): **+0.030**
- **AUC: 0.5693**
- Acurácia no corte 0,5: **47.6%** (verdadeiros positivos 3/22, verdadeiros negativos 17/20)

## Caso a caso

| Período | Componente | Eixo | Risco previsto | O que aconteceu | Acertou? |
|---|---|---|---|---|---|
| 2022.2 | MATC73A INTRODUÇÃO À LÓGICA MATEMÁTICA | quantitativo | 0.139 | TRANC | **não** |
| 2022.2 | ADME99A ECONOMIA DA INOVAÇÃO | teorico | 0.044 | APR | sim |
| 2022.2 | MATC92A FUNDAMENTOS DE SISTEMAS DE INFORMA | teorico | 0.044 | APR | sim |
| 2022.2 | MATD04A ESTRUTURAS DE DADOS | teorico | 0.044 | REP | **não** |
| 2022.2 | MATC90A CIRCUITOS DIGITAIS E ARQUITETURA D | programacao | 0.030 | REPF | **não** |
| 2023.1 | MATD04 ESTRUTURAS DE DADOS | teorico | 0.376 | REP | **não** |
| 2023.1 | MATC73 INTRODUÇÃO À LÓGICA MATEMÁTICA | quantitativo | 0.341 | REP | **não** |
| 2023.1 | MATF34 ACCS:PROGRAMAÇÃO COMPETITIVA-COMPU | programacao | 0.313 | REP | **não** |
| 2023.1 | ADM001 INTRODUCÃO À ADMINISTRACAO | teorico | 0.236 | APR | sim |
| 2023.1 | ENGC75 INTRODUÇAO À ROBOTICA | teorico | 0.236 | REP | **não** |
| 2023.1 | LETA15 LEITURA DE TEXTOS EM LINGUA INGLES | teorico | 0.236 | APR | sim |
| 2023.1 | MAT220 EMPREENDEDORES EM INFORMATICA | projeto | 0.215 | REPF | **não** |
| 2023.2 | MATD04 ESTRUTURAS DE DADOS | teorico | 0.543 | REP | sim |
| 2023.2 | MATC73 INTRODUÇÃO À LÓGICA MATEMÁTICA | quantitativo | 0.531 | TRANC | sim |
| 2023.2 | MATC90 CIRCUITOS DIGITAIS E ARQUITETURA D | programacao | 0.508 | APR | **não** |
| 2023.2 | MATD81 REDES DE SENSORES SEM FIO | programacao | 0.368 | TRANC | **não** |
| 2023.2 | LETE48 LIBRAS I- LÍNGUA BRASILEIRA DE SIN | teorico | 0.263 | REPF | **não** |
| 2024.1 | MATD04 ESTRUTURAS DE DADOS | teorico | 0.776 | TRANC | sim |
| 2024.1 | MATC89 APLICAÇÕES PARA DISPOSITIVOS MÓVEI | programacao | 0.381 | TRANC | **não** |
| 2024.1 | MATA58 SISTEMAS OPERACIONAIS | teorico | 0.356 | TRANC | **não** |
| 2024.1 | MATA82 SISTEMAS DE TEMPO REAL | teorico | 0.356 | TRANC | **não** |
| 2024.1 | MATC72 INTERAÇÃO HUMANO-COMPUTADOR | teorico | 0.356 | TRANC | **não** |
| 2024.2 | MATA58 SISTEMAS OPERACIONAIS | teorico | 0.394 | APR | sim |
| 2024.2 | MATA59 REDES DE COMPUTADORES I | programacao | 0.345 | APR | sim |
| 2024.2 | LETF01 LÍNGUA PORTUGUESA - LEITURA E PROD | teorico | 0.324 | APR | sim |
| 2024.2 | MATA76 LINGUAGENS PARA APLICAÇÃO COMERCIA | teorico | 0.324 | APR | sim |
| 2025.1 | MATD04 ESTRUTURAS DE DADOS | teorico | 0.835 | APR | **não** |
| 2025.1 | MATA07 ÁLGEBRA LINEAR A | quantitativo | 0.392 | TRANC | **não** |
| 2025.1 | MATC82 SISTEMAS WEB | programacao | 0.371 | APR | sim |
| 2025.1 | MATE85 TÓPICOS EM SISTEMAS DE INFORMAÇÃO  | programacao | 0.358 | APR | sim |
| 2025.1 | ECOB40 INTRODUÇÃO À ECONOMIA I | teorico | 0.345 | TRANC | **não** |
| 2025.1 | FCC024 CONTABILIDADE DE CUSTOS | teorico | 0.345 | TRANC | **não** |
| 2025.1 | MATE22 TÓPICOS EM COMPUTAÇÃO VISUAL IV | teorico | 0.345 | TRANC | **não** |
| 2025.2 | MATA07 ÁLGEBRA LINEAR A | quantitativo | 0.291 | APR | sim |
| 2025.2 | MATA55 PROGRAMAÇÃO ORIENTADA A OBJETOS | programacao | 0.169 | APR | sim |
| 2025.2 | MATA60 BANCO DE DADOS | programacao | 0.169 | APR | sim |
| 2026.1 | MAT220 EMPREENDEDORES EM INFORMATICA | projeto | 0.510 | APR | **não** |
| 2026.1 | MATA62 ENGENHARIA DE SOFTWARE I | projeto | 0.370 | APR | sim |
| 2026.1 | ADM211 MÉTODOS QUANTITATIVOS APLICADOS À  | teorico | 0.152 | APR | sim |
| 2026.1 | MATB19 SISTEMAS MULTIMÍDIA | teorico | 0.152 | APR | sim |
| 2026.1 | MATA56 PARADIGMAS DE LINGUAGENS DE PROGRA | programacao | 0.123 | APR | sim |
| 2026.2 | MAT236 MÉTODOS ESTATÍSTICOS | quantitativo | 0.159 | TRANC | **não** |

## Limitações, ditas sem maquiagem

1. **Amostra de um aluno só.** São dezenas de casos, não milhares. O
   resultado indica que o modelo ordena melhor que o acaso, não que ele
   generaliza para a universidade inteira.
2. **Os pesos não foram estimados a partir destes dados**, foram
   arbitrados a partir da literatura de retenção e da leitura do
   histórico. Isso é honesto, mas significa que o modelo é um **escore
   aditivo com pesos declarados**, não uma regressão ajustada.
3. **O atraso entra como zero no backtesting**, porque o semestre ideal
   de cada componente na época não é recuperável do histórico. O termo
   existe na operação real, mas não é testado aqui.
4. **Trancamento é tratado como insucesso.** É discutível: trancar pode
   ser uma decisão acertada. A escolha torna o teste mais severo.
5. **Não há grupo de controle.** Não se compara com a decisão que o
   aluno de fato tomou nem com uma recomendação alternativa.