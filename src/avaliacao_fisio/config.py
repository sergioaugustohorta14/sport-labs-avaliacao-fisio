"""Leitura de configuração: `st.secrets` (Streamlit Cloud e `.streamlit/secrets.toml`
local) com fallback pra variável de ambiente."""
from __future__ import annotations

import os

import streamlit as st


def obter_config(chave: str, padrao: str = "") -> str:
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:
        pass
    return os.getenv(chave, padrao)


def obter_secret_tabela(nome: str) -> dict:
    """Tabela inteira do TOML (ex.: `[gcp_service_account]`) como dict comum."""
    try:
        return dict(st.secrets[nome])
    except Exception:
        return {}
