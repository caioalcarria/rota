"""
Cliente da sigaa-ufba-api.

O Rota não guarda nada: recebe o token do navegador a cada chamada e repassa.
Credencial só passa por aqui no momento do login, e segue direto para a API,
que por sua vez fala com o SIGAA.

Adaptado à versão turbo da API (out/2026):
  - 401  -> sessão caiu; quem decide é a camada de cima (o usuário reloga)
  - 503  -> `sigaa_ocupado`, respeitar Retry-After e tentar de novo
  - 504  -> `tempo_esgotado`, erro claro em vez de travar a tela
  - cache da API com X-Cache / Age; `fresco=True` força dado na hora
"""

from __future__ import annotations
import asyncio
import os
import httpx

BASE = os.environ.get("SIGAA_API", "http://127.0.0.1:8000")
TIMEOUT = httpx.Timeout(240.0, connect=15.0)
TENTATIVAS_OCUPADO = 3
ESPERA_PADRAO = 5.0

# A API deixa 6 requisições em voo por aluno; a 7ª volta 429 na hora, sem
# esperar. Hoje o painel dispara 5 rotas distintas, então cabe. A trava existe
# para o dia em que alguém somar a sexta rota ao gather e só descobrir o
# estouro na apresentação. Rotas repetidas não contam (a API junta pedidos
# iguais num só), mas o semáforo não sabe disso e segura mesmo assim: esperar
# alguns milissegundos é melhor do que tomar 429.
LIMITE_POR_TOKEN = 6
_portoes: dict[str, asyncio.Semaphore] = {}


def _portao(token: str | None) -> asyncio.Semaphore:
    chave = token or "_sem_token"
    sem = _portoes.get(chave)
    if sem is None:
        sem = _portoes[chave] = asyncio.Semaphore(LIMITE_POR_TOKEN)
    return sem


class SigaaIndisponivel(Exception):
    """Falha de comunicação ou do lado do SIGAA."""


class SessaoExpirada(SigaaIndisponivel):
    """Token morto: o usuário precisa entrar de novo."""


class SigaaOcupado(SigaaIndisponivel):
    """A API está sem conexão livre com o SIGAA mesmo depois de reesperar."""


def _detalhe(r: httpx.Response) -> str:
    try:
        corpo = r.json()
    except Exception:
        return r.text[:200]
    erro = corpo.get("erro") if isinstance(corpo, dict) else None
    if isinstance(erro, dict):
        return erro.get("mensagem") or erro.get("codigo") or str(erro)[:200]
    return str(corpo.get("detail") or corpo)[:200] if isinstance(corpo, dict) else str(corpo)[:200]


def _cabecalhos(token: str | None, fresco: bool) -> dict[str, str]:
    h = {"Accept-Encoding": "gzip"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if fresco:
        h["Cache-Control"] = "no-cache"
    return h


async def _pede(metodo: str, caminho: str, token: str | None,
                params: dict | None = None, corpo: dict | None = None,
                fresco: bool = False) -> tuple[dict, dict]:
    """Devolve (dados, meta). `meta` traz a procedência do cache."""
    p = dict(params or {})
    if fresco:
        p["fresco"] = "true"

    ultima = None
    for tentativa in range(TENTATIVAS_OCUPADO):
        async with _portao(token), httpx.AsyncClient(timeout=TIMEOUT) as c:
            try:
                r = await c.request(metodo, f"{BASE}{caminho}",
                                    headers=_cabecalhos(token, fresco),
                                    params={k: v for k, v in p.items() if v is not None},
                                    json=corpo)
            except httpx.RequestError as e:
                raise SigaaIndisponivel(f"não consegui falar com a API: {e}") from e

        if r.status_code == 401:
            raise SessaoExpirada("sua sessão do SIGAA caiu; entre de novo")

        if r.status_code == 503:
            # a API diz quanto esperar; respeitar é mais educado que insistir
            espera = float(r.headers.get("Retry-After") or ESPERA_PADRAO)
            ultima = _detalhe(r)
            if tentativa < TENTATIVAS_OCUPADO - 1:
                await asyncio.sleep(min(espera, 15.0))
                continue
            raise SigaaOcupado(
                "o SIGAA está congestionado agora; tente de novo em instantes")

        if r.status_code == 504:
            raise SigaaIndisponivel(
                "o SIGAA demorou demais para responder; tente de novo")

        if r.status_code >= 400:
            raise SigaaIndisponivel(f"{caminho}: {_detalhe(r)}")

        meta = {
            "cache": r.headers.get("X-Cache"),
            "idade_s": int(r.headers.get("Age") or 0),
            "gerado_em": r.headers.get("X-Cache-Gerado-Em"),
        }
        return r.json(), meta

    raise SigaaOcupado(ultima or "SIGAA ocupado")


async def login(usuario: str, senha: str, lembrar: bool = True) -> dict:
    dados, _ = await _pede("POST", "/v1/auth/login", None,
                           corpo={"usuario": usuario, "senha": senha,
                                  "lembrar": lembrar})
    return dados


async def get(caminho: str, token: str, fresco: bool = False, **params):
    dados, _ = await _pede("GET", caminho, token, params=params, fresco=fresco)
    return dados


async def get_com_meta(caminho: str, token: str, fresco: bool = False, **params):
    return await _pede("GET", caminho, token, params=params, fresco=fresco)


async def post(caminho: str, token: str, corpo: dict):
    dados, _ = await _pede("POST", caminho, token, corpo=corpo)
    return dados


async def publico(caminho: str, **params):
    """
    Rotas /v1/publico/* não exigem token: são documento público do curso
    (matriz curricular, estruturas). Não passam pelo semáforo por token
    porque não consomem sessão do aluno.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        try:
            r = await c.get(f"{BASE}{caminho}", params=params or None,
                            headers={"Accept-Encoding": "gzip"})
        except httpx.HTTPError as e:
            raise SigaaIndisponivel(f"falha ao falar com a API: {e}")
    if r.status_code >= 400:
        raise SigaaIndisponivel(_detalhe(r))
    return r.json()


async def status() -> dict:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as c:
        try:
            r = await c.get(f"{BASE}/v1/status")
            return r.json()
        except Exception as e:
            return {"ok": False, "erro": str(e)[:120]}
