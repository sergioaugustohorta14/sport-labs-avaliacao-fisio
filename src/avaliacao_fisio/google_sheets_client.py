"""Cliente enxuto do Google Sheets — mesmo padrão do Painel Feegow
(`feegow_analytics.clients.google_sheets_client`): conta de serviço, sem login
de usuário. A planilha precisa estar compartilhada com o e-mail da conta de
serviço como **Editor**.
"""
from __future__ import annotations

from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from avaliacao_fisio.config import obter_secret_tabela

_ESCOPO = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsClient:
    def __init__(self):
        info = obter_secret_tabela("gcp_service_account")
        if not info:
            raise RuntimeError("[gcp_service_account] não configurado nos Secrets.")
        credenciais = service_account.Credentials.from_service_account_info(info, scopes=_ESCOPO)
        self._servico = build("sheets", "v4", credentials=credenciais, cache_discovery=False)

    def ler_intervalo(self, spreadsheet_id: str, intervalo: str) -> list[list[Any]]:
        """Sem nome de aba, vale a primeira (o nome padrão muda com o idioma da conta Google).
        Números voltam como número (sem a formatação regional da conta)."""
        resposta = self._servico.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=intervalo, valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        return resposta.get("values", [])

    def escrever_intervalo(self, spreadsheet_id: str, intervalo: str, valores: list[list[Any]]) -> None:
        # RAW (e não USER_ENTERED): o Sheets não "interpreta" texto como data/número.
        self._servico.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=intervalo, valueInputOption="RAW", body={"values": valores},
        ).execute()

    def acrescentar_linhas(self, spreadsheet_id: str, intervalo: str, linhas: list[list[Any]]) -> None:
        self._servico.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=intervalo, valueInputOption="RAW",
            insertDataOption="INSERT_ROWS", body={"values": linhas},
        ).execute()
