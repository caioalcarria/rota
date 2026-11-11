"""
Previsão de oferta por período.

A UFBA só publica a oferta perto da matrícula, então para planejar 2027.1 não
existe dado de 2027.1. O que existe é o padrão histórico.

Este módulo deixou de inferir a paridade por conta própria e passou a consumir
`/v1/planejamento/previsao-oferta` da sigaa-ufba-api, que olha desde 2023.1 e
pondera os semestres recentes. A mudança corrigiu um erro real: com os três
semestres que eu conseguia raspar, MAT236 parecia "só em semestre par" e o
plano a empurrava um semestre à frente sem necessidade. Ela abre todo semestre.

Guarda-se o padrão em memória; a decisão de "abre neste período?" vira uma
consulta local, sem bater na origem a cada ajuste de parâmetro.
"""

from __future__ import annotations

SEMPRE = "sempre"
IMPAR = "impar"
PAR = "par"
DESCONHECIDA = "desconhecida"
ATIVIDADE = "atividade"

ROTULO = {
    SEMPRE: "ofertada todo semestre",
    IMPAR: "costuma abrir em semestre ímpar",
    PAR: "costuma abrir em semestre par",
    DESCONHECIDA: "sem histórico de oferta",
    ATIVIDADE: "não abre turma: matrícula pelo colegiado",
}

# Abaixo disto a oferta é tratada como improvável no período.
CORTE = 0.5


def paridade(periodo: str) -> int:
    try:
        return int(periodo.split(".")[1])
    except Exception:
        return 1


def proximo_periodo(p: str, passos: int = 1) -> str:
    try:
        ano, per = (int(x) for x in p.split("."))
    except Exception:
        return p
    for _ in range(passos):
        per += 1
        if per > 2:
            per, ano = 1, ano + 1
    return f"{ano}.{per}"


def distancia(de: str, ate: str) -> int:
    try:
        a1, p1 = (int(x) for x in de.split("."))
        a2, p2 = (int(x) for x in ate.split("."))
    except Exception:
        return 0
    return (a2 - a1) * 2 + (p2 - p1)


class Oferta:
    """
    Padrão de oferta por componente, vindo da previsão da API.

    `previsao` é o corpo de /v1/planejamento/previsao-oferta.
    """

    def __init__(self, previsao: dict | None = None):
        self._chance: dict[str, tuple[float, float]] = {}   # cod -> (ímpar, par)
        # a contagem CRUA por lado do ano: ((abriu, analisados) ímpar, idem par).
        # Vai sempre ao lado da chance ponderada: 17% sozinho parece preciso e
        # esconde que a base são 4 observações.
        self._contagem: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}
        self._ultima: dict[str, str | None] = {}
        self._sem_historico: set[str] = set()
        # TCC e estágio nunca abrem turma: a previsão devolve 0% e dizer
        # "sem histórico de oferta" faz o aluno achar que a matéria sumiu.
        # A API explica o caso, e é essa explicação que vai para a tela.
        self._atividades: dict[str, str] = {}

        for c in ((previsao or {}).get("componentes") or []):
            cod = c.get("codigo")
            if not cod:
                continue
            if c.get("sem_turma") or c.get("tipo") == "ATIVIDADE":
                self._atividades[cod] = (
                    (c.get("previsao") or {}).get("motivo") or ROTULO[ATIVIDADE])
                self._sem_historico.add(cod)
                continue
            r = c.get("resumo") or {}
            ci = r.get("chance_impar")
            cp = r.get("chance_par")
            if ci is None and cp is None:
                self._sem_historico.add(cod)
                continue
            self._chance[cod] = (float(ci or 0.0), float(cp or 0.0))
            if r.get("impares_analisados") is not None and r.get("pares_analisados") is not None:
                self._contagem[cod] = ((int(r.get("ofertas_impar") or 0), int(r["impares_analisados"])),
                                       (int(r.get("ofertas_par") or 0), int(r["pares_analisados"])))
            self._ultima[cod] = r.get("ultima_oferta")
            if not (r.get("periodos_com_oferta") or []):
                self._sem_historico.add(cod)

    # ------------------------------------------------------------- leitura
    def chance(self, codigo: str, periodo: str) -> float | None:
        par = self._chance.get(codigo)
        if par is None:
            return None
        impar, parc = par
        return impar if paridade(periodo) == 1 else parc

    def contagem(self, codigo: str, periodo: str) -> tuple[int, int] | None:
        """(semestres em que abriu, semestres analisados) do mesmo lado do ano."""
        c = self._contagem.get(codigo)
        if c is None:
            return None
        return c[0] if paridade(periodo) == 1 else c[1]

    def padrao(self, codigo: str) -> str:
        par = self._chance.get(codigo)
        if par is None or codigo in self._sem_historico:
            return DESCONHECIDA
        impar, parc = par
        if impar >= CORTE and parc >= CORTE:
            return SEMPRE
        if impar >= CORTE:
            return IMPAR
        if parc >= CORTE:
            return PAR
        return DESCONHECIDA

    def sem_historico(self, codigo: str) -> bool:
        return codigo in self._sem_historico or codigo not in self._chance

    def sera_ofertada(self, codigo: str, periodo_alvo: str) -> bool:
        """
        Sem histórico, assume que pode abrir: é melhor sugerir e o aluno
        conferir do que esconder uma disciplina que ele precisa.

        O TCC cai aqui e é o caso que obriga o cuidado: ele é atividade, nunca
        abre turma, e a previsão devolve chance 0 em vez de nula. Tratar esse 0
        como "não abre" prenderia o TCC fora de qualquer plano — ou seja, o
        aluno nunca se formaria.
        """
        if self.sem_historico(codigo):
            return True
        c = self.chance(codigo, periodo_alvo)
        return True if c is None else c >= CORTE

    def explica(self, codigo: str, periodo_alvo: str) -> str:
        """Frase curta para a tela, com o número por trás."""
        if codigo in self._atividades:
            return ROTULO[ATIVIDADE]
        if self.sem_historico(codigo):
            return ROTULO[DESCONHECIDA]
        c = self.chance(codigo, periodo_alvo)
        if c is None:
            return ROTULO[DESCONHECIDA]
        p = self.padrao(codigo)
        pct = int(round(c * 100))
        lado = "ímpar" if paridade(periodo_alvo) == 1 else "par"
        lados = "ímpares" if paridade(periodo_alvo) == 1 else "pares"
        # Porcentagem sem a base é falsa precisão: com 4 semestres de cada lado
        # do ano, "17%" é 1 em 4 com peso. A contagem crua vai SEMPRE junto, e
        # a palavra "ponderada" avisa que há peso (os dois semestres mais
        # recentes de cada lado valem o dobro; a tela explica uma vez).
        k_n = self.contagem(codigo, periodo_alvo)
        base = (f"abriu em {k_n[0]} de {k_n[1]} {lados}, chance ponderada {pct}%"
                if k_n else f"{pct}% de chance")
        if p == SEMPRE:
            # "todo semestre" só quando abre de fato nos dois lados do ano. O
            # corte de 0,5 é inclusivo: a MATC99 abriu em 2 de 4 semestres
            # pares e saía como "todo semestre" (validação de 10/11). Só o
            # RÓTULO muda; a regra de planejamento (sera_ofertada) é a mesma.
            if min(self._chance.get(codigo) or (0, 0)) >= 0.95:
                todos = self._contagem.get(codigo)
                return (f"{ROTULO[SEMPRE]} · abriu em {todos[0][0] + todos[1][0]} de "
                        f"{todos[0][1] + todos[1][1]}") if todos else ROTULO[SEMPRE]
            return f"abre nos dois lados do ano · {base}"
        # O que o aluno precisa saber é se a janela é ESTE semestre ou daqui a
        # um ano. Repetir "ímpar" duas vezes na mesma frase não diz isso.
        casa = (p == IMPAR) == (paridade(periodo_alvo) == 1)
        if casa:
            return f"abre em semestre {lado} · {base}"
        return f"{ROTULO[p]} · em semestre {lado}, como {periodo_alvo}: {base}"

    def motivo(self, codigo: str) -> str | None:
        """A explicação da API para componentes que não abrem turma."""
        return self._atividades.get(codigo)

    def ultima_oferta(self, codigo: str) -> str | None:
        return self._ultima.get(codigo)
