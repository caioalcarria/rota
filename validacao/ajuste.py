"""
Estimação dos pesos do modelo de risco a partir do histórico real.

Troca os coeficientes arbitrados por coeficientes ESTIMADOS: regressão
logística ajustada por descida de gradiente com regularização L2, em Python
puro (sem dependência externa).

O protocolo de avaliação respeita o tempo: para prever o período P, o modelo
é treinado só com o que aconteceu até P-1. Nenhum resultado futuro vaza.

Uso:  python3 -I validacao/ajuste.py [snapshot.json]
"""

from __future__ import annotations
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo_rejeitado import eixos, risco as mrisco  # noqa: E402

APROVADO = {"APR", "APRN", "DISP", "CUMP"}
REPROVADO = {"REP", "REPF", "REPMF", "REPNF"}
TRANCADO = {"TRANC", "TRANCB"}

VARIAVEIS = [
    "desempenho_no_eixo",      # quanto o aluno sofre no tipo da disciplina
    "reprovacoes_no_componente",
    "trancamentos_no_componente",
    "aproveitamento_recente",  # proteção: vinha passando?
    "carga_do_periodo",        # nº de componentes assumidos
]


def ordem(p: str) -> tuple[int, int]:
    try:
        a, s = p.split(".")
        return int(a), int(s)
    except Exception:
        return (0, 0)


def monta_casos(componentes: list[dict]) -> list[dict]:
    """Uma linha por componente cursado, com as variáveis no estado de então."""
    periodos = sorted({c["periodo"] for c in componentes if c.get("periodo")}, key=ordem)
    casos = []
    for i, alvo in enumerate(periodos):
        if i == 0:
            continue
        passado = [c for c in componentes if ordem(c["periodo"]) < ordem(alvo)]
        atuais = [c for c in componentes if c["periodo"] == alvo
                  and c.get("situacao") in APROVADO | REPROVADO | TRANCADO]
        if not atuais or not passado:
            continue
        desempenho = mrisco.desempenho_por_eixo(passado)
        recente = mrisco.aproveitamento_recente(passado)
        for c in atuais:
            perfil = eixos.perfil(c.get("nome") or "", c.get("codigo") or "")
            hist = mrisco.historico_do_componente(passado, c.get("codigo") or "")
            casos.append({
                "periodo": alvo, "codigo": c["codigo"], "nome": c["nome"],
                "x": [
                    sum(perfil[e] * desempenho.get(e, 0.35) for e in eixos.EIXOS),
                    min(hist["reprovacoes"], 3) / 3.0,
                    min(hist["trancamentos"], 3) / 3.0,
                    recente,
                    min(len(atuais), 8) / 8.0,
                ],
                "y": 1.0 if c["situacao"] in REPROVADO | TRANCADO else 0.0,
            })
    return casos


def sigmoide(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def ajusta(casos: list[dict], passos: int = 6000, taxa: float = 0.35,
           l2: float = 0.05) -> list[float]:
    """Devolve [intercepto, w1..wn]."""
    n = len(VARIAVEIS)
    w = [0.0] * (n + 1)
    if not casos:
        return w
    for _ in range(passos):
        grad = [0.0] * (n + 1)
        for c in casos:
            z = w[0] + sum(w[j + 1] * c["x"][j] for j in range(n))
            erro = sigmoide(z) - c["y"]
            grad[0] += erro
            for j in range(n):
                grad[j + 1] += erro * c["x"][j]
        m = len(casos)
        w[0] -= taxa * grad[0] / m
        for j in range(n):
            w[j + 1] -= taxa * (grad[j + 1] / m + l2 * w[j + 1])
    return [round(v, 4) for v in w]


def prob(w: list[float], x: list[float]) -> float:
    return sigmoide(w[0] + sum(w[j + 1] * x[j] for j in range(len(x))))


def auc(pares: list[tuple[float, float]]) -> float | None:
    ruins = [p for p, y in pares if y == 1.0]
    bons = [p for p, y in pares if y == 0.0]
    if not ruins or not bons:
        return None
    g = sum(1.0 if r > b else 0.5 if r == b else 0.0 for r in ruins for b in bons)
    return round(g / (len(ruins) * len(bons)), 4)


def valida_no_tempo(casos: list[dict]) -> tuple[float | None, int]:
    """Treina até P-1, testa em P, acumula. É o número honesto."""
    periodos = sorted({c["periodo"] for c in casos}, key=ordem)
    fora_da_amostra: list[tuple[float, float]] = []
    for i, p in enumerate(periodos):
        if i == 0:
            continue
        treino = [c for c in casos if ordem(c["periodo"]) < ordem(p)]
        teste = [c for c in casos if c["periodo"] == p]
        if len(treino) < 6 or not teste:
            continue
        w = ajusta(treino)
        fora_da_amostra += [(prob(w, c["x"]), c["y"]) for c in teste]
    return auc(fora_da_amostra), len(fora_da_amostra)


if __name__ == "__main__":
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parent / "dados_reais_anonimizados.json"
    with open(caminho, encoding="utf-8") as f:
        comps = json.load(f)["historico"]["componentes"]

    casos = monta_casos(comps)
    w = ajusta(casos)
    auc_dentro = auc([(prob(w, c["x"]), c["y"]) for c in casos])
    auc_fora, n_fora = valida_no_tempo(casos)

    print(f"casos: {len(casos)}  (insucessos: {sum(c['y'] for c in casos):.0f})")
    print()
    print("coeficientes estimados (logito):")
    print(f"  {'intercepto':<28} {w[0]:+.4f}")
    for nome, coef in zip(VARIAVEIS, w[1:]):
        print(f"  {nome:<28} {coef:+.4f}")
    print()
    print(f"AUC dentro da amostra : {auc_dentro}")
    print(f"AUC fora da amostra   : {auc_fora}   (em {n_fora} casos)")
    print(f"AUC do modelo arbitrado (referência): 0.5693")

    destino = Path(__file__).resolve().parent / "pesos-estimados.json"
    json.dump({"variaveis": VARIAVEIS, "pesos": w,
               "auc_dentro": auc_dentro, "auc_fora": auc_fora,
               "n_casos": len(casos), "n_fora_da_amostra": n_fora},
              open(destino, "w"), ensure_ascii=False, indent=1)
    print(f"\n[pesos salvos em {destino}]")
