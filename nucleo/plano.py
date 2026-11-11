"""
Plano de conclusão: do semestre atual até a formatura.

A decisão que este módulo apoia não é "o que eu pego no próximo semestre" —
é **"eu quero me formar até tal data; o que eu preciso fazer?"**. O aluno
informa o alvo, e o sistema devolve a grade semestre a semestre, dizendo se o
alvo é alcançável e, quando não é, qual é a data mais cedo possível e por quê.

Três restrições governam a montagem, nesta ordem:
  1. **Pré-requisito** — um componente só entra depois dos que o destravam.
  2. **Oferta por paridade** — só entra num semestre em que costuma abrir.
  3. **Carga por semestre** — o teto que o aluno declara aguentar.
"""

from __future__ import annotations
import re

from . import oferta as moferta

MAX_SEMESTRES = 14  # trava de segurança contra plano infinito


def _codigos_do_prerequisito(texto: str | None) -> list[list[str]]:
    """
    Converte "(MATA03) OU (MATA02) OU (MATA01 E MATA42)" numa lista de
    alternativas, cada uma com os códigos que precisam estar todos cumpridos.
    """
    if not texto:
        return []
    alternativas = []
    for bloco in re.split(r"\bOU\b", texto, flags=re.I):
        codigos = re.findall(r"[A-Z]{2,4}\d{2,4}", bloco.upper())
        if codigos:
            alternativas.append(codigos)
    return alternativas


def falta_mesmo(c: dict, cumpridos: set[str] | None = None,
                preferir: set[str] | None = None) -> list[str]:
    """
    O que realmente falta para destravar o componente.

    O campo `faltando` do SIGAA é a UNIÃO dos códigos de todas as alternativas
    não satisfeitas. Mostrá-lo cru engana: Inteligência Artificial aparece
    pedindo MATC73, MATA47, MATA53 e MATE12, quando o pré-requisito é
    "(MATC73) OU (MATA47 E MATA53 E MATE12) OU ((MATC73) E (MATD04))" e uma
    alternativa basta. Aqui a expressão é lida e devolve-se UMA alternativa: a
    que pede menos matérias fora do que o aluno já vai cursar (`preferir`) e,
    no empate, a mais curta. Para um aluno de Ciência da Computação isso dá
    MATA53 e MATE12, que estão no currículo dele, e não MATC73, que não está.
    """
    cumpridos = cumpridos or set()
    if c.get("apto") is True:
        return []
    alts = _codigos_do_prerequisito(c.get("pre_requisitos"))
    faltando = list(c.get("faltando") or [])
    if not alts:
        return faltando
    citados = {cod for alt in alts for cod in alt}
    ja_tem = cumpridos | (citados - set(faltando))
    caminhos = [[cod for cod in alt if cod not in ja_tem] for alt in alts]
    if not caminhos:
        return faltando

    # Empate no tamanho: vale mais a alternativa que passa pelo que o aluno
    # JÁ VAI cursar. Qualidade de Software aceita MATE11 ou Engenharia de
    # Software II; apontar MATE11, que nem está no currículo dele, manda o
    # aluno atrás de uma matéria que ele nunca vai pegar.
    # E vale mais a que só passa pelo que ele já tem que cursar: Inteligência
    # Artificial em Ciência da Computação aceita MATC73 sozinha ou MATA53 e
    # MATE12. MATC73 é "mais curta", mas não é do currículo dele; MATA53 e
    # MATE12 ele vai cursar de qualquer jeito. Mostrar "falta MATC73" mandava
    # o aluno atrás de uma matéria a mais.
    pref = preferir or set()
    return min(caminhos,
               key=lambda alt: (sum(1 for cod in alt if cod not in pref), len(alt)))


def _liberado(c: dict, cumpridos: set[str]) -> bool:
    """
    Decide se o componente já pode ser cursado.

    Duas fontes, cada uma com o que só ela sabe:

    - A **expressão** `pre_requisitos` do SIGAA tem a estrutura OU/E. É dela
      que sai "basta MATC73" em vez de "precisa de MATC73 e mais três".
    - O **veredito** da API (`apto`, `faltando`) sabe o que o aluno de fato já
      cumpriu, inclusive por equivalência — o TCC I exige LETA09 e o aluno fez
      LETA15; só o SIGAA sabe que uma vale pela outra.

    `faltando` é a união dos códigos de todas as alternativas não satisfeitas,
    não uma lista "E". Por isso ela não é usada como exigência: ela é usada ao
    contrário, para descobrir que um código citado na expressão e AUSENTE dela
    já está cumprido.
    """
    if c.get("apto") is True:
        return True

    alts = _codigos_do_prerequisito(c.get("pre_requisitos"))
    if not alts:
        # sem expressão, o único veredito é o da API; se ela também não opinou,
        # não há o que travar
        return c.get("apto") is None

    faltando = set(c.get("faltando") or [])
    citados = {cod for alt in alts for cod in alt}
    # citado na expressão mas não listado como faltando = o aluno já tem
    ja_tem = cumpridos | (citados - faltando)
    return any(all(cod in ja_tem for cod in alt) for alt in alts)


# A sequência (TCC I antes de TCC II) agora vem do próprio SIGAA, no campo
# `pre_requisitos`, e da inferência da API em `sequencia_apos`. A heurística de
# numeral romano que existia aqui foi removida: era frágil e desnecessária.


def _sequencia_pendente(c: dict, feitos: set[str]) -> bool:
    """True se falta cursar algo que precisa vir antes deste componente."""
    return any(a not in feitos for a in (c.get("sequencia_apos") or []))


def monta(
    pendentes: list[dict],
    optativas_faltantes: int,
    optativa_ch: int,
    cumpridos: set[str],
    periodo_inicial: str,
    por_semestre: int,
    oferta: moferta.Oferta,
    alvo: str | None = None,
    limites: dict[str, int] | None = None,
    pular: list[str] | None = None,
    fixar: dict[str, str] | None = None,
    reprovar: list[str] | None = None,
) -> dict:
    """
    Devolve a grade semestre a semestre até acabarem as pendências.

    `pendentes` são as obrigatórias que faltam (sem o que já está em curso e
    sem o que não é disciplina). `optativas_faltantes` entra como vagas
    genéricas, porque qualquer optativa serve para fechar a carga.
    """
    restantes = {p["codigo"]: dict(p) for p in pendentes}
    pular = set(pular or [])
    fixar = fixar or {}            # {"GICC0003": "2027.2"}
    reprovar = set(reprovar or [])  # hipótese: estas o aluno reprova e refaz
    feitos = set(cumpridos)
    optativas_restantes = max(0, optativas_faltantes)

    semestres: list[dict] = []
    periodo = periodo_inicial
    travadas_por_oferta: dict[str, str] = {}

    while (restantes or optativas_restantes) and len(semestres) < MAX_SEMESTRES:
        # o aluno pode apertar um semestre específico (viagem, trabalho puxado)
        vagas = (limites or {}).get(periodo, por_semestre)
        deste: list[dict] = []
        adiadas_oferta: list[dict] = []

        if periodo in pular:
            semestres.append({
                "periodo": periodo, "componentes": [], "carga_horaria": 0,
                "nota": "Você marcou este semestre para não cursar nada.",
                "pulado": True,
            })
            periodo = moferta.proximo_periodo(periodo)
            continue

        # candidatos: pré-requisito cumprido e antecessor da sequência já feito
        elegiveis = []
        for c in restantes.values():
            if not _liberado(c, feitos):
                continue
            if _sequencia_pendente(c, feitos):
                continue
            elegiveis.append(c)

        # quem só abre nesta paridade entra primeiro: perder a janela custa um ano
        def prioridade(c):
            padrao = oferta.padrao(c["codigo"])
            raro = 0 if padrao in (moferta.IMPAR, moferta.PAR) else 1
            return (raro, -len(c.get("desbloqueia") or []), c["codigo"])

        elegiveis = [c for c in elegiveis
                     if fixar.get(c["codigo"]) in (None, periodo)]
        presos = [c for c in elegiveis if fixar.get(c["codigo"]) == periodo]
        outros = [c for c in elegiveis if c["codigo"] not in
                  {x["codigo"] for x in presos}]

        for c in presos + sorted(outros, key=prioridade):
            if vagas <= 0:
                break
            if not oferta.sera_ofertada(c["codigo"], periodo):
                adiadas_oferta.append(c)
                travadas_por_oferta[c["codigo"]] = oferta.explica(
                    c["codigo"], periodo)
                continue
            deste.append({
                "codigo": c["codigo"], "nome": c.get("nome"),
                "carga_horaria": c.get("carga_horaria"),
                "tipo": "obrigatória",
                "padrao_oferta": oferta.explica(c["codigo"], periodo),
                "destrava": len(c.get("desbloqueia") or []),
            })
            vagas -= 1

        # sobrou vaga: completa com optativa (serve qualquer uma)
        while vagas > 0 and optativas_restantes > 0:
            deste.append({
                "codigo": "OPTATIVA", "nome": "Optativa (qualquer uma que você escolher)",
                "carga_horaria": optativa_ch, "tipo": "optativa",
                "padrao_oferta": "há várias ofertadas todo semestre", "destrava": 0,
            })
            optativas_restantes -= 1
            vagas -= 1

        if not deste:
            # nada entra neste semestre: só esperar a oferta abrir
            semestres.append({
                "periodo": periodo, "componentes": [], "carga_horaria": 0,
                "nota": "Nenhuma disciplina pendente abre neste semestre.",
            })
            periodo = moferta.proximo_periodo(periodo)
            continue

        for item in deste:
            if item["tipo"] != "obrigatória":
                continue
            if item["codigo"] in reprovar:
                # a hipótese é que ele cursa e reprova: ocupa a vaga do
                # semestre, não destrava nada e continua pendente
                item["reprovada"] = True
                reprovar.discard(item["codigo"])
                continue
            restantes.pop(item["codigo"], None)
            feitos.add(item["codigo"])

        semestres.append({
            "periodo": periodo,
            "componentes": deste,
            "carga_horaria": sum(x["carga_horaria"] or 0 for x in deste),
            "nota": None,
        })
        periodo = moferta.proximo_periodo(periodo)

    for sem in semestres:
        comps = sem["componentes"]
        sem["obrigatorias"] = sum(1 for x in comps if x["tipo"] == "obrigatória")
        sem["optativas"] = sum(1 for x in comps if x["tipo"] == "optativa")

    conclusao = semestres[-1]["periodo"] if semestres else periodo_inicial
    sobrou = list(restantes.values())

    return {
        "periodo_inicial": periodo_inicial,
        "por_semestre": por_semestre,
        "semestres": semestres,
        "conclusao": conclusao,
        "total_semestres": len(semestres),
        "nao_coube": [{"codigo": c["codigo"], "nome": c.get("nome")} for c in sobrou],
        "travadas_por_oferta": travadas_por_oferta,
        "alvo": alvo,
        "alcanca_alvo": (moferta.distancia(conclusao, alvo) >= 0) if alvo else None,
    }


def menor_carga_para(alvo: str, **kwargs) -> dict:
    """
    Quantas disciplinas por semestre são necessárias para fechar até o alvo.
    Testa de 1 a 8 e devolve a primeira carga que alcança, junto com o plano.
    """
    for n in range(1, 9):
        p = monta(por_semestre=n, alvo=alvo, **kwargs)
        if p["alcanca_alvo"] and not p["nao_coube"]:
            p["carga_necessaria"] = n
            return p
    p = monta(por_semestre=8, alvo=alvo, **kwargs)
    p["carga_necessaria"] = None
    return p
