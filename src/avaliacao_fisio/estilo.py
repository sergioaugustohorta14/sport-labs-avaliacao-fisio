"""Tema visual do Tablet de Avaliação — identidade "neon" preto/branco/
dourado (decisão de 09/10/2026, ajustada no mesmo dia pra usar as cores
reais da marca Sport Labs em vez de um azul/ciano genérico: visual
próprio deste app, deliberadamente diferente do cinza do Feegow-Analytics).
Fonte Inter e botões grandes pra toque continuam do desenho original.
"""
from __future__ import annotations

import streamlit as st

FONTE_GOOGLE_QUERY = "Inter:wght@400;500;600;700"

COR_FUNDO = "#121212"
COR_SURFACE = "#1a1a1a"
COR_TEXTO = "#f3efe6"
COR_MUTED = "#9c9690"
COR_BORDA = "rgba(212, 175, 95, 0.35)"
COR_GLOW = "rgba(212, 175, 95, 0.30)"
COR_TEXTO_SOBRE_GRADIENTE = "#1a1407"
GRADIENTE_PRIMARIO = "linear-gradient(90deg, #9c7a2e 0%, #f0cf7a 50%, #b8902f 100%)"


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
            background: radial-gradient(circle at 50% 0%, #1c1c1c 0%, #121212 55%, #090909 100%);
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
            border-radius: 8px;
        }}

        /* Botões grandes, alvo de toque confortável num tablet. */
        .stButton button {{
            width: 100%;
            padding: 0.9rem 1rem;
            font-size: 1.05rem;
            font-weight: 600;
            border-radius: 10px;
            border: 1px solid {COR_BORDA};
            background: transparent;
        }}
        /* `*` nos filhos é necessário: a regra genérica de cor de texto
        (span, div, acima) pinta o texto interno do botão (que o Streamlit
        envolve num elemento próprio) por cima da cor definida aqui — sem
        isso o texto ficava invisível num fundo também claro. */
        .stButton button[kind="primary"] {{
            background: {GRADIENTE_PRIMARIO};
            border: none;
            box-shadow: 0 0 18px {COR_GLOW};
        }}
        .stButton button[kind="primary"],
        .stButton button[kind="primary"] * {{
            color: {COR_TEXTO_SOBRE_GRADIENTE} !important;
            font-weight: 700 !important;
        }}
        .stButton button[kind="primary"]:hover {{
            box-shadow: 0 0 26px {COR_GLOW};
            filter: brightness(1.08);
        }}

        /* Segmented control (Protocolo / Tipo de avaliação) — pill bar.
        `width="stretch"` no Python já faz o grupo ocupar 100% da largura;
        aqui força cada botão a dividir esse espaço em partes iguais
        (`flex: 1 1 0`) e garante a forma de cápsula + altura confortável,
        que o CSS nativo do Streamlit (mais específico) sobrescrevia. */
        div[data-testid="stButtonGroup"] {{
            width: 100% !important;
        }}
        div[data-testid="stButtonGroup"] > div {{
            width: 100% !important;
            display: flex !important;
        }}
        div[data-testid="stButtonGroup"] button {{
            flex: 1 1 0 !important;
            background: transparent !important;
            border: none !important;
            border-radius: 999px !important;
            padding: 0.85rem 1rem !important;
            font-size: 1rem !important;
            font-weight: 600;
        }}
        div[data-testid="stButtonGroup"] button[data-selected],
        div[data-testid="stButtonGroup"] [data-selected] button {{
            background: {GRADIENTE_PRIMARIO} !important;
            box-shadow: 0 0 16px {COR_GLOW};
        }}
        div[data-testid="stButtonGroup"] button[data-selected] *,
        div[data-testid="stButtonGroup"] [data-selected] button * {{
            color: {COR_TEXTO_SOBRE_GRADIENTE} !important;
            font-weight: 700 !important;
        }}

        /* Cartões com brilho (ver `cartao()`) — envolvem os seletores da
        tela inicial, mesmo padrão visual do mockup aprovado em 09/10/2026. */
        [class*="st-key-cartao_"] {{
            background: rgba(26, 26, 26, 0.65);
            border: 1px solid {COR_BORDA};
            border-radius: 14px;
            padding: 18px 20px 6px;
            margin-bottom: 14px;
            box-shadow: 0 0 22px rgba(212, 175, 95, 0.12);
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


def cartao(key: str):
    """Container com o cartão de brilho ciano usado na tela inicial
    (Protocolo / Tipo de avaliação) — `key` vira a classe `st-key-cartao_<key>`
    que a regra em `injetar_tema()` estiliza. Ver padrão equivalente em
    `feegow_analytics.reports.estilo.container_filtros()`."""
    return st.container(key=f"cartao_{key}")


def cabecalho_pagina(logo_base64: str | None, titulo: str, subtitulo: str | None = None) -> None:
    colunas = st.columns([1, 5])
    with colunas[0]:
        if logo_base64:
            st.image(logo_base64, width=72)
    with colunas[1]:
        st.markdown(f"### {titulo}")
        if subtitulo:
            st.caption(subtitulo)
