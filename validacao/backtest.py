"""
Backtesting do modelo de risco do Rota.

Procedimento: para cada período já cursado, congela o estado do aluno no fim
do período ANTERIOR, roda o modelo de risco como se fosse aquele momento, e
compara o risco previsto com o que de fato aconteceu.

É validação fora da amostra no eixo do tempo: ao prever o período P, o modelo
só enxerga o que aconteceu até P-1. Nenhum resultado futuro vaza para trás.

Uso:  python3 -I validacao/backtest.py [caminho_do_snapshot.json]
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo_rejeitado import risco as mrisco  # noqa: E402

APROVADO = {"APR", "APRN", "DISP", "CUMP"}
REPROVADO = {"REP", "REPF", "REPMF", "REPNF"}
TRANCADO = {"TRANC", "TRANCB"}


def carrega(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    return d["historico"]["componentes"]


def periodo_ordenavel(p: str) -> tuple[int, int]:
    try:
        a, s = p.split(".")
        return int(a), int(s)
    except Exception:
        return (0, 0)


def rodar(componentes: list[dict]) -> dict:
    periodos = sorted({c["periodo"] for c in componentes if c.get("periodo")},
                      key=periodo_ordenavel)

    previsoes: list[dict] = []
    for i, alvo in enumerate(periodos):
        if i == 0:
            continue  # não há passado para treinar

        passado = [c for c in componentes
                   if periodo_ordenavel(c["periodo"]) < periodo_ordenavel(alvo)]
        atuais = [c for c in componentes if c["periodo"] == alvo
                  and c.get("situacao") in APROVADO | REPROVADO | TRANCADO]
        if not atuais or not passado:
            continue

        desempenho = mrisco.desempenho_por_eixo(passado)
        recuperacao = mrisco.aproveitamento_recente(passado)

        for c in atuais:
            aval = mrisco.estimar(
                {"codigo": c["codigo"], "nome": c["nome"],
                 "natureza": c.get("natureza")},
                desempenho, passado,
                atraso_semestres=0,          # desconhecido no passado; neutro
                componentes_no_periodo=len(atuais),
                recuperacao=recuperacao,
            )
            situacao = c.get("situacao")
            previsoes.append({
                "periodo": alvo,
                "codigo": c["codigo"],
                "nome": c["nome"],
                "eixo": aval["eixo_dominante"],
                "risco": aval["risco"],
                "situacao": situacao,
                "deu_errado": situacao in REPROVADO | TRANCADO,
            })

    return {"previsoes": previsoes, "periodos": periodos}


def auc(previsoes: list[dict]) -> float | None:
    """
    Área sob a curva ROC pelo método das comparações par a par:
    a probabilidade de o modelo dar risco maior a um caso que deu errado
    do que a um caso que deu certo. 0,5 = moeda; 1,0 = separação perfeita.
    """
    ruins = [p["risco"] for p in previsoes if p["deu_errado"]]
    bons = [p["risco"] for p in previsoes if not p["deu_errado"]]
    if not ruins or not bons:
        return None
    ganhos = sum((1.0 if r > b else 0.5 if r == b else 0.0)
                 for r in ruins for b in bons)
    return round(ganhos / (len(ruins) * len(bons)), 4)


def relatorio(res: dict) -> str:
    p = res["previsoes"]
    if not p:
        return "Sem casos suficientes para validar."

    ruins = [x for x in p if x["deu_errado"]]
    bons = [x for x in p if not x["deu_errado"]]
    m_ruins = sum(x["risco"] for x in ruins) / len(ruins) if ruins else 0
    m_bons = sum(x["risco"] for x in bons) / len(bons) if bons else 0
    a = auc(p)

    # taxa de acerto usando o ponto de corte 0,5
    vp = sum(1 for x in ruins if x["risco"] >= 0.5)
    vn = sum(1 for x in bons if x["risco"] < 0.5)
    acuracia = (vp + vn) / len(p)

    linhas = [
        "# Backtesting do modelo de risco — Rota",
        "",
        "Validação fora da amostra no eixo do tempo: para prever o período P,",
        "o modelo só enxerga o histórico até P-1.",
        "",
        f"- Períodos avaliados: **{len(res['periodos']) - 1}**",
        f"- Casos previstos: **{len(p)}** "
        f"({len(ruins)} deram errado, {len(bons)} deram certo)",
        f"- Risco médio atribuído a quem **reprovou ou trancou**: **{m_ruins:.3f}**",
        f"- Risco médio atribuído a quem **foi aprovado**: **{m_bons:.3f}**",
        f"- Separação (diferença entre as médias): **{m_ruins - m_bons:+.3f}**",
        f"- **AUC: {a}**" if a is not None else "- AUC: não calculável",
        f"- Acurácia no corte 0,5: **{acuracia:.1%}** "
        f"(verdadeiros positivos {vp}/{len(ruins)}, verdadeiros negativos {vn}/{len(bons)})",
        "",
        "## Caso a caso",
        "",
        "| Período | Componente | Eixo | Risco previsto | O que aconteceu | Acertou? |",
        "|---|---|---|---|---|---|",
    ]
    for x in sorted(p, key=lambda y: (periodo_ordenavel(y["periodo"]), -y["risco"])):
        previu_mal = x["risco"] >= 0.5
        acertou = "sim" if previu_mal == x["deu_errado"] else "**não**"
        linhas.append(
            f"| {x['periodo']} | {x['codigo']} {x['nome'][:34]} | {x['eixo']} "
            f"| {x['risco']:.3f} | {x['situacao']} | {acertou} |")

    linhas += [
        "",
        "## Limitações, ditas sem maquiagem",
        "",
        "1. **Amostra de um aluno só.** São dezenas de casos, não milhares. O",
        "   resultado indica que o modelo ordena melhor que o acaso, não que ele",
        "   generaliza para a universidade inteira.",
        "2. **Os pesos não foram estimados a partir destes dados**, foram",
        "   arbitrados a partir da literatura de retenção e da leitura do",
        "   histórico. Isso é honesto, mas significa que o modelo é um **escore",
        "   aditivo com pesos declarados**, não uma regressão ajustada.",
        "3. **O atraso entra como zero no backtesting**, porque o semestre ideal",
        "   de cada componente na época não é recuperável do histórico. O termo",
        "   existe na operação real, mas não é testado aqui.",
        "4. **Trancamento é tratado como insucesso.** É discutível: trancar pode",
        "   ser uma decisão acertada. A escolha torna o teste mais severo.",
        "5. **Não há grupo de controle.** Não se compara com a decisão que o",
        "   aluno de fato tomou nem com uma recomendação alternativa.",
    ]
    return "\n".join(linhas)


if __name__ == "__main__":
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parent / "dados_reais_anonimizados.json"
    saida = relatorio(rodar(carrega(caminho)))
    destino = Path(__file__).resolve().parent / "resultado-backtest.md"
    destino.write_text(saida, encoding="utf-8")
    print(saida[:2200])
    print(f"\n[relatório completo em {destino}]")
