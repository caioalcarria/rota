"""
Funções analíticas do Rota: agrupamento e associação.

Por que este módulo existe
--------------------------
O enunciado do Trabalho Final exige que o sistema empregue, *de forma
justificada*, pelo menos três funções entre sumarização, agrupamento,
associação, regressão e classificação, indicando para cada uma **entrada,
processamento e resultado decisório**.

O Rota já fazia sumarização (`nucleo/situacao.py` e o ritmo em `app.py`).
Faltavam duas, e elas não entram aqui como enfeite: cada uma responde uma
pergunta que o aluno dessemestralizado faz e que o sistema não respondia.

  AGRUPAMENTO  — "são 18 matérias; por onde eu começo?"
                 Agrupa as pendências por PERFIL (quanto destrava, quão raro
                 abre, quão atrasada está, quanto pesa) e nomeia cada grupo
                 pelo que o centróide tem de extremo. Resultado decisório: o
                 aluno ataca o grupo gargalo primeiro, não a lista inteira.

  ASSOCIAÇÃO   — "dá pra pegar estas duas no mesmo semestre?"
                 Minera o histórico de oferta: cada semestre é uma transação,
                 cada disciplina ofertada é um item. Resultado decisório: pares
                 que costumam abrir JUNTOS podem ser planejados no mesmo
                 semestre; pares que nunca abriram juntos, não.

Por que sem biblioteca
----------------------
k-médias e apriori estão implementados aqui em Python puro, sem scikit-learn
nem mlxtend. Três motivos: (1) o professor precisa conseguir rodar o protótipo,
e `requirements.txt` com três pacotes instala em qualquer lugar; (2) n é
pequeno (dezenas de pontos, 8 transações) — a vantagem de performance das
bibliotecas não existe nessa escala; (3) o apriori é o algoritmo de AGRAWAL &
SRIKANT (1994), que está na própria lista de referências da disciplina, e
escrevê-lo é mais honesto do que importá-lo.

Limitação declarada
-------------------
As duas funções rodam sobre o histórico de UM aluno e sobre 8 semestres de
oferta. Os números são exatos (não são estimativas), mas o suporte é pequeno:
por isso a saída sempre carrega a CONTAGEM ABSOLUTA ("em 6 dos 8 semestres"),
e não só o percentual. Regressão e classificação foram testadas e REJEITADAS
com evidência — ver `validacao/resultado-backtest.md`.
"""

from __future__ import annotations

from itertools import combinations

# --------------------------------------------------------------------------
# AGRUPAMENTO — k-médias
# --------------------------------------------------------------------------

EIXOS = [
    ("destrava", "quantas matérias ela libera"),
    ("raridade", "fração dos semestres em que NÃO abriu"),
    ("atraso", "quantos semestres de matriz ela está atrás de você"),
    ("carga", "carga horária"),
]


def _zscore(linhas: list[list[float]]) -> tuple[list[list[float]], list[dict]]:
    """
    Padroniza cada eixo. Sem isso a carga horária (60, 68, 102) domina tudo e
    o agrupamento vira "por carga horária", escondendo os outros três eixos.

    Eixo com desvio zero (todas as matérias com o mesmo valor) vira constante 0
    em vez de divisão por zero: ele simplesmente não separa ninguém.
    """
    n = len(linhas)
    if not n:
        return [], []
    k = len(linhas[0])
    escalas = []
    for j in range(k):
        col = [l[j] for l in linhas]
        media = sum(col) / n
        var = sum((x - media) ** 2 for x in col) / n
        dp = var ** 0.5
        escalas.append({"media": media, "desvio": dp})
    z = [[0.0 if escalas[j]["desvio"] == 0
          else (l[j] - escalas[j]["media"]) / escalas[j]["desvio"]
          for j in range(k)] for l in linhas]
    return z, escalas


def _dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _sementes(pontos: list[list[float]], k: int) -> list[list[float]]:
    """
    Início DETERMINÍSTICO: ordena os pontos pela soma dos eixos padronizados
    (que é a projeção no vetor 1,1,1,1 — o eixo do "mais de tudo") e pega k
    posições igualmente espaçadas.

    k-médias com início aleatório daria um agrupamento diferente a cada
    execução, e num trabalho avaliado o resultado tem que ser reproduzível:
    o professor roda e vê o mesmo que está no PDF.
    """
    ordem = sorted(range(len(pontos)), key=lambda i: (sum(pontos[i]), i))
    if k <= 1:
        return [list(pontos[ordem[0]])]
    passo = (len(ordem) - 1) / (k - 1)
    return [list(pontos[ordem[round(i * passo)]]) for i in range(k)]


def _kmedias(pontos: list[list[float]], k: int, max_iter: int = 100):
    """k-médias clássico. Devolve (rótulos, centróides, iterações)."""
    cents = _sementes(pontos, k)
    rotulos = [0] * len(pontos)
    iteracoes = 0
    for iteracoes in range(1, max_iter + 1):
        novos = [min(range(k), key=lambda c: _dist(p, cents[c])) for p in pontos]
        if novos == rotulos and iteracoes > 1:
            break
        rotulos = novos
        for c in range(k):
            membros = [p for p, r in zip(pontos, rotulos) if r == c]
            if membros:
                cents[c] = [sum(m[j] for m in membros) / len(membros)
                            for j in range(len(membros[0]))]
    return rotulos, cents, iteracoes


def _silhueta(pontos: list[list[float]], rotulos: list[int]) -> float:
    """
    Silhueta média: para cada ponto, quanto ele está mais perto dos seus do que
    do grupo vizinho mais próximo. Vai de -1 a 1. É o critério que usamos para
    ESCOLHER o k, em vez de arbitrar 3 — e o número entra no relatório, porque
    silhueta baixa é um resultado legítimo e precisa aparecer.
    """
    n = len(pontos)
    grupos: dict[int, list[int]] = {}
    for i, r in enumerate(rotulos):
        grupos.setdefault(r, []).append(i)
    if len(grupos) < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        meu = rotulos[i]
        iguais = [j for j in grupos[meu] if j != i]
        a = (sum(_dist(pontos[i], pontos[j]) for j in iguais) / len(iguais)
             if iguais else 0.0)
        b = min(sum(_dist(pontos[i], pontos[j]) for j in grupos[g]) / len(grupos[g])
                for g in grupos if g != meu)
        if max(a, b) > 0:
            total += (b - a) / max(a, b)
    return total / n if n else 0.0


def _nomeia(centroide: list[float]) -> tuple[str, str]:
    """
    Nomeia o grupo pelo que o centróide tem de EXTREMO em unidades de desvio
    padrão. Nada de rótulo inventado: o nome é uma leitura do número.
    """
    destrava, raridade, atraso, carga = centroide
    if destrava >= 0.5 and raridade >= 0.3:
        return ("Gargalo", "destrava mais que a média E abre menos que a média: "
                           "perder a janela custa caro")
    if destrava >= 0.5:
        return ("Destrava o caminho", "libera mais matérias que a média — "
                                      "adiar atrasa tudo que vem depois")
    if raridade >= 0.5:
        return ("Janela estreita", "abre em menos semestres que a média: "
                                   "quando abrir, é a hora")
    if atraso >= 0.5:
        return ("Atrasada", "está mais atrás na matriz que a média das suas "
                            "pendências")
    return ("Encaixe livre", "sem extremo nenhum: entra quando sobrar vaga")


def agrupar(componentes: list[dict], ks: tuple[int, ...] = (2, 3, 4)) -> dict:
    """
    Agrupa as pendências por perfil.

    `componentes` é uma lista de dicts com, no mínimo:
        codigo, nome, destrava (int), raridade (0..1), atraso (int), carga (int)

    Devolve os grupos, a silhueta de cada k testado e o k escolhido.
    """
    # TCC, estágio e atividades NÃO entram. Elas nunca abrem turma, então o
    # eixo "raridade" marcaria 100% para elas e o agrupamento leria isso como
    # "disciplina raríssima, corra atrás". É o contrário: elas não dependem de
    # vaga. Entrariam como outlier e puxariam um grupo só para si — foi o que
    # aconteceu na primeira execução, com o Estágio virando um grupo de um.
    fora = [c for c in componentes if c.get("fora_de_oferta")]
    uteis = [c for c in componentes
             if c.get("codigo") and not c.get("fora_de_oferta")]
    if len(uteis) < 4:
        return {"aplicavel": False,
                "motivo": f"São só {len(uteis)} pendências que dependem de "
                          f"oferta — agrupar não acrescenta nada a uma lista "
                          f"que cabe na tela.",
                "grupos": [],
                "fora": [{"codigo": c["codigo"], "nome": c.get("nome")}
                         for c in fora]}

    linhas = [[float(c.get("destrava") or 0), float(c.get("raridade") or 0.0),
               float(c.get("atraso") or 0), float(c.get("carga") or 0)]
              for c in uteis]
    z, escalas = _zscore(linhas)

    tentativas = []
    melhor = None
    for k in ks:
        if k >= len(uteis):
            continue
        rot, cents, it = _kmedias(z, k)
        if len(set(rot)) < k:        # grupo vazio: esse k não se sustenta
            tentativas.append({"k": k, "silhueta": None,
                               "nota": "um dos grupos ficou vazio"})
            continue
        s = round(_silhueta(z, rot), 3)
        # Um grupo de UM não é um grupo: é um ponto isolado que a silhueta
        # premia (ele fica sozinho, então a distância interna é zero) e que na
        # tela vira uma gaveta com uma matéria dentro. Sem esta regra, o k=4
        # vencia aqui com um grupo contendo só MATC84.
        sozinho = any(sum(1 for r in rot if r == c) < 2 for c in range(k))
        tentativas.append({"k": k, "silhueta": s, "iteracoes": it,
                           **({"nota": "descartado: grupo com um só membro"}
                              if sozinho else {})})
        if sozinho:
            continue
        if melhor is None or s > melhor["silhueta"]:
            melhor = {"k": k, "silhueta": s, "rotulos": rot, "centroides": cents}

    if melhor is None:
        return {"aplicavel": False,
                "motivo": ("Nenhum k testado deu grupos com pelo menos duas "
                           "matérias cada."),
                "tentativas": tentativas, "grupos": []}

    grupos = []
    for c in range(melhor["k"]):
        membros = [uteis[i] for i, r in enumerate(melhor["rotulos"]) if r == c]
        if not membros:
            continue
        nome, porque = _nomeia(melhor["centroides"][c])
        grupos.append({
            "id": c, "nome": nome, "porque": porque,
            "quantos": len(membros),
            # média em unidade de VERDADE (não em z), que é o que o aluno lê
            "perfil": {
                "destrava": round(sum(m.get("destrava") or 0 for m in membros) / len(membros), 1),
                "abre_em_pct": round(100 * (1 - sum(m.get("raridade") or 0 for m in membros) / len(membros))),
                "atraso": round(sum(m.get("atraso") or 0 for m in membros) / len(membros), 1),
                "carga": round(sum(m.get("carga") or 0 for m in membros) / len(membros)),
            },
            "componentes": [{"codigo": m["codigo"], "nome": m.get("nome")}
                            for m in sorted(membros,
                                            key=lambda x: (-(x.get("destrava") or 0),
                                                           x["codigo"]))],
        })
    # o grupo mais urgente primeiro: destrava muito e abre pouco
    grupos.sort(key=lambda g: (-g["perfil"]["destrava"], g["perfil"]["abre_em_pct"]))

    # Dois grupos com o mesmo nome deixam a tela sem sentido ("em qual eu
    # mexo?"). Quando o rótulo repete, o segundo é desempatado pelo eixo em que
    # os dois mais diferem, com o número junto — continua sendo leitura do
    # centróide, não nome inventado.
    vistos: dict[str, dict] = {}
    for g in grupos:
        if g["nome"] not in vistos:
            vistos[g["nome"]] = g
            continue
        irmao = vistos[g["nome"]]
        # "destrava" entra no desempate: no caso de Ciência da Computação os
        # dois "Encaixe livre" só diferem nela, e sem ela o desempate caía em
        # "carga maior/menor" com as duas cargas em 60 h, um rótulo falso
        eixos = ("destrava", "carga", "atraso", "abre_em_pct")
        eixo = max(eixos, key=lambda e: abs(g["perfil"][e] - irmao["perfil"][e]))
        if g["perfil"][eixo] == irmao["perfil"][eixo]:
            continue                      # nada separa os dois: não se inventa
        rotulo = {"destrava": "destrava", "carga": "carga", "atraso": "atraso",
                  "abre_em_pct": "oferta"}[eixo]
        maior = g["perfil"][eixo] > irmao["perfil"][eixo]
        mais, menos = ("mais", "menos") if eixo == "destrava" else ("maior", "menor")
        g["nome"] = f"{g['nome']} · {rotulo} {mais if maior else menos}"
        irmao["nome"] = f"{irmao['nome']} · {rotulo} {menos if maior else mais}"

    return {
        "aplicavel": True,
        "k": melhor["k"],
        "silhueta": melhor["silhueta"],
        "tentativas": tentativas,
        "eixos": [{"nome": n, "o_que_e": d} for n, d in EIXOS],
        "escalas": [{"eixo": EIXOS[j][0], "media": round(escalas[j]["media"], 2),
                     "desvio": round(escalas[j]["desvio"], 2)}
                    for j in range(len(EIXOS))],
        "grupos": grupos,
        "n": len(uteis),
        "fora": [{"codigo": c["codigo"], "nome": c.get("nome"),
                  "porque": "não depende de oferta de turma"} for c in fora],
        "metodo": ("k-médias com início determinístico (quantis do eixo "
                   "1,1,1,1), eixos padronizados por z-score; k escolhido pela "
                   "maior silhueta média entre os testados."),
    }


# --------------------------------------------------------------------------
# ASSOCIAÇÃO — apriori sobre o histórico de oferta
# --------------------------------------------------------------------------

def transacoes_de_oferta(previsao: dict, apenas: set[str] | None = None):
    """
    Monta as transações: um semestre = uma transação, uma disciplina ofertada
    naquele semestre = um item.

    Componentes sem turma (TCC, estágio, atividades) ficam de FORA: eles nunca
    aparecem na oferta, então entrariam como item de suporte zero e sujariam
    toda regra. A matrícula deles é por colegiado, não por vaga em turma.
    """
    comps = (previsao or {}).get("componentes") or []
    periodos: set[str] = set()
    por_cod: dict[str, set[str]] = {}
    fora: list[str] = []
    for c in comps:
        cod = c.get("codigo")
        if not cod or (apenas is not None and cod not in apenas):
            continue
        if c.get("sem_turma") or c.get("tipo") == "ATIVIDADE":
            fora.append(cod)
            continue
        r = c.get("resumo") or {}
        analisados = r.get("periodos_analisados") or []
        if not analisados:
            fora.append(cod)
            continue
        periodos |= set(analisados)
        por_cod[cod] = set(r.get("periodos_com_oferta") or [])

    ordenados = sorted(periodos)
    trans = [{cod for cod, ofs in por_cod.items() if p in ofs} for p in ordenados]
    return trans, ordenados, por_cod, fora


def _suporte(trans: list[set[str]], itens: frozenset) -> int:
    return sum(1 for t in trans if itens <= t)


def apriori(trans: list[set[str]], min_suporte: int, max_tam: int = 2):
    """
    AGRAWAL & SRIKANT (1994), por níveis e com poda: um conjunto de tamanho k
    só é candidato se TODOS os seus subconjuntos de tamanho k-1 passaram no
    suporte mínimo.

    `max_tam` é 2 porque a pergunta que o aluno faz é sobre PARES ("posso pegar
    estas duas juntas?"). Trios são calculáveis e não mudariam a decisão.
    """
    frequentes: dict[frozenset, int] = {}
    itens = sorted({i for t in trans for i in t})
    nivel = [frozenset([i]) for i in itens]
    nivel = [c for c in nivel if _suporte(trans, c) >= min_suporte]
    for c in nivel:
        frequentes[c] = _suporte(trans, c)

    tam = 1
    while nivel and tam < max_tam:
        candidatos = set()
        for a, b in combinations(nivel, 2):
            u = a | b
            if len(u) != tam + 1:
                continue
            if all(frozenset(s) in frequentes
                   for s in combinations(u, tam)):      # poda do apriori
                candidatos.add(u)
        nivel = []
        for c in sorted(candidatos, key=sorted):
            s = _suporte(trans, c)
            if s >= min_suporte:
                frequentes[c] = s
                nivel.append(c)
        tam += 1
    return frequentes


def regras_de_cooferta(previsao: dict, apenas: set[str] | None = None,
                       min_suporte_frac: float = 0.25) -> dict:
    """
    Minera "estas duas costumam abrir no mesmo semestre".

    Confiança de A→B = em que fração dos semestres em que A abriu, B também
    abriu. Lift = confiança / suporte(B): acima de 1, as duas andam juntas mais
    do que o acaso explicaria; igual a 1, são independentes.
    """
    trans, periodos, por_cod, fora = transacoes_de_oferta(previsao, apenas)
    n = len(trans)
    if n < 4 or len(por_cod) < 2:
        return {"aplicavel": False,
                "motivo": (f"{n} semestres de histórico e {len(por_cod)} "
                           f"disciplinas com oferta — pouco para minerar."),
                "regras": [], "nunca_juntas": [], "periodos": periodos}

    min_sup = max(2, round(min_suporte_frac * n))
    freq = apriori(trans, min_sup, max_tam=2)

    regras = []
    for conj, sup in freq.items():
        if len(conj) != 2:
            continue
        a, b = sorted(conj)
        for ante, cons in ((a, b), (b, a)):
            sa = freq.get(frozenset([ante]), 0)
            sb = freq.get(frozenset([cons]), 0)
            if not sa or not sb:
                continue
            conf = sup / sa
            lift = conf / (sb / n)
            regras.append({
                "se": ante, "entao": cons,
                "suporte_n": sup, "suporte": round(sup / n, 3),
                "confianca": round(conf, 3), "lift": round(lift, 2),
                "frase": (f"Nos {sup} semestres em que {ante} e {cons} abriram "
                          f"juntas (de {n} analisados), dá para planejar as "
                          f"duas no mesmo semestre."),
            })
    regras.sort(key=lambda r: (-r["lift"], -r["suporte_n"], r["se"]))

    # A pergunta do aluno é simétrica ("dá pra pegar as duas juntas?"), então a
    # tela mostra PARES, não as duas direções da mesma regra. Guarda-se a
    # confiança MENOR das duas: é a garantia mais fraca do par, e prometer a
    # maior seria escolher o número que soa melhor.
    pares = []
    for conj, sup in freq.items():
        if len(conj) != 2:
            continue
        a, b = sorted(conj)
        lado = [r for r in regras if {r["se"], r["entao"]} == {a, b}]
        if not lado:
            continue
        pares.append({
            "a": a, "b": b, "suporte_n": sup, "de_n": n,
            "confianca_min": min(r["confianca"] for r in lado),
            "lift": lado[0]["lift"],
            "frase": (f"abriram juntas em {sup} dos {n} semestres"),
        })
    pares.sort(key=lambda p: (-p["suporte_n"], -p["lift"], p["a"]))

    # Observação direta, não regra minerada: pares que NUNCA coincidiram.
    # Vale mais para a decisão do que qualquer regra positiva, porque é o que
    # quebra um plano — e por isso vem rotulado como observação, não como regra.
    codigos = sorted(por_cod)
    nunca = []
    for a, b in combinations(codigos, 2):
        if por_cod[a] and por_cod[b] and not (por_cod[a] & por_cod[b]):
            nunca.append({
                "a": a, "b": b,
                "a_abriu_n": len(por_cod[a]), "b_abriu_n": len(por_cod[b]),
                "frase": (f"{a} abriu em {len(por_cod[a])} semestres e {b} em "
                          f"{len(por_cod[b])}, e em NENHUM os dois coincidiram: "
                          f"não conte com as duas no mesmo semestre."),
            })
    nunca.sort(key=lambda x: -(x["a_abriu_n"] + x["b_abriu_n"]))

    # --------------------------------------------------------------- leitura
    # Trinta e seis pares com lift 1,00 não são trinta e seis achados: lift 1
    # é INDEPENDÊNCIA, ou seja, a regra não diz nada que o acaso já não diga.
    # Despejar a lista crua seria o painel que o aluno não lê. O que decide é:
    # (1) o que SEMPRE coincidiu, (2) o que raramente coincide, (3) o que nunca
    # coincidiu, e (4) com que frequência cada disciplina abre sozinha.
    frequencia = sorted(
        ({"codigo": cod, "abriu_n": len(ofs), "de_n": n,
          "pct": round(100 * len(ofs) / n)} for cod, ofs in por_cod.items()),
        key=lambda f: (f["abriu_n"], f["codigo"]))

    juntas_sempre = [p for p in pares if p["suporte_n"] == n]
    arriscadas = [p for p in pares if p["confianca_min"] < 0.6]
    dependentes = [p for p in pares if p["lift"] > 1.05]

    if nunca:
        veredito = (f"{len(nunca)} par(es) nunca abriram no mesmo semestre em "
                    f"{n} semestres: esses não podem ser planejados juntos.")
    elif dependentes or arriscadas:
        veredito = (f"Nenhum par ficou impedido, mas {len(arriscadas)} par(es) "
                    f"coincidem em menos de 60% das vezes — planejar os dois no "
                    f"mesmo semestre é aposta.")
    elif all(len(ofs) == n for ofs in por_cod.values()):
        # o caso de Ciência da Computação: toda pendência abriu em todo
        # semestre. A frase antiga culpava a paridade, que aqui não existe.
        veredito = (f"Todas as {len(por_cod)} abriram nos {n} semestres. A "
                    f"oferta não limita o plano; o que limita é o "
                    f"pré-requisito.")
    else:
        veredito = (f"Em {n} semestres, todas as combinações já coincidiram "
                    f"pelo menos uma vez e o lift fica em torno de 1 (as "
                    f"aberturas são independentes entre si). Conclusão para a "
                    f"decisão: a co-oferta NÃO limita o seu plano — o que "
                    f"limita é a paridade de cada disciplina, isolada.")

    return {
        "aplicavel": True,
        "periodos": periodos,
        "transacoes": n,
        "itens": len(por_cod),
        "min_suporte_n": min_sup,
        "fora": fora,
        "regras": regras,
        "pares": pares,
        "frequencia": frequencia,
        "juntas_sempre": juntas_sempre,
        "arriscadas": arriscadas,
        "nunca_juntas": nunca,
        "veredito": veredito,
        "metodo": (f"Apriori (Agrawal & Srikant, 1994) sobre {n} semestres de "
                   f"oferta; cada semestre é uma transação, cada disciplina "
                   f"ofertada é um item; suporte mínimo de {min_sup} semestres."),
    }
