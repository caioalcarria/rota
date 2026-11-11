"""
Eixos de esforço de um componente curricular.

Cada componente recebe um peso em quatro eixos. A soma dos pesos é 1.
A classificação é por palavra-chave no nome, porque é o que o SIGAA
entrega de forma estável para qualquer curso, sem depender de ementa.

Isto implementa a função analítica de CLASSIFICAÇÃO: entra o nome do
componente, sai o perfil de esforço que ele exige.
"""

from __future__ import annotations
import unicodedata

EIXOS = ("quantitativo", "programacao", "teorico", "projeto")

ROTULO = {
    "quantitativo": "quantitativo",
    "programacao": "programação",
    "teorico": "teórico",
    "projeto": "projeto",
}

# palavra-chave -> eixo. A ordem não importa; o peso é proporcional
# à quantidade de marcas encontradas em cada eixo.
MARCAS: dict[str, tuple[str, ...]] = {
    "quantitativo": (
        "calculo", "matematica", "matematico", "estatistic", "probabilidade",
        "algebra", "discreta", "numeric", "otimizacao", "logica matematica",
        "linguagens formais", "teoria da computacao", "grafo", "analise real",
        "geometria", "fisica", "pesquisa operacional",
    ),
    "programacao": (
        "programacao", "algoritmo", "estrutura de dados", "compilador",
        "banco de dados", "web", "dispositivos moveis", "rede", "sistema operacional",
        "arquitetura de computadores", "circuito", "paradigma", "linguagem de",
        "inteligencia artificial", "computacao grafica", "desenvolvimento",
    ),
    "projeto": (
        "engenharia de software", "projeto", "qualidade", "gerencia", "gestao de projeto",
        "laboratorio", "pratica", "tcc", "trabalho de conclusao", "estagio",
        "metodologia", "empreendedor",
    ),
    "teorico": (
        "etica", "sociedade", "economia", "administracao", "humano-computador",
        "seminario", "seguranca", "auditoria", "apoio a decisao", "direito",
        "psicologia", "sociologia", "filosofia", "portugues", "ingles", "leitura",
        "sistemas de informacao", "inovacao",
    ),
}


def _normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def perfil(nome: str, codigo: str = "") -> dict[str, float]:
    """Devolve o peso do componente em cada eixo, somando 1."""
    alvo = _normaliza(f"{nome} {codigo}")
    bruto = {e: 0.0 for e in EIXOS}

    for eixo, marcas in MARCAS.items():
        for m in marcas:
            if m in alvo:
                bruto[eixo] += 1.0

    total = sum(bruto.values())
    if total == 0:
        # sem marca reconhecida: trata como teórico, que é o eixo mais neutro
        return {"quantitativo": 0.0, "programacao": 0.0, "teorico": 1.0, "projeto": 0.0}

    return {e: round(v / total, 3) for e, v in bruto.items()}


def dominante(nome: str, codigo: str = "") -> str:
    """O eixo de maior peso, usado como rótulo curto na interface."""
    p = perfil(nome, codigo)
    return max(p, key=p.get)


def intensidade_quantitativa(nome: str, codigo: str = "") -> float:
    """Atalho: o quanto o componente puxa para o lado quantitativo (0 a 1)."""
    return perfil(nome, codigo)["quantitativo"]
