"""
Fonte única da pergunta "quanto falta pra eu me formar".

Existe porque a mesma pergunta estava sendo respondida de três jeitos em três
telas, em duas unidades diferentes, e a conta não fechava. Toda tela passa a
ler daqui.

Duas armadilhas do dado do SIGAA tratadas aqui:

1. **Excedente não conta.** O aluno pode ter mais horas integralizadas numa
   categoria do que o curso exige (no caso de referência, 200 h de
   complementares para 100 h exigidas). Somar o bruto dá um total maior que o
   exigido e um percentual errado. Só conta até o teto de cada categoria.

2. **Nem toda pendência é matéria.** ENADE aparece como componente obrigatório
   pendente com 0 h, e o que o aluno já está cursando continua listado como
   pendente. Nenhum dos dois é "matéria que ainda preciso pegar".
"""

from __future__ import annotations

# Componentes que aparecem como pendentes mas não são disciplina cursável.
NAO_E_MATERIA = {"ENADE"}


def _categorias(integ: dict) -> list[dict]:
    return [l for l in (integ.get("carga_horaria") or [])
            if not (l.get("categoria") or "").lower().startswith("total")]


def _linha(integ: dict, prefixo: str) -> dict:
    for l in (integ.get("carga_horaria") or []):
        if (l.get("categoria") or "").lower().startswith(prefixo):
            return l
    return {}


def optativas_em_curso(hist: list[dict]) -> list[dict]:
    """Optativas matriculadas agora. O SIGAA ainda as conta como pendentes."""
    return [c for c in hist or []
            if c.get("situacao") == "MATR" and (c.get("natureza") or "") in ("OP", "EP")]


def resumo(integ: dict, pendentes: list[dict], optativas: list[dict],
           optativas_cursando: list[dict] | None = None) -> dict:
    """
    Devolve o retrato consolidado. Todo número que aparece na tela sai daqui.

    `optativas_cursando`: as optativas que o aluno cursa agora. O plano conta o
    que está em curso como aprovado; nas obrigatórias isso já acontecia (saem da
    lista), nas optativas não: as horas delas seguiam pendentes e o plano
    reservava vaga para elas de novo (duas a mais no caso de demonstração).
    """
    cats = _categorias(integ)
    exigido = sum(l.get("exigido") or 0 for l in cats)
    # o que conta é o integralizado limitado ao teto de cada categoria
    conta = sum(min(l.get("integralizado") or 0, l.get("exigido") or 0) for l in cats)
    pendente_h = sum(l.get("pendente") or 0 for l in cats)
    excedente = sum(max(0, (l.get("integralizado") or 0) - (l.get("exigido") or 0))
                    for l in cats)

    obrig = _linha(integ, "obrig")
    opt = _linha(integ, "optat")

    # --- matérias obrigatórias que ainda precisam ser cursadas -------------
    cursando = [p for p in pendentes if p.get("matriculado")]
    nao_materia = [p for p in pendentes
                   if (p.get("codigo") or "").upper() in NAO_E_MATERIA]
    falta_obrig = [p for p in pendentes
                   if not p.get("matriculado")
                   and (p.get("codigo") or "").upper() not in NAO_E_MATERIA]

    # --- optativas: o SIGAA só dá horas, então estima em matérias ----------
    ch_tipica = _ch_tipica(optativas)
    em_curso_opt_h = sum(c.get("carga_horaria") or 0 for c in (optativas_cursando or []))
    pend_opt_h = max(0, (opt.get("pendente") or 0) - em_curso_opt_h)
    falta_opt_n = -(-pend_opt_h // ch_tipica) if ch_tipica else 0  # teto

    total_materias = len(falta_obrig) + falta_opt_n

    return {
        "percentual": round(conta / exigido * 100, 1) if exigido else 0.0,
        "horas": {
            "exigido": exigido,
            "concluido": conta,
            "pendente": pendente_h,
            "excedente_que_nao_conta": excedente,
            "fecha": conta + pendente_h == exigido,
        },
        "materias": {
            "total_a_cursar": total_materias,
            "obrigatorias_a_cursar": len(falta_obrig),
            "optativas_a_cursar": falta_opt_n,
            "optativa_ch_tipica": ch_tipica,
            "cursando_agora": len(cursando) + len(optativas_cursando or []),
            "optativas_cursando_h": em_curso_opt_h,
            "pendencias_que_nao_sao_materia": [p.get("codigo") for p in nao_materia],
        },
        # Quebra por categoria pronta para a tela: quanto já foi, quanto falta,
        # em horas e — onde faz sentido — em matérias.
        "categorias": [
            {
                "nome": l.get("categoria"),
                "exigido_h": l.get("exigido") or 0,
                "feito_h": min(l.get("integralizado") or 0, l.get("exigido") or 0),
                "bruto_h": l.get("integralizado") or 0,
                "pendente_h": l.get("pendente") or 0,
                "excedente_h": max(0, (l.get("integralizado") or 0)
                                   - (l.get("exigido") or 0)),
                "percentual": round(
                    min(l.get("integralizado") or 0, l.get("exigido") or 0)
                    / (l.get("exigido") or 1) * 100, 1),
                "materias_feitas": None,
                "materias_a_fazer": (len(falta_obrig)
                                     if (l.get("categoria") or "").lower().startswith("obrig")
                                     else (falta_opt_n
                                           if (l.get("categoria") or "").lower().startswith("optat")
                                           else None)),
                "concluida": (l.get("pendente") or 0) == 0,
            }
            for l in cats
        ],
        "por_categoria": {
            "obrigatorias": {"exigido": obrig.get("exigido"),
                             "pendente": obrig.get("pendente")},
            "optativas": {"exigido": opt.get("exigido"),
                          "pendente": pend_opt_h},
        },
        "frase": _frase(total_materias, len(falta_obrig), falta_opt_n, pendente_h),
    }


def _ch_tipica(optativas: list[dict]) -> int:
    """Carga horária mediana das optativas realmente ofertadas."""
    chs = sorted(o.get("carga_horaria") or 0 for o in optativas if o.get("carga_horaria"))
    if not chs:
        return 60
    return chs[len(chs) // 2]


def _frase(total: int, obrig: int, opt: int, horas: int) -> str:
    """A resposta em uma linha, do jeito que o aluno pergunta."""
    if total <= 0:
        return "Você já cumpriu a carga do curso."
    partes = []
    if obrig:
        partes.append(f"{obrig} obrigatória" + ("s" if obrig > 1 else ""))
    if opt:
        partes.append(f"cerca de {opt} optativa" + ("s" if opt > 1 else ""))
    # sem "somando N horas": as horas do SIGAA incluem complementares e o que
    # está em curso, e a soma não era das matérias contadas na mesma frase
    return f"Faltam {total} matérias: " + " e ".join(partes) + "."
