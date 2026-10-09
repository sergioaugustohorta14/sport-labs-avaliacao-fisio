"""Tablet de Avaliação — ponto de entrada.

Rodar com:
    streamlit run src/avaliacao_fisio/app.py
"""
from __future__ import annotations

import streamlit as st

from avaliacao_fisio import auth, estilo, wizard

st.set_page_config(page_title="Sport Labs | Tablet de Avaliação", layout="centered")
estilo.injetar_tema()

auth.exigir_login()

wizard.render()
