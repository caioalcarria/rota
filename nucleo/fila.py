"""
Posição do aluno na fila de alocação de vagas — Resolução CAE nº 02/2017 (UFBA).

Por que isto existe
-------------------
Destravar o pré-requisito e CONSEGUIR A VAGA são dois problemas diferentes, e
toda ferramenta que existe trata só do primeiro. Na UFBA o segundo tem resposta
determinística e pública: a Resolução CAE 02/2017 ordena a fila em seis níveis
de prioridade e define os critérios de desempate. O aluno sente a regra agindo
contra ele ("fiquei sem vaga", "nunca tem vaga sobrando") sem saber o nome dela.

O SAD não inventa cálculo novo aqui: ele devolve ao aluno uma informação que já
existe sobre ele, usando só norma pública e o histórico do próprio titular.

A norma, nos trechos que este módulo implementa
-----------------------------------------------
Art. 2º — definições:
  I   SC  Semestre cronológico: quantidade de semestres do estudante no curso,
          com base no ano e semestre de ingresso.
  II  SA  Semestre de Avaliação: "o primeiro semestre da matriz curricular do
          qual ainda não tenha cumprido mais da metade dos componentes".
  III SD  Semestre da Disciplina: semestre indicado na matriz curricular.
  IV  PC  Provável concluinte: cumpriu no mínimo 80% da carga horária total.
  V       Semestralizado: SA >= SC.

Art. 4º — ordem de prioridade na alocação:
  I   semestralizado pedindo componente com SD = SA, trancado no máximo 1 vez
  II  provável concluinte
  III NÃO semestralizado pedindo componente com SD = SA, trancado no máx. 1 vez
  IV  demais componentes com SD < SA  (matéria atrasada)
  V   demais componentes com SD > SA  (adiantar)
  VI  o que não se enquadra acima

Art. 6º — desempate, em ordem decrescente de aplicação:
  I IAP · II menos reprovações por falta · III menos trancamentos ·
  IV maior período de ingresso.

Texto oficial:
https://colmat.ufba.br/sites/colmat.ufba.br/files/resolucao_no_02.2017_-_cae.pdf
"""

from __future__ import annotations

APROVADO = {"APR", "APRN", "DISP", "CUMP"}
TRANCADO = {"TRANC", "TRANCB"}
REPROVADO_FALTA = {"REPF", "REPMF"}

# Art. 4º, na ordem da norma. O número é a posição na fila: menor é melhor.
NIVEIS = {
    1: "Semestralizado pedindo componente do seu semestre de avaliação",
    2: "Provável concluinte (80% ou mais da carga horária cumprida)",
    3: "Não semestralizado pedindo componente do seu semestre de avaliação",
    4: "Componente atrasado (semestre da matriz menor que o seu SA)",
    5: "Componente adiantado (semestre da matriz maior que o seu SA)",
    6: "Não se enquadra nas situações acima",
}
ROMANO = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}


def _base(codigo: str) -> str:
    """
    "MATA02A" e "MATA02" são o mesmo componente na matriz: o sufixo marca a
    versão equivalente que o aluno cursou. Sem isso, matéria feita por
    equivalência conta como não cumprida e o SA sai menor do que é.
    """
    c = (codigo or "").strip().upper()
    return c[:-1] if len(c) > 6 and c[-1] == "A" else c


def _cumpridos(historico: list[dict]) -> set[str]:
    return {_base(c.get("codigo")) for c in historico
            if c.get("situacao") in APROVADO}


def semestre_cronologico(ingresso: str, atual: str) -> int:
    """Art. 2º I. Quantos semestres o aluno tem de curso, contando o de ingresso."""
    try:
        a1, p1 = (int(x) for x in ingresso.split("."))
        a2, p2 = (int(x) for x in atual.split("."))
    except Exception:
        return 0
    return (a2 - a1) * 2 + (p2 - p1) + 1


def semestre_de_avaliacao(niveis: list[dict], cumpridos: set[str]) -> dict:
    """
    Art. 2º II: o PRIMEIRO semestre da matriz do qual o aluno ainda não cumpriu
    MAIS DA METADE dos componentes. "Mais da metade" é estrito: num nível de 5,
    três cumprem; dois não.

    Devolve também a conta de cada nível, porque o aluno tem direito de ver de
    onde saiu o número que define a posição dele na fila.
    """
    detalhe = []
    sa = None
    for n in sorted(niveis, key=lambda x: x.get("nivel") or 0):
        comps = [_base(c.get("codigo")) for c in (n.get("componentes") or [])]
        if not comps:
            continue                      # nível vazio na matriz não entra
        feitos = [c for c in comps if c in cumpridos]
        passou = len(feitos) > len(comps) / 2
        detalhe.append({
            "nivel": n.get("nivel"),
            "componentes": len(comps),
            "cumpridos": len(feitos),
            "mais_da_metade": passou,
            "faltando": [c for c in comps if c not in cumpridos],
        })
        if not passou and sa is None:
            sa = n.get("nivel")
    return {"sa": sa, "niveis": detalhe}


def _trancamentos_por_componente(historico: list[dict]) -> dict[str, int]:
    conta: dict[str, int] = {}
    for c in historico:
        if c.get("situacao") in TRANCADO:
            k = _base(c.get("codigo"))
            conta[k] = conta.get(k, 0) + 1
    return conta


def _sd_por_componente(niveis: list[dict]) -> dict[str, int]:
    sd: dict[str, int] = {}
    for n in niveis:
        for c in (n.get("componentes") or []):
            sd[_base(c.get("codigo"))] = n.get("nivel")
    return sd


def nivel_de(codigo: str, sd: int | None, sa: int | None,
             semestralizado: bool, provavel_concluinte: bool,
             trancos: int) -> tuple[int, str]:
    """
    Art. 4º. Devolve (nível, por quê) para UM componente.

    A ordem dos testes é a da norma, e importa: o provável concluinte (II)
    vem antes do não semestralizado (III), então quem está perto de concluir
    passa à frente mesmo pedindo matéria fora do seu SA.
    """
    if sd is None or sa is None:
        return 6, "Componente fora da matriz do seu currículo (optativa livre, por exemplo)."

    if sd == sa and trancos <= 1:
        if semestralizado:
            return 1, (f"É do seu semestre de avaliação (SD = SA = {sa}) e você "
                       f"está semestralizado.")
        if provavel_concluinte:
            return 2, "Você é provável concluinte, o que tem prioridade maior."
        return 3, (f"É do seu semestre de avaliação (SD = SA = {sa}), mas você "
                   f"não está semestralizado.")

    if provavel_concluinte:
        return 2, "Você é provável concluinte, o que tem prioridade maior."

    if sd == sa and trancos > 1:
        return (4 if sd < sa else 5), (
            f"É do seu SA, mas você já trancou este componente {trancos} vezes, "
            f"e a norma exige no máximo uma para a prioridade do seu nível.")

    if sd < sa:
        return 4, f"Está atrasado: é do {sd}º semestre da matriz e você está no {sa}º."
    return 5, f"Está adiantado: é do {sd}º semestre da matriz e você está no {sa}º."


def posicao(estrutura: dict, historico: list[dict], integ: dict,
            indices: dict, vinculo: dict, codigos: list[str]) -> dict:
    """
    Monta o retrato completo da fila para os componentes pedidos.

    `estrutura` é o corpo de /v1/publico/cursos/{id}/estruturas/{id}.
    `codigos` são os componentes que o aluno pensa em pedir.
    """
    hist = historico or []
    niveis = (estrutura or {}).get("niveis") or []
    cumpridos = _cumpridos(hist)

    ingresso = (vinculo or {}).get("ingresso_periodo") or ""
    atual = (vinculo or {}).get("periodo_atual") or ""
    sc = (vinculo or {}).get("periodo_letivo_atual")
    if not sc:
        sc = semestre_cronologico(ingresso, atual)

    aval = semestre_de_avaliacao(niveis, cumpridos)
    sa = aval["sa"]
    semestralizado = bool(sa and sc and sa >= sc)

    # Art. 2º IV — provável concluinte: 80% da carga horária total do curso.
    linhas = [l for l in (integ.get("carga_horaria") or [])
              if not (l.get("categoria") or "").lower().startswith("total")]
    exigido = sum(l.get("exigido") or 0 for l in linhas)
    # conta o excedente de uma categoria? Não: a norma fala em carga do CURSO,
    # e o teto de cada categoria é o que o curso exige.
    feito = sum(min(l.get("integralizado") or 0, l.get("exigido") or 0)
                for l in linhas)
    pct = (feito / exigido * 100) if exigido else 0.0
    pc = pct >= 80.0

    sd_de = _sd_por_componente(niveis)
    trancos = _trancamentos_por_componente(hist)

    itens = []
    for cod in codigos or []:
        b = _base(cod)
        sd = sd_de.get(b)
        n, porque = nivel_de(b, sd, sa, semestralizado, pc, trancos.get(b, 0))
        itens.append({
            "codigo": cod, "sd": sd, "nivel": n, "romano": ROMANO[n],
            "rotulo": NIVEIS[n], "porque": porque,
            "trancamentos_neste": trancos.get(b, 0),
        })
    itens.sort(key=lambda x: (x["nivel"], x["codigo"]))

    ofic = (indices or {}).get("oficiais") or {}
    return {
        "sc": sc,
        "sa": sa,
        "semestralizado": semestralizado,
        "provavel_concluinte": pc,
        "percentual_ch": round(pct, 1),
        "niveis_da_matriz": aval["niveis"],
        "componentes": itens,
        "desempate": {
            "iap": ofic.get("iap"),
            "reprovacoes_por_falta": sum(1 for c in hist
                                         if c.get("situacao") in REPROVADO_FALTA),
            "trancamentos": sum(1 for c in hist if c.get("situacao") in TRANCADO),
            "periodo_ingresso": ingresso,
        },
        "norma": {
            "nome": "Resolução CAE nº 02/2017 (UFBA)",
            "url": "https://colmat.ufba.br/sites/colmat.ufba.br/files/"
                   "resolucao_no_02.2017_-_cae.pdf",
            "artigos": {
                "definicoes": "Art. 2º",
                "escalonamento": "Art. 3º (ordem decrescente de SA e, dentro dele, de CR)",
                "prioridade": "Art. 4º",
                "desempate": "Art. 6º (IAP, menos reprovações por falta, "
                             "menos trancamentos, maior período de ingresso)",
            },
        },
    }
