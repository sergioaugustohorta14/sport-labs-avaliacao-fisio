"""Cliente mínimo da API do RunScribe (https://api.runscribe.com/doc.html).

SÓ LEITURA: a única chamada que escreve é o login (`POST /v2/authenticate`, que
devolve o token). O resto é GET de corridas e métricas.

Credenciais (e-mail e senha de uma conta RunScribe, liberadas pela diretoria)
ficam nos Secrets (`RUNSCRIBE_EMAIL`, `RUNSCRIBE_PASSWORD`; chaves de nível raiz,
ANTES de qualquer `[tabela]` do TOML), nunca no código nem no repositório.

A documentação não traz exemplos de resposta completos e mistura token no corpo
e no cabeçalho; por isso o login aceita o token em mais de um formato e as
leituras mandam o token no cabeçalho `X-Auth-Token` (o padrão dos endpoints de
corrida). O formato real das respostas é confirmado na primeira chamada de verdade.
"""
from __future__ import annotations

import concurrent.futures
from typing import Any

import requests
import streamlit as st

from avaliacao_fisio.config import obter_config

_URL_PADRAO = "https://api.runscribe.com"
_TIMEOUT = 20


class RunScribeErro(Exception):
    """Falha de comunicação ou de login com o RunScribe (mensagem pronta pra tela)."""


def configurado() -> bool:
    return bool(obter_config("RUNSCRIBE_EMAIL")) and bool(obter_config("RUNSCRIBE_PASSWORD"))


def _base() -> str:
    return obter_config("RUNSCRIBE_API_URL", _URL_PADRAO).rstrip("/")


def _extrair_token(resposta: Any) -> str | None:
    """O token pode vir na raiz ({"token": "..."}) ou dentro de um objeto aninhado."""
    if isinstance(resposta, dict):
        if isinstance(resposta.get("token"), str):
            return resposta["token"]
        for valor in resposta.values():
            achado = _extrair_token(valor)
            if achado:
                return achado
    return None


@st.cache_data(ttl=1500, show_spinner=False)
def _token() -> str:
    """Login. Cache curto (25 min) pra não autenticar a cada clique; se o RunScribe
    recusar o token antes disso, `_get` limpa o cache e tenta de novo."""
    if not configurado():
        raise RunScribeErro("RunScribe não configurado: faltam RUNSCRIBE_EMAIL e RUNSCRIBE_PASSWORD nos Secrets.")
    try:
        resposta = requests.post(
            f"{_base()}/v2/authenticate",
            json={"email": obter_config("RUNSCRIBE_EMAIL"), "password": obter_config("RUNSCRIBE_PASSWORD")},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as erro:
        raise RunScribeErro(f"Não consegui falar com o RunScribe: {erro.__class__.__name__}.") from erro
    if resposta.status_code in (400, 401, 403):
        raise RunScribeErro("O RunScribe recusou o e-mail ou a senha configurados.")
    if not resposta.ok:
        raise RunScribeErro(f"O RunScribe respondeu com erro {resposta.status_code} no login.")
    token = _extrair_token(resposta.json())
    if not token:
        raise RunScribeErro("O login do RunScribe funcionou, mas a resposta não trouxe o token no formato esperado.")
    return token


def _chamar(token: str, caminho: str, parametros: dict | None = None) -> Any:
    """GET puro (sem Streamlit): pode rodar em threads."""
    try:
        resposta = requests.get(
            f"{_base()}{caminho}", params=parametros, headers={"X-Auth-Token": token}, timeout=_TIMEOUT,
        )
    except requests.RequestException as erro:
        raise RunScribeErro(f"Não consegui falar com o RunScribe: {erro.__class__.__name__}.") from erro
    if resposta.status_code in (401, 403):
        raise _TokenRecusado()
    if resposta.status_code == 404:
        raise RunScribeErro("O RunScribe não encontrou o que foi pedido (404).")
    if not resposta.ok:
        raise RunScribeErro(f"O RunScribe respondeu com erro {resposta.status_code}.")
    return resposta.json()


class _TokenRecusado(RunScribeErro):
    """Token vencido ou recusado: o chamador renova o login e tenta de novo."""


def _get(caminho: str, parametros: dict | None = None) -> Any:
    try:
        return _chamar(_token(), caminho, parametros)
    except _TokenRecusado:
        _token.clear()
        try:
            return _chamar(_token(), caminho, parametros)
        except _TokenRecusado as erro:
            raise RunScribeErro("O RunScribe recusou o acesso mesmo depois de refazer o login.") from erro


def listar_corridas(limite: int = 50, a_partir_de: str | None = None) -> Any:
    parametros: dict[str, Any] = {"limit": limite}
    if a_partir_de:
        parametros["from"] = a_partir_de
    return _get("/v2/runs", parametros)


def corrida(run_id: str | int) -> Any:
    return _get(f"/v2/runs/{run_id}")


def metrica(run_id: str | int, nome: str, unidades: str = "metric") -> Any:
    return _get(f"/v2/runs/{run_id}/metric/{nome}", {"units": unidades})


def estatisticas(de: str | None = None, ate: str | None = None) -> Any:
    parametros = {k: v for k, v in (("from", de), ("to", ate)) if v}
    return _get("/v2/account/stats", parametros)


# --------------------------------------------------------------------------- corridas pro protocolo de Corrida
@st.cache_data(ttl=600, show_spinner=False)
def corridas_resumidas() -> list[dict]:
    """Todas as corridas da conta, da mais recente pra mais antiga, só com o que a
    tela precisa. A conta da clínica enxerga as corridas de TODOS os atletas; o
    paciente é identificado apenas pela etiqueta (`label`) digitada no app."""
    brutas = listar_corridas(1000).get("runs", [])
    return [{
        "id": r["id"],
        "label": (r.get("label") or "").strip(),
        "data": str(r.get("timestamp", ""))[:10],
        "distancia": r.get("distance"),
        "tempo": r.get("time"),
        "passos": r.get("steps"),
        "pes": sorted({m["position"] for m in r.get("mountings", []) if m.get("position") in ("left", "right")}),
    } for r in brutas]


_LADO_DO_PE = {"right": "D", "left": "E"}


def _media_por_pe(resposta_metrica: dict) -> dict[str, float | None]:
    """{"D": média do pé direito, "E": média do pé esquerdo} de uma métrica. Se o pé
    tiver mais de um sensor, vale o dos cadarços (`laces`)."""
    medias: dict[str, float | None] = {"D": None, "E": None}
    for montagem in resposta_metrica.get("metric", {}).get("mountings", []):
        lado = _LADO_DO_PE.get(montagem.get("foot"))
        if lado is None or (medias[lado] is not None and montagem.get("placement") != "laces"):
            continue
        valor = montagem.get("average")
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            valores = [v for v in montagem.get("values", []) if isinstance(v, (int, float))]
            valor = sum(valores) / len(valores) if valores else None
        medias[lado] = float(valor) if valor is not None else None
    return medias


@st.cache_data(ttl=3600, show_spinner=False)
def resumo_corrida(run_id: int, metricas: tuple[str, ...]) -> dict:
    """Dados de uma corrida: {"corrida": {...}, "metricas": {nome: {"D": x, "E": y}}}.
    As métricas são buscadas em paralelo (uma chamada por métrica)."""
    token = _token()
    try:
        detalhe = _chamar(token, f"/v2/runs/{run_id}").get("run", {})
    except _TokenRecusado:
        _token.clear()
        raise RunScribeErro("O RunScribe recusou o acesso. Tente de novo.")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futuros = {nome: pool.submit(_chamar, token, f"/v2/runs/{run_id}/metric/{nome}", {"units": "metric"}) for nome in metricas}
        resultado: dict[str, dict[str, float | None]] = {}
        for nome, futuro in futuros.items():
            try:
                resultado[nome] = _media_por_pe(futuro.result())
            except Exception:
                resultado[nome] = {"D": None, "E": None}
    return {
        "corrida": {
            "id": detalhe.get("id", run_id), "label": (detalhe.get("label") or "").strip(),
            "data": str(detalhe.get("timestamp", ""))[:10], "distancia": detalhe.get("distance"),
            "tempo": detalhe.get("time"), "passos": detalhe.get("steps"),
        },
        "metricas": resultado,
    }
