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
"""
from __future__ import annotations

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


def _listar_pacientes_bruto() -> list[dict[str, Any]]:
    """GET /patient/list — nunca levanta exceção pra quem chama (se a API
    falhar ou o token não estiver configurado, devolve lista vazia e o
    campo de busca degrada pra digitação livre, sem travar o wizard)."""
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


@st.cache_data(ttl=86400, show_spinner=False)
def nomes_pacientes_cache() -> list[str]:
    """Nomes únicos dos pacientes conhecidos (dos ~500 que `patient/list`
    devolve), ordenados — cacheado 24h, mesmo TTL usado pras listas de
    opções do Feegow-Analytics (opcoes.py), que raramente mudam."""
    pacientes = _listar_pacientes_bruto()
    nomes: list[str] = []
    vistos: set[str] = set()
    for p in pacientes:
        if not isinstance(p, dict):
            continue
        nome = (p.get("nome") or p.get("nome_social") or "").strip()
        if nome and nome not in vistos:
            nomes.append(nome)
            vistos.add(nome)
    return sorted(nomes)
