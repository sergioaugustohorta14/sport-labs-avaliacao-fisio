"""Tema visual fixo do Tablet de Avaliação — skin de marca sempre escuro
(independente do tema claro/escuro do tablet), fonte Inter e botões grandes
pra toque, no mesmo espírito da tela de login do Painel Feegow
(`feegow_analytics.reports.auth`) e do tema geral
(`feegow_analytics.reports.estilo`).
"""
from __future__ import annotations

import streamlit as st

FONTE_GOOGLE_QUERY = "Inter:wght@400;500;600;700"

COR_FUNDO = "#322f33"
COR_SURFACE = "#1c1a1d"
COR_TEXTO = "#f5f4f6"
COR_MUTED = "#9c99a0"
COR_BORDA = "#5c5960"


def injetar_tema() -> None:
    """Chamar uma vez, logo após `st.set_page_config`, antes de desenhar
    qualquer outra coisa na página."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family={FONTE_GOOGLE_QUERY}&display=swap');

        html, body {{ color-scheme: dark; }}

        html, body, .stApp, .stMarkdown, .stMetric, .stDataFrame, table,
        h1, h2, h3, h4, h5, h6, p, label,
        .stButton button, .stTextInput input, .stNumberInput input,
        .stSelectbox, .stRadio, .stDateInput input {{
            font-family: 'Inter', sans-serif !important;
        }}

        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            background: {COR_FUNDO};
        }}
        [data-testid="stMain"] .block-container {{
            max-width: 52rem; padding-top: 2rem; padding-bottom: 8rem;
        }}
        #MainMenu, footer {{ visibility: hidden; }}

        h1, h2, h3, h4, h5, h6, p, label, span, div {{ color: {COR_TEXTO}; }}
        [data-testid="stCaptionContainer"] {{ color: {COR_MUTED} !important; }}

        .stTextInput input, .stNumberInput input, .stDateInput input,
        div[data-baseweb="select"] > div {{
            background-color: {COR_SURFACE} !important;
            color: {COR_TEXTO} !important;
            border: 1px solid {COR_BORDA} !important;
            border-radius: 6px;
        }}

        /* Botões grandes, alvo de toque confortável num tablet. */
        .stButton button {{
            width: 100%;
            padding: 0.9rem 1rem;
            font-size: 1.05rem;
            font-weight: 600;
            border-radius: 8px;
            border: 1px solid {COR_BORDA};
        }}
        .stButton button[kind="primary"] {{
            background: {COR_TEXTO}; color: {COR_FUNDO}; border: none;
        }}
        .stButton button[kind="primary"]:hover {{
            background: #ffffff; color: {COR_SURFACE};
        }}

        .sl-progresso {{
            color: {COR_MUTED}; font-size: 0.85rem; letter-spacing: 0.06em;
            text-transform: uppercase; margin-bottom: 0.25rem;
        }}
        .sl-titulo-secao {{ margin-top: 0; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def cabecalho_pagina(logo_base64: str | None, titulo: str, subtitulo: str | None = None) -> None:
    colunas = st.columns([1, 5])
    with colunas[0]:
        if logo_base64:
            st.image(logo_base64, width=72)
    with colunas[1]:
        st.markdown(f"### {titulo}")
        if subtitulo:
            st.caption(subtitulo)
