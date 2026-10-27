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


def _get(caminho: str, parametros: dict | None = None, tentar_de_novo: bool = True) -> Any:
    try:
        resposta = requests.get(
            f"{_base()}{caminho}", params=parametros, headers={"X-Auth-Token": _token()}, timeout=_TIMEOUT,
        )
    except requests.RequestException as erro:
        raise RunScribeErro(f"Não consegui falar com o RunScribe: {erro.__class__.__name__}.") from erro
    if resposta.status_code in (401, 403) and tentar_de_novo:
        _token.clear()
        return _get(caminho, parametros, tentar_de_novo=False)
    if resposta.status_code == 404:
        raise RunScribeErro("O RunScribe não encontrou o que foi pedido (404).")
    if not resposta.ok:
        raise RunScribeErro(f"O RunScribe respondeu com erro {resposta.status_code}.")
    return resposta.json()


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
