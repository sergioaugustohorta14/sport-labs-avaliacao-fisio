"""Cliente mínimo pra API Feegow — só o necessário pra autocompletar o
campo "Nome completo" com os pacientes já cadastrados na clínica. Este
projeto só LÊ a lista de pacientes, nunca grava nada na API Feegow.

Mesmo padrão de autenticação do `feegow_analytics.clients.feegow_client`
(header `x-access-token`), mas reduzido ao essencial. Token em
`st.secrets["FEEGOW_API_TOKEN"]` (local: `.streamlit/secrets.toml`; produção:
Settings > Secrets do app no Streamlit Community Cloud) — mesmo token já
usado pelo Painel Feegow (Feegow-Analytics), reaproveitado a pedido do
Sergio em 10/10/2026.

Achado documentado na skill `integracao_feegow` (Feegow-Analytics),
confirmado aqui: `GET /patient/list` não pagina de verdade (sempre os
mesmos ~500 cadastros, os mais antigos por `patient_id`) e o parâmetro
`nome` não filtra no servidor (aceito, mas ignorado) — por isso a lista
inteira é buscada uma vez (cacheada) e o filtro por nome é feito no
cliente (`st.selectbox` com busca difusa). Pacientes fora desses ~500
(a clínica já passou desse total) não aparecem na sugestão — o campo
aceita digitação livre nesse caso (`accept_new_options=True`), nunca
bloqueia o preenchimento.

Achado de 13/10/2026 (pedido da equipe de fisioterapeutas): dois
pacientes podem ter o MESMO nome (ex.: um cadastro ativo e um inativo
antigo) — por isso o rótulo mostrado inclui o ID do Feegow entre
parênteses, pra desambiguar. O ID também permite autopreencher a data de
nascimento (já vem no bulk de `/patient/list`, campo `nascimento`,
formato `AAAA-MM-DD`) sem precisar de uma chamada extra à API.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any

import requests
import streamlit as st


def _config(chave: str, padrao: str = "") -> str:
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:
        pass
    return os.getenv(chave, padrao)


def _token() -> str | None:
    return _config("FEEGOW_API_TOKEN") or None


def _base_url() -> str:
    return _config("FEEGOW_API_BASE_URL", "https://api.feegow.com/v1/api").rstrip("/")


@st.cache_data(ttl=86400, show_spinner=False)
def _listar_pacientes_bruto() -> list[dict[str, Any]]:
    """GET /patient/list — nunca levanta exceção pra quem chama (se a API
    falhar ou o token não estiver configurado, devolve lista vazia e o
    campo de busca degrada pra digitação livre, sem travar o wizard).
    Cacheado aqui (não só na função derivada) pra qualquer consumidor
    futuro reaproveitar a mesma busca sem duplicar a chamada à API."""
    token = _token()
    if not token:
        return []
    try:
        resposta = requests.get(
            f"{_base_url()}/patient/list",
            headers={"x-access-token": token, "Accept": "application/json"},
            timeout=15,
        )
        resposta.raise_for_status()
        payload = resposta.json()
        if isinstance(payload, dict) and "success" in payload:
            if not payload.get("success"):
                return []
            return payload.get("content") or []
        return payload or []
    except Exception:
        return []


def _parse_data(valor: str | None) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(valor[:10])
    except (ValueError, TypeError):
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def pacientes_mapa_cache() -> dict[str, dict[str, Any]]:
    """{"Nome (ID 1234)": {"patient_id": 1234, "nascimento": date|None}} —
    o ID no rótulo desambigua pacientes com o mesmo nome (achado real:
    dois cadastros "WARLEI CANTARERO", um ativo e um inativo, IDs
    diferentes). Ordenado por nome. Cacheado 24h."""
    pacientes = _listar_pacientes_bruto()
    mapa: dict[str, dict[str, Any]] = {}
    for p in pacientes:
        if not isinstance(p, dict):
            continue
        nome = (p.get("nome") or p.get("nome_social") or "").strip()
        patient_id = p.get("patient_id")
        if not nome or patient_id is None:
            continue
        rotulo = f"{nome} (ID {patient_id})"
        mapa[rotulo] = {"patient_id": patient_id, "nascimento": _parse_data(p.get("nascimento"))}
    return dict(sorted(mapa.items()))
