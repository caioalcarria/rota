"""
Modelo de risco de reprovação por componente.

É um modelo linear, de propósito: cada termo é legível e pode ser
mostrado ao usuário como justificativa. Isso atende à exigência da
disciplina de que o sistema explique por que recomendou o que recomendou.

Implementa a função analítica de REGRESSÃO: as variáveis independentes
são o desempenho do aluno no eixo, o histórico no próprio componente,
o atraso e a carga assumida; a variável dependente é a probabilidade
estimada de NÃO aprovação.
"""

from __future__ import annotations
from . import eixos

# Pesos do modelo. Mantidos num dicionário para aparecerem no relatório
# e poderem ser discutidos na seção de validação do trabalho.
BETA = {
    "intercepto": 0.18,
    "desempenho_eixo": 0.42,   # quanto pior o histórico no eixo, maior o risco
    "reprovacao_previa": 0.14,  # por reprovação anterior no mesmo componente
    "trancamento_previo": 0.07,  # por trancamento anterior no mesmo componente
    "atraso": 0.012,            # por semestre de atraso
    "carga": 0.030,             # por componente acima de 4 no período
    "recuperacao": -0.26,       # desconto por aproveitamento recente alto
}

TETO_REPROVACAO = 3
TETO_ATRASO = 8


def _nota_para_fator(nota: float | None, situacao: str) -> float | None:
    """Converte uma linha do histórico num fator de 0 (ótimo) a 1 (ruim)."""
    if situacao in ("REP", "REPF", "REPMF"):
        return 1.0
    if situacao == "TRANC":
        return 0.55          # trancar não é reprovar, mas sinaliza dificuldade
    if situacao in ("APR", "DISP", "CUMP") and nota is not None:
        return max(0.0, min(1.0, (10.0 - float(nota)) / 10.0))
    return None


def desempenho_por_eixo(historico: list[dict]) -> dict[str, float]:
    """
    Média ponderada do fator de dificuldade do aluno em cada eixo.
    0 = foi muito bem nesse eixo; 1 = sofreu.
    """
    soma = {e: 0.0 for e in eixos.EIXOS}
    peso = {e: 0.0 for e in eixos.EIXOS}

    for c in historico:
        if c.get("cursando"):
            continue
        fator = _nota_para_fator(c.get("nota"), c.get("situacao") or "")
        if fator is None:
            continue
        p = eixos.perfil(c.get("nome") or "", c.get("codigo") or "")
        for e, w in p.items():
            if w <= 0:
                continue
            soma[e] += fator * w
            peso[e] += w

    saida = {}
    for e in eixos.EIXOS:
        saida[e] = round(soma[e] / peso[e], 3) if peso[e] > 0 else 0.35
    return saida


def historico_do_componente(historico: list[dict], codigo: str) -> dict[str, int]:
    """Quantas vezes o aluno já reprovou ou trancou este componente."""
    base = (codigo or "").rstrip("A")
    rep = tranc = 0
    for c in historico:
        cod = (c.get("codigo") or "").rstrip("A")
        if cod != base:
            continue
        s = c.get("situacao")
        if s in ("REP", "REPF", "REPMF"):
            rep += 1
        elif s == "TRANC":
            tranc += 1
    return {"reprovacoes": rep, "trancamentos": tranc}


def aproveitamento_recente(historico: list[dict], janela: int = 3) -> float:
    """
    Proporção de aprovação nos últimos períodos com atividade real.
    Capta a virada: quem vem passando em tudo há dois anos não carrega
    para sempre o peso de uma reprovação antiga.
    """
    periodos = sorted({c.get("periodo") for c in historico if c.get("periodo")})
    considerados, apr, tot = [], 0, 0
    for p in reversed(periodos):
        linhas = [c for c in historico
                  if c.get("periodo") == p and not c.get("cursando")
                  and c.get("situacao") in ("APR", "REP", "REPF", "REPMF")]
        if not linhas:
            continue
        considerados.append(p)
        apr += sum(1 for c in linhas if c.get("situacao") == "APR")
        tot += len(linhas)
        if len(considerados) >= janela:
            break
    return round(apr / tot, 3) if tot else 0.5


def estimar(
    componente: dict,
    desempenho: dict[str, float],
    historico: list[dict],
    atraso_semestres: int,
    componentes_no_periodo: int,
    recuperacao: float = 0.5,
) -> dict:
    """
    Devolve o risco estimado (0 a 1) e a contribuição de cada termo,
    para que a interface possa mostrar a conta aberta.
    """
    nome = componente.get("nome") or ""
    codigo = componente.get("codigo") or ""
    perfil = eixos.perfil(nome, codigo)

    # desempenho do aluno ponderado pelo perfil do componente
    desemp = sum(perfil[e] * desempenho.get(e, 0.35) for e in eixos.EIXOS)

    hist = historico_do_componente(historico, codigo)
    rep = min(hist["reprovacoes"], TETO_REPROVACAO)
    tra = min(hist["trancamentos"], TETO_REPROVACAO)
    atr = max(0, min(atraso_semestres, TETO_ATRASO))
    excesso = max(0, componentes_no_periodo - 4)

    termos = {
        "base": BETA["intercepto"],
        "desempenho no eixo": BETA["desempenho_eixo"] * desemp,
        "reprovações anteriores": BETA["reprovacao_previa"] * rep,
        "trancamentos anteriores": BETA["trancamento_previo"] * tra,
        "atraso": BETA["atraso"] * atr,
        "carga do período": BETA["carga"] * excesso,
        "recuperação recente": BETA["recuperacao"] * recuperacao,
    }

    risco = max(0.03, min(0.95, sum(termos.values())))

    return {
        "risco": round(risco, 3),
        "perfil": perfil,
        "eixo_dominante": max(perfil, key=perfil.get),
        "desempenho_no_eixo": round(desemp, 3),
        "reprovacoes": hist["reprovacoes"],
        "trancamentos": hist["trancamentos"],
        "termos": {k: round(v, 4) for k, v in termos.items()},
    }
