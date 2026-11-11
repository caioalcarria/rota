"""
Rota — Sistema de Apoio à Decisão para progressão acadêmica.

Camada de decisão sobre a sigaa-ufba-api. Nada é gravado: a credencial
vai direto para o SIGAA através da API, e o token fica apenas no
navegador do usuário.
"""

from __future__ import annotations
import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nucleo import (sigaa, situacao as msituacao, oferta as moferta,
                    plano as mplano, fila as mfila, mineracao as mmin)

WEB = Path(__file__).parent / "web"

app = FastAPI(
    title="Rota — SAD de progressão acadêmica",
    description="Camada de decisão sobre a sigaa-ufba-api. Não persiste dados.",
    version="0.1.0",
    docs_url="/api/docs",
)


class LoginBody(BaseModel):
    usuario: str
    senha: str


class PainelBody(BaseModel):
    # Havia aqui quatro parâmetros (tolerância a matéria quantitativa, carga
    # horária máxima, máximo de componentes e turnos). Saíram: o teste de
    # usabilidade mostrou que o controle de tolerância era uma armadilha
    # (11 posições, 3 rótulos repetidos, e a resposta honesta dava o PIOR
    # semestre), e os outros três viraram decisão do próprio planejador.
    # A API parou de anunciar botão que não gira nada.
    fresco: bool = False


class PlanoBody(BaseModel):
    alvo: str | None = None          # "2028.2"; vazio = calcula o mais cedo
    por_semestre: int | None = None  # se o aluno quiser fixar a carga
    limites: dict[str, int] | None = None   # teto por semestre: {"2027.1": 3}
    pular: list[str] | None = None          # semestres sem cursar nada
    fixar: dict[str, str] | None = None     # {"GICC0003": "2027.2"}
    reprovar: list[str] | None = None       # hipótese de reprovação
    fresco: bool = False


# ---------------------------------------------------------------- cache
# O professor foi explícito em aula: um SAD não consulta a base transacional
# a cada interação, porque trava o sistema de produção. Ele acessa uma base
# espelhada, carregada uma vez. Aqui o espelho é um snapshot em memória por
# sessão: o SIGAA é lido UMA vez e os sliders só reprocessam a decisão.
_ESPELHO: dict[str, tuple[float, dict]] = {}
ESPELHO_TTL = 30 * 60  # segundos


def _do_espelho(chave: str) -> dict | None:
    item = _ESPELHO.get(chave)
    if not item:
        return None
    nascido, dados = item
    if time.time() - nascido > ESPELHO_TTL:
        _ESPELHO.pop(chave, None)
        return None
    return dados


def _guarda_espelho(chave: str, dados: dict) -> None:
    _ESPELHO[chave] = (time.time(), dados)


def _token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "sem token")
    return authorization.split(" ", 1)[1].strip()


def _proximo_periodo(p: str) -> str:
    try:
        ano, per = (int(x) for x in p.split("."))
    except Exception:
        return p
    per += 1
    if per > 2:
        per, ano = 1, ano + 1
    return f"{ano}.{per}"


async def _estrutura_do_curso(me: dict, vinculo: dict) -> dict | None:
    """
    A matriz curricular, nível a nível. É dela que sai o SD de cada componente
    e, principalmente, o SA do aluno (Art. 2º II da Resolução CAE 02/2017).

    Usa a rota PÚBLICA da API: a matriz é documento público do curso, não dado
    pessoal, então não gasta sessão autenticada nem expõe nada do aluno.
    """
    curso_id = (me.get("curso") or {}).get("id")
    curriculo = (vinculo or {}).get("curriculo") or ""
    codigo = curriculo.split("-")[0].strip()      # "T20252 - 2025.2" -> "T20252"
    if not curso_id or not codigo:
        return None
    try:
        ests = await sigaa.publico(f"/v1/publico/cursos/{curso_id}/estruturas")
        alvo = next((e for e in (ests or []) if e.get("codigo") == codigo), None)
        if alvo is None:
            return None
        return await sigaa.publico(
            f"/v1/publico/cursos/{curso_id}/estruturas/{alvo['id']}")
    except sigaa.SigaaIndisponivel:
        return None


async def _oferta_do_alvo(tok: str, me: dict, fresco: bool = False) -> tuple[dict, dict]:
    """
    A decisão é sobre o PRÓXIMO semestre, não sobre o que já está em curso.
    O problema é que a UFBA só publica a oferta perto da matrícula. Então:
    tenta o semestre alvo; se ainda não houver oferta publicada, usa a do
    semestre corrente como PROXY e deixa isso explícito na tela.

    Em qualquer um dos casos, o que o aluno cursa agora conta como aprovado,
    porque na hora de cursar o próximo semestre ele já terá concluído.
    """
    atual = me.get("semestre_atual") or ""
    alvo = _proximo_periodo(atual) if atual else ""
    ano_alvo, per_alvo = (alvo.split(".") + ["", ""])[:2]

    if alvo:
        plano = await sigaa.get("/v1/planejamento/matricula", tok, fresco=fresco,
                                ano=ano_alvo, periodo=per_alvo,
                                considerar_cursando_como_aprovado="true")
        if (plano.get("total_ofertados_para_o_curso") or 0) > 0:
            return plano, {"alvo": alvo, "oferta_de": alvo, "proxy": False,
                           "aviso": None}

    plano = await sigaa.get("/v1/planejamento/matricula", tok, fresco=fresco,
                            considerar_cursando_como_aprovado="true")
    de = f"{plano.get('ano')}.{plano.get('periodo')}"
    return plano, {
        "alvo": alvo or de,
        "oferta_de": de,
        "proxy": bool(alvo) and de != alvo,
        "aviso": (f"A oferta de {alvo} ainda não foi publicada pela UFBA. "
                  f"O plano usa a oferta de {de} como referência: os horários e "
                  f"professores podem mudar, mas quais disciplinas você já pode "
                  f"cursar não muda.") if alvo and de != alvo else None,
    }


# Modo demonstração: o professor e os colegas precisam abrir o sistema sem a
# credencial pessoal de ninguém. O snapshot é de um aluno FICTÍCIO montado
# sobre a matriz, os pré-requisitos e a oferta reais do curso (dado público), e
# é também o que garante que a apresentação não dependa do SIGAA estar no ar.
# O histórico real anonimizado que servia aqui foi para
# validacao/dados_reais_anonimizados.json: a validação do modelo usa ele.
DEMO_TOKEN = "demo"
_DEMO = Path(__file__).parent / "dados_demo.json"

# ROTA_MODO=demo tranca o login real.
#
# Existe por uma razão de segurança, não de conveniência. Uma instância pública
# do Rota com o login do SIGAA aberto é, na prática, uma página que pede a
# senha institucional de quem chegar — e ninguém que a digitasse teria como
# saber quem está do outro lado. Então a instância que vai para a internet
# roda em `demo`, e o modo completo só existe quando o próprio aluno sobe o
# sistema na máquina dele, contra a API dele.
import os as _os
MODO = _os.environ.get("ROTA_MODO", "completo").strip().lower()
SO_DEMO = MODO == "demo"


def _carrega_demo() -> dict:
    import json
    with open(_DEMO, encoding="utf-8") as f:
        d = json.load(f)
    d["oferta_info"] = {
        "alvo": _proximo_periodo(d["me"].get("semestre_atual") or ""),
        "oferta_de": f"{d['plano'].get('ano')}.{d['plano'].get('periodo')}",
        "proxy": True,
        "aviso": ("Modo demonstração: aluno fictício, sobre a matriz e a oferta "
                  "reais do curso. Nenhuma conexão com o SIGAA é feita."),
    }
    d["carregado_em"] = time.time()
    return d


@app.post("/api/login")
async def api_login(body: LoginBody):
    if body.usuario.strip().lower() == "demo" and body.senha.strip().lower() == "demo":
        if not _DEMO.exists():
            raise HTTPException(503, "snapshot de demonstração não encontrado")
        return {"token": DEMO_TOKEN, "expira_em": None, "demo": True}
    if SO_DEMO:
        raise HTTPException(403, (
            "Esta instância está em modo demonstração e não aceita login do "
            "SIGAA — de propósito: nenhuma senha institucional deve ser "
            "digitada num endereço público. Entre pelo botão de demonstração. "
            "Para usar com a sua conta, rode o Rota na sua máquina "
            "(instruções no README)."))
    try:
        sess = await sigaa.login(body.usuario, body.senha)
    except sigaa.SigaaOcupado as e:
        raise HTTPException(503, str(e))
    except sigaa.SigaaIndisponivel as e:
        raise HTTPException(401, str(e))
    tok = sess.get("token")
    if not tok:
        raise HTTPException(502, "a API não devolveu token")
    return {"token": tok, "expira_em": sess.get("expira_em")}


DIAS = {1: "Domingo", 2: "Segunda", 3: "Terça", 4: "Quarta",
        5: "Quinta", 6: "Sexta", 7: "Sábado"}


def _cursando(hist: list[dict], grade: dict) -> list[dict]:
    """
    O que o aluno cursa AGORA, com professor, horário e sala.

    Quem está matriculado vem do histórico (situação MATR); onde e quando a
    aula acontece vem da grade. São duas rotas diferentes do SIGAA, e só a
    junção das duas responde "o que eu faço nesta semana".
    """
    encontros: dict[str, list[dict]] = {}
    locais: dict[str, str] = {}
    for dia in (grade or {}).get("dias") or []:
        for a in dia.get("aulas") or []:
            cod = a.get("codigo")
            if not cod:
                continue
            encontros.setdefault(cod, []).append({
                "dia": a.get("dia_nome") or DIAS.get(a.get("dia"), ""),
                "dia_numero": a.get("dia"),
                "inicio": a.get("inicio"), "fim": a.get("fim"),
                "turno": a.get("turno"),
            })
            if a.get("local"):
                locais[cod] = a["local"]

    fora = [c.get("codigo") for c in (grade or {}).get("sem_horario") or []]

    saida = []
    for c in hist:
        if c.get("situacao") != "MATR":
            continue
        cod = c.get("codigo")
        saida.append({
            "codigo": cod, "nome": c.get("nome"),
            "carga_horaria": c.get("carga_horaria"),
            "natureza": c.get("natureza_descricao") or c.get("natureza"),
            "docentes": [d.get("nome") for d in (c.get("docentes") or [])
                         if d.get("nome")],
            "encontros": sorted(encontros.get(cod, []),
                                key=lambda e: (e.get("dia_numero") or 9,
                                               e.get("inicio") or "")),
            "local": locais.get(cod),
            "sem_horario": cod in fora,
        })
    saida.sort(key=lambda c: c["codigo"])
    return saida


def _so_a_cursar(pendentes: list[dict]) -> list[dict]:
    """
    O que a tela "Falta pegar" deve listar: nem o que já está sendo cursado
    neste semestre, nem o que não é disciplina (ENADE é prova, não matéria).
    """
    return [p for p in pendentes
            if not p.get("matriculado")
            and (p.get("codigo") or "").upper() not in msituacao.NAO_E_MATERIA]


def _hist_do_espelho(tok: str) -> list[dict]:
    e = _do_espelho(tok) or {}
    return (e.get("historico") or {}).get("componentes") or []


async def _contexto_do_plano(tok: str):
    """Monta os argumentos do planejador a partir do espelho. None se não há."""
    espelho = _do_espelho(tok)
    if espelho is None and tok == DEMO_TOKEN:
        espelho = _carrega_demo()
        _guarda_espelho(tok, espelho)
    if espelho is None:
        return None

    me = espelho["me"]; integ = espelho["integ"]
    hist = (espelho["historico"] or {}).get("componentes") or []
    cands = {c["codigo"]: c for c in (espelho["plano"].get("candidatos") or [])}
    reqs = {r["codigo"]: r for r in (espelho["plano"].get("requisitos") or [])}
    of = moferta.Oferta(espelho.get("previsao") or {})

    pend = []
    for p in (integ.get("obrigatorios_pendentes") or []):
        cod = p.get("codigo") or ""
        if p.get("matriculado") or cod.upper() in msituacao.NAO_E_MATERIA:
            continue
        c = cands.get(cod, {}); r = reqs.get(cod, {})
        pend.append({**p,
                     "pre_requisitos": r.get("pre_requisitos")
                                       or c.get("pre_requisitos"),
                     "sequencia_apos": r.get("sequencia_apos") or [],
                     "apto": r.get("apto", c.get("apto")),
                     "faltando": r.get("faltando") or c.get("faltando") or [],
                     "desbloqueia": c.get("desbloqueia") or []})

    feitos = {(c.get("codigo") or "").rstrip("A") for c in hist
              if c.get("situacao") in APROVADO_SIT}
    feitos |= {c.get("codigo") for c in hist if c.get("situacao") == "MATR"}

    optativas = [_enxuga_leve(c) for c in (espelho["plano"].get("candidatos") or [])
                 if c.get("natureza") != "OBRIGATORIO"]
    resumo = msituacao.resumo(integ, pend, optativas, msituacao.optativas_em_curso(hist))
    inicio = moferta.proximo_periodo(me.get("semestre_atual") or "2026.2")

    base = dict(pendentes=pend,
                optativas_faltantes=resumo["materias"]["optativas_a_cursar"],
                optativa_ch=resumo["materias"]["optativa_ch_tipica"],
                cumpridos=feitos, periodo_inicial=inicio, oferta=of)
    base["_resumo"] = resumo
    return base, _media_aprovadas(hist), inicio


@app.post("/api/painel")
async def api_painel(body: PainelBody, authorization: str | None = Header(None)):
    """
    O retrato do aluno: o que ele cursa, o que falta e o que está ofertado.
    A decisão em si mora em /api/caminhos, /api/plano e /api/e-se.
    """
    tok = _token(authorization)
    if body.fresco:
        _ESPELHO.pop(tok, None)

    espelho = _do_espelho(tok)
    if espelho is None and tok == DEMO_TOKEN:
        espelho = _carrega_demo()
        _guarda_espelho(tok, espelho)
    if espelho is None:
        try:
            f = body.fresco
            me, integ, idx, historico, grade = await asyncio.gather(
                sigaa.get("/v1/me", tok, fresco=f),
                sigaa.get("/v1/integralizacao", tok, fresco=f),
                sigaa.get("/v1/indices", tok, fresco=f),
                sigaa.get("/v1/historico", tok, fresco=f),
                sigaa.get("/v1/grade-horaria", tok, fresco=f),
            )
            plano, oferta_info = await _oferta_do_alvo(tok, me, fresco=f)
            estrutura = await _estrutura_do_curso(
                me, (historico or {}).get("vinculo") or {})
            try:
                previsao = await sigaa.get("/v1/planejamento/previsao-oferta", tok,
                                           fresco=f, alvo=oferta_info["alvo"])
            except sigaa.SigaaIndisponivel:
                previsao = {}
        except sigaa.SessaoExpirada as e:
            raise HTTPException(401, str(e))
        except sigaa.SigaaOcupado as e:
            raise HTTPException(503, str(e))
        except sigaa.SigaaIndisponivel as e:
            raise HTTPException(502, str(e))
        espelho = {"me": me, "integ": integ, "idx": idx, "historico": historico,
                   "grade": grade, "plano": plano, "oferta_info": oferta_info,
                   "previsao": previsao, "estrutura": estrutura,
                   "carregado_em": time.time()}
        _guarda_espelho(tok, espelho)

    me = espelho["me"]; integ = espelho["integ"]; idx = espelho["idx"]
    hist = (espelho["historico"] or {}).get("componentes") or []
    vinculo = (espelho["historico"] or {}).get("vinculo") or {}
    plano = espelho["plano"]; oferta_info = espelho["oferta_info"]
    of = moferta.Oferta(espelho.get("previsao") or {})
    alvo = oferta_info["alvo"]

    reqs = {r["codigo"]: r for r in (plano.get("requisitos") or [])}
    cands = {c["codigo"]: c for c in (plano.get("candidatos") or [])}
    periodo_letivo = int(vinculo.get("periodo_letivo_atual") or 1)

    def enfeita(c: dict) -> dict:
        cod = c.get("codigo")
        r = reqs.get(cod, {})
        ideal = c.get("semestre_ideal") or periodo_letivo
        return {
            "codigo": cod, "nome": c.get("nome"),
            "natureza": c.get("natureza"),
            "carga_horaria": c.get("carga_horaria"),
            # o atraso é recontado depois da fila, a partir do semestre de
            # avaliação (ver abaixo); aqui fica só o nível da matéria
            "nivel": c.get("semestre_ideal"),
            "atraso": 0,
            "desbloqueia": c.get("desbloqueia") or [],
            "pre_requisitos": r.get("pre_requisitos") or c.get("pre_requisitos"),
            "apto": c.get("apto"),
            "faltando": mplano.falta_mesmo({**c, **r}),
            "padrao_oferta": of.explica(cod, alvo),
            "turmas": [{"codigo_turma": t.get("codigo_turma"),
                        "docentes": t.get("docentes") or [],
                        "horario_codigo": t.get("horario_codigo"),
                        "horarios": t.get("horarios") or []}
                       for t in (c.get("turmas") or [])],
        }

    todos = [enfeita(c) for c in (plano.get("candidatos") or [])]
    aptos = [c for c in todos if c["apto"]]
    optativas = [c for c in aptos if c["natureza"] != "OBRIGATORIO"]
    obrigatorias = [c for c in aptos if c["natureza"] == "OBRIGATORIO"]
    ordem = lambda c: (-len(c["desbloqueia"]), -c["atraso"], c["codigo"])
    optativas.sort(key=ordem); obrigatorias.sort(key=ordem)

    pendentes_todas = []
    a_cursar = {(p.get("codigo") or "") for p in
                (integ.get("obrigatorios_pendentes") or [])}
    for p in (integ.get("obrigatorios_pendentes") or []):
        cod = p.get("codigo")
        r = reqs.get(cod, {}); c = cands.get(cod, {})
        pendentes_todas.append({
            "codigo": cod, "nome": p.get("nome"),
            "carga_horaria": p.get("carga_horaria"),
            "matriculado": bool(p.get("matriculado")),
            "ofertada": cod in cands,
            "apto": c.get("apto") if c else r.get("apto"),
            "faltando": mplano.falta_mesmo({**c, **r} if c else r,
                                           preferir=a_cursar),
            "pre_requisitos": r.get("pre_requisitos") or c.get("pre_requisitos"),
            "padrao_oferta": of.explica(cod, alvo),
            "desbloqueia": c.get("desbloqueia") or [],
        })

    # Resolução CAE 02/2017: a posição na fila de vaga. Só entra o que o aluno
    # pode de fato PEDIR — o que já cursa e o que não é disciplina ficam fora.
    pedir = [p["codigo"] for p in _so_a_cursar(pendentes_todas)]
    pedir += [c["codigo"] for c in optativas[:12]]
    estrutura = espelho.get("estrutura")
    # Matéria cumprida por EQUIVALÊNCIA (LETA09 feita através de LETF01) vem do
    # SIGAA numa lista à parte, `historico.equivalencias`, e não no histórico
    # de componentes. Sem ela, a fila listava LETA09 como faltando no nível 4
    # (validação de 10/11). A regra da fila é a mesma: só a entrada fica
    # completa, com o que o próprio SIGAA declara como cumprido.
    equivalentes = [{"codigo": (e.get("componente") or {}).get("codigo"),
                     "situacao": "CUMP", "por_equivalencia": True}
                    for e in ((espelho["historico"] or {}).get("equivalencias") or [])
                    if e.get("tipo") == "Cumpriu" and (e.get("componente") or {}).get("codigo")]
    fila = (mfila.posicao(estrutura, hist + equivalentes, integ, idx,
                          {**vinculo, "periodo_atual": me.get("semestre_atual")},
                          sorted(set(pedir)))
            if estrutura else None)

    # "N sem. atrasada" conta a partir do semestre de AVALIAÇÃO (SA), não do
    # cronológico: é a mesma conta do agrupamento (`_mineracao`) e da fila.
    # Antes "Montar" contava do cronológico e o k-médias do SA, e a mesma
    # matéria tinha duas idades na tela (MAT236: 4 num lugar, 2 no outro). Do
    # cronológico, todo dessemestralizado vê tudo "atrasado", inclusive o que
    # está À FRENTE de onde ele de fato está na matriz (MATE11, nível 6, com
    # SA 5); do SA, sobra o que é dívida de verdade.
    sa = (fila or {}).get("sa")
    for c in obrigatorias + optativas:
        c["atraso"] = _atraso(c.get("nivel"), sa)
    obrigatorias.sort(key=ordem)

    return {
        "aluno": {
            "nome": me.get("nome"), "nome_abreviado": me.get("nome_abreviado"),
            "curso": (me.get("curso") or {}).get("nome"),
            "unidade": (me.get("curso") or {}).get("unidade_sigla"),
            "matricula": me.get("matricula"),
            "semestre": me.get("semestre_atual"),
            "periodo_letivo": periodo_letivo,
            "curriculo": vinculo.get("curriculo"),
            "prazo_padrao": vinculo.get("prazo_conclusao_padrao"),
            "prazo_maximo": vinculo.get("prazo_conclusao_maximo"),
            # de onde o prazo sai: o campo da estrutura, contado da entrada,
            # mais trancamento total e prorrogação (a tela refaz a conta)
            "prazo_maximo_semestres": (estrutura or {}).get("prazo_maximo"),
            "ingresso": vinculo.get("ingresso_periodo"),
            "suspensoes": vinculo.get("suspensoes") or [],
            "prorrogacoes": vinculo.get("prorrogacoes"),
        },
        "dados": {"carregado_em": espelho.get("carregado_em"),
                  "demo": tok == DEMO_TOKEN},
        "situacao": msituacao.resumo(integ, pendentes_todas, optativas,
                                     msituacao.optativas_em_curso(hist)),
        "integralizacao": integ,
        "indices": idx,
        "cursando": _cursando(hist, espelho["grade"]),
        "pendentes": _so_a_cursar(pendentes_todas),
        "mineracao": _mineracao(_so_a_cursar(pendentes_todas), fila,
                                espelho.get("previsao") or {}),
        "optativas": optativas,
        "obrigatorias_ofertadas": obrigatorias,
        "fila": fila,
        "oferta": {
            "ano": plano.get("ano"), "periodo": plano.get("periodo"),
            "total_ofertados": plano.get("total_ofertados_para_o_curso"),
            "avisos": plano.get("avisos") or [],
            "semestre_alvo": alvo,
            "oferta_de": oferta_info["oferta_de"],
            "proxy": oferta_info["proxy"],
            "aviso_proxy": oferta_info["aviso"],
            "provaveis": (espelho.get("previsao") or {}).get("provaveis") or [],
            "improvaveis": (espelho.get("previsao") or {}).get("improvaveis") or [],
        },
    }


@app.post("/api/plano")
async def api_plano(body: PlanoBody, authorization: str | None = Header(None)):
    """
    "Quero me formar até tal data, o que preciso fazer?"
    Devolve a grade semestre a semestre e o veredito de viabilidade.
    """
    tok = _token(authorization)
    dados = await _contexto_do_plano(tok)
    if dados is None:
        raise HTTPException(409, "carregue o painel antes de pedir o plano")
    base, media, inicio = dados
    resumo = base.pop("_resumo")
    hist = _hist_do_espelho(tok)

    mais_cedo = mplano.monta(por_semestre=8, **base)

    if body.por_semestre:
        r = mplano.monta(por_semestre=body.por_semestre, alvo=body.alvo,
                         **_restr(body), **base)
        r["carga_necessaria"] = body.por_semestre
    elif body.alvo:
        r = mplano.menor_carga_para(body.alvo, **_restr(body), **base)
    else:
        r = mplano.monta(por_semestre=4, **_restr(body), **base)
        r["carga_necessaria"] = 4

    carga = r.get("carga_necessaria")
    prazo = _prazo_maximo(tok)
    r["comparacao"] = {
        "media_aprovadas_por_semestre": media,
        "veredito": _veredito(carga, media, r.get("alcanca_alvo"), body.alvo,
                              r.get("conclusao"), prazo),
        "prazo_maximo": prazo,
        "diante_do_prazo": _diante_do_prazo(r.get("conclusao"), prazo),
    }
    r["inicio_do_plano"] = inicio
    r["mais_cedo_possivel"] = mais_cedo["conclusao"]
    r["situacao"] = resumo
    # Chance de oferta de cada matéria NO semestre em que o plano a pôs. O
    # planejador aceita qualquer chance a partir de 50%, então pode empilhar
    # duas matérias de 50% no mesmo semestre (MATC94 e MATC99 em 2028.2). A
    # regra não muda hoje; a tela passa a DIZER que aquele semestre é incerto.
    of = base["oferta"]
    for s in r.get("semestres") or []:
        for c in s.get("componentes") or []:
            cod = c.get("codigo")
            if (cod and cod != "OPTATIVA" and of.motivo(cod) is None
                    and not of.sem_historico(cod)):
                c["chance_oferta"] = of.chance(cod, s["periodo"])
    return r


def _perfil_de_oferta(previsao: dict) -> tuple[dict[str, float], set[str]]:
    """
    Dois números por componente, tirados da previsão de oferta:
      - raridade: fração dos semestres analisados em que ele NÃO abriu;
      - se ele é atividade (TCC, estágio), que não abre turma nenhuma.

    A segunda informação é indispensável no agrupamento: sem ela o TCC entra
    como "raridade 1,0" e o k-médias o lê como a disciplina mais rara do curso,
    quando na verdade ele não depende de vaga.
    """
    raridade: dict[str, float] = {}
    atividades: set[str] = set()
    for c in ((previsao or {}).get("componentes") or []):
        cod = c.get("codigo")
        if not cod:
            continue
        if c.get("sem_turma") or c.get("tipo") == "ATIVIDADE":
            atividades.add(cod)
        r = c.get("resumo") or {}
        analisados = r.get("periodos_analisados") or []
        if analisados:
            sem = r.get("periodos_sem_oferta") or []
            raridade[cod] = len(sem) / len(analisados)
    return raridade, atividades


def _mineracao(pendentes: list[dict], fila: dict | None, previsao: dict) -> dict:
    """
    Roda as duas funções analíticas do `nucleo/mineracao.py` sobre o retrato
    atual do aluno e devolve o bloco pronto para a tela.

    Entrada de cada uma, explicitada aqui porque o enunciado do trabalho cobra
    entrada → processamento → resultado decisório:

      agrupamento  entrada: as pendências, com quanto cada uma destrava, quão
                   raro abre, quanto está atrasada na matriz e quanto pesa.
      associação   entrada: o histórico de oferta dos últimos semestres, um
                   semestre por transação.
    """
    raridade, atividades = _perfil_de_oferta(previsao)
    sa = (fila or {}).get("sa")
    sd = {c.get("codigo"): c.get("sd")
          for c in ((fila or {}).get("componentes") or [])}

    entradas = []
    for p in pendentes:
        cod = p.get("codigo")
        meu_sd = sd.get(cod)
        entradas.append({
            "codigo": cod,
            "nome": p.get("nome"),
            "destrava": len(p.get("desbloqueia") or []),
            # sem previsão para o código, assume o meio: não inventa nem
            # "abre sempre" nem "nunca abre"
            "raridade": raridade.get(cod, 0.5),
            "atraso": _atraso(meu_sd, sa),
            "carga": p.get("carga_horaria") or 0,
            "fora_de_oferta": cod in atividades,
        })

    # A tela "Como a conta é feita" mostra a ENTRADA de cada função, não só o
    # resultado: as linhas exatas que o k-médias recebeu e a matriz de oferta
    # (disciplina × semestre) que o apriori minerou. Só exposição — nenhum
    # cálculo muda.
    _, periodos, por_cod, _ = mmin.transacoes_de_oferta(previsao)
    return {
        "agrupamento": mmin.agrupar(entradas),
        "associacao": mmin.regras_de_cooferta(previsao),
        "entradas_agrupamento": entradas,
        "matriz_oferta": {"periodos": periodos,
                          "abriu": {c: sorted(p) for c, p in por_cod.items()}},
    }


def _atraso(nivel, sa) -> int:
    """Semestres de matriz que a matéria está ATRÁS do semestre de avaliação.
    Uma conta só, usada em "Montar o semestre" e no agrupamento."""
    return max(0, int(sa) - int(nivel)) if (sa and nivel) else 0


def _enxuga_leve(c: dict) -> dict:
    return {"codigo": c.get("codigo"), "carga_horaria": c.get("carga_horaria")}


APROVADO_SIT = ("APR", "APRN", "DISP", "CUMP")
JANELA_RITMO = 5


def _ritmo(hist: list[dict]) -> dict:
    """
    Quantas matérias o aluno costuma APROVAR por semestre.

    Dois cuidados que mudam muito o número:
      - semestre de trancamento total (nada cursado) não entra, senão puxa a
        média para baixo descrevendo um semestre que não existiu;
      - o semestre em curso não entra, porque ainda não tem resultado.
    Olha só os últimos semestres, porque o ritmo de 2022 não descreve o de hoje.
    """
    por: dict[str, dict] = {}
    for c in hist:
        p = c.get("periodo")
        sit = c.get("situacao")
        if not p or sit == "MATR":
            continue
        d = por.setdefault(p, {"aprovadas": 0, "encerradas": 0})
        d["encerradas"] += 1
        if sit in APROVADO_SIT:
            d["aprovadas"] += 1

    cursados = [(p, d) for p, d in sorted(por.items())
                if d["encerradas"] > 0 and d["aprovadas"] > 0]
    janela = cursados[-JANELA_RITMO:]
    if not janela:
        return {"media": 0.0, "semestres": [], "janela": 0}
    media = sum(d["aprovadas"] for _, d in janela) / len(janela)
    return {
        "media": round(media, 1),
        "janela": len(janela),
        "semestres": [{"periodo": p, "aprovadas": d["aprovadas"]} for p, d in janela],
    }


def _media_aprovadas(hist: list[dict]) -> float:
    return _ritmo(hist)["media"]


def _prazo_maximo(tok: str) -> str | None:
    """O prazo máximo de conclusão do vínculo, como o histórico do SIGAA traz."""
    esp = _do_espelho(tok) or {}
    return ((esp.get("historico") or {}).get("vinculo") or {}).get("prazo_conclusao_maximo")


def _diante_do_prazo(conclusao: str | None, prazo: str | None) -> str | None:
    """'passa' (termina depois do prazo máximo), 'no_limite' (termina nele) ou
    'dentro'. None quando não se sabe o prazo."""
    if not conclusao or not prazo:
        return None
    d = moferta.distancia(prazo, conclusao)
    return "passa" if d > 0 else ("no_limite" if d == 0 else "dentro")


def _veredito(carga: int | None, media: float, alcanca, alvo: str | None,
              conclusao: str | None = None, prazo: str | None = None) -> str:
    """
    O juízo de um caminho: a carga contra o ritmo E a data contra o prazo
    máximo do curso. Antes só a carga entrava, e o caminho de 2031.2 (2 por
    semestre, além do prazo de 2030.1) saía "Dá, com folga" com o aviso de
    prazo estourado logo embaixo: a tela dizia as duas coisas. Carga leve não
    salva caminho que termina depois do prazo; e o que termina NO prazo não
    tem semestre de margem, por mais que a carga caiba.
    """
    if carga is None:
        return ("Mesmo pegando 8 matérias por semestre não dá para fechar até "
                f"{alvo}. O alvo precisa ser mais tarde.")
    lado = _diante_do_prazo(conclusao, prazo)
    if lado == "passa":
        if 0 < media and carga <= media:
            return (f"Não é uma opção: {carga} por semestre fica abaixo do seu ritmo de "
                    f"{media}, mas termina em {conclusao}, depois do prazo máximo ({prazo}).")
        return (f"Não é uma opção: termina em {conclusao}, depois do prazo "
                f"máximo ({prazo}).")
    if media <= 0:
        return f"O plano pede {carga} matérias por semestre."
    limite = (f" E termina em {conclusao}, o próprio prazo máximo: qualquer atraso "
              f"passa do prazo.") if lado == "no_limite" else ""
    if carga <= media:
        if lado == "no_limite":
            return (f"Cabe no seu ritmo ({carga} por semestre, ritmo {media}), mas "
                    f"termina em {conclusao}, o próprio prazo máximo: qualquer atraso "
                    f"passa do prazo.")
        antes = (moferta.distancia(conclusao, prazo) if lado == "dentro" else 0)
        margem = (f", e termina {antes} {'semestre' if antes == 1 else 'semestres'} "
                  f"antes do prazo máximo ({prazo})") if antes > 0 else ""
        return f"Dá, com folga: {carga} por semestre, ritmo {media}{margem}."
    # "Um tropeço empurra a formatura" saiu: no caminho de 4 por semestre a
    # simulação logo abaixo mostra que nenhuma reprovação sozinha atrasa. O
    # que a carga diz de certo é só isto; o custo de reprovar fica no "E se".
    if carga <= media + 1.5:
        return (f"Dá, mas apertado: {carga} por semestre contra um ritmo de "
                f"{media}.{limite}")
    # "considere um alvo mais tarde" só vale se houver alvo mais tarde dentro
    # do prazo; no limite, o conselho mandaria o aluno para fora dele
    if lado == "no_limite":
        return (f"É arriscado: {carga} por semestre contra um ritmo de {media}, "
                f"e termina em {conclusao}, o próprio prazo máximo: não há alvo "
                f"mais tarde dentro do prazo.")
    return (f"É arriscado: {carga} por semestre contra um ritmo de {media}. "
            f"Considere um alvo mais tarde.")


def _restr(body) -> dict:
    return {"limites": body.limites, "pular": body.pular,
            "fixar": body.fixar, "reprovar": body.reprovar}


@app.post("/api/e-se")
async def api_e_se(body: PlanoBody, authorization: str | None = Header(None)):
    """
    Análise de sensibilidade: quanto cada reprovação custaria, em semestres.

    Não é recomendação — é o custo de um evento que o aluno pode querer
    considerar. Ele olha a lista e decide onde quer colocar energia.
    """
    tok = _token(authorization)
    dados = await _contexto_do_plano(tok)
    if dados is None:
        raise HTTPException(409, "carregue o painel antes")
    base, media, _ = dados
    base.pop("_resumo", None)
    n = body.por_semestre or 4

    normal = mplano.monta(por_semestre=n, limites=body.limites,
                          pular=body.pular, fixar=body.fixar, **base)
    ref = normal["conclusao"]

    linhas = []
    for c in base["pendentes"]:
        alt = mplano.monta(por_semestre=n, limites=body.limites,
                           pular=body.pular, fixar=body.fixar,
                           reprovar=[c["codigo"]], **base)
        atraso = moferta.distancia(ref, alt["conclusao"])
        linhas.append({
            "codigo": c["codigo"], "nome": c.get("nome"),
            "conclusao_se_reprovar": alt["conclusao"],
            "atraso_semestres": atraso,
            "padrao_oferta": base["oferta"].explica(c["codigo"], ref),
        })
    linhas.sort(key=lambda x: (-x["atraso_semestres"], x["codigo"]))
    custam = [l for l in linhas if l["atraso_semestres"] > 0]

    # Onze linhas de "+0" não informam nada. Quando o ritmo escolhido tem
    # folga, o resultado é UMA frase: nenhuma reprovação isolada atrasa.
    if not custam:
        frase = (f"Com {n} por semestre, nenhuma reprovação sozinha atrasa a "
                 f"formatura: o plano tem vaga para refazer a matéria.")
    else:
        pior = custam[0]["atraso_semestres"]
        quais = ", ".join(l["codigo"] for l in custam if
                          l["atraso_semestres"] == pior)
        frase = (f"Com {n} por semestre, reprovar em {quais} é o que custa "
                 f"mais: {pior} semestre{'s' if pior > 1 else ''} a mais.")

    return {"conclusao_base": ref, "por_semestre": n, "impactos": linhas,
            "custam": custam, "sem_custo": len(linhas) - len(custam),
            "frase": frase}


@app.post("/api/caminhos")
async def api_caminhos(body: PlanoBody, authorization: str | None = Header(None)):
    """
    Os caminhos possíveis, lado a lado. É a tela que faz do Rota um apoio à
    decisão e não um gerador de grade: o aluno vê o que cada data de formatura
    custa em carga por semestre, e escolhe.
    """
    tok = _token(authorization)
    dados = await _contexto_do_plano(tok)
    if dados is None:
        raise HTTPException(409, "carregue o painel antes de pedir os caminhos")
    base, media, inicio = dados
    base.pop("_resumo", None)

    mais_cedo = mplano.monta(por_semestre=8, **base)["conclusao"]
    prazo = _prazo_maximo(tok)
    caminhos = []
    alvo = mais_cedo
    # Um caminho por DATA DE CONCLUSÃO real. Pedir "até 2030.2" e "até 2029.2"
    # pode devolver exatamente o mesmo plano — e oferecer duas vezes a mesma
    # coisa com nomes diferentes é fingir uma escolha que não existe.
    vistos: set[str] = set()
    for _ in range(8):
        r = mplano.menor_carga_para(alvo, **base)
        carga = r.get("carga_necessaria")
        if carga and r["conclusao"] not in vistos:
            vistos.add(r["conclusao"])
            caminhos.append({
                "alvo": r["conclusao"],
                "pedido": alvo,
                "por_semestre": carga,
                "semestres": r["total_semestres"],
                "carga_total_h": sum(s["carga_horaria"] for s in r["semestres"]),
                "obrigatorias": sum(s["obrigatorias"] for s in r["semestres"]),
                "optativas": sum(s["optativas"] for s in r["semestres"]),
                "por_periodo": [{"periodo": s["periodo"], "n": len(s["componentes"]),
                                 "obrig": s["obrigatorias"], "opt": s["optativas"],
                                 "ch": s["carga_horaria"]} for s in r["semestres"]],
                "veredito": _veredito(carga, media, True, r["conclusao"],
                                      r["conclusao"], prazo),
                # folga de CARGA (ritmo menos carga) e, à parte, a posição da
                # data contra o prazo máximo: as duas entram no rótulo
                "folga": round(media - carga, 1),
                "diante_do_prazo": _diante_do_prazo(r["conclusao"], prazo),
            })
        alvo = moferta.proximo_periodo(alvo)
    return {"media_aprovadas_por_semestre": media, "mais_cedo_possivel": mais_cedo,
            "inicio_do_plano": inicio, "prazo_maximo": prazo, "caminhos": caminhos,
            "ritmo": _ritmo(_hist_do_espelho(tok))}


@app.get("/api/status")
async def api_status():
    # Em modo demonstração não se bate na API de origem: ela pode nem existir
    # no ambiente onde a instância pública roda, e perguntar por ela deixaria
    # a tela de login pendurada esperando um timeout.
    return {"rota": "ok", "modo": MODO, "so_demo": SO_DEMO,
            "sigaa_api": None if SO_DEMO else await sigaa.status()}


app.mount("/assets", StaticFiles(directory=WEB), name="assets")


def _versiona_assets() -> None:
    """
    Carimba o hash do conteúdo na URL do CSS e do JS a cada boot. Sem isto, o
    navegador serve a versão antiga do cache e some com correções que já estão
    no disco — o que me custou uma hora de caça a um erro que não existia.
    """
    import hashlib
    import re as _re
    try:
        idx = WEB / "index.html"
        html = idx.read_text(encoding="utf-8")
        for nome in ("style.css", "app.js"):
            v = hashlib.md5((WEB / nome).read_bytes()).hexdigest()[:8]
            html = _re.sub(rf"/assets/{nome}(\?v=[0-9a-f]+)?",
                           f"/assets/{nome}?v={v}", html)
        idx.write_text(html, encoding="utf-8")
    except Exception:
        pass


_versiona_assets()


@app.get("/")
async def raiz():
    return FileResponse(WEB / "index.html")
