"""Tela de login do Tablet de Avaliação — mesmo padrão do Painel Feegow
(`feegow_analytics.reports.auth`): usuário/senha ficam nos "Secrets" do
Streamlit (nunca no código-fonte), na seção [auth.users]:

    [auth.users]
    recepcao = "uma-senha-forte-aqui"

Aviso: isto é uma proteção básica (senha em texto simples comparada em
memória, sem hashing/rate-limit) — suficiente para afastar acesso casual
ao link público do app quando publicado (ex.: Streamlit Community
Cloud), não é segurança de nível corporativo. Não reuse essas senhas em
nenhum outro sistema.
"""
from __future__ import annotations

import base64
import datetime as dt
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from avaliacao_fisio import estilo

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


@lru_cache(maxsize=None)
def _imagem_base64(nome_arquivo: str) -> str | None:
    caminho = _ASSETS_DIR / nome_arquivo
    if not caminho.exists():
        return None
    tipo = "png" if caminho.suffix.lower() == ".png" else "jpeg"
    dados = base64.b64encode(caminho.read_bytes()).decode()
    return f"data:image/{tipo};base64,{dados}"


def _usuarios_configurados() -> dict[str, str]:
    try:
        return dict(st.secrets["auth"]["users"])
    except Exception:
        return {}


def _tela_login() -> None:
    logo = _imagem_base64("logo.png")

    st.markdown(
        f"""
        <style>
        html, body {{ color-scheme: dark; }}
        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            background: radial-gradient(circle at 50% 0%, #1b2436 0%, #10141f 55%, #0c0f17 100%);
        }}
        [data-testid="stMain"] .block-container {{ padding-top: 4rem; max-width: 30rem; }}
        #MainMenu, footer {{ visibility: hidden; }}

        .sl-logo-wrap {{ text-align: center; margin: 0 0 4px; }}
        .sl-logo-wrap img {{ width: 170px; max-width: 60vw; }}
        .sl-eyebrow {{
            text-align: center; color: {estilo.COR_MUTED}; font-size: 11.5px; font-weight: 600;
            letter-spacing: 0.22em; text-transform: uppercase; margin-bottom: 34px;
        }}

        div[data-testid="stForm"] {{ border: none; padding: 0; background: transparent; }}
        div[data-testid="stTextInput"] label {{
            color: {estilo.COR_MUTED}; font-size: 11px; font-weight: 600;
            letter-spacing: 0.14em; text-transform: uppercase;
        }}
        div[data-testid="stTextInput"] input {{
            background-color: {estilo.COR_SURFACE} !important; color: {estilo.COR_TEXTO} !important;
            border: none; border-bottom: 1px solid {estilo.COR_BORDA}; border-radius: 0;
            padding: 10px 2px; font-size: 16px; caret-color: {estilo.COR_TEXTO};
        }}
        div[data-testid="stTextInput"] input:focus {{
            border-bottom: 1px solid {estilo.COR_TEXTO}; box-shadow: none;
        }}
        div[data-testid="stTextInput"] input:-webkit-autofill,
        div[data-testid="stTextInput"] input:-webkit-autofill:hover,
        div[data-testid="stTextInput"] input:-webkit-autofill:focus {{
            -webkit-text-fill-color: {estilo.COR_TEXTO} !important;
            -webkit-box-shadow: 0 0 0 1000px {estilo.COR_SURFACE} inset !important;
            transition: background-color 9999s ease-in-out 0s;
        }}
        div[data-testid="stFormSubmitButton"] {{ width: 100% !important; }}
        div[data-testid="stFormSubmitButton"] button {{
            width: 100% !important; margin-top: 18px; background: {estilo.GRADIENTE_PRIMARIO};
            border: none; border-radius: 8px; padding: 12px 0 !important; font-weight: 700;
            letter-spacing: 0.04em; font-size: 14px; box-shadow: 0 0 18px {estilo.COR_GLOW};
        }}
        div[data-testid="stFormSubmitButton"] button,
        div[data-testid="stFormSubmitButton"] button * {{
            color: {estilo.COR_TEXTO_SOBRE_GRADIENTE} !important;
        }}
        div[data-testid="stFormSubmitButton"] button:hover {{ filter: brightness(1.08); }}
        div[data-testid="stAlert"] {{ background: #46333a; color: #f3d9de; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if logo:
        st.markdown(f'<div class="sl-logo-wrap"><img src="{logo}"></div>', unsafe_allow_html=True)
    else:
        st.markdown(f"<h2 style='text-align:center;color:{estilo.COR_TEXTO};'>Sport Labs</h2>", unsafe_allow_html=True)

    st.markdown('<div class="sl-eyebrow">Tablet de Avaliação · Acesso restrito</div>', unsafe_allow_html=True)

    with st.form("login_form"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", width="stretch")

    if entrar:
        usuarios = _usuarios_configurados()
        if usuarios.get(usuario) == senha and senha:
            st.session_state["autenticado"] = True
            st.session_state["usuario_logado"] = usuario
            st.session_state["login_em"] = dt.datetime.now(_FUSO_BRASIL)
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")


def exigir_login() -> None:
    """Bloqueia o resto da página até o usuário informar usuário/senha
    válidos. Se nenhum usuário estiver configurado nos Secrets, libera o
    acesso direto (útil pra rodar localmente durante o desenvolvimento,
    sem precisar configurar nada)."""
    usuarios = _usuarios_configurados()

    if not usuarios:
        st.sidebar.warning("⚠️ Login não configurado (modo desenvolvimento) — acesso liberado.")
        return

    if st.session_state.get("autenticado"):
        with st.sidebar:
            usuario = st.session_state.get("usuario_logado", "")
            st.markdown(f"**Olá, {usuario.capitalize()}**")
            if st.button("Sair"):
                st.session_state["autenticado"] = False
                st.session_state.pop("usuario_logado", None)
                st.session_state.pop("login_em", None)
                st.rerun()
        return

    _tela_login()
    st.stop()
